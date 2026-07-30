#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Iterator

_REDACTED = "[REDACTED]"

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
        rf"\1{_REDACTED}",
    ),
    (
        re.compile(r"(?i)(\"authorization\"\s*:\s*\"bearer\s+)[^\"]+"),
        rf"\1{_REDACTED}",
    ),
    (
        re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
        f"sk-{_REDACTED}",
    ),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)"
            r"([\"']?\s*[:=]\s*[\"']?)"
            r"([^\s,;\"'}]{6,})"
        ),
        rf"\1\2{_REDACTED}",
    ),
    (
        re.compile(r"(?i)(postgres(?:ql)?://[^:\s/@]+:)[^@\s]+@"),
        rf"\1{_REDACTED}@",
    ),
    (
        re.compile(r"(?i)((?:cookie|set-cookie)\s*:\s*)[^\r\n]+"),
        rf"\1{_REDACTED}",
    ),
)

_PRIVATE_KEY_BEGIN = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
_PRIVATE_KEY_END = re.compile(r"-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")


def redact_line(line: str) -> str:
    redacted = line
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_stream(lines: Iterable[str]) -> Iterator[str]:
    inside_private_key = False
    for line in lines:
        if inside_private_key:
            if _PRIVATE_KEY_END.search(line):
                inside_private_key = False
            continue
        if _PRIVATE_KEY_BEGIN.search(line):
            inside_private_key = True
            yield f"{_REDACTED} PRIVATE KEY BLOCK\n"
            continue
        yield redact_line(line)


def main() -> int:
    for line in redact_stream(sys.stdin):
        sys.stdout.write(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
