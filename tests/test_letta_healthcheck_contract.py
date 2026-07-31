from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.yml"


class LettaHealthcheckContractTests(unittest.TestCase):
    def test_secure_letta_healthcheck_uses_server_password(self) -> None:
        compose = COMPOSE_FILE.read_text(encoding="utf-8")
        letta = compose.split("  letta:\n", 1)[1].split("\n  qdrant:\n", 1)[0]

        self.assertIn('SECURE: "true"', letta)
        self.assertIn("LETTA_SERVER_PASSWORD", letta)
        self.assertIn("http://localhost:8283/v1/health/", letta)
        self.assertIn("Authorization", letta)
        self.assertIn("Bearer ", letta)
        self.assertIn("os.environ['LETTA_SERVER_PASSWORD']", letta)
        self.assertNotIn(
            "urllib.request.urlopen('http://localhost:8283/v1/health'", letta
        )

    def test_healthcheck_does_not_echo_or_expand_password_in_compose(self) -> None:
        compose = COMPOSE_FILE.read_text(encoding="utf-8")
        letta = compose.split("  letta:\n", 1)[1].split("\n  qdrant:\n", 1)[0]
        healthcheck = letta.split("    healthcheck:\n", 1)[1]

        self.assertNotIn("echo", healthcheck)
        self.assertNotIn("${LETTA_SERVER_PASSWORD}", healthcheck)
        self.assertIn("os.environ['LETTA_SERVER_PASSWORD']", healthcheck)


if __name__ == "__main__":
    unittest.main()
