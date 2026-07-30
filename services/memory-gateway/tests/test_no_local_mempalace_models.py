from __future__ import annotations

import ast
from pathlib import Path


def test_runtime_does_not_depend_on_upstream_local_mempalace_package() -> None:
    root = Path(__file__).resolve().parents[1]
    requirements = [
        line.strip().lower()
        for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert not any(line.startswith("mempalace") for line in requirements)
    assert not any(line.startswith("onnxruntime") for line in requirements)

    imported_modules: set[str] = set()
    for path in sorted((root / "app").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported_modules.add(node.module)

    assert not any(
        module == "mempalace" or module.startswith("mempalace.")
        for module in imported_modules
    )
    assert not any(
        module == "onnxruntime" or module.startswith("onnxruntime.")
        for module in imported_modules
    )
