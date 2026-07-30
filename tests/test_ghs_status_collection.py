from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_SCRIPT = ROOT / "scripts" / "github-status-snapshot.py"
WRAPPER_SCRIPT = ROOT / "scripts" / "collect-project-status-ghs.py"


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GitHubStatusSnapshotTests(unittest.TestCase):
    def test_snapshot_contains_only_bounded_metadata(self) -> None:
        module = load_module(SNAPSHOT_SCRIPT, "sumeme_github_status_snapshot")
        token = "secret-token-that-must-not-appear"

        responses: dict[str, Any] = {
            "/repos/b8vipvip/sumeme": {"default_branch": "main"},
            "/repos/b8vipvip/sumeme/branches/main": {
                "commit": {"sha": "a" * 40}
            },
            "/repos/b8vipvip/sumeme/actions/runs?per_page=12": {
                "workflow_runs": [
                    {
                        "name": "CI",
                        "display_title": "test",
                        "event": "push",
                        "status": "completed",
                        "conclusion": "success",
                        "head_branch": "main",
                        "head_sha": "a" * 40,
                        "run_number": 10,
                        "created_at": "2026-07-30T00:00:00Z",
                        "updated_at": "2026-07-30T00:01:00Z",
                        "html_url": "https://github.com/example/run/10",
                        "logs_url": "must-not-be-copied",
                    }
                ]
            },
            "/repos/b8vipvip/sumeme/pulls?state=open&per_page=20": [
                {
                    "number": 43,
                    "title": "Reliability",
                    "draft": False,
                    "head": {"ref": "agent/test"},
                    "base": {"ref": "main"},
                    "updated_at": "2026-07-30T00:00:00Z",
                    "html_url": "https://github.com/example/pr/43",
                    "body": "must-not-be-copied",
                }
            ],
            "/repos/b8vipvip/sumeme/issues?state=open&per_page=20": [
                {
                    "number": 4,
                    "title": "Phase 1.5",
                    "updated_at": "2026-07-30T00:00:00Z",
                    "html_url": "https://github.com/example/issues/4",
                    "body": "must-not-be-copied",
                },
                {
                    "number": 43,
                    "title": "PR duplicate in issues API",
                    "pull_request": {},
                },
            ],
        }

        def fake_github_json(path: str, *, token: str) -> Any:
            self.assertEqual(token, "secret-token-that-must-not-appear")
            return responses[path]

        module.github_json = fake_github_json
        snapshot = module.build_snapshot("b8vipvip/sumeme", token=token)
        rendered = json.dumps(snapshot, ensure_ascii=False)

        self.assertEqual(snapshot["source"], "github-hosted-runner")
        self.assertEqual(snapshot["latest_main_sha"], "a" * 40)
        self.assertEqual(len(snapshot["open_pull_requests"]), 1)
        self.assertEqual(len(snapshot["open_issues"]), 1)
        self.assertEqual(len(snapshot["recent_workflows"]), 1)
        self.assertNotIn(token, rendered)
        self.assertNotIn("must-not-be-copied", rendered)
        self.assertNotIn("logs_url", rendered)
        self.assertNotIn("body", rendered)


class GHSCollectorWrapperTests(unittest.TestCase):
    def test_wrapper_injects_snapshot_without_github_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot_path = root / "github.json"
            output_path = root / "output.json"
            collector_path = root / "collector.py"

            snapshot = {
                "schema_version": 1,
                "source": "github-hosted-runner",
                "default_branch": "main",
                "latest_main_sha": "b" * 40,
                "open_pull_requests": [],
                "open_issues": [],
                "recent_workflows": [],
            }
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            collector_path.write_text(
                """
import argparse
import json

def github_snapshot():
    return {"unexpected": True}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True)
    args = parser.parse_args()
    with open(args.json, "w", encoding="utf-8") as handle:
        json.dump(github_snapshot(), handle)
    return 0
""".lstrip(),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(WRAPPER_SCRIPT),
                    "--github-snapshot",
                    str(snapshot_path),
                    "--collector",
                    str(collector_path),
                    "--json",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                env={},
            )

            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result, snapshot)


if __name__ == "__main__":
    unittest.main()
