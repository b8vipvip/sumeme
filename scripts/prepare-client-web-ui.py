#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise RuntimeError(f"Missing build directory: {source}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(desktop_dist: Path, auth_dist: Path, output: Path, upstream_ref: str) -> None:
    desktop_index = desktop_dist / "index.html"
    auth_index = auth_dist / "index.auth.html"
    if not desktop_index.is_file():
        raise RuntimeError(f"Missing LobeHub desktop index: {desktop_index}")
    if not auth_index.is_file():
        raise RuntimeError(f"Missing LobeHub auth index: {auth_index}")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    # Vite emits absolute /_spa and /_spa-auth asset paths. Preserve that exact
    # public layout so the embedded loopback server can serve the unmodified UI.
    copy_tree(desktop_dist, output / "_spa")
    copy_tree(auth_dist, output / "_spa-auth")
    shutil.copy2(desktop_index, output / "desktop.html")
    shutil.copy2(auth_index, output / "auth.html")

    files = sorted(path for path in output.rglob("*") if path.is_file())
    manifest = {
        "schema": 1,
        "upstream": "lobehub/lobehub",
        "upstream_ref": upstream_ref,
        "files": len(files),
        "desktop_index_sha256": sha256(output / "desktop.html"),
        "auth_index_sha256": sha256(output / "auth.html"),
    }
    (output / "bundle.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage LobeHub desktop/auth SPA builds for the SuMeMe client"
    )
    parser.add_argument("--desktop-dist", required=True, type=Path)
    parser.add_argument("--auth-dist", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--upstream-ref", default="v2.2.11")
    args = parser.parse_args()

    prepare(
        args.desktop_dist.resolve(),
        args.auth_dist.resolve(),
        args.output.resolve(),
        args.upstream_ref,
    )
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
