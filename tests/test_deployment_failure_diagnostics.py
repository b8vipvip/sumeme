from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy-production.sh"


class DeploymentFailureDiagnosticsTests(unittest.TestCase):
    def test_redacted_diagnostics_run_before_snapshot_restore(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        handler_start = script.index("rollback_on_error()")
        handler_end = script.index("trap rollback_on_error ERR")
        handler = script[handler_start:handler_end]

        self.assertIn("print_failure_diagnostics", handler)
        self.assertIn('restore_snapshot "${CURRENT_SHA}"', handler)
        self.assertLess(
            handler.index("print_failure_diagnostics"),
            handler.index('restore_snapshot "${CURRENT_SHA}"'),
        )

    def test_diagnostics_are_bounded_and_use_redacted_log_helper(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('"${service}" 120 20m', script)
        self.assertIn('scripts/show-logs.sh', script)
        self.assertIn('for service in memory-gateway letta', script)
        self.assertNotIn('cat "${DEPLOY_DIR}/.env"', script)

    def test_smoke_output_exposes_only_structured_status_fields(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        for field in (
            '"checks": value.get("checks")',
            '"write_components": value.get("write_components")',
            '"recall_components": value.get("recall_components")',
            '"error_codes": value.get("error_codes")',
        ):
            self.assertIn(field, script)


if __name__ == "__main__":
    unittest.main()
