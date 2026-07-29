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
    def run_enricher(self, *, used_percent: float, free_bytes: int) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            json_path = root / "status.json"
            markdown_path = root / "STATUS.md"
            smoke_path = root / "smoke.json"
            generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
            status = {
                "schema_version": 1,
                "generated_at": generated_at,
                "overall": "healthy",
                "reasons": [],
                "system": {
                    "disk": {
                        "used_percent": used_percent,
                        "free_bytes": free_bytes,
                    }
                },
            }
            smoke = {
                "generated_at": generated_at,
                "overall": "success",
                "checks": {"chat": True, "mempalace": True, "letta": True, "s3": True},
                "error_codes": [],
            }
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


if __name__ == "__main__":
    unittest.main()
