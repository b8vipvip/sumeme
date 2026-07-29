from __future__ import annotations

import json
import re
from typing import Any


_SAFE_ID = re.compile(r"[^a-zA-Z0-9_.-]+")


def safe_id(value: str, fallback: str = "default") -> str:
    value = _SAFE_ID.sub("_", (value or "").strip()).strip("_.-")
    return value[:96] or fallback


def flatten_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (int, float, bool)):
        return str(content)
    if isinstance(content, dict):
        return _flatten_part(content)
    if isinstance(content, list):
        parts = [_flatten_part(item) for item in content]
        return "\n".join(part for part in parts if part)
    return json.dumps(content, ensure_ascii=False, default=str)


def _flatten_part(part: Any) -> str:
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return flatten_content(part)

    part_type = str(part.get("type") or "")
    if part_type in {"text", "input_text", "output_text"}:
        return str(part.get("text") or "")
    if part_type in {"image_url", "input_image"}:
        image = part.get("image_url") or part.get("url") or ""
        if isinstance(image, dict):
            image = image.get("url") or ""
        return f"[图片附件: {abbreviate_secret_url(str(image))}]"
    if part_type in {"input_audio", "audio"}:
        return "[音频附件]"
    if part_type in {"file", "input_file"}:
        name = part.get("filename") or part.get("name") or part.get("file_id") or "未命名文件"
        mime = part.get("mime_type") or part.get("media_type") or ""
        return f"[文件附件: {name}{' / ' + str(mime) if mime else ''}]"

    text = part.get("text")
    if text:
        return str(text)
    return json.dumps(part, ensure_ascii=False, default=str)


def abbreviate_secret_url(url: str) -> str:
    if not url:
        return "unknown"
    if url.startswith("data:"):
        media = url.split(";", 1)[0]
        return f"{media};base64,<omitted>"
    return url[:500]


def latest_user_message(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message
    return None


def assistant_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return flatten_content(message.get("content"))
