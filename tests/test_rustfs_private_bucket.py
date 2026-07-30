from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPOSITORY_ROOT / "docker-compose.yml"
ENV_EXAMPLE = REPOSITORY_ROOT / ".env.example"
PRIVATE_SMOKE = REPOSITORY_ROOT / "scripts" / "smoke-private-object.sh"
DEPLOY_SCRIPT = REPOSITORY_ROOT / "scripts" / "deploy-production.sh"
SMOKE_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "smoke-production.yml"


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

    def test_private_smoke_uploads_reads_deletes_and_verifies_absence(self) -> None:
        script = PRIVATE_SMOKE.read_text(encoding="utf-8")

        self.assertIn("RUSTFS_PRIVATE_BUCKET", script)
        self.assertIn(
            'services/${SMOKE_ACCOUNT_ID}/vaults/${SMOKE_VAULT_ID}/objects/',
            script,
        )
        self.assertIn('mc pipe "$target"', script)
        self.assertIn('mc cat "$target"', script)
        self.assertIn('mc rm "$target"', script)
        self.assertIn('mc stat "$target"', script)
        self.assertNotIn("RUSTFS_LOBE_BUCKET", script)

    def test_deployment_gates_on_private_and_application_smoke(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        private_index = script.index("bash scripts/smoke-private-object.sh")
        application_index = script.index("bash scripts/smoke-test.sh")
        self.assertLess(private_index, application_index)
        self.assertIn("private_object_status != 0 || smoke_status != 0", script)

    def test_scheduled_smoke_uses_ghs_with_pinned_host_key(self) -> None:
        workflow = SMOKE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Smoke production (GHS)", workflow)
        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertNotIn("runs-on: [self-hosted", workflow)
        self.assertIn("StrictHostKeyChecking=yes", workflow)
        self.assertIn("SUMEME_SSH_HOST_KEY", workflow)
        self.assertIn("bash scripts/smoke-private-object.sh", workflow)
        self.assertIn("bash scripts/smoke-test.sh", workflow)


if __name__ == "__main__":
    unittest.main()
