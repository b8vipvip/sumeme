from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
UI_WORKFLOW = ROOT / ".github" / "workflows" / "public-ui-smoke.yml"
HEALTH_CHECK = ROOT / "scripts" / "health-check.sh"
UI_SMOKE = ROOT / "scripts" / "smoke-public-ui.py"
PATCH_SCRIPT = ROOT / "scripts" / "patch-lobehub-auth-assets.py"


def load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("sumeme_public_ui_patch", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicUIDeliveryContractTests(unittest.TestCase):
    def test_compose_uses_local_pinned_lobehub_image(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")
        lobe = compose.split("  lobe:\n", 1)[1].split("\n  ai-provider-proxy:\n", 1)[0]

        self.assertIn("LOBEHUB_IMAGE_PIN", lobe)
        self.assertIn("sumeme-lobehub:2.2.11-auth-assets-1", lobe)
        self.assertIn("pull_policy: never", lobe)
        self.assertNotIn("lobehub/lobehub:latest", lobe)

    def test_upstream_patch_is_exact_and_idempotent(self) -> None:
        module = load_module(PATCH_SCRIPT)
        with tempfile.TemporaryDirectory() as temp:
            dockerfile = Path(temp) / "Dockerfile"
            dockerfile.write_text(
                "FROM scratch\n"
                "COPY --from=builder /app/public/_spa /app/public/_spa\n",
                encoding="utf-8",
            )

            self.assertTrue(module.patch_dockerfile(dockerfile))
            patched = dockerfile.read_text(encoding="utf-8")
            self.assertEqual(patched.count(module.SPA_COPY), 1)
            self.assertEqual(patched.count(module.AUTH_COPY), 1)
            self.assertFalse(module.patch_dockerfile(dockerfile))

    def test_ghs_preloads_patched_image_before_deployment(self) -> None:
        workflow = CI.read_text(encoding="utf-8")

        self.assertIn("prepare-lobehub-image-ghs:", workflow)
        self.assertIn("LOBEHUB_UPSTREAM_REF: v2.2.11", workflow)
        self.assertIn("LOBEHUB_IMAGE_TAG: sumeme-lobehub:2.2.11-auth-assets-1", workflow)
        self.assertIn("repository: lobehub/lobehub", workflow)
        self.assertIn("python scripts/patch-lobehub-auth-assets.py", workflow)
        self.assertIn("docker save", workflow)
        self.assertIn("docker load", workflow)
        self.assertIn("StrictHostKeyChecking=yes", workflow)

        deployment = workflow.split("  deploy-production-ssh:\n", 1)[1]
        self.assertIn("- prepare-lobehub-image-ghs", deployment)

    def test_health_check_rejects_html_shell_with_missing_assets(self) -> None:
        health = HEALTH_CHECK.read_text(encoding="utf-8")
        smoke = UI_SMOKE.read_text(encoding="utf-8")

        self.assertIn("PUBLIC_UI_SMOKE_MODE", health)
        self.assertIn('python3 scripts/smoke-public-ui.py "${APP_URL%/}/"', health)
        self.assertIn("public UI references missing or unavailable assets", health)
        self.assertIn("class AssetParser", smoke)
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
