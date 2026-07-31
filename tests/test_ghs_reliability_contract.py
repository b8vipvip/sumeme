from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy-production-v2.sh"
COMPOSE_FILE = ROOT / "docker-compose.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
STATUS_WORKFLOW = ROOT / ".github" / "workflows" / "publish-status.yml"
SMOKE_WORKFLOW = ROOT / ".github" / "workflows" / "smoke-production.yml"


class GHSReliabilityContractTests(unittest.TestCase):
    def test_production_and_rollback_rebuild_all_local_runtime_images(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        command = "docker compose build memory-gateway ai-provider-proxy"
        self.assertEqual(script.count(command), 2)
        self.assertNotIn("docker compose build memory-gateway || true", script)

    def test_rollback_fails_closed_and_records_accurate_history(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        rollback = script.split("rollback_on_error() {", 1)[1].split(
            "trap rollback_on_error ERR", 1
        )[0]

        self.assertIn('rm -f "${STATE_DIR}/deploying_sha"', rollback)
        self.assertIn("rollback target=${CURRENT_SHA} failed=${TARGET_SHA}", rollback)
        self.assertIn("rollback_failed target=${CURRENT_SHA}", rollback)
        self.assertIn('if [[ "${rollback_succeeded}" == "true" ]]', rollback)
        self.assertIn("runtime_recovery_failed", rollback)
        self.assertNotIn("docker compose up -d --remove-orphans || true", rollback)
        self.assertNotIn("bash scripts/health-check.sh || true", rollback)

    def test_compose_recovery_recreates_containers_without_pruning_volumes(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        recovery = script.split("compose_up_resilient() {", 1)[1].split(
            "print_failure_diagnostics() {", 1
        )[0]

        self.assertIn("com.docker.compose.project=${project}", recovery)
        self.assertIn('docker rm -f "${project_containers[@]}"', recovery)
        self.assertIn('docker network rm "${project}"', recovery)
        self.assertNotIn("docker volume", recovery)
        self.assertNotIn("--volumes", recovery)

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
        self.assertEqual(workflow.count("deploy-production-v2.sh"), 2)
        self.assertNotIn("deploy_script: scripts/deploy-production.sh", workflow)

    def test_scheduled_smoke_uses_current_scripts_and_cannot_false_green(self) -> None:
        workflow = SMOKE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Upload current trusted smoke scripts", workflow)
        self.assertIn("scripts/smoke-private-object.sh scripts/smoke-test.sh", workflow)
        self.assertIn("sumeme-smoke-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}", workflow)
        self.assertIn("SMOKE_OUTPUT_PATH=\"${application_report}\"", workflow)
        self.assertIn("PRIVATE_OBJECT_SMOKE_OUTPUT_PATH=\"${private_report}\"", workflow)
        self.assertIn("test -s \"${application_report}\"", workflow)
        self.assertIn("test -s \"${private_report}\"", workflow)
        self.assertIn(
            "github.event_name == 'workflow_dispatch' && inputs.required == false",
            workflow,
        )
        self.assertNotIn("github.event_name == 'schedule' ||", workflow)
        self.assertNotIn("/opt/sumeme/.deploy/smoke/latest.json", workflow)
        self.assertNotIn("/opt/sumeme/.deploy/smoke/private-object.json", workflow)

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
