from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT_MAIN = ROOT / "clients" / "sumeme_app" / "lib" / "main.dart"
CLIENT_SHELL = ROOT / "clients" / "sumeme_app" / "lib" / "app_shell.dart"
CLIENT_STATE = ROOT / "clients" / "sumeme_app" / "lib" / "app_state.dart"
API_CLIENT = ROOT / "clients" / "sumeme_app" / "lib" / "api_client.dart"
PUBSPEC = ROOT / "clients" / "sumeme_app" / "pubspec.yaml"
MATERIALIZER = ROOT / "scripts" / "materialize-flutter-client.py"
CLIENT_WORKFLOW = ROOT / ".github" / "workflows" / "build-clients.yml"


class NativeClientUIContractTests(unittest.TestCase):
    def test_client_uses_native_flutter_widgets_not_webview(self) -> None:
        main = CLIENT_MAIN.read_text(encoding="utf-8")
        shell = CLIENT_SHELL.read_text(encoding="utf-8")

        self.assertIn("SuMeMeRoot", main)
        self.assertIn("NavigationRail", shell)
        self.assertIn("NavigationBar", shell)
        self.assertIn("_ChatPage", shell)
        self.assertIn("_MemoryPage", shell)
        self.assertIn("_LibraryPage", shell)
        self.assertIn("_VaultPage", shell)
        self.assertIn("_SyncPage", shell)
        self.assertIn("_SettingsPage", shell)
        self.assertNotIn("WebView", main + shell)
        self.assertNotIn("LobeHub", main + shell)
        self.assertFalse(
            (ROOT / "clients" / "sumeme_app" / "lib" / "bundled_lobehub_server.dart").exists()
        )

    def test_client_connects_directly_to_reviewed_server_api(self) -> None:
        api = API_CLIENT.read_text(encoding="utf-8")
        state = CLIENT_STATE.read_text(encoding="utf-8")

        self.assertIn("/api/gateway/", api)
        self.assertIn("/sumeme-health", api)
        self.assertIn("v1/chat/completions", api)
        self.assertIn("api/memory/search", api)
        self.assertIn("api/vaults/list", api)
        self.assertIn("api/objects/list", api)
        self.assertIn("FlutterSecureStorage", state)
        self.assertIn("SharedPreferences", state)
        self.assertNotIn("HttpServer.bind", api + state)

    def test_pubspec_has_native_dependencies_and_no_webview_assets(self) -> None:
        pubspec = PUBSPEC.read_text(encoding="utf-8")

        self.assertIn("version: 0.3.0+1", pubspec)
        self.assertIn("flutter_secure_storage", pubspec)
        self.assertIn("shared_preferences", pubspec)
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

    def test_workflow_builds_native_android_and_windows_clients(self) -> None:
        workflow = CLIENT_WORKFLOW.read_text(encoding="utf-8")

        self.assertNotIn("prepare-web-ui:", workflow)
        self.assertNotIn("lobehub/lobehub", workflow)
        self.assertNotIn("--web-ui", workflow)
        self.assertIn("ui=native-flutter", workflow)
        self.assertIn("webview=false", workflow)
        self.assertIn("--build-name 0.3.0", workflow)
        self.assertIn("flutter build apk --release", workflow)
        self.assertIn("flutter build windows --release", workflow)


if __name__ == "__main__":
    unittest.main()
