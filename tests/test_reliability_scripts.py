from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "enrich-project-status.py"


class EnrichProjectStatusTests(unittest.TestCase):
    def run_enricher(
        self,
        *,
        used_percent: float,
        free_bytes: int,
        generated_age_seconds: int = 0,
        current_sha: str = "a" * 40,
        main_sha: str = "a" * 40,
        deploying_sha: str = "",
        history: list[str] | None = None,
    ) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            json_path = root / "status.json"
            markdown_path = root / "STATUS.md"
            smoke_path = root / "smoke.json"
            deploy_dir = root / "deploy"
            state_dir = deploy_dir / ".deploy"
            state_dir.mkdir(parents=True)
            (deploy_dir / ".env").write_text(
                "LETTA_REQUIRED=false\n", encoding="utf-8"
            )

            generated_at = (
                dt.datetime.now(dt.timezone.utc)
                - dt.timedelta(seconds=generated_age_seconds)
            ).isoformat()
            deployment_history = history or [f"2026-07-30T00:00:00+00:00 {current_sha}"]
            status = {
                "schema_version": 1,
                "generated_at": generated_at,
                "repository": "b8vipvip/sumeme",
                "overall": "healthy",
                "project_stage": "deployed_and_stable",
                "reasons": [],
                "deployment_in_sync": current_sha == main_sha,
                "deployment": {
                    "current_sha": current_sha,
                    "previous_sha": "b" * 40,
                    "history": deployment_history,
                },
                "health": {
                    "local_gateway": {"ok": True, "status": 200},
                    "public": {"ok": True, "status": 200},
                },
                "services": [
                    {
                        "service": "letta",
                        "name": "sumeme-letta",
                        "state": "running",
                        "health": "healthy",
                        "status": "Up (healthy)",
                        "critical": True,
                    }
                ],
                "github": {
                    "latest_main_sha": main_sha,
                    "open_pull_requests": [],
                    "open_issues": [],
                    "recent_workflows": [],
                },
                "system": {
                    "disk": {
                        "used_percent": used_percent,
                        "free_bytes": free_bytes,
                    },
                    "memory": {
                        "used_percent": 50.0,
                        "available_bytes": 2 * 1024**3,
                    },
                },
            }
            smoke = {
                "generated_at": generated_at,
                "overall": "success",
                "checks": {"chat": True, "mempalace": True, "letta": True, "s3": True},
                "error_codes": [],
            }
            if deploying_sha:
                (state_dir / "deploying_sha").write_text(
                    deploying_sha + "\n", encoding="utf-8"
                )

            json_path.write_text(json.dumps(status), encoding="utf-8")
            markdown_path.write_text("# Status\n", encoding="utf-8")
            smoke_path.write_text(json.dumps(smoke), encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--json",
                    str(json_path),
                    "--markdown",
                    str(markdown_path),
                    "--smoke",
                    str(smoke_path),
                    "--deploy-dir",
                    str(deploy_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return json.loads(json_path.read_text(encoding="utf-8"))

    def test_warning_disk_marks_snapshot_degraded(self) -> None:
        status = self.run_enricher(used_percent=82.5, free_bytes=5 * 1024**3)
        self.assertEqual(status["overall"], "degraded")
        self.assertEqual(status["reliability"]["disk"]["level"], "warning")
        self.assertFalse(status["freshness"]["stale_at_publish"])
        self.assertEqual(status["reliability"]["smoke_test"]["overall"], "success")

    def test_low_free_space_is_critical(self) -> None:
        status = self.run_enricher(used_percent=70, free_bytes=2 * 1024**3)
        self.assertEqual(status["overall"], "degraded")
        self.assertEqual(status["reliability"]["disk"]["level"], "critical")
        self.assertIn("磁盘空间低于安全部署阈值", status["reasons"])

    def test_freshness_aliases_and_in_sync_state(self) -> None:
        status = self.run_enricher(used_percent=50, free_bytes=10 * 1024**3)

        self.assertEqual(status["schema_version"], 3)
        self.assertIsInstance(status["age_seconds"], int)
        self.assertFalse(status["stale"])
        self.assertEqual(status["freshness"]["age_seconds"], status["age_seconds"])
        self.assertFalse(status["freshness"]["stale"])
        self.assertTrue(status["deployment_in_sync"])
        self.assertEqual(status["deployment"]["state"], "idle")
        self.assertEqual(status["deployment"]["last_result"], "success")
        self.assertFalse(status["components"]["letta"]["required"])
        self.assertTrue(status["components"]["letta"]["available"])

    def test_stale_deploying_marker_is_visible_and_degraded(self) -> None:
        sha = "c" * 40
        status = self.run_enricher(
            used_percent=50,
            free_bytes=10 * 1024**3,
            current_sha=sha,
            main_sha=sha,
            deploying_sha=sha,
        )

        self.assertEqual(status["deployment"]["state"], "stale_marker")
        self.assertFalse(status["deployment_consistency"]["marker_consistent"])
        self.assertEqual(status["overall"], "degraded")
        self.assertIn("部署状态存在未清理的 deploying_sha 标记", status["reasons"])

    def test_active_deployment_and_rollback_history_are_classified(self) -> None:
        current = "d" * 40
        target = "e" * 40
        status = self.run_enricher(
            used_percent=50,
            free_bytes=10 * 1024**3,
            current_sha=current,
            main_sha=target,
            deploying_sha=target,
            history=[
                f"2026-07-30T00:00:00+00:00 {current}",
                (
                    "2026-07-30T01:00:00+00:00 rollback "
                    f"target={current} failed={target}"
                ),
            ],
        )

        self.assertEqual(status["deployment"]["state"], "in_progress")
        self.assertEqual(status["project_stage"], "deployment_in_progress")
        self.assertEqual(status["deployment"]["last_result"], "rollback")
        self.assertTrue(status["deployment_consistency"]["deploying_matches_main"])
        self.assertFalse(status["deployment_in_sync"])


if __name__ == "__main__":
    unittest.main()
