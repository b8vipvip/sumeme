from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
REQUIREMENTS = ROOT / "services" / "memory-gateway" / "requirements.txt"


class MemoryDeploymentContractTests(unittest.TestCase):
    def test_production_uses_remote_semantic_embeddings(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")

        self.assertIn("EMBEDDING_PROVIDER_MODE: remote-semantic-hash", compose)
        self.assertNotIn("EMBEDDING_PROVIDER_MODE: ${EMBEDDING_PROVIDER_MODE:-auto}", compose)

    def test_gateway_declares_openai_compatible_letta_handles(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")

        self.assertIn("LETTA_MODEL: openai/${OPENAI_MEMORY_MODEL}", compose)
        self.assertIn("LETTA_EMBEDDING: openai/${OPENAI_EMBEDDING_MODEL}", compose)
        self.assertNotIn("LETTA_MODEL: openai-proxy/", compose)

    def test_letta_openai_endpoint_stays_on_internal_provider_proxy(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")

        self.assertIn("OPENAI_API_BASE: http://ai-provider-proxy:8100/v1", compose)
        self.assertIn("OPENAI_BASE_URL: http://ai-provider-proxy:8100/v1", compose)

    def test_letta_runtime_and_sdk_are_pinned(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")
        requirements = REQUIREMENTS.read_text(encoding="utf-8")

        self.assertIn("LETTA_IMAGE_PIN:-letta/letta:0.16.8", compose)
        self.assertNotIn("LETTA_IMAGE:-letta/letta:latest", compose)
        self.assertIn("letta-client==1.12.1", requirements)
        self.assertNotIn("letta-client>=0.1,<1", requirements)

    def test_production_keeps_mempalace_required_and_letta_observable(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")

        self.assertIn("LETTA_REQUIRED: ${LETTA_REQUIRED:-false}", compose)
        self.assertIn("MEMPALACE_QDRANT_URL: http://qdrant:6333", compose)


if __name__ == "__main__":
    unittest.main()
