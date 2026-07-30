from __future__ import annotations

from app.object_config import ObjectAccessSettings


def test_blank_private_override_falls_back_to_existing_s3_endpoint() -> None:
    settings = ObjectAccessSettings(
        object_api_enabled=True,
        rustfs_public_endpoint="",
        s3_endpoint="https://s3.example.test/",
        rustfs_access_key="access",
        rustfs_secret_key="secret",
    )

    assert settings.rustfs_public_endpoint == "https://s3.example.test"
