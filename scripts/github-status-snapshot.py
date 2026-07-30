#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


API_VERSION = "2022-11-28"
USER_AGENT = "sumeme-ghs-status/1.0"


def github_json(path: str, *, token: str) -> Any:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub API request failed status={exc.code} path={path}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub API request failed path={path}") from exc


def build_snapshot(repository: str, *, token: str) -> dict[str, Any]:
    repo_raw = github_json(f"/repos/{repository}", token=token)
    if not isinstance(repo_raw, dict):
        raise RuntimeError("GitHub repository response is not an object")

    default_branch = str(repo_raw.get("default_branch") or "main")
    branch_raw = github_json(
        f"/repos/{repository}/branches/{default_branch}", token=token
    )
    workflows_raw = github_json(
        f"/repos/{repository}/actions/runs?per_page=12", token=token
    )
    pulls_raw = github_json(
        f"/repos/{repository}/pulls?state=open&per_page=20", token=token
    )
    issues_raw = github_json(
        f"/repos/{repository}/issues?state=open&per_page=20", token=token
    )

    if not isinstance(branch_raw, dict):
        branch_raw = {}
    if not isinstance(workflows_raw, dict):
        workflows_raw = {}
    if not isinstance(pulls_raw, list):
        pulls_raw = []
    if not isinstance(issues_raw, list):
        issues_raw = []

    workflows = []
    for item in workflows_raw.get("workflow_runs", [])[:12]:
        if not isinstance(item, dict):
            continue
        workflows.append(
            {
                "name": item.get("name"),
                "display_title": item.get("display_title"),
                "event": item.get("event"),
                "status": item.get("status"),
                "conclusion": item.get("conclusion"),
                "head_branch": item.get("head_branch"),
                "head_sha": item.get("head_sha"),
                "run_number": item.get("run_number"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "html_url": item.get("html_url"),
            }
        )

    pulls = []
    for item in pulls_raw:
        if not isinstance(item, dict):
            continue
        pulls.append(
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "draft": item.get("draft"),
                "head": (item.get("head") or {}).get("ref"),
                "base": (item.get("base") or {}).get("ref"),
                "updated_at": item.get("updated_at"),
                "html_url": item.get("html_url"),
            }
        )

    issues = []
    for item in issues_raw:
        if not isinstance(item, dict) or "pull_request" in item:
            continue
        issues.append(
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "updated_at": item.get("updated_at"),
                "html_url": item.get("html_url"),
            }
        )

    return {
        "schema_version": 1,
        "source": "github-hosted-runner",
        "default_branch": default_branch,
        "latest_main_sha": ((branch_raw.get("commit") or {}).get("sha")),
        "open_pull_requests": pulls,
        "open_issues": issues,
        "recent_workflows": workflows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a sanitized GitHub metadata snapshot for GHS status collection"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not repository or "/" not in repository:
        raise SystemExit("GITHUB_REPOSITORY is required")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")

    snapshot = build_snapshot(repository, token=token)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "repository": repository,
                "latest_main_sha": snapshot.get("latest_main_sha"),
                "open_pull_requests": len(snapshot["open_pull_requests"]),
                "open_issues": len(snapshot["open_issues"]),
                "recent_workflows": len(snapshot["recent_workflows"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
