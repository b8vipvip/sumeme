#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


SPA_COPY = "COPY --from=builder /app/public/_spa /app/public/_spa"
AUTH_COPY = "COPY --from=builder /app/public/_spa-auth /app/public/_spa-auth"
CONTROL_PANEL_COPY = (
    "COPY --from=builder /app/public/sumeme-control /app/public/sumeme-control"
)


def patch_dockerfile(path: Path) -> bool:
    content = path.read_text(encoding="utf-8")
    occurrences = content.count(SPA_COPY)
    if occurrences != 1:
        raise RuntimeError(
            f"Expected exactly one SPA copy instruction in {path}, found {occurrences}"
        )

    additions = [
        instruction
        for instruction in (AUTH_COPY, CONTROL_PANEL_COPY)
        if instruction not in content
    ]
    if not additions:
        return False

    replacement = "\n".join((SPA_COPY, *additions))
    patched = content.replace(SPA_COPY, replacement, 1)
    path.write_text(patched, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Patch LobeHub's Dockerfile to include auth SPA assets and the "
            "SuMeMe control panel."
        )
    )
    parser.add_argument("dockerfile", type=Path)
    args = parser.parse_args()

    changed = patch_dockerfile(args.dockerfile)
    print("patched" if changed else "already-patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
