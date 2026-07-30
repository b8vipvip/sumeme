from __future__ import annotations

import math
import os
from dataclasses import dataclass


def _seconds_from_env(
    name: str,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default

    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc

    if not math.isfinite(value) or value < minimum or value > maximum:
        raise ValueError(
            f"{name} must be between {minimum:g} and {maximum:g} seconds"
        )
    return value


@dataclass(frozen=True, slots=True)
class MemoryDeadlines:
    """Latency budgets for optional memory work.

    Recall is on the user-facing critical path and therefore fails open after a
    short deadline. Writes are not allowed to hang forever either, but receive a
    longer budget because Letta may perform a remote model call before returning.
    """

    recall_seconds: float
    write_seconds: float

    @classmethod
    def from_environment(cls) -> MemoryDeadlines:
        return cls(
            recall_seconds=_seconds_from_env(
                "MEMORY_RECALL_TIMEOUT_SECONDS",
                default=20.0,
                minimum=0.1,
                maximum=300.0,
            ),
            write_seconds=_seconds_from_env(
                "MEMORY_WRITE_TIMEOUT_SECONDS",
                default=180.0,
                minimum=0.1,
                maximum=1800.0,
            ),
        )
