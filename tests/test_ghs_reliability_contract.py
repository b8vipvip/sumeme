from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy-production.sh"
COMPOSE_FILE = ROOT / "docker-compose.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_production_and_rollback_rebuild_all_local_runtime_images() -> None:
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    command = "docker compose build memory-gateway ai-provider-proxy"
    assert script.count(command) == 2
    assert "docker compose build memory-gateway || true" not in script


def test_rollback_clears_deploying_marker_and_records_history() -> None:
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    rollback = script.split("rollback_on_error() {", 1)[1].split(
        "trap rollback_on_error ERR", 1
    )[0]

    assert 'rm -f "${STATE_DIR}/deploying_sha"' in rollback
    assert "rollback target=%s failed=%s" in rollback


def test_optional_letta_does_not_block_gateway_container_start() -> None:
    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    gateway = compose.split("  memory-gateway:\n", 1)[1].split("\n  letta:\n", 1)[0]

    assert "LETTA_REQUIRED: ${LETTA_REQUIRED:-false}" in gateway
    assert "\n      letta:" not in gateway
    assert "condition: service_healthy" in gateway


def test_production_workflow_remains_explicitly_ghs() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "Deploy production (GHS)" in workflow
    assert "adob_mode: GHS" in workflow
    assert "vars.SUMEME_DEPLOY_TRANSPORT == 'github-hosted-ssh'" in workflow
    assert "Deploy production (VSR fallback)" in workflow
