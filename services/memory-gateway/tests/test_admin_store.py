from __future__ import annotations

from pathlib import Path

import pytest

from app.admin_store import AdminStore


@pytest.mark.asyncio
async def test_admin_bootstrap_auth_settings_and_release(tmp_path: Path) -> None:
    store = AdminStore(
        str(tmp_path / "admin.sqlite3"),
        master_secret="unit-test-master-secret",
        lobe_database_url="",
    )
    await store.initialize()
    assert await store.has_admin() is False

    session, token = await store.bootstrap_admin(
        email="owner@example.com",
        password="correct-horse-battery-staple",
        display_name="Owner",
    )
    assert session.email == "owner@example.com"
    assert token
    assert await store.has_admin() is True
    assert (await store.get_session(token)) is not None

    authenticated = await store.authenticate(
        email="owner@example.com",
        password="correct-horse-battery-staple",
    )
    assert authenticated is not None
    assert await store.authenticate(email="owner@example.com", password="wrong") is None

    await store.update_settings(
        admin_id=session.admin_id,
        values={
            "api.relay_base_url": "https://relay.example/v1",
            "api.relay_api_key": "secret-key",
            "modules.public_registration_enabled": False,
        },
        secret_keys={"api.relay_api_key"},
    )
    public = await store.get_settings()
    assert public["api.relay_api_key"] == {"configured": True, "masked": ""}
    private = await store.get_settings(include_secrets=True)
    assert private["api.relay_api_key"] == "secret-key"
    assert private["modules.public_registration_enabled"] is False

    release = await store.upsert_release(
        admin_id=session.admin_id,
        platform="windows",
        channel="stable",
        latest_version="0.4.0",
        minimum_version="0.3.0",
        download_url=(
            "https://github.com/b8vipvip/sumeme/releases/download/v0.4.0/"
            "SuMeMe-Windows-0.4.0-Setup.exe"
        ),
        notes="test",
    )
    assert release["latest_version"] == "0.4.0"
    saved = await store.get_release("windows", "stable")
    assert saved is not None
    assert saved["download_url"].endswith("Setup.exe")

    events = await store.audit_log()
    assert {event["action"] for event in events} >= {
        "admin.bootstrap",
        "settings.update",
        "release.update",
    }


@pytest.mark.asyncio
async def test_admin_bootstrap_is_single_use(tmp_path: Path) -> None:
    store = AdminStore(
        str(tmp_path / "admin.sqlite3"),
        master_secret="unit-test-master-secret",
        lobe_database_url="",
    )
    await store.initialize()
    await store.bootstrap_admin(
        email="owner@example.com",
        password="correct-horse-battery-staple",
        display_name="Owner",
    )
    with pytest.raises(ValueError, match="admin_already_initialized"):
        await store.bootstrap_admin(
            email="second@example.com",
            password="another-correct-battery-staple",
            display_name="Second",
        )
