from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT_MAIN = ROOT / "clients" / "sumeme_app" / "lib" / "main.dart"
CLIENT_SHELL = ROOT / "clients" / "sumeme_app" / "lib" / "client_app.dart"
CLIENT_STATE = ROOT / "clients" / "sumeme_app" / "lib" / "client_state.dart"
CLIENT_CHAT = ROOT / "clients" / "sumeme_app" / "lib" / "chat_page.dart"
CLIENT_LIBRARY = ROOT / "clients" / "sumeme_app" / "lib" / "library_page.dart"
CLIENT_SETTINGS = ROOT / "clients" / "sumeme_app" / "lib" / "settings_page.dart"
API_CLIENT = ROOT / "clients" / "sumeme_app" / "lib" / "client_api.dart"
PUBSPEC = ROOT / "clients" / "sumeme_app" / "pubspec.yaml"
MATERIALIZER = ROOT / "scripts" / "materialize-flutter-client.py"
CLIENT_WORKFLOW = ROOT / ".github" / "workflows" / "build-clients.yml"


class NativeClientUIContractTests(unittest.TestCase):
    def test_client_uses_native_single_chat_widgets_not_webview(self) -> None:
        main = CLIENT_MAIN.read_text(encoding="utf-8")
        shell = CLIENT_SHELL.read_text(encoding="utf-8")
        chat = CLIENT_CHAT.read_text(encoding="utf-8")
        library = CLIENT_LIBRARY.read_text(encoding="utf-8")
        settings = CLIENT_SETTINGS.read_text(encoding="utf-8")

        self.assertIn("SuMeMeClientApp", main)
        self.assertIn("NavigationDrawer", shell)
        self.assertIn("SuMeMeChatPage", shell)
        self.assertIn("SuMeMeLibraryPage", shell)
        self.assertIn("SuMeMeSettingsPage", shell)
        self.assertIn("查找记忆记录", shell)
        self.assertIn("隐藏历史对话", shell)
        self.assertIn("上传文件", chat)
        self.assertIn("载入更早的聊天", chat)
        self.assertIn("_TimelineRail", library)
        self.assertIn("关于与更新", settings)
        self.assertNotIn("NavigationRail", shell)
        self.assertNotIn("NavigationBar", shell)
        self.assertNotIn("WebView", main + shell + chat + library + settings)
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
        self.assertIn("file.getFiles", api)
        self.assertIn("upload.createS3PreSignedUrl", api)
        self.assertIn("FlutterSecureStorage", state)
        self.assertIn("SharedPreferences", state)
        self.assertIn("checkForUpdates", state)
        self.assertIn("sumeme.single_timeline.v1", state)
        self.assertNotIn("gatewayToken", api + state)
        self.assertNotIn("adminToken", api + state)
        self.assertNotIn("OPENAI_RELAY_API_KEY", api + state)
        self.assertNotIn("HttpServer.bind", api + state)

    def test_pubspec_has_native_dependencies_and_no_webview_assets(self) -> None:
        pubspec = PUBSPEC.read_text(encoding="utf-8")

        self.assertIn("version: 0.5.0+1", pubspec)
        self.assertIn("crypto:", pubspec)
        self.assertIn("file_picker:", pubspec)
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
        self.assertIn("ui=single-chat-native-flutter", workflow)
        self.assertIn("persistent-single-timeline=true", workflow)
        self.assertIn("webview=false", workflow)
        self.assertIn("managed-server-config=true", workflow)
        self.assertIn("--build-name 0.5.0", workflow)
        self.assertIn("flutter build apk --release", workflow)
        self.assertIn("flutter build windows --release", workflow)
        self.assertIn("gh release upload v0.5.0", workflow)


if __name__ == "__main__":
    unittest.main()
