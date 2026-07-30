from __future__ import annotations

from app.memory_result import MemoryWriteResult


def test_optional_letta_failure_is_visible_degraded_success() -> None:
    result = MemoryWriteResult(
        provider="mempalace-letta",
        components={"mempalace": True, "letta": False},
        required_components=("mempalace",),
        error_codes=("letta_agent_create_failed",),
    )

    assert result.success is True
    assert result.degraded is True
    assert result.as_dict() == {
        "provider": "mempalace-letta",
        "success": True,
        "degraded": True,
        "components": {"mempalace": True, "letta": False},
        "required_components": ["mempalace"],
        "error_codes": ["letta_agent_create_failed"],
    }


def test_required_letta_failure_blocks_write() -> None:
    result = MemoryWriteResult(
        provider="mempalace-letta",
        components={"mempalace": True, "letta": False},
        required_components=("mempalace", "letta"),
        error_codes=("letta_agent_create_failed",),
    )

    assert result.success is False
    assert result.degraded is False


def test_missing_required_component_blocks_write() -> None:
    result = MemoryWriteResult(
        provider="mempalace-letta",
        components={"letta": True},
        required_components=("mempalace",),
    )

    assert result.success is False


def test_legacy_result_requires_all_declared_components() -> None:
    result = MemoryWriteResult(
        provider="legacy",
        components={"first": True, "second": False},
    )

    assert result.effective_required_components == ("first", "second")
    assert result.success is False
