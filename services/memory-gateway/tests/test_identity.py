from __future__ import annotations

import hashlib
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from pydantic import SecretStr, ValidationError
from starlette.datastructures import Headers

from app.config import Settings
from app.identity import IdentityError, IdentityResolver
from app.memory_scope import MemoryScope

ISSUER = "https://identity.example"
AUDIENCE = "sumeme-memory-gateway"
KID = "sumeme-test-key"


def key_material() -> tuple[rsa.RSAPrivateKey, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = KID
    public_jwk["use"] = "sig"
    public_jwk["alg"] = "RS256"
    return private_key, json.dumps({"keys": [public_jwk]})


def verified_account_id(subject: str, issuer: str = ISSUER) -> str:
    digest = hashlib.sha256(f"{issuer}\x00{subject}".encode()).hexdigest()
    return f"oidc-{digest[:32]}"


def make_settings(jwks: str, **overrides) -> Settings:
    values = {
        "openai_relay_base_url": "https://relay.example/v1",
        "openai_relay_api_key": SecretStr("relay-key"),
        "gateway_api_key": SecretStr("gateway-key"),
        "gateway_admin_token": SecretStr("admin-key"),
        "gateway_service_token": SecretStr("service-key"),
        "identity_mode": "jwt-required",
        "identity_issuer": ISSUER,
        "identity_audience": AUDIENCE,
        "identity_jwks_json": SecretStr(jwks),
        "identity_allowed_algorithms": "RS256",
        "identity_max_token_age_seconds": 3600,
    }
    values.update(overrides)
    return Settings(**values)


def issue_token(
    private_key: rsa.RSAPrivateKey,
    *,
    subject: str = "oidc-user-123",
    audience: str = AUDIENCE,
    issued_at: int | None = None,
    expires_at: int | None = None,
    vaults: list[str] | str | None = None,
    default_vault: str = "default",
) -> str:
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "aud": audience,
        "sub": subject,
        "iat": issued_at if issued_at is not None else now,
        "exp": expires_at if expires_at is not None else now + 300,
        "sumeme_default_vault": default_vault,
    }
    if vaults is not None:
        payload["sumeme_vaults"] = vaults
    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": KID, "typ": "JWT"},
    )


@pytest.mark.asyncio
async def test_verified_subject_replaces_all_client_asserted_account_ids() -> None:
    private_key, jwks = key_material()
    resolver = IdentityResolver(make_settings(jwks))
    token = issue_token(
        private_key,
        vaults=["default", "work"],
        default_vault="work",
    )

    scope = await resolver.resolve_chat_scope(
        Headers(
            {
                "x-sumeme-identity-token": token,
                "x-sumeme-account-id": "attacker-controlled-account",
                "x-sumeme-user-id": "another-forged-account",
                "x-sumeme-vault-id": "work",
            }
        ),
        {
            "user": "forged-payload-user",
            "metadata": {"vault_id": "default", "device_id": "phone-a"},
        },
    )

    expected_account = verified_account_id("oidc-user-123")
    assert scope == MemoryScope.account(expected_account, "work", device_id="phone-a")
    assert "attacker" not in scope.storage_key
    assert "oidc-user-123" not in scope.storage_key
    assert scope.principal_type == "account"


@pytest.mark.asyncio
async def test_subjects_that_normalize_similarly_still_get_distinct_accounts() -> None:
    private_key, jwks = key_material()
    resolver = IdentityResolver(make_settings(jwks))

    first = await resolver.resolve_chat_scope(
        Headers(
            {
                "x-sumeme-identity-token": issue_token(
                    private_key,
                    subject="tenant/a",
                )
            }
        ),
        {},
    )
    second = await resolver.resolve_chat_scope(
        Headers(
            {
                "x-sumeme-identity-token": issue_token(
                    private_key,
                    subject="tenant_a",
                )
            }
        ),
        {},
    )

    assert first.account_id != second.account_id
    assert first.storage_key != second.storage_key


@pytest.mark.asyncio
async def test_token_can_only_open_vaults_granted_by_claim() -> None:
    private_key, jwks = key_material()
    resolver = IdentityResolver(make_settings(jwks))
    token = issue_token(private_key, vaults=["default"])

    with pytest.raises(IdentityError) as captured:
        await resolver.resolve_chat_scope(
            Headers(
                {
                    "x-sumeme-identity-token": token,
                    "x-sumeme-vault-id": "work",
                }
            ),
            {"messages": []},
        )

    assert captured.value.status_code == 403
    assert captured.value.code == "identity_vault_forbidden"


