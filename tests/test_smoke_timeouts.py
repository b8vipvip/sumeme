from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPOSITORY_ROOT / "scripts" / "smoke-test.sh"
ENV_EXAMPLE = REPOSITORY_ROOT / ".env.example"


class SmokeTimeoutTests(unittest.TestCase):
    def test_chat_and_memory_requests_use_configured_timeouts(self) -> None:
        script = SMOKE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            'SMOKE_CHAT_TIMEOUT_SECONDS="$(read_env SMOKE_CHAT_TIMEOUT_SECONDS '
            '"${RELAY_TIMEOUT_SECONDS}")"',
            script,
        )
        self.assertIn(
            'SMOKE_MEMORY_TIMEOUT_SECONDS="$(read_env SMOKE_MEMORY_TIMEOUT_SECONDS '
            '"${RELAY_TIMEOUT_SECONDS}")"',
            script,
        )
        self.assertIn('--max-time "${SMOKE_CHAT_TIMEOUT_SECONDS}"', script)
        self.assertGreaterEqual(
            script.count('--max-time "${SMOKE_MEMORY_TIMEOUT_SECONDS}"'),
            2,
        )
        self.assertNotIn(
            'chat-response.json" \\\n  --write-out',
            script.replace('--max-time "${SMOKE_CHAT_TIMEOUT_SECONDS}" \\\n  --output "${temp_dir}/chat-response.json" \\\n  --write-out', ''),
        )

    def test_timeout_values_are_bounded(self) -> None:
        script = SMOKE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "timeout_value < 30 || timeout_value > 1800",
            script,
        )
        self.assertIn("exit 64", script)

    def test_example_documents_explicit_defaults(self) -> None:
        env_example = ENV_EXAMPLE.read_text(encoding="utf-8")

        self.assertIn("RELAY_TIMEOUT_SECONDS=600", env_example)
        self.assertIn("SMOKE_CHAT_TIMEOUT_SECONDS=600", env_example)
        self.assertIn("SMOKE_MEMORY_TIMEOUT_SECONDS=600", env_example)


if __name__ == "__main__":
    unittest.main()
