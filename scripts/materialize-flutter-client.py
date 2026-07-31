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


def resolve_flutter() -> str:
    executable = shutil.which("flutter.bat") or shutil.which("flutter")
    if executable is None:
        raise RuntimeError("flutter is not available on PATH")
    return executable


def replace_required(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    if old not in content:
        raise RuntimeError(f"Expected text not found in {path}: {old!r}")
    path.write_text(content.replace(old, new), encoding="utf-8")


def materialize(output: Path) -> None:
    flutter = resolve_flutter()
    if not CLIENT_SOURCE.is_dir():
        raise RuntimeError(f"Missing client source: {CLIENT_SOURCE}")

    if output.exists():
        shutil.rmtree(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    run(
        flutter,
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
        source = CLIENT_SOURCE / directory
        if source.exists():
            shutil.copytree(source, destination)

    shell = output / "lib" / "app_shell.dart"
    # Flutter 3.44 separates inherited component themes from ThemeData values.
    replace_required(shell, "cardTheme: CardTheme(", "cardTheme: CardThemeData(")
    # Keep the checked-in source compatible with the older analyzer while making
    # the generated release project pass the current strict const lint set.
    replace_required(
        shell,
        "          Padding(\n"
        "            padding: const EdgeInsets.symmetric(horizontal: 14),\n"
        "            child: TextField(\n"
        "              decoration: const InputDecoration(\n"
        "                hintText: '搜索本机会话',",
        "          const Padding(\n"
        "            padding: EdgeInsets.symmetric(horizontal: 14),\n"
        "            child: TextField(\n"
        "              decoration: InputDecoration(\n"
        "                hintText: '搜索本机会话',",
    )
    replace_required(
        shell,
        "          Wrap(\n"
        "            spacing: 8,\n"
        "            runSpacing: 8,\n"
        "            children: const <Widget>[\n"
        "              Chip(label: Text('全部')),",
        "          const Wrap(\n"
        "            spacing: 8,\n"
        "            runSpacing: 8,\n"
        "            children: <Widget>[\n"
        "              Chip(label: Text('全部')),",
    )

    manifest = output / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    replace_required(
        manifest,
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">',
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <uses-permission android:name="android.permission.INTERNET" />\n'
        '    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />',
    )
    replace_required(
        manifest,
        'android:label="sumeme_app"',
        'android:label="SuMeMe"',
    )

    gradle_kts = output / "android" / "app" / "build.gradle.kts"
    replace_required(
        gradle_kts,
        "minSdk = flutter.minSdkVersion",
        "minSdk = 24",
    )

    windows_main = output / "windows" / "runner" / "main.cpp"
    replace_required(windows_main, 'L"sumeme_app"', 'L"SuMeMe"')

    run(flutter, "pub", "get", cwd=output)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate native Android and Windows Flutter projects for SuMeMe"
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    materialize(args.output.resolve())
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
