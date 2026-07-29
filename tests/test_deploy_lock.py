from __future__ import annotations

import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = REPOSITORY_ROOT / "scripts" / "deploy-production.sh"


class DeployLockTests(unittest.TestCase):
    def test_deploy_script_waits_instead_of_failing_immediately(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('DEPLOY_LOCK_WAIT_SECONDS="${DEPLOY_LOCK_WAIT_SECONDS:-1800}"', script)
        self.assertIn('flock -w "${DEPLOY_LOCK_WAIT_SECONDS}" 9', script)
        self.assertNotIn("flock -n 9", script)
        self.assertIn("deploy.lock.owner", script)
        self.assertIn("exit 75", script)

    def test_flock_waiter_continues_after_holder_releases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            lock_file = Path(temporary_directory) / "deploy.lock"
            holder = subprocess.Popen(
                [
                    "bash",
                    "-c",
                    'exec 9>"$1"; flock 9; sleep 0.4',
                    "bash",
                    str(lock_file),
                ]
            )
            try:
                time.sleep(0.1)
                started_at = time.monotonic()
                waiter = subprocess.run(
                    [
                        "bash",
                        "-c",
                        'exec 9>"$1"; flock -w 2 9',
                        "bash",
                        str(lock_file),
                    ],
                    check=False,
                )
                elapsed = time.monotonic() - started_at
            finally:
                holder.wait(timeout=3)

            self.assertEqual(waiter.returncode, 0)
            self.assertGreaterEqual(elapsed, 0.2)

    def test_flock_waiter_times_out_with_temporary_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            lock_file = Path(temporary_directory) / "deploy.lock"
            holder = subprocess.Popen(
                [
                    "bash",
                    "-c",
                    'exec 9>"$1"; flock 9; sleep 1',
                    "bash",
                    str(lock_file),
                ]
            )
            try:
                time.sleep(0.1)
                waiter = subprocess.run(
                    [
                        "bash",
                        "-c",
                        'exec 9>"$1"; flock -w 0.1 9',
                        "bash",
                        str(lock_file),
                    ],
                    check=False,
                )
            finally:
                holder.wait(timeout=3)

            self.assertNotEqual(waiter.returncode, 0)


if __name__ == "__main__":
    unittest.main()
