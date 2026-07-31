#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLIENT_SOURCE = REPOSITORY_ROOT / "clients" / "sumeme_app"


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, check=True, cwd=cwd)


def replace_required(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    if old not in content:
        raise RuntimeError(f"Expected text not found in {path}: {old!r}")
    path.write_text(content.replace(old, new), encoding="utf-8")


def materialize(output: Path) -> None:
    if shutil.which("flutter") is None:
        raise RuntimeError("flutter is not available on PATH")
    if not CLIENT_SOURCE.is_dir():
        raise RuntimeError(f"Missing client source: {CLIENT_SOURCE}")

    if output.exists():
        shutil.rmtree(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    run(
        "flutter",
        "create",
        "--platforms=android,windows",
        "--org",
        "cn.mv3.sumeme",
        "--project-name",
        "sumeme_app",
        str(output),
    )

    for filename in ("pubspec.yaml", "analysis_options.yaml"):
        shutil.copy2(CLIENT_SOURCE / filename, output / filename)
    for directory in ("lib", "test"):
        destination = output / directory
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(CLIENT_SOURCE / directory, destination)

    manifest = output / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    replace_required(
        manifest,
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">',
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <uses-permission android:name="android.permission.INTERNET" />',
    )
    replace_required(manifest, 'android:label="sumeme_app"', 'android:label="SuMeMe"')

    gradle_kts = output / "android" / "app" / "build.gradle.kts"
    replace_required(
        gradle_kts,
        "minSdk = flutter.minSdkVersion",
        "minSdk = 24",
    )

    windows_main = output / "windows" / "runner" / "main.cpp"
    replace_required(windows_main, 'L"sumeme_app"', 'L"SuMeMe"')

    run("flutter", "pub", "get", cwd=output)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Android and Windows Flutter platform projects for SuMeMe"
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    materialize(args.output.resolve())
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
