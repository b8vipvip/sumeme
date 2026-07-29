from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPOSITORY_ROOT / "services" / "memory-gateway" / "Dockerfile"


class GatewayDockerfileTests(unittest.TestCase):
    def test_pip_cache_is_persisted_between_builds(self) -> None:
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")

        self.assertIn("# syntax=docker/dockerfile:1.7", dockerfile)
        self.assertIn(
            "--mount=type=cache,target=/root/.cache/pip,sharing=locked",
            dockerfile,
        )
        self.assertNotIn("PIP_NO_CACHE_DIR=1", dockerfile)
        self.assertIn("PIP_DISABLE_PIP_VERSION_CHECK=1", dockerfile)


if __name__ == "__main__":
    unittest.main()
