#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def load_collector(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("sumeme_project_status_collector", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load collector: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_snapshot(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("GitHub status snapshot must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the project status collector with a pre-sanitized GitHub snapshot"
    )
    parser.add_argument("--github-snapshot", required=True)
    parser.add_argument(
        "--collector",
        default=str(Path(__file__).with_name("collect-project-status.py")),
    )
    args, collector_args = parser.parse_known_args()

    snapshot = read_snapshot(Path(args.github_snapshot))
    collector_path = Path(args.collector)
    collector = load_collector(collector_path)

    # sumeme-web owns the public FDEX-derived frontend, while lobe remains the
    # required account, Better Auth, conversation, attachment and application
    # backend. Both services are required for the product to be usable.
    critical_services = getattr(collector, "CRITICAL_SERVICES", None)
    if isinstance(critical_services, set):
        critical_services.add("lobe")
        critical_services.add("sumeme-web")

    collector.github_snapshot = lambda: snapshot

    original_argv = sys.argv
    try:
        sys.argv = [str(collector_path), *collector_args]
        return int(collector.main())
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    raise SystemExit(main())
