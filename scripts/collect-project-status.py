#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEPLOY_DIR = Path(os.environ.get("DEPLOY_DIR", "/opt/sumeme"))
STATE_DIR = DEPLOY_DIR / ".deploy"
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "b8vipvip/sumeme")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
CRITICAL_SERVICES = {
    "lobe",
    "memory-gateway",
    "letta",
    "postgresql",
    "qdrant",
    "redis",
    "rustfs",
    "searxng",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return default


def parse_env_value(key: str, default: str = "") -> str:
    env_path = DEPLOY_DIR / ".env"
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name == key:
                return value.strip().strip('"').strip("'")
    except OSError:
        pass
    return default


def run(command: list[str], *, cwd: Path | None = None, timeout: int = 30) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip()[:2000],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(exc)[:2000]}


def http_json(url: str, *, timeout: int = 8) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "sumeme-status/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(1_000_000).decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"body": body[:1000]}
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "data": parsed,
            }
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": str(exc)}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "status": None, "error": str(exc)}


def github_json(path: str) -> Any:
    if not TOKEN:
        return None
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sumeme-status/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return None


def parse_compose_ps() -> list[dict[str, Any]]:
    result = run(["docker", "compose", "ps", "--format", "json"], cwd=DEPLOY_DIR, timeout=30)
    if not result["ok"] or not result["stdout"]:
        return []
    raw = result["stdout"]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    records: list[dict[str, Any]] = []
    for line in raw.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def normalize_services(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    for record in records:
        service = str(record.get("Service") or record.get("service") or "")
        state = str(record.get("State") or record.get("state") or "unknown")
        health = str(record.get("Health") or record.get("health") or "")
        status = str(record.get("Status") or record.get("status") or "")
        name = str(record.get("Name") or record.get("name") or service)
        services.append(
            {
                "service": service,
                "name": name,
                "state": state,
                "health": health,
                "status": status,
                "critical": service in CRITICAL_SERVICES,
            }
        )
    services.sort(key=lambda item: item["service"])
    return services


def memory_stats() -> dict[str, Any]:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            number = raw.strip().split()[0]
            values[key] = int(number) * 1024
    except (OSError, ValueError, IndexError):
        return {}
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    return {
        "total_bytes": total,
        "available_bytes": available,
        "used_percent": round((1 - available / total) * 100, 1) if total else None,
    }


def disk_stats() -> dict[str, Any]:
    usage = shutil.disk_usage(DEPLOY_DIR)
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": round(usage.used / usage.total * 100, 1) if usage.total else None,
    }


def recent_history() -> list[str]:
    history = read_text(STATE_DIR / "history.log")
    return history.splitlines()[-10:] if history else []


def github_snapshot() -> dict[str, Any]:
    workflows_raw = github_json(f"/repos/{REPOSITORY}/actions/runs?per_page=12") or {}
    pulls_raw = github_json(f"/repos/{REPOSITORY}/pulls?state=open&per_page=20") or []
    issues_raw = github_json(f"/repos/{REPOSITORY}/issues?state=open&per_page=20") or []
    repo_raw = github_json(f"/repos/{REPOSITORY}") or {}
    default_branch = str(repo_raw.get("default_branch") or "main")
    branch_raw = github_json(f"/repos/{REPOSITORY}/branches/{default_branch}") or {}

    workflows = []
    for item in workflows_raw.get("workflow_runs", [])[:12]:
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

    pulls = [
        {
            "number": item.get("number"),
            "title": item.get("title"),
            "draft": item.get("draft"),
            "head": (item.get("head") or {}).get("ref"),
            "base": (item.get("base") or {}).get("ref"),
            "updated_at": item.get("updated_at"),
            "html_url": item.get("html_url"),
        }
        for item in pulls_raw
    ]
    issues = [
        {
            "number": item.get("number"),
            "title": item.get("title"),
            "updated_at": item.get("updated_at"),
            "html_url": item.get("html_url"),
        }
        for item in issues_raw
        if "pull_request" not in item
    ]

    latest_main_sha = ((branch_raw.get("commit") or {}).get("sha"))
    return {
        "default_branch": default_branch,
        "latest_main_sha": latest_main_sha,
        "open_pull_requests": pulls,
        "open_issues": issues,
        "recent_workflows": workflows,
    }


