from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
UI_WORKFLOW = ROOT / ".github" / "workflows" / "public-ui-smoke.yml"
HEALTH_CHECK = ROOT / "scripts" / "health-check.sh"
UI_SMOKE = ROOT / "scripts" / "smoke-public-ui.py"
SERVER_UI = ROOT / "web" / "server-ui" / "index.html"
SERVER_NGINX = ROOT / "web" / "server-ui" / "nginx.conf"
SERVER_DOCKERFILE = ROOT / "web" / "server-ui" / "Dockerfile"


class PublicUIDeliveryContractTests(unittest.TestCase):
    def test_compose_exposes_sumeme_web_not_lobehub(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")
        web = compose.split("  sumeme-web:\n", 1)[1].split("\n  lobe:\n", 1)[0]
        lobe = compose.split("  lobe:\n", 1)[1].split("\n  ai-provider-proxy:\n", 1)[0]

        self.assertIn("context: ./web/server-ui", web)
        self.assertIn("127.0.0.1:${WEB_PORT:-3210}:80", web)
        self.assertIn("condition: service_healthy", web)
        self.assertNotIn("ports:", lobe)
        self.assertIn('expose:\n      - "3210"', lobe)
        self.assertIn("migration only", lobe)

    def test_server_ui_is_native_sumeme_and_proxies_only_reviewed_apis(self) -> None:
        html = SERVER_UI.read_text(encoding="utf-8")
        nginx = SERVER_NGINX.read_text(encoding="utf-8")
        dockerfile = SERVER_DOCKERFILE.read_text(encoding="utf-8")

        self.assertIn("<title>SuMeMe · 服务端</title>", html)
        self.assertIn("服务端管理中心", html)
        self.assertIn("MEMORY EXPLORER", html)
        self.assertIn("PRIVACY VAULTS", html)
        self.assertIn("/api/gateway/", html)
        self.assertIn("/sumeme-health", html)
        self.assertNotIn("LobeHub", html)
        self.assertNotIn("GATEWAY_ADMIN_TOKEN", html)
        self.assertNotIn("RUSTFS_SECRET_KEY", html)
        self.assertIn("location /api/gateway/", nginx)
        self.assertIn("proxy_pass http://memory-gateway:8000", nginx)
        self.assertIn("location = /sumeme-health", nginx)
        self.assertIn("nginx:1.27-alpine", dockerfile)

    def test_health_check_requires_native_server_ui(self) -> None:
        health = HEALTH_CHECK.read_text(encoding="utf-8")
        smoke = UI_SMOKE.read_text(encoding="utf-8")

        self.assertIn("sumeme-web", health)
        self.assertIn("<title>SuMeMe · 服务端</title>", health)
        self.assertIn("服务端管理中心", health)
        self.assertIn('python3 scripts/smoke-public-ui.py "${APP_URL%/}/"', health)
        self.assertIn("required_markers", smoke)
        self.assertIn("self_contained", smoke)
        self.assertIn("asset_failures", smoke)
        self.assertIn("return 1 if failures else 0", smoke)

    def test_external_ui_smoke_runs_after_successful_main_ci(self) -> None:
        workflow = UI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_run:", workflow)
        self.assertIn("workflows: [CI]", workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", workflow)
        self.assertNotIn("pull_request:", workflow)


if __name__ == "__main__":
    unittest.main()
