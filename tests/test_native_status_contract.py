from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GHS_COLLECTOR = ROOT / "scripts" / "collect-project-status-ghs.py"
COMPOSE = ROOT / "docker-compose.yml"


class NativeStatusContractTests(unittest.TestCase):
    def test_frontend_and_lobehub_backend_are_both_critical(self) -> None:
        wrapper = GHS_COLLECTOR.read_text(encoding="utf-8")
        compose = COMPOSE.read_text(encoding="utf-8")

        self.assertIn('critical_services.add("lobe")', wrapper)
        self.assertIn('critical_services.add("sumeme-web")', wrapper)
        self.assertNotIn('critical_services.discard("lobe")', wrapper)
        self.assertIn("  sumeme-web:\n", compose)
        lobe = compose.split("  lobe:\n", 1)[1].split(
            "\n  ai-provider-proxy:\n", 1
        )[0]
        self.assertNotIn("ports:", lobe)
        self.assertIn("account, conversation, attachment", lobe)
        self.assertNotIn("migration only", lobe)
        self.assertIn("APP_URL: ${APP_URL:-https://sumeme.mv3.cn}", lobe)


if __name__ == "__main__":
    unittest.main()
