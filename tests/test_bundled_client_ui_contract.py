from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT_MAIN = ROOT / "clients" / "sumeme_app" / "lib" / "main.dart"
CLIENT_SHELL = ROOT / "clients" / "sumeme_app" / "lib" / "client_app.dart"
CLIENT_STATE = ROOT / "clients" / "sumeme_app" / "lib" / "client_state.dart"
API_CLIENT = ROOT / "clients" / "sumeme_app" / "lib" / "client_api.dart"
PUBSPEC = ROOT / "clients" / "sumeme_app" / "pubspec.yaml"
MATERIALIZER = ROOT / "scripts" / "materialize-flutter-client.py"
CLIENT_WORKFLOW = ROOT / ".github" / "workflows" / "build-clients.yml"


class NativeClientUIContractTests(unittest.TestCase):
    def test_client_uses_native_flutter_widgets_not_webview(self) -> None:
        main = CLIENT_MAIN.read_text(encoding="utf-8")
        shell = CLIENT_SHELL.read_text(encoding="utf-8")

        self.assertIn("SuMeMeClientApp", main)
        self.assertIn("NavigationRail", shell)
        self.assertIn("NavigationBar", shell)
        self.assertIn("_ChatPage", shell)
        self.assertIn("_MemoryPage", shell)
        self.assertIn("_SettingsPage", shell)
        self.assertIn("关于与更新", shell)
        self.assertNotIn("WebView", main + shell)
        self.assertFalse(
            (ROOT / "clients" / "sumeme_app" / "lib" / "bundled_lobehub_server.dart").exists()
        )

    def test_client_uses_managed_server_api_without_server_secrets(self) -> None:
        api = API_CLIENT.read_text(encoding="utf-8")
        state = CLIENT_STATE.read_text(encoding="utf-8")

        self.assertIn("https://sumeme.mv3.cn", api)
        self.assertIn("/api/client/config", api)
        self.assertIn("/api/client/models", api)
        self.assertIn("/api/client/chat/completions", api)
        self.assertIn("/api/client/releases/", api)
        self.assertIn("FlutterSecureStorage", state)
        self.assertIn("SharedPreferences", state)
        self.assertIn("checkForUpdates", state)
        self.assertNotIn("gatewayToken", api + state)
        self.assertNotIn("adminToken", api + state)
        self.assertNotIn("OPENAI_RELAY_API_KEY", api + state)
        self.assertNotIn("HttpServer.bind", api + state)

    def test_pubspec_has_native_dependencies_and_no_webview_assets(self) -> None:
        pubspec = PUBSPEC.read_text(encoding="utf-8")

        self.assertIn("version: 0.4.0+1", pubspec)
        self.assertIn("flutter_secure_storage", pubspec)
        self.assertIn("shared_preferences", pubspec)
        self.assertIn("package_info_plus", pubspec)
        self.assertIn("url_launcher", pubspec)
        self.assertIn("http:", pubspec)
        self.assertNotIn("webview_flutter", pubspec)
        self.assertNotIn("assets/lobehub", pubspec)
        self.assertNotIn("assets/control-panel", pubspec)

    def test_materializer_does_not_require_web_ui_or_cleartext_loopback(self) -> None:
        materializer = MATERIALIZER.read_text(encoding="utf-8")

        self.assertNotIn('"--web-ui"', materializer)
        self.assertNotIn("validate_web_ui", materializer)
        self.assertNotIn("CONTROL_PANEL_SOURCE", materializer)
        self.assertNotIn("usesCleartextTraffic", materializer)
        self.assertIn("android.permission.INTERNET", materializer)
        self.assertIn('android:label="SuMeMe"', materializer)

    def test_workflow_builds_and_publishes_native_clients(self) -> None:
        workflow = CLIENT_WORKFLOW.read_text(encoding="utf-8")

        self.assertNotIn("prepare-web-ui:", workflow)
        self.assertNotIn("lobehub/lobehub", workflow)
        self.assertNotIn("--web-ui", workflow)
        self.assertIn("ui=native-flutter", workflow)
        self.assertIn("webview=false", workflow)
        self.assertIn("managed-server-config=true", workflow)
        self.assertIn("--build-name 0.4.0", workflow)
        self.assertIn("flutter build apk --release", workflow)
        self.assertIn("flutter build windows --release", workflow)
        self.assertIn("gh release upload v0.4.0", workflow)


if __name__ == "__main__":
    unittest.main()
