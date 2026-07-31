from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JAVASCRIPT = ROOT / "web" / "server-ui" / "static" / "files-manager.js"
CSS = ROOT / "web" / "server-ui" / "static" / "files-manager.css"
NGINX = ROOT / "web" / "server-ui" / "nginx.conf"


class FilesManagerContractTests(unittest.TestCase):
    def test_uses_current_lobehub_session_and_native_file_routes(self) -> None:
        javascript = JAVASCRIPT.read_text(encoding="utf-8")

        self.assertIn("credentials: 'include'", javascript)
        self.assertIn("file.getFiles", javascript)
        self.assertIn("file.findById", javascript)
        self.assertIn("file.updateFile", javascript)
        self.assertIn("file.removeFile", javascript)
        self.assertIn("file.checkFileHash", javascript)
        self.assertIn("upload.createS3PreSignedUrl", javascript)
        self.assertIn("file.createFile", javascript)
        self.assertIn("request.open('PUT', url)", javascript)
        self.assertIn("source: 'sumeme-files'", javascript)
        self.assertNotIn("GATEWAY_ADMIN_TOKEN", javascript)
        self.assertNotIn("RUSTFS_SECRET_KEY", javascript)
        self.assertNotIn("Authorization", javascript)
        self.assertNotIn("/api/v1/files", javascript)

    def test_requires_explicit_delete_confirmation_and_safe_rendering(self) -> None:
        javascript = JAVASCRIPT.read_text(encoding="utf-8")

        self.assertIn("window.confirm", javascript)
        self.assertIn("name.textContent = file.name", javascript)
        self.assertIn("description.textContent", javascript)
        self.assertNotIn("deleteKnowledgeItemsByQuery", javascript)
        self.assertNotIn("removeFiles", javascript)

    def test_assets_are_injected_through_extensionless_routes(self) -> None:
        css = CSS.read_text(encoding="utf-8")
        nginx = NGINX.read_text(encoding="utf-8")

        self.assertIn(".files-manager-panel", css)
        self.assertIn(".files-row", css)
        self.assertIn(".files-upload-item", css)
        self.assertIn("/assets/files-style", nginx)
        self.assertIn("files-manager.css", nginx)
        self.assertIn("/assets/files-manager", nginx)
        self.assertIn("files-manager.js", nginx)
        self.assertIn("default_type application/javascript", nginx)
        self.assertIn("default_type text/css", nginx)


if __name__ == "__main__":
    unittest.main()
