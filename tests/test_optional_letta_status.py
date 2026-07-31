from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "enrich-project-status.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sumeme_enrich_status", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def status_with_services(*services: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall": "unhealthy",
        "reasons": [],
        "services": list(services),
        "health": {
            "local_gateway": {"ok": True, "status": 200},
            "public": {"ok": True, "status": 200},
        },
    }


class OptionalLettaStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def deploy_dir(self, letta_required: bool) -> tempfile.TemporaryDirectory[str]:
        temporary = tempfile.TemporaryDirectory()
        Path(temporary.name, ".env").write_text(
            f"LETTA_REQUIRED={'true' if letta_required else 'false'}\n",
            encoding="utf-8",
        )
        return temporary

    def test_optional_starting_letta_is_degraded_not_unhealthy(self) -> None:
        status = status_with_services(
            {
                "service": "letta",
                "state": "running",
                "health": "starting",
                "critical": True,
            }
        )
        status["reasons"] = ["关键服务异常: letta(running/starting)"]

        with self.deploy_dir(False) as deploy_dir:
            result = self.module.normalize_optional_letta_status(
                status, Path(deploy_dir)
            )

        self.assertEqual(status["overall"], "degraded")
        self.assertFalse(result["required"])
        self.assertFalse(result["available"])
        self.assertFalse(status["services"][0]["critical"])
        self.assertNotIn("关键服务异常", "\n".join(status["reasons"]))
        self.assertIn(
            "可选 Letta 结构化记忆不可用或尚未就绪", status["reasons"]
        )

    def test_required_starting_letta_remains_unhealthy(self) -> None:
        status = status_with_services(
            {
                "service": "letta",
                "state": "running",
                "health": "starting",
                "critical": True,
            }
        )
        status["reasons"] = ["关键服务异常: letta(running/starting)"]

        with self.deploy_dir(True) as deploy_dir:
            result = self.module.normalize_optional_letta_status(
                status, Path(deploy_dir)
            )

        self.assertEqual(status["overall"], "unhealthy")
        self.assertTrue(result["required"])
        self.assertTrue(status["services"][0]["critical"])
        self.assertIn("关键服务异常: letta", status["reasons"][0])

    def test_other_critical_failure_is_not_hidden(self) -> None:
        status = status_with_services(
            {
                "service": "letta",
                "state": "running",
                "health": "starting",
                "critical": True,
            },
            {
                "service": "qdrant",
                "state": "exited",
                "health": "unhealthy",
                "critical": True,
            },
        )
        status["reasons"] = [
            "关键服务异常: letta(running/starting), qdrant(exited/unhealthy)"
        ]

        with self.deploy_dir(False) as deploy_dir:
            self.module.normalize_optional_letta_status(status, Path(deploy_dir))

        self.assertEqual(status["overall"], "unhealthy")
        self.assertIn("qdrant(exited/unhealthy)", "\n".join(status["reasons"]))
        self.assertNotIn("letta(running/starting)", "\n".join(status["reasons"]))

    def test_optional_healthy_letta_restores_healthy_status(self) -> None:
        status = status_with_services(
            {
                "service": "letta",
                "state": "running",
                "health": "healthy",
                "critical": True,
            }
        )

        with self.deploy_dir(False) as deploy_dir:
            result = self.module.normalize_optional_letta_status(
                status, Path(deploy_dir)
            )

        self.assertEqual(status["overall"], "healthy")
        self.assertTrue(result["available"])
        self.assertEqual(status["reasons"], [])


if __name__ == "__main__":
    unittest.main()
