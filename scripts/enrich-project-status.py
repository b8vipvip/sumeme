#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_REFRESH_SECONDS = 15 * 60
DEFAULT_STALE_SECONDS = 35 * 60
DEFAULT_SMOKE_STALE_SECONDS = 24 * 60 * 60
DEFAULT_DISK_WARN_PERCENT = 80.0
DEFAULT_DISK_FAIL_PERCENT = 90.0
DEFAULT_MIN_FREE_BYTES = 3 * 1024**3
_SHA_RE = re.compile(r"^[0-9a-f]{7,64}$", re.IGNORECASE)


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def append_reason(status: dict[str, Any], reason: str) -> None:
    reasons = status.setdefault("reasons", [])
    if isinstance(reasons, list) and reason not in reasons:
        reasons.append(reason)


def last_deployment_result(history: Any) -> tuple[str, str | None]:
    if not isinstance(history, list):
        return "unknown", None
    entries = [str(item).strip() for item in history if str(item).strip()]
    if not entries:
        return "unknown", None

    latest = entries[-1]
    if " rollback " in f" {latest} ":
        return "rollback", latest

    parts = latest.split()
    if len(parts) >= 2 and _SHA_RE.fullmatch(parts[1]):
        return "success", latest
    return "unknown", latest


def add_deployment_signals(status: dict[str, Any], deploy_dir: Path) -> dict[str, Any]:
    deployment = status.setdefault("deployment", {})
    if not isinstance(deployment, dict):
        deployment = {}
        status["deployment"] = deployment

    current_sha = str(deployment.get("current_sha") or "").strip() or None
    previous_sha = str(deployment.get("previous_sha") or "").strip() or None
    deploying_sha = read_text(deploy_dir / ".deploy" / "deploying_sha") or None
    github = status.get("github") if isinstance(status.get("github"), dict) else {}
    main_sha = str((github or {}).get("latest_main_sha") or "").strip() or None

    history = deployment.get("history")
    if not isinstance(history, list):
        raw_history = read_text(deploy_dir / ".deploy" / "history.log")
        history = raw_history.splitlines()[-10:] if raw_history else []
        deployment["history"] = history

    result, history_entry = last_deployment_result(history)
    deployment_state = "idle"
    marker_consistent = True
    if deploying_sha:
        if current_sha and deploying_sha == current_sha:
            deployment_state = "stale_marker"
            marker_consistent = False
        else:
            deployment_state = "in_progress"

    current_matches_main = bool(current_sha and main_sha and current_sha == main_sha)
    deploying_matches_main = (
        bool(deploying_sha and main_sha and deploying_sha == main_sha)
        if deploying_sha
        else None
    )

    deployment.update(
        {
            "current_sha": current_sha,
            "previous_sha": previous_sha,
            "deploying_sha": deploying_sha,
            "last_result": result,
            "last_history_entry": history_entry,
            "state": deployment_state,
        }
    )
    status["deployment_in_sync"] = current_matches_main
    status["deployment_consistency"] = {
        "state": deployment_state,
        "marker_consistent": marker_consistent,
        "current_matches_main": current_matches_main,
        "deploying_matches_main": deploying_matches_main,
        "main_sha": main_sha,
    }

    if deployment_state == "stale_marker":
        append_reason(status, "部署状态存在未清理的 deploying_sha 标记")
        if status.get("overall") == "healthy":
            status["overall"] = "degraded"
    elif deployment_state == "in_progress":
        status["project_stage"] = "deployment_in_progress"

    return status["deployment_consistency"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Add reliability signals to a SuMeMe status snapshot")
    parser.add_argument("--json", required=True, dest="json_path")
    parser.add_argument("--markdown", required=True, dest="markdown_path")
    parser.add_argument("--smoke", dest="smoke_path")
    parser.add_argument(
        "--deploy-dir",
        default=os.environ.get("DEPLOY_DIR", "/opt/sumeme"),
        dest="deploy_dir",
    )
    parser.add_argument("--refresh-seconds", type=int, default=DEFAULT_REFRESH_SECONDS)
    parser.add_argument("--stale-seconds", type=int, default=DEFAULT_STALE_SECONDS)
    args = parser.parse_args()

    json_path = Path(args.json_path)
    markdown_path = Path(args.markdown_path)
    status = read_json(json_path)
    if status is None:
        raise SystemExit(f"Invalid status JSON: {json_path}")

    now = dt.datetime.now(dt.timezone.utc)
    generated_at = parse_time(status.get("generated_at"))
    age_seconds = max(0, int((now - generated_at).total_seconds())) if generated_at else None
    stale = generated_at is None or (age_seconds is not None and age_seconds > args.stale_seconds)

    status["schema_version"] = max(int(status.get("schema_version") or 1), 3)
    status["age_seconds"] = age_seconds
    status["stale"] = stale
    status["freshness"] = {
        "age_seconds": age_seconds,
        "stale": stale,
        "age_seconds_at_publish": age_seconds,
        "expected_refresh_seconds": args.refresh_seconds,
        "stale_after_seconds": args.stale_seconds,
        "stale_at_publish": stale,
        "generated_at": status.get("generated_at"),
    }
    if stale:
        append_reason(status, "状态快照在发布时已过期")
        if status.get("overall") == "healthy":
            status["overall"] = "degraded"

    consistency = add_deployment_signals(status, Path(args.deploy_dir))

    disk = ((status.get("system") or {}).get("disk") or {})
    used_percent = float(disk.get("used_percent") or 0)
    free_bytes = int(disk.get("free_bytes") or 0)
    disk_level = "ok"
    if used_percent >= DEFAULT_DISK_FAIL_PERCENT or free_bytes < DEFAULT_MIN_FREE_BYTES:
        disk_level = "critical"
        append_reason(status, "磁盘空间低于安全部署阈值")
        if status.get("overall") == "healthy":
            status["overall"] = "degraded"
    elif used_percent >= DEFAULT_DISK_WARN_PERCENT:
        disk_level = "warning"
        append_reason(status, "磁盘使用率达到 80% 警戒线")
        if status.get("overall") == "healthy":
            status["overall"] = "degraded"

    status["reliability"] = {
        "disk": {
            "level": disk_level,
            "warning_percent": DEFAULT_DISK_WARN_PERCENT,
            "failure_percent": DEFAULT_DISK_FAIL_PERCENT,
            "minimum_free_bytes": DEFAULT_MIN_FREE_BYTES,
        }
    }

    smoke: dict[str, Any] | None = None
    if args.smoke_path:
        smoke = read_json(Path(args.smoke_path))
    if smoke:
        smoke_time = parse_time(smoke.get("generated_at") or smoke.get("finished_at"))
        smoke_age = max(0, int((now - smoke_time).total_seconds())) if smoke_time else None
        smoke_stale = smoke_time is None or (
            smoke_age is not None and smoke_age > DEFAULT_SMOKE_STALE_SECONDS
        )
        status["reliability"]["smoke_test"] = {
            **smoke,
            "age_seconds_at_publish": smoke_age,
            "stale_at_publish": smoke_stale,
            "stale_after_seconds": DEFAULT_SMOKE_STALE_SECONDS,
        }
    else:
        status["reliability"]["smoke_test"] = {
            "available": False,
            "stale_at_publish": True,
        }

    json_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    smoke_status = status["reliability"]["smoke_test"]
    smoke_result = smoke_status.get("overall") or ("unavailable" if not smoke else "unknown")
    deployment = status["deployment"]
    reliability_section = [
        "",
        "## 可靠性信号",
        "",
        f"- 状态快照发布时年龄：`{age_seconds if age_seconds is not None else 'unknown'}s`",
        f"- 状态快照过期：`{'yes' if stale else 'no'}`（阈值 {args.stale_seconds}s）",
        f"- 部署状态：`{deployment.get('state') or 'unknown'}`",
        f"- 当前版本与 main 一致：`{'yes' if consistency.get('current_matches_main') else 'no'}`",
        f"- deploying SHA：`{deployment.get('deploying_sha') or 'none'}`",
        f"- 最近发布结果：`{deployment.get('last_result') or 'unknown'}`",
        f"- 磁盘保护级别：`{disk_level}`",
        f"- 最近 smoke test：`{smoke_result}`",
        "- 自动清理不会删除 Docker 数据卷、数据库或用户附件。",
        "",
    ]
    markdown_path.write_text(markdown.rstrip() + "\n" + "\n".join(reliability_section), encoding="utf-8")
    print(
        json.dumps(
            {
                "overall": status.get("overall"),
                "disk_level": disk_level,
                "stale": stale,
                "deployment_state": deployment.get("state"),
                "deployment_in_sync": status.get("deployment_in_sync"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