def determine_overall(
    services: list[dict[str, Any]], local_health: dict[str, Any], public_health: dict[str, Any]
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    by_name = {item["service"]: item for item in services}
    missing = sorted(CRITICAL_SERVICES - set(by_name))
    if missing:
        reasons.append("缺少关键服务: " + ", ".join(missing))

    unhealthy = []
    for name in sorted(CRITICAL_SERVICES & set(by_name)):
        item = by_name[name]
        state_ok = item["state"].lower() in {"running", "up"}
        health_value = item["health"].lower()
        health_ok = health_value in {"", "healthy"}
        if not state_ok or not health_ok:
            unhealthy.append(f"{name}({item['state']}/{item['health'] or 'no-healthcheck'})")
    if unhealthy:
        reasons.append("关键服务异常: " + ", ".join(unhealthy))

    if not local_health.get("ok"):
        reasons.append("本地 memory-gateway 健康检查失败")
    if not public_health.get("ok"):
        reasons.append("公网健康检查失败")

    if missing or unhealthy or not local_health.get("ok"):
        return "unhealthy", reasons
    if not public_health.get("ok"):
        return "degraded", reasons
    return "healthy", reasons


def human_bytes(value: int | float | None) -> str:
    if value is None:
        return "-"
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(amount) < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TiB"


def markdown(status: dict[str, Any]) -> str:
    github = status["github"]
    deploy = status["deployment"]
    lines = [
        "# SuMeMe 项目状态",
        "",
        f"- **采集时间：** {status['generated_at']}",
        f"- **总体状态：** `{status['overall']}`",
        f"- **开发阶段：** `{status['project_stage']}`",
        f"- **线上版本：** `{deploy['current_sha'] or 'unknown'}`",
        f"- **main 最新版本：** `{github.get('latest_main_sha') or 'unknown'}`",
        f"- **线上与 main 同步：** {'是' if status['deployment_in_sync'] else '否'}",
        f"- **开放 PR：** {len(github.get('open_pull_requests', []))}",
        f"- **开放 Issue：** {len(github.get('open_issues', []))}",
        "",
    ]
    if status["reasons"]:
        lines.extend(["## 需要关注", ""])
        lines.extend(f"- {reason}" for reason in status["reasons"])
        lines.append("")

    lines.extend(
        [
            "## 健康检查",
            "",
            f"- 本地网关：`{'ok' if status['health']['local_gateway'].get('ok') else 'failed'}`",
            f"- 公网入口：`{'ok' if status['health']['public'].get('ok') else 'failed'}`",
            f"- 磁盘使用：`{status['system']['disk'].get('used_percent')}%`，剩余 {human_bytes(status['system']['disk'].get('free_bytes'))}",
            f"- 内存使用：`{status['system']['memory'].get('used_percent')}%`，可用 {human_bytes(status['system']['memory'].get('available_bytes'))}",
            "",
            "## 容器服务",
            "",
            "| 服务 | 状态 | 健康 | 说明 |",
            "|---|---|---|---|",
        ]
    )
    for item in status["services"]:
        lines.append(
            f"| {item['service']} | {item['state']} | {item['health'] or '-'} | {item['status'] or '-'} |"
        )

    lines.extend(["", "## 最近工作流", "", "| 工作流 | 结果 | 分支 | 时间 |", "|---|---|---|---|"])
    for item in github.get("recent_workflows", [])[:8]:
        result = item.get("conclusion") or item.get("status") or "unknown"
        lines.append(
            f"| {item.get('name') or '-'} | {result} | {item.get('head_branch') or '-'} | {item.get('updated_at') or '-'} |"
        )

    lines.extend(["", "## 开放 PR", ""])
    if github.get("open_pull_requests"):
        for item in github["open_pull_requests"]:
            lines.append(f"- #{item['number']} {item['title']} (`{item['head']}` → `{item['base']}`)")
    else:
        lines.append("- 无")

    lines.extend(["", "## 开放 Issue", ""])
    if github.get("open_issues"):
        for item in github["open_issues"]:
            lines.append(f"- #{item['number']} {item['title']}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 最近部署", ""])
    if deploy["history"]:
        lines.extend(f"- `{entry}`" for entry in reversed(deploy["history"]))
    else:
        lines.append("- 暂无部署历史")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a sanitized SuMeMe runtime and GitHub status snapshot")
    parser.add_argument("--json", required=True, dest="json_path")
    parser.add_argument("--markdown", required=True, dest="markdown_path")
    args = parser.parse_args()

    services = normalize_services(parse_compose_ps())
    app_url = parse_env_value("APP_URL", "https://sumeme.mv3.cn").rstrip("/")
    local_health = http_json("http://127.0.0.1:8010/health")
    public_health = http_json(f"{app_url}/sumeme-health")
    github = github_snapshot()
    current_sha = read_text(STATE_DIR / "current_sha")
    previous_sha = read_text(STATE_DIR / "previous_sha")
    overall, reasons = determine_overall(services, local_health, public_health)
    latest_main_sha = github.get("latest_main_sha")
    in_sync = bool(current_sha and latest_main_sha and current_sha == latest_main_sha)

    if not current_sha:
        stage = "deployment_not_recorded"
    elif overall == "unhealthy":
        stage = "deployed_unhealthy"
    elif not in_sync:
        stage = "deployment_behind_main"
    elif github.get("open_pull_requests"):
        stage = "development_in_progress"
    else:
        stage = "deployed_and_stable"

    status = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "repository": REPOSITORY,
        "overall": overall,
        "project_stage": stage,
        "reasons": reasons,
        "deployment_in_sync": in_sync,
        "deployment": {
            "current_sha": current_sha or None,
            "previous_sha": previous_sha or None,
            "history": recent_history(),
        },
        "health": {"local_gateway": local_health, "public": public_health},
        "services": services,
        "system": {"disk": disk_stats(), "memory": memory_stats()},
        "github": github,
        "collector": {
            "event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "workflow": os.environ.get("GITHUB_WORKFLOW"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
        },
    }

    json_path = Path(args.json_path)
    markdown_path = Path(args.markdown_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown(status), encoding="utf-8")
    print(json.dumps({"overall": overall, "stage": stage, "in_sync": in_sync}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
