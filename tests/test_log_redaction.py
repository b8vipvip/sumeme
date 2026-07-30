from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REDACTOR_PATH = ROOT / "scripts" / "redact-log-stream.py"
SHOW_LOGS_PATH = ROOT / "scripts" / "show-logs.sh"


def load_redactor():
    spec = importlib.util.spec_from_file_location("sumeme_log_redactor", REDACTOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_redacts_common_credentials_without_removing_context() -> None:
    redactor = load_redactor()
    source = (
        "Authorization: Bearer top.secret.token\n"
        'api_key="abcdefghijk123" password=hunter22 secret:verysecretvalue\n'
        "OPENAI_API_KEY=sk-abcdefghijklmnop\n"
        "postgresql://sumeme:database-password@postgresql:5432/app\n"
        "Cookie: session=private-session-value\n"
    )

    output = "".join(redactor.redact_stream(source.splitlines(keepends=True)))

    for secret in (
        "top.secret.token",
        "abcdefghijk123",
        "hunter22",
        "verysecretvalue",
        "abcdefghijklmnop",
        "database-password",
        "private-session-value",
    ):
        assert secret not in output
    assert "Authorization: Bearer [REDACTED]" in output
    assert "postgresql://sumeme:[REDACTED]@postgresql:5432/app" in output
    assert "Cookie: [REDACTED]" in output


def test_collapses_private_key_block() -> None:
    redactor = load_redactor()
    source = (
        "before\n"
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "secret-private-key-material\n"
        "-----END OPENSSH PRIVATE KEY-----\n"
        "after\n"
    )

    output = "".join(redactor.redact_stream(source.splitlines(keepends=True)))

    assert "before" in output
    assert "after" in output
    assert "secret-private-key-material" not in output
    assert output.count("[REDACTED] PRIVATE KEY BLOCK") == 1


def test_show_logs_uses_allow_list_and_python_redactor() -> None:
    script = SHOW_LOGS_PATH.read_text(encoding="utf-8")

    assert "python3 scripts/redact-log-stream.py" in script
    assert "ai-provider-proxy" in script
    assert "LINES < 1 || LINES > 1000" in script
    assert "sed -E" not in script
