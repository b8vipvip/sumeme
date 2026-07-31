from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
COMPOSE_OVERRIDE = ROOT / "docker-compose.override.yml"
UI_WORKFLOW = ROOT / ".github" / "workflows" / "public-ui-smoke.yml"
HEALTH_CHECK = ROOT / "scripts" / "health-check.sh"
UI_SMOKE = ROOT / "scripts" / "smoke-public-ui.py"
SERVER_UI = ROOT / "web" / "server-ui" / "index.html"
SERVER_JS = ROOT / "web" / "server-ui" / "static" / "app.js"
SERVER_CSS = ROOT / "web" / "server-ui" / "static" / "admin.css"
SERVER_NGINX = ROOT / "web" / "server-ui" / "nginx.conf"
SERVER_DOCKERFILE = ROOT / "web" / "server-ui" / "Dockerfile"


class PublicUIDeliveryContractTests(unittest.TestCase):
    def test_compose_uses_sumeme_frontend_and_preserves_lobehub_backend(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")
        web = compose.split("  sumeme-web:\n", 1)[1].split("\n  lobe:\n", 1)[0]
        lobe = compose.split("  lobe:\n", 1)[1].split("\n  ai-provider-proxy:\n", 1)[0]

        self.assertIn("context: ./web/server-ui", web)
        self.assertIn("127.0.0.1:${WEB_PORT:-3210}:80", web)
        self.assertIn("lobe:", web)
        self.assertIn("condition: service_started", web)
        self.assertNotIn("ports:", lobe)
        self.assertIn('expose:\n      - "3210"', lobe)
        self.assertIn("account, conversation, attachment", lobe)
        self.assertNotIn("migration only", lobe)
        self.assertIn("APP_URL: ${APP_URL:-https://sumeme.mv3.cn}", lobe)

    def test_production_compose_always_rebuilds_the_public_frontend(self) -> None:
        override = COMPOSE_OVERRIDE.read_text(encoding="utf-8")
        web = override.split("  sumeme-web:\n", 1)[1].split("\n  lobe:\n", 1)[0]

        self.assertIn("pull_policy: build", web)
        self.assertIn("exact release source", web)
        self.assertNotIn("image:", web)

    def test_server_ui_uses_fdex_style_and_lobehub_auth_api(self) -> None:
        html = SERVER_UI.read_text(encoding="utf-8")
        javascript = SERVER_JS.read_text(encoding="utf-8")
        css = SERVER_CSS.read_text(encoding="utf-8")
        nginx = SERVER_NGINX.read_text(encoding="utf-8")
        dockerfile = SERVER_DOCKERFILE.read_text(encoding="utf-8")

        self.assertIn("<title>SuMeMe · 服务端</title>", html)
        self.assertIn("服务端管理中心", html)
        self.assertIn("SUMEME OPERATIONS CENTER", html)
        self.assertIn("FDEX", html)
        self.assertIn("LobeHub 后端", html)
        self.assertIn("/static/admin.css", html)
        self.assertIn("/static/app.js", html)
        self.assertIn("/api/auth/get-session", javascript)
        self.assertIn("/api/auth/sign-in/email", javascript)
        self.assertIn("/api/auth/sign-up/email", javascript)
        self.assertIn("/api/auth/sign-out", javascript)
        self.assertIn("--sidebar:#111827", css)
        self.assertNotIn("GATEWAY_ADMIN_TOKEN", html + javascript)
        self.assertNotIn("RUSTFS_SECRET_KEY", html + javascript)
        self.assertIn("location ^~ /api/auth/", nginx)
        self.assertIn("location ^~ /trpc/", nginx)
        self.assertIn("location ^~ /api/", nginx)
        self.assertIn("location ^~ /_spa-auth/", nginx)
        self.assertIn("proxy_pass http://lobe:3210", nginx)
        self.assertIn("location ^~ /api/gateway/", nginx)
        self.assertIn("proxy_pass http://memory-gateway:8000", nginx)
        self.assertIn("location = /sumeme-health", nginx)
        self.assertIn("COPY static /usr/share/nginx/html/static", dockerfile)

    def test_health_check_requires_sumeme_frontend(self) -> None:
        health = HEALTH_CHECK.read_text(encoding="utf-8")
        smoke = UI_SMOKE.read_text(encoding="utf-8")

        self.assertIn("sumeme-web", health)
        self.assertIn("<title>SuMeMe · 服务端</title>", health)
        self.assertIn("服务端管理中心", health)
        self.assertIn('python3 scripts/smoke-public-ui.py "${APP_URL%/}/"', health)
        self.assertIn("required_markers", smoke)
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
