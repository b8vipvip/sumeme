from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Mapping

import anyio
import jwt
from jwt import InvalidTokenError, PyJWK, PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from .config import Settings
from .content import safe_id
from .memory_scope import MemoryScope

_IDENTITY_HEADER = "x-sumeme-identity-token"
_MAX_VAULTS_PER_TOKEN = 32


class IdentityError(Exception):
    def __init__(self, code: str, status_code: int = 401):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    subject: str
    account_id: str
    allowed_vaults: frozenset[str]
    default_vault: str

    def scope(self, requested_vault: str, *, device_id: str = "") -> MemoryScope:
        vault = MemoryScope.account(
            self.account_id,
            requested_vault or self.default_vault,
        ).vault_id
        if vault not in self.allowed_vaults:
            raise IdentityError("identity_vault_forbidden", status_code=403)
        return MemoryScope.account(self.account_id, vault, device_id=device_id)


class IdentityVerifier:
    """Validate an OIDC/JWT token without trusting request-supplied account IDs."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.algorithms = settings.identity_algorithm_list
        self._static_jwks = self._load_static_jwks()
        self._jwks_client = (
            PyJWKClient(settings.identity_jwks_url.strip())
            if settings.identity_jwks_url.strip()
            else None
        )

    async def verify(self, token: str) -> VerifiedIdentity:
        if not token or len(token) > self.settings.identity_max_token_chars:
            raise IdentityError("identity_token_missing_or_oversized")
        return await anyio.to_thread.run_sync(self._verify_sync, token)

    def _verify_sync(self, token: str) -> VerifiedIdentity:
        try:
            header = jwt.get_unverified_header(token)
            algorithm = str(header.get("alg") or "")
            if algorithm not in self.algorithms:
                raise IdentityError("identity_algorithm_not_allowed")

            signing_key = self._resolve_signing_key(token, header)
            claims = jwt.decode(
                token,
                key=signing_key,
                algorithms=self.algorithms,
                audience=self.settings.identity_audience,
                issuer=self.settings.identity_issuer,
                leeway=self.settings.identity_clock_skew_seconds,
                options={
                    "require": ["exp", "iat", "sub", "iss", "aud"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
            return self._identity_from_claims(claims)
        except IdentityError:
            raise
        except PyJWKClientConnectionError as exc:
            raise IdentityError(
                "identity_verifier_unavailable",
                status_code=503,
            ) from exc
        except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise IdentityError("identity_token_invalid") from exc

    def _resolve_signing_key(self, token: str, header: dict[str, Any]) -> Any:
        if self._static_jwks is not None:
            keys = self._static_jwks.get("keys") or []
            kid = str(header.get("kid") or "")
            if kid:
                matches = [key for key in keys if str(key.get("kid") or "") == kid]
            else:
                matches = keys if len(keys) == 1 else []
            if len(matches) != 1:
                raise IdentityError("identity_signing_key_not_found")
            return PyJWK.from_dict(matches[0], algorithm=header.get("alg")).key

        if self._jwks_client is None:
            raise IdentityError("identity_verifier_not_configured", status_code=503)
        return self._jwks_client.get_signing_key_from_jwt(token).key

    def _identity_from_claims(self, claims: dict[str, Any]) -> VerifiedIdentity:
        subject = str(claims.get("sub") or "").strip()
        if not subject or len(subject) > 512:
            raise IdentityError("identity_subject_invalid")

        issued_at = claims.get("iat")
        if isinstance(issued_at, bool) or not isinstance(issued_at, (int, float)):
            raise IdentityError("identity_iat_invalid")
        age = time.time() - float(issued_at)
        if age > (
            self.settings.identity_max_token_age_seconds
            + self.settings.identity_clock_skew_seconds
        ):
            raise IdentityError("identity_token_too_old")

        account_scope = MemoryScope.account(subject)
        vaults = self._vault_claim(claims)
        default_raw = str(
            claims.get(self.settings.identity_default_vault_claim) or "default"
        )
        default_vault = MemoryScope.account(subject, default_raw).vault_id
        if default_vault not in vaults:
            raise IdentityError("identity_default_vault_not_allowed")

        return VerifiedIdentity(
            subject=subject,
            account_id=account_scope.account_id,
            allowed_vaults=frozenset(vaults),
            default_vault=default_vault,
        )

    def _vault_claim(self, claims: dict[str, Any]) -> set[str]:
        raw = claims.get(self.settings.identity_vaults_claim)
        if raw is None:
            values: list[str] = ["default"]
        elif isinstance(raw, str):
            values = [raw]
        elif isinstance(raw, list) and all(isinstance(item, str) for item in raw):
            values = raw
        else:
            raise IdentityError("identity_vault_claim_invalid")

        if not values or len(values) > _MAX_VAULTS_PER_TOKEN:
            raise IdentityError("identity_vault_claim_invalid")

        normalized = {
            MemoryScope.account("identity", value).vault_id
            for value in values
            if value.strip()
        }
        if not normalized:
            raise IdentityError("identity_vault_claim_invalid")
        return normalized

    def _load_static_jwks(self) -> dict[str, Any] | None:
        raw = self.settings.identity_jwks_json.get_secret_value().strip()
        if not raw:
            return None
        value = json.loads(raw)
        if not isinstance(value, dict) or not isinstance(value.get("keys"), list):
            raise ValueError("IDENTITY_JWKS_JSON must contain a JWKS keys array")
        return value


class IdentityResolver:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.verifier = (
            IdentityVerifier(settings)
            if settings.identity_mode in {"jwt-preferred", "jwt-required"}
            else None
        )

    async def resolve_chat_scope(
        self,
        headers: Mapping[str, str],
        payload: dict[str, Any],
    ) -> MemoryScope:
        token = str(headers.get(_IDENTITY_HEADER) or "").strip()
        if token:
            if self.verifier is None:
                raise IdentityError("identity_token_not_configured", status_code=400)
            identity = await self.verifier.verify(token)
            metadata = payload.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            requested_vault = (
                str(headers.get("x-sumeme-vault-id") or "").strip()
                or str(metadata.get("vault_id") or "").strip()
                or identity.default_vault
            )
            device_id = (
                str(headers.get("x-sumeme-device-id") or "").strip()
                or str(metadata.get("device_id") or "").strip()
            )
            return identity.scope(requested_vault, device_id=device_id)

        if self.settings.identity_mode == "jwt-required":
            raise IdentityError("identity_token_required")
        return self._legacy_scope(headers, payload)

    def _legacy_scope(
        self,
        headers: Mapping[str, str],
        payload: dict[str, Any],
    ) -> MemoryScope:
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        raw_account = (
            str(headers.get("x-sumeme-account-id") or "").strip()
            or str(headers.get("x-sumeme-user-id") or "").strip()
            or str(payload.get("user") or "").strip()
            or self.settings.sumeme_user_id
        )
        raw_vault = (
            str(headers.get("x-sumeme-vault-id") or "").strip()
            or str(metadata.get("vault_id") or "").strip()
            or "default"
        )
        device_id = (
            str(headers.get("x-sumeme-device-id") or "").strip()
            or str(metadata.get("device_id") or "").strip()
        )

        normalized_account = safe_id(raw_account, self.settings.sumeme_user_id)
        if normalized_account == "sumeme_smoke":
            return MemoryScope.service(
                "sumeme-smoke",
                safe_id(raw_vault, "production-smoke"),
                device_id=device_id,
            )
        return MemoryScope.account(
            normalized_account,
            safe_id(raw_vault, "default"),
            device_id=device_id,
        )
