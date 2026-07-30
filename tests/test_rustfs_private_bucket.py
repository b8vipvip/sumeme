from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPOSITORY_ROOT / "docker-compose.yml"
ENV_EXAMPLE = REPOSITORY_ROOT / ".env.example"


class RustFSPrivateBucketTests(unittest.TestCase):
    def test_private_vault_bucket_is_created_without_anonymous_access(self) -> None:
        compose = COMPOSE_FILE.read_text(encoding="utf-8")

        self.assertIn(
            'mc mb "rustfs/${RUSTFS_PRIVATE_BUCKET:-sumeme-vaults}" --ignore-existing',
            compose,
        )
        self.assertIn(
            'mc anonymous set none "rustfs/${RUSTFS_PRIVATE_BUCKET:-sumeme-vaults}"',
            compose,
        )
        self.assertNotIn(
            'mc anonymous set-json /bucket.config.json '
            '"rustfs/${RUSTFS_PRIVATE_BUCKET:-sumeme-vaults}"',
            compose,
        )

    def test_gateway_receives_only_internal_private_bucket_coordinates(self) -> None:
        compose = COMPOSE_FILE.read_text(encoding="utf-8")

        self.assertIn("RUSTFS_INTERNAL_ENDPOINT: http://rustfs:9000", compose)
        self.assertIn(
            "RUSTFS_PRIVATE_BUCKET: ${RUSTFS_PRIVATE_BUCKET:-sumeme-vaults}",
            compose,
        )

    def test_example_configuration_separates_legacy_and_private_buckets(self) -> None:
        env_example = ENV_EXAMPLE.read_text(encoding="utf-8")

        self.assertIn("RUSTFS_LOBE_BUCKET=lobe", env_example)
        self.assertIn("RUSTFS_PRIVATE_BUCKET=sumeme-vaults", env_example)
        self.assertIn("anonymous=none", env_example)


if __name__ == "__main__":
    unittest.main()
