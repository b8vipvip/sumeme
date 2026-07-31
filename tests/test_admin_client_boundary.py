from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AdminClientBoundaryTest(unittest.TestCase):
    def test_admin_is_separate_from_public_client(self) -> None:
        admin = (ROOT / "web/server-ui/admin/index.html").read_text(encoding="utf-8")
        self.assertIn("服务端管理后台", admin)
        self.assertIn("API 与模型", admin)
        self.assertIn("用户管理", admin)
        self.assertIn("云存储", admin)
        self.assertNotIn('id="page-chat"', admin)
        self.assertNotIn('id="page-memories"', admin)
        self.assertNotIn('id="page-files"', admin)

    def test_native_client_contains_no_server_secret_configuration(self) -> None:
        client_files = list((ROOT / "clients/sumeme_app/lib").glob("client_*.dart"))
        text = "\n".join(path.read_text(encoding="utf-8") for path in client_files)
        forbidden = (
            "gatewayToken",
            "adminToken",
            "GATEWAY_API_KEY",
            "GATEWAY_ADMIN_TOKEN",
            "OPENAI_RELAY_API_KEY",
            "客户端 Gateway 凭据",
            "管理员凭据",
        )
        for marker in forbidden:
            self.assertNotIn(marker, text)
        self.assertIn("/api/client/config", text)
        self.assertIn("/api/client/releases/", text)
        self.assertIn("关于与更新", text)

    def test_nginx_routes_admin_and_client_apis_independently(self) -> None:
        nginx = (ROOT / "web/server-ui/nginx.conf").read_text(encoding="utf-8")
        self.assertIn("location = /admin", nginx)
        self.assertIn("location ^~ /api/admin/", nginx)
        self.assertIn("location ^~ /api/client/", nginx)
        self.assertIn("/admin/index.html", nginx)


if __name__ == "__main__":
    unittest.main()
