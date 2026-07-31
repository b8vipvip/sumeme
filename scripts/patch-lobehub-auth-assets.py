#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


SPA_COPY = "COPY --from=builder /app/public/_spa /app/public/_spa"
AUTH_COPY = "COPY --from=builder /app/public/_spa-auth /app/public/_spa-auth"


def patch_dockerfile(path: Path) -> bool:
    content = path.read_text(encoding="utf-8")
    if AUTH_COPY in content:
        return False

    occurrences = content.count(SPA_COPY)
    if occurrences != 1:
        raise RuntimeError(
            f"Expected exactly one SPA copy instruction in {path}, found {occurrences}"
        )

    patched = content.replace(SPA_COPY, f"{SPA_COPY}\n{AUTH_COPY}", 1)
    path.write_text(patched, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch LobeHub's Dockerfile to include built auth SPA assets."
    )
    parser.add_argument("dockerfile", type=Path)
    args = parser.parse_args()

    changed = patch_dockerfile(args.dockerfile)
    print("patched" if changed else "already-patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
