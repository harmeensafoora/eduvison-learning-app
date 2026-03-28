import json
from typing import Any

import httpx

from .config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
)


def _is_configured() -> bool:
    return bool(AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT and AZURE_OPENAI_API_VERSION)


def _chat_completions_url() -> str:
    endpoint = AZURE_OPENAI_ENDPOINT.rstrip("/")
    return f"{endpoint}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"


def _extract_text_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = (choices[0] or {}).get("message") or {}
    return (message.get("content") or "").strip()


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()
    return t


async def azure_text(system: str, prompt: str, fallback: str) -> str:
    if not _is_configured():
        return fallback

    headers = {"api-key": AZURE_OPENAI_API_KEY, "content-type": "application/json"}
    body = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1800,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            res = await client.post(_chat_completions_url(), headers=headers, json=body)
            res.raise_for_status()
            data = res.json()
            text = _extract_text_content(data)
            return text or fallback
    except Exception:
        return fallback


async def azure_json(system: str, prompt: str, fallback: dict[str, Any]) -> dict[str, Any]:
    if not _is_configured():
        return fallback

    headers = {"api-key": AZURE_OPENAI_API_KEY, "content-type": "application/json"}
    body = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1200,
        "temperature": 0.2,
        # Ask the model to return strict JSON (supported by modern Azure OpenAI chat models).
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            res = await client.post(_chat_completions_url(), headers=headers, json=body)
            res.raise_for_status()
            data = res.json()
            text = _strip_code_fences(_extract_text_content(data))
            return json.loads(text)
    except Exception:
        return fallback
