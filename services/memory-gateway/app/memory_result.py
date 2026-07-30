from __future__ import annotations

from dataclasses import dataclass, field


class MemoryOperationError(RuntimeError):
    """A stable, content-free error category from a memory component."""

    def __init__(self, code: str):
        normalized = code.strip().lower()
        if not normalized or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
            for character in normalized
        ):
            raise ValueError("memory operation error code is invalid")
        super().__init__(normalized)
        self.code = normalized


@dataclass(frozen=True, slots=True)
class MemoryWriteResult:
    """Sanitized component-level outcome for one memory write.

    Error codes are stable categories only. They must never contain user content,
    provider responses, credentials or exception messages.
    """

    provider: str
    components: dict[str, bool]
    error_codes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def success(self) -> bool:
        return bool(self.components) and all(self.components.values())

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "success": self.success,
            "components": dict(self.components),
            "error_codes": list(self.error_codes),
        }
