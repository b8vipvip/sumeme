from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "scripts" / "deploy-production-v2.sh"
CLEANUP = ROOT / "scripts" / "cleanup-runtime.sh"


class DeploymentPreflightContractTests(unittest.TestCase):
    def test_preflight_finishes_before_runtime_rollback_is_armed(self) -> None:
        script = DEPLOY.read_text(encoding="utf-8")

        preflight_call = script.index("if run_disk_preflight; then")
        snapshot_call = script.index('snapshot_current "${CURRENT_SHA}"')
        rollback_trap = script.index("trap rollback_on_error ERR")
        source_sync = script.index("rsync -a --delete", rollback_trap)

        self.assertLess(preflight_call, snapshot_call)
        self.assertLess(snapshot_call, rollback_trap)
        self.assertLess(rollback_trap, source_sync)
        self.assertIn("preflight_blocked current=${CURRENT_SHA} target=${TARGET_SHA}", script)
        self.assertIn("current release ${CURRENT_SHA} remains active", script)
        self.assertIn("Commands evaluated as an `if` condition do not fire", script)
        self.assertNotIn("trap rollback_on_error ERR\n\nrun_disk_preflight", script)

    def test_critical_preflight_requests_safe_aggressive_cleanup(self) -> None:
        script = DEPLOY.read_text(encoding="utf-8")

        self.assertIn('if output="$(DEPLOY_DIR="${DEPLOY_DIR}" bash', script)
        self.assertIn('AGGRESSIVE_CLEANUP="${aggressive}"', script)
        self.assertIn('SOURCE_DIR="${SOURCE_DIR}"', script)
        self.assertIn('"${level}" == "critical"', script)
        self.assertIn("Disk preflight after cleanup", script)
        self.assertIn("blocked before code or containers are changed", script)

    def test_cleanup_reclaims_only_rebuildable_runtime_artifacts(self) -> None:
        script = CLEANUP.read_text(encoding="utf-8")

        self.assertIn('INCOMING_DIR="${ADOB_STAGING_ROOT}/incoming"', script)
        self.assertIn("old uploaded source tree", script)
        self.assertIn("Preserved active uploaded source tree", script)
        self.assertIn("current_sha previous_sha", script)
        self.assertIn("Preserved protected rollback snapshot", script)
        self.assertIn("docker builder prune --all --force", script)
        self.assertIn("docker image prune --all --force", script)
        self.assertNotIn("docker volume prune", script)
        self.assertNotIn("docker system prune --volumes", script)
        self.assertIn("Data volumes are never pruned", script)


if __name__ == "__main__":
    unittest.main()
