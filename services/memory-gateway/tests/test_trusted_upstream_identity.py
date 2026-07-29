from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError
from starlette.datastructures import Headers

from app.config import Settings
from app.identity import IdentityError, IdentityResolver, derive_account_id
from app.memory_scope import MemoryScope

UPSTREAM_ISSUER = "lobehub-internal"


def make_settings(**overrides) -> Settings:
    values = {
        "openai_relay_base_url": "https://relay.example/v1",
        "openai_relay_api_key": SecretStr("relay-key"),
        "gateway_api_key": SecretStr("gateway-key"),
        "gateway_admin_token": SecretStr("admin-key"),
        "gateway_service_token": SecretStr("service-key"),
        "identity_mode": "trusted-openai-user",
        "identity_trusted_upstream_issuer": UPSTREAM_ISSUER,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_openai_user_becomes_hashed_account_scope() -> None:
    resolver = IdentityResolver(make_settings())

    scope = await resolver.resolve_chat_scope(
        Headers(
            {
                "x-sumeme-account-id": "forged-account",
                "x-sumeme-user-id": "another-forged-account",
                "x-sumeme-vault-id": "forged-header-vault",
                "x-sumeme-device-id": "forged-header-device",
            }
        ),
        {
            "user": "better-auth-user-id",
            "metadata": {"vault_id": "work", "device_id": "desktop-a"},
        },
    )

    expected = derive_account_id(UPSTREAM_ISSUER, "better-auth-user-id")
    assert scope == MemoryScope.account(expected, "work", device_id="desktop-a")
    assert "better-auth-user-id" not in scope.storage_key
    assert "forged" not in scope.storage_key


@pytest.mark.asyncio
async def test_trusted_mode_requires_server_injected_user() -> None:
    resolver = IdentityResolver(make_settings())

    with pytest.raises(IdentityError) as captured:
        await resolver.resolve_chat_scope(
            Headers({"x-sumeme-account-id": "client-only-account"}),
            {"messages": []},
        )

    assert captured.value.status_code == 401
    assert captured.value.code == "trusted_upstream_user_required"


@pytest.mark.asyncio
async def test_trusted_mode_rejects_invalid_user_type() -> None:
    resolver = IdentityResolver(make_settings())

    with pytest.raises(IdentityError) as captured:
        await resolver.resolve_chat_scope(Headers(), {"user": ["not", "a", "string"]})

    assert captured.value.code == "trusted_upstream_user_required"


@pytest.mark.asyncio
async def test_client_headers_cannot_change_trusted_account() -> None:
    resolver = IdentityResolver(make_settings())
    payload = {"user": "stable-user"}

    first = await resolver.resolve_chat_scope(
        Headers({"x-sumeme-account-id": "account-a"}),
        payload,
    )
    second = await resolver.resolve_chat_scope(
        Headers({"x-sumeme-account-id": "account-b"}),
        payload,
    )

    assert first.account_id == second.account_id
    assert first.account_id == derive_account_id(UPSTREAM_ISSUER, "stable-user")


@pytest.mark.asyncio
async def test_service_identity_overrides_trusted_user_for_operations() -> None:
    resolver = IdentityResolver(make_settings())

    scope = await resolver.resolve_chat_scope(
        Headers(
            {
                "x-sumeme-service-token": "service-key",
                "x-sumeme-service-id": "sumeme-smoke",
                "x-sumeme-vault-id": "production-smoke",
            }
        ),
        {"user": "real-account-user"},
    )

    assert scope == MemoryScope.service("sumeme-smoke", "production-smoke")


def test_trusted_mode_requires_stable_upstream_issuer() -> None:
    with pytest.raises(ValidationError):
        make_settings(identity_trusted_upstream_issuer="")


def test_issuer_is_part_of_account_derivation() -> None:
    first = derive_account_id("lobehub-a", "same-user")
    second = derive_account_id("lobehub-b", "same-user")

    assert first != second
    assert len(first) == 32
    assert len(second) == 32
