from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.main import Settings


def configure(monkeypatch, **overrides) -> None:
    values = {
        "OPENAI_RELAY_BASE_URL": "https://relay.example/v1",
        "OPENAI_RELAY_API_KEY": "relay-key",
        "PROVIDER_PROXY_API_KEY": "proxy-key",
        "OPENAI_CHAT_MODEL": "gpt-test",
        "EMBEDDING_PROVIDER_MODE": "auto",
    }
    values.update({key: str(value) for key, value in overrides.items()})
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_settings_require_remote_semantic_model_in_auto_mode(monkeypatch) -> None:
    configure(
        monkeypatch,
        OPENAI_CHAT_MODEL="replace_me",
        OPENAI_MEMORY_MODEL="replace_me",
        EMBEDDING_SEMANTIC_MODEL="replace_me",
    )

    with pytest.raises(ValueError, match="must name a remote model"):
        Settings.from_environment()


def test_settings_validate_embedding_dimension(monkeypatch) -> None:
    configure(monkeypatch, EMBEDDING_DIMENSION="64")

    with pytest.raises(ValueError, match="EMBEDDING_DIMENSION"):
        Settings.from_environment()


def test_provider_proxy_has_no_local_model_runtime_dependencies() -> None:
    root = Path(__file__).resolve().parents[1]
    requirements = [
        line.strip().lower()
        for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    forbidden_packages = (
        "torch",
        "transformers",
        "onnxruntime",
        "sentence-transformers",
        "vllm",
        "llama-cpp",
        "whisper",
    )
    assert not any(
        line.startswith(package)
        for package in forbidden_packages
        for line in requirements
    )

    imported_modules: set[str] = set()
    for path in sorted((root / "app").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported_modules.add(node.module)

    forbidden_modules = {
        "torch",
        "transformers",
        "onnxruntime",
        "sentence_transformers",
        "vllm",
        "llama_cpp",
        "whisper",
    }
    assert imported_modules.isdisjoint(forbidden_modules)
