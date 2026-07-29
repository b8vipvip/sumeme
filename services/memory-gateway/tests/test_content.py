from app.content import (
    abbreviate_secret_url,
    flatten_content,
    latest_user_message,
    safe_id,
)


def test_flatten_multimodal_content():
    value = flatten_content(
        [
            {"type": "text", "text": "你好"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            {"type": "file", "filename": "report.pdf", "mime_type": "application/pdf"},
        ]
    )
    assert "你好" in value
    assert "data:image/png;base64,<omitted>" in value
    assert "report.pdf" in value


def test_latest_user_message():
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "last"},
    ]
    assert latest_user_message(messages)["content"] == "last"


def test_safe_id():
    assert safe_id(" user/../../x ") == "user_.._.._x"


def test_abbreviate_url():
    assert abbreviate_secret_url("data:image/jpeg;base64,secret") == "data:image/jpeg;base64,<omitted>"