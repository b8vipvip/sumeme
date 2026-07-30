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
    provider responses, credentials or exception messages. Required components
    determine the deployment gate; optional component failures remain visible as
    a degraded result instead of being silently treated as success.
    """

    provider: str
    components: dict[str, bool]
    error_codes: tuple[str, ...] = field(default_factory=tuple)
    required_components: tuple[str, ...] = field(default_factory=tuple)

    @property
    def effective_required_components(self) -> tuple[str, ...]:
        return self.required_components or tuple(self.components)

    @property
    def success(self) -> bool:
        required = self.effective_required_components
        return bool(required) and all(self.components.get(name) is True for name in required)

    @property
    def degraded(self) -> bool:
        return self.success and any(accepted is not True for accepted in self.components.values())

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "success": self.success,
            "degraded": self.degraded,
            "components": dict(self.components),
            "required_components": list(self.effective_required_components),
            "error_codes": list(self.error_codes),
        }
