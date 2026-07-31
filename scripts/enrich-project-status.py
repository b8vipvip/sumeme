#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
from pathlib import Path
from types import ModuleType
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


def parse_env_value(env_path: Path, key: str, default: str = "") -> str:
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"').strip("'")
    except OSError:
        pass
    return default


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def append_reason(status: dict[str, Any], reason: str) -> None:
    reasons = status.setdefault("reasons", [])
    if isinstance(reasons, list) and reason not in reasons:
        reasons.append(reason)


def strip_service_from_reason(reason: str, prefix: str, service: str) -> str | None:
    if not reason.startswith(prefix):
        return reason
    entries = [entry.strip() for entry in reason[len(prefix) :].split(",")]
    remaining = [
        entry
        for entry in entries
        if entry and entry != service and not entry.startswith(f"{service}(")
    ]
    if not remaining:
        return None
    return prefix + ", ".join(remaining)


def normalize_optional_letta_status(
    status: dict[str, Any], deploy_dir: Path
) -> dict[str, Any]:
    letta_required = parse_bool(
        parse_env_value(deploy_dir / ".env", "LETTA_REQUIRED", "false")
    )
    services = status.get("services")
    service_items = services if isinstance(services, list) else []
    letta = next(
        (
            item
            for item in service_items
            if isinstance(item, dict) and item.get("service") == "letta"
        ),
        None,
    )

    if isinstance(letta, dict):
        letta["required"] = letta_required
        letta["critical"] = letta_required
        state = str(letta.get("state") or "unknown").lower()
        health = str(letta.get("health") or "").lower()
        letta_available = state in {"running", "up"} and health in {"", "healthy"}
    else:
        letta_available = False

    components = status.setdefault("components", {})
    if not isinstance(components, dict):
        components = {}
        status["components"] = components
    components["letta"] = {
        "required": letta_required,
        "available": letta_available,
        "state": letta.get("state") if isinstance(letta, dict) else "missing",
        "health": letta.get("health") if isinstance(letta, dict) else "missing",
    }

    if letta_required:
        return components["letta"]

    reasons = status.get("reasons")
    normalized_reasons: list[str] = []
    if isinstance(reasons, list):
        for raw_reason in reasons:
            reason = str(raw_reason)
            updated = strip_service_from_reason(reason, "缺少关键服务: ", "letta")
            if updated is not None:
                updated = strip_service_from_reason(
                    updated, "关键服务异常: ", "letta"
                )
            if updated:
                normalized_reasons.append(updated)
    status["reasons"] = normalized_reasons

    if not letta_available:
        append_reason(status, "可选 Letta 结构化记忆不可用或尚未就绪")

    hard_failure = any(
        reason.startswith("缺少关键服务: ")
        or reason.startswith("关键服务异常: ")
        or reason == "本地 memory-gateway 健康检查失败"
        for reason in status.get("reasons", [])
    )
    public_health = status.get("health")
    public_ok = bool(
        isinstance(public_health, dict)
        and isinstance(public_health.get("public"), dict)
        and public_health["public"].get("ok")
    )

    if hard_failure:
        status["overall"] = "unhealthy"
    elif not letta_available or not public_ok:
        status["overall"] = "degraded"
    else:
        status["overall"] = "healthy"
    return components["letta"]


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
    return status["deployment_consistency"]


def update_project_stage(status: dict[str, Any]) -> None:
    deployment = status.get("deployment")
    deployment = deployment if isinstance(deployment, dict) else {}
    github = status.get("github")
    github = github if isinstance(github, dict) else {}

    if deployment.get("state") == "in_progress":
        stage = "deployment_in_progress"
    elif not deployment.get("current_sha"):
        stage = "deployment_not_recorded"
    elif status.get("overall") == "unhealthy":
        stage = "deployed_unhealthy"
    elif not status.get("deployment_in_sync"):
        stage = "deployment_behind_main"
    elif github.get("open_pull_requests"):
        stage = "development_in_progress"
    elif status.get("overall") == "degraded":
        stage = "deployed_degraded"
    else:
        stage = "deployed_and_stable"
    status["project_stage"] = stage


def load_status_collector() -> ModuleType:
    path = Path(__file__).with_name("collect-project-status.py")
    spec = importlib.util.spec_from_file_location("sumeme_status_collector", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load status collector: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_base_markdown(status: dict[str, Any]) -> str:
    collector = load_status_collector()
    return str(collector.markdown(status))


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
    deploy_dir = Path(args.deploy_dir)
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

    letta_status = normalize_optional_letta_status(status, deploy_dir)
    consistency = add_deployment_signals(status, deploy_dir)

    if stale:
        append_reason(status, "状态快照在发布时已过期")
        if status.get("overall") == "healthy":
            status["overall"] = "degraded"

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

    update_project_stage(status)
    status["reliability"] = {
        "disk": {
            "level": disk_level,
            "warning_percent": DEFAULT_DISK_WARN_PERCENT,
            "failure_percent": DEFAULT_DISK_FAIL_PERCENT,
            "minimum_free_bytes": DEFAULT_MIN_FREE_BYTES,
        },
        "optional_components": {"letta": letta_status},
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
        f"- Letta 必需：`{'yes' if letta_status.get('required') else 'no'}`",
        f"- Letta 可用：`{'yes' if letta_status.get('available') else 'no'}`",
        f"- 最近 smoke test：`{smoke_result}`",
        "- 自动清理不会删除 Docker 数据卷、数据库或用户附件。",
        "",
    ]
    markdown_path.write_text(
        render_base_markdown(status).rstrip() + "\n" + "\n".join(reliability_section),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "overall": status.get("overall"),
                "disk_level": disk_level,
                "stale": stale,
                "deployment_state": deployment.get("state"),
                "deployment_in_sync": status.get("deployment_in_sync"),
                "letta_required": letta_status.get("required"),
                "letta_available": letta_status.get("available"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
