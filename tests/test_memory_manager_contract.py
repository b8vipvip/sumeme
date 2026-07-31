from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_JS = ROOT / "web" / "server-ui" / "static" / "memory-manager.js"
UI_CSS = ROOT / "web" / "server-ui" / "static" / "memory-manager.css"
NGINX = ROOT / "web" / "server-ui" / "nginx.conf"
API = ROOT / "services" / "memory-gateway" / "app" / "browser_memory.py"
STORE = ROOT / "services" / "memory-gateway" / "app" / "browser_memory_store.py"
ENTRY = ROOT / "services" / "memory-gateway" / "app" / "entry.py"


class MemoryManagerContractTests(unittest.TestCase):
    def test_browser_never_selects_or_asserts_an_account_identity(self) -> None:
        javascript = UI_JS.read_text(encoding="utf-8")

        self.assertIn("/api/gateway/api/ui/memory", javascript)
        self.assertIn("credentials: 'include'", javascript)
        self.assertNotIn("account_id", javascript)
        self.assertNotIn("principal_type", javascript)
        self.assertNotIn("GATEWAY_ADMIN_TOKEN", javascript)
        self.assertNotIn("gateway_admin_token", javascript)
        self.assertNotIn("Authorization", javascript)
        self.assertNotIn("/api/memory/search", javascript)
        self.assertNotIn("/api/memory/checkpoint", javascript)

    def test_gateway_derives_scope_from_lobehub_better_auth_session(self) -> None:
        api = API.read_text(encoding="utf-8")
        entry = ENTRY.read_text(encoding="utf-8")

        self.assertIn("/api/auth/get-session", api)
        self.assertIn('request.headers.get("cookie"', api)
        self.assertIn('MemoryScope.account(str(user["id"]), vault_id', api)
        self.assertIn("_require_same_origin(request)", api)
        self.assertIn("lobehub_session_required", api)
        self.assertIn("build_browser_memory_router(settings)", entry)
        self.assertNotIn("resolve_admin_scope", api)
        self.assertNotIn("require_admin_auth", api)

    def test_list_detail_stats_and_delete_always_include_scope_predicate(self) -> None:
        store = STORE.read_text(encoding="utf-8")

        self.assertIn(
            '"principal_type = ? AND account_id = ? AND vault_id = ?"',
            store,
        )
        self.assertIn("_get_delete_target_sync", store)
        self.assertIn("_delete_qdrant_point", store)
        self.assertIn("DELETE FROM mempalace_drawers", store)
        self.assertIn("/points/delete?wait=true", store)
        self.assertNotIn("DELETE FROM mempalace_drawers WHERE drawer_id = ?", store)

    def test_destructive_actions_require_explicit_confirmation_and_safe_rendering(self) -> None:
        javascript = UI_JS.read_text(encoding="utf-8")

        self.assertIn("window.confirm", javascript)
        self.assertIn("detailContent.textContent", javascript)
        self.assertIn("preview.textContent", javascript)
        self.assertIn("text.textContent", javascript)
        self.assertNotIn("innerHTML", javascript)
        self.assertNotIn("delete all", javascript.lower())

    def test_memory_assets_are_extensionless_and_mobile_ready(self) -> None:
        css = UI_CSS.read_text(encoding="utf-8")
        nginx = NGINX.read_text(encoding="utf-8")

        self.assertIn(".memory-manager-panel", css)
        self.assertIn(".memory-row", css)
        self.assertIn(".memory-semantic-results", css)
        self.assertIn("@media(max-width:860px)", css)
        self.assertIn("/assets/memory-style", nginx)
        self.assertIn("memory-manager.css", nginx)
        self.assertIn("/assets/memory-manager", nginx)
        self.assertIn("memory-manager.js", nginx)


if __name__ == "__main__":
    unittest.main()
