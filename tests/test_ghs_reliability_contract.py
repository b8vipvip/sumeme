from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy-production.sh"
COMPOSE_FILE = ROOT / "docker-compose.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
STATUS_WORKFLOW = ROOT / ".github" / "workflows" / "publish-status.yml"


class GHSReliabilityContractTests(unittest.TestCase):
    def test_production_and_rollback_rebuild_all_local_runtime_images(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        command = "docker compose build memory-gateway ai-provider-proxy"
        self.assertEqual(script.count(command), 2)
        self.assertNotIn("docker compose build memory-gateway || true", script)

    def test_rollback_clears_deploying_marker_and_records_history(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        rollback = script.split("rollback_on_error() {", 1)[1].split(
            "trap rollback_on_error ERR", 1
        )[0]

        self.assertIn('rm -f "${STATE_DIR}/deploying_sha"', rollback)
        self.assertIn("rollback target=%s failed=%s", rollback)

    def test_optional_letta_does_not_block_gateway_container_start(self) -> None:
        compose = COMPOSE_FILE.read_text(encoding="utf-8")
        gateway = compose.split("  memory-gateway:\n", 1)[1].split(
            "\n  letta:\n", 1
        )[0]

        self.assertIn("LETTA_REQUIRED: ${LETTA_REQUIRED:-false}", gateway)
        self.assertNotIn("\n      letta:", gateway)
        self.assertIn("condition: service_healthy", gateway)

    def test_production_workflow_remains_explicitly_ghs(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Deploy production (GHS)", workflow)
        self.assertIn("adob_mode: GHS", workflow)
        self.assertIn(
            "vars.SUMEME_DEPLOY_TRANSPORT == 'github-hosted-ssh'", workflow
        )
        self.assertIn("Deploy production (VSR fallback)", workflow)

    def test_status_publisher_uses_ghs_without_sending_token_to_vps(self) -> None:
        workflow = STATUS_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Publish project status (GHS)", workflow)
        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertNotIn("runs-on: [self-hosted", workflow)
        self.assertIn("StrictHostKeyChecking=yes", workflow)
        self.assertIn("SUMEME_SSH_HOST_KEY", workflow)
        self.assertIn("github-status-snapshot.py", workflow)
        self.assertIn("collect-project-status-ghs.py", workflow)
        self.assertIn("ADOB mode: GHS", workflow)

        remote_collection = workflow.split(
            "- name: Collect sanitized production status through GHS", 1
        )[1].split("- name: Remove remote temporary collector bundle", 1)[0]
        self.assertNotIn("GITHUB_TOKEN", remote_collection)
        self.assertIn("github-status.json", remote_collection)


if __name__ == "__main__":
    unittest.main()