@pytest.mark.asyncio
async def test_required_mode_rejects_missing_identity_token() -> None:
    _private_key, jwks = key_material()
    resolver = IdentityResolver(make_settings(jwks))

    with pytest.raises(IdentityError) as captured:
        await resolver.resolve_chat_scope(
            Headers({"x-sumeme-account-id": "client-value"}),
            {"user": "payload-value"},
        )

    assert captured.value.status_code == 401
    assert captured.value.code == "identity_token_required"


@pytest.mark.asyncio
async def test_preferred_mode_keeps_explicit_transition_fallback() -> None:
    _private_key, jwks = key_material()
    resolver = IdentityResolver(
        make_settings(jwks, identity_mode="jwt-preferred")
    )

    scope = await resolver.resolve_chat_scope(
        Headers({"x-sumeme-account-id": "legacy-user"}),
        {"metadata": {"vault_id": "legacy-vault"}},
    )

    assert scope == MemoryScope.account("legacy-user", "legacy-vault")


@pytest.mark.asyncio
async def test_invalid_audience_never_falls_back_to_client_identity() -> None:
    private_key, jwks = key_material()
    resolver = IdentityResolver(
        make_settings(jwks, identity_mode="jwt-preferred")
    )
    token = issue_token(private_key, audience="another-service")

    with pytest.raises(IdentityError) as captured:
        await resolver.resolve_chat_scope(
            Headers(
                {
                    "x-sumeme-identity-token": token,
                    "x-sumeme-account-id": "fallback-attacker",
                }
            ),
            {},
        )

    assert captured.value.code == "identity_token_invalid"


@pytest.mark.asyncio
async def test_old_but_unexpired_token_is_rejected() -> None:
    private_key, jwks = key_material()
    resolver = IdentityResolver(
        make_settings(jwks, identity_max_token_age_seconds=300)
    )
    now = int(time.time())
    token = issue_token(
        private_key,
        issued_at=now - 600,
        expires_at=now + 300,
    )

    with pytest.raises(IdentityError) as captured:
        await resolver.resolve_chat_scope(
            Headers({"x-sumeme-identity-token": token}),
            {},
        )

    assert captured.value.code == "identity_token_too_old"


@pytest.mark.asyncio
async def test_service_token_creates_only_a_service_scope() -> None:
    _private_key, jwks = key_material()
    resolver = IdentityResolver(make_settings(jwks))

    scope = await resolver.resolve_chat_scope(
        Headers(
            {
                "x-sumeme-service-token": "service-key",
                "x-sumeme-service-id": "sumeme-smoke",
                "x-sumeme-vault-id": "production-smoke",
                "x-sumeme-account-id": "real-user-cannot-be-impersonated",
            }
        ),
        {"user": "another-account"},
    )

    assert scope == MemoryScope.service("sumeme-smoke", "production-smoke")
    assert scope.principal_type == "service"


@pytest.mark.asyncio
async def test_invalid_service_token_never_falls_back() -> None:
    _private_key, jwks = key_material()
    resolver = IdentityResolver(
        make_settings(jwks, identity_mode="jwt-preferred")
    )

    with pytest.raises(IdentityError) as captured:
        await resolver.resolve_chat_scope(
            Headers(
                {
                    "x-sumeme-service-token": "wrong",
                    "x-sumeme-service-id": "smoke",
                    "x-sumeme-account-id": "fallback-user",
                }
            ),
            {},
        )

    assert captured.value.code == "service_identity_invalid"


def test_jwt_mode_rejects_hmac_algorithm_configuration() -> None:
    _private_key, jwks = key_material()

    with pytest.raises(ValidationError):
        make_settings(jwks, identity_allowed_algorithms="HS256")


def test_static_jwks_rejects_private_key_material() -> None:
    private_key, _jwks = key_material()
    private_jwk = json.loads(RSAAlgorithm.to_jwk(private_key))
    private_jwk["kid"] = KID

    with pytest.raises(ValidationError):
        make_settings(json.dumps({"keys": [private_jwk]}))
