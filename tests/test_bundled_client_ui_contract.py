from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT_MAIN = ROOT / "clients" / "sumeme_app" / "lib" / "main.dart"
CLIENT_SERVER = ROOT / "clients" / "sumeme_app" / "lib" / "bundled_lobehub_server.dart"
PUBSPEC = ROOT / "clients" / "sumeme_app" / "pubspec.yaml"
MATERIALIZER = ROOT / "scripts" / "materialize-flutter-client.py"
PREPARER = ROOT / "scripts" / "prepare-client-web-ui.py"
CLIENT_WORKFLOW = ROOT / ".github" / "workflows" / "build-clients.yml"
CONTROL_PANEL = ROOT / "web" / "control-panel" / "index.html"


class BundledClientUIContractTests(unittest.TestCase):
    def test_client_starts_a_loopback_server_and_loads_local_ui(self) -> None:
        main = CLIENT_MAIN.read_text(encoding="utf-8")
        server = CLIENT_SERVER.read_text(encoding="utf-8")

        self.assertIn("BundledLobeHubServer", main)
        self.assertIn("await _server.start()", main)
        self.assertIn("_AndroidBrowser(localOrigin: origin)", main)
        self.assertIn("_WindowsBrowser(localOrigin: origin)", main)
        self.assertNotIn("..loadRequest(Uri.parse(defaultAppUrl));", main)
        self.assertNotIn("await _controller.loadUrl(defaultAppUrl);", main)

        self.assertIn("InternetAddress.loopbackIPv4", server)
        self.assertIn("assets/lobehub/desktop.html", server)
        self.assertIn("assets/lobehub/auth.html", server)
        self.assertIn("assets/control-panel/index.html", server)
        self.assertIn("await _proxy(request)", server)
        self.assertIn("'/api'", server)
        self.assertIn("'/trpc'", server)

    def test_pubspec_requires_bundled_assets(self) -> None:
        pubspec = PUBSPEC.read_text(encoding="utf-8")

        self.assertIn("version: 0.2.0+1", pubspec)
        self.assertIn("- assets/lobehub/", pubspec)
        self.assertIn("- assets/control-panel/", pubspec)

    def test_materializer_fails_closed_without_web_ui(self) -> None:
        materializer = MATERIALIZER.read_text(encoding="utf-8")

        self.assertIn('"--web-ui"', materializer)
        self.assertIn("required=True", materializer)
        self.assertIn("validate_web_ui(web_ui)", materializer)
        self.assertIn('web_ui / "desktop.html"', materializer)
        self.assertIn('web_ui / "_spa-auth"', materializer)
        self.assertIn("CONTROL_PANEL_SOURCE", materializer)

    def test_preparer_preserves_lobehub_asset_roots(self) -> None:
        preparer = PREPARER.read_text(encoding="utf-8")

        self.assertIn('output / "_spa"', preparer)
        self.assertIn('output / "_spa-auth"', preparer)
        self.assertIn('output / "desktop.html"', preparer)
        self.assertIn('output / "auth.html"', preparer)
        self.assertIn('output / "bundle.json"', preparer)

    def test_workflow_builds_one_pinned_ui_for_both_clients(self) -> None:
        workflow = CLIENT_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("prepare-web-ui:", workflow)
        self.assertIn("LOBEHUB_UPSTREAM_REF: v2.2.11", workflow)
        self.assertIn("repository: lobehub/lobehub", workflow)
        self.assertIn("pnpm run build:spa", workflow)
        self.assertIn("pnpm run build:spa:auth", workflow)
        self.assertIn("scripts/prepare-client-web-ui.py", workflow)
        self.assertIn("name: sumeme-lobehub-web-ui", workflow)
        self.assertEqual(workflow.count("needs: prepare-web-ui"), 2)
        self.assertEqual(workflow.count("--web-ui"), 2)
        self.assertIn("--build-name 0.2.0", workflow)

    def test_control_panel_is_bundled_and_has_no_inline_secrets(self) -> None:
        panel = CONTROL_PANEL.read_text(encoding="utf-8")

        self.assertIn("服务端控制面板", panel)
        self.assertIn("/sumeme-health", panel)
        self.assertIn("/__sumeme/client-info", panel)
        self.assertNotIn("replace_with_random_secret", panel)
        self.assertNotIn("Authorization: Bearer", panel)

    def test_preparer_writes_a_manifest_for_provenance(self) -> None:
        namespace: dict[str, object] = {}
        exec(PREPARER.read_text(encoding="utf-8"), namespace)
        prepare = namespace["prepare"]

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            desktop = root / "desktop"
            auth = root / "auth"
            output = root / "output"
            (desktop / "assets").mkdir(parents=True)
            (auth / "assets").mkdir(parents=True)
            (desktop / "index.html").write_text("<html>desktop</html>", encoding="utf-8")
            (auth / "index.auth.html").write_text("<html>auth</html>", encoding="utf-8")
            (desktop / "assets" / "app.js").write_text("desktop", encoding="utf-8")
            (auth / "assets" / "auth.js").write_text("auth", encoding="utf-8")

            prepare(desktop, auth, output, "v2.2.11")

            self.assertTrue((output / "desktop.html").is_file())
            self.assertTrue((output / "auth.html").is_file())
            manifest = (output / "bundle.json").read_text(encoding="utf-8")
            self.assertIn('"upstream_ref": "v2.2.11"', manifest)


if __name__ == "__main__":
    unittest.main()
