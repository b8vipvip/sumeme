#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs if value}
        if tag.lower() == "script" and values.get("src"):
            self.assets.append(("script", values["src"]))
            return
        if tag.lower() != "link" or not values.get("href"):
            return
        rel = {part.lower() for part in values.get("rel", "").split()}
        if rel & {"stylesheet", "modulepreload", "preload"}:
            self.assets.append(("link", values["href"]))


def fetch(url: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/javascript,text/css,*/*;q=0.8",
            "User-Agent": "sumeme-public-ui-smoke/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(5_000_000)
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "url": response.geturl(),
                "content_type": response.headers.get_content_type(),
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "url": exc.geturl(),
            "content_type": exc.headers.get_content_type() if exc.headers else None,
            "error": str(exc),
            "body": exc.read(1000),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "status": None,
            "url": url,
            "content_type": None,
            "error": str(exc),
            "body": b"",
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that the public SuMeMe HTML and all referenced UI assets load."
    )
    parser.add_argument("url", nargs="?", default="https://sumeme.mv3.cn/")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    page = fetch(args.url, args.timeout)
    page_summary = {key: value for key, value in page.items() if key != "body"}
    print(json.dumps({"page": page_summary}, ensure_ascii=False))
    if not page["ok"]:
        return 1

    content_type = str(page.get("content_type") or "")
    if content_type not in {"text/html", "application/xhtml+xml"}:
        print(f"Expected HTML but received {content_type!r}", file=sys.stderr)
        return 1

    html = page["body"].decode("utf-8", errors="replace")
    asset_parser = AssetParser()
    asset_parser.feed(html)

    final_url = str(page["url"])
    parsed_origin = urllib.parse.urlsplit(final_url)
    origin = (parsed_origin.scheme, parsed_origin.netloc)
    seen: set[str] = set()
    failures: list[dict[str, Any]] = []
    checked = 0

    for kind, raw_url in asset_parser.assets:
        resolved = urllib.parse.urljoin(final_url, raw_url)
        parsed = urllib.parse.urlsplit(resolved)
        if (parsed.scheme, parsed.netloc) != origin or resolved in seen:
            continue
        seen.add(resolved)
        checked += 1
        result = fetch(resolved, args.timeout)
        summary = {
            "kind": kind,
            "reference": raw_url,
            **{key: value for key, value in result.items() if key != "body"},
        }
        print(json.dumps({"asset": summary}, ensure_ascii=False))
        if not result["ok"]:
            failures.append(summary)

    print(
        json.dumps(
            {
                "summary": {
                    "final_url": final_url,
                    "assets_checked": checked,
                    "asset_failures": len(failures),
                }
            },
            ensure_ascii=False,
        )
    )

    if checked == 0:
        print("No first-party scripts or stylesheets were referenced by the HTML.", file=sys.stderr)
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
