from __future__ import annotations

from pathlib import Path


def test_runtime_does_not_depend_on_upstream_local_mempalace_package() -> None:
    root = Path(__file__).resolve().parents[1]
    requirements = (root / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "mempalace" not in requirements

    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "app").glob("*.py"))
    ).lower()
    assert "from mempalace" not in source
    assert "import mempalace" not in source
    assert "onnxruntime" not in source
    assert "huggingface" not in source
