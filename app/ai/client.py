import asyncio
import json
from typing import List, Dict, Any, Optional

import anthropic
from app.config import settings
from app.services.session import session_manager

_anthropic_client: Optional[anthropic.AsyncAnthropic] = None

_UA = "sga-notion-agent/1.0"


async def _base_headers() -> Dict[str, str]:
    cfg = await session_manager.get_ai_config()
    return {
        "x-api-key": cfg.get("anthropic_api_key") or settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "user-agent": _UA,
    }


async def _messages_url() -> str:
    cfg = await session_manager.get_ai_config()
    base = (cfg.get("anthropic_base_url") or settings.anthropic_base_url).rstrip("/")
    return base if base.endswith("/v1/messages") else f"{base}/v1/messages"


def _text_from_message(msg: Dict[str, Any]) -> str:
    return "".join(
        b.get("text", "") for b in (msg.get("content") or [])
        if isinstance(b, dict) and b.get("type") == "text"
    )


async def _parse_body(response) -> str:
    """Router SELALU membalas text/event-stream walau stream=false.
    Parse SSE manual: kumpulkan text_delta sampai message_stop."""
    ctype = response.headers.get("content-type", "")
    if "text/event-stream" not in ctype:
        body_bytes = await response.aread()
        if response.status_code >= 400:
            raise RuntimeError(f"upstream {response.status_code}: {body_bytes[:200]!r}")
        return _text_from_message(json.loads(body_bytes))

    text_parts: List[str] = []
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            evt = json.loads(data)
        except json.JSONDecodeError:
            continue
        etype = evt.get("type") or evt.get("event", {}).get("type") if isinstance(evt.get("event"), dict) else evt.get("type")
        delta = evt.get("delta") or {}
        if etype == "content_block_delta" and delta.get("type") == "text_delta":
            text_parts.append(delta.get("text", ""))
        elif etype == "message_stop":
            break
        elif etype == "error":
            raise RuntimeError(f"SSE error: {str(evt)[:200]}")
    return "".join(text_parts)


async def _raw_create(payload: Dict[str, Any]) -> str:
    """POST langsung tanpa SDK: hindari bug parse SSE router."""
    try:
        import httpx2
    except ImportError:
        import httpx as httpx2

    url = await _messages_url()
    headers = await _base_headers()

    async with httpx2.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            url,
            headers=headers,
            json=payload,
        ) as response:
            return await _parse_body(response)


async def create_message(
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    max_tokens: int = 1000,
    model: Optional[str] = None,
) -> str:
    ai_cfg = await session_manager.get_ai_config()
    target_model = model or ai_cfg.get("ai_model") or settings.ai_model

    payload: Dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "max_tokens": max_tokens,
        # ponytail: stream=True WAJIB — mode non-stream router balas content kosong
        # (token reasoning memakan seluruh completion). Upgrade: pindah model tanpa reasoning.
        "stream": True,
    }
    if system:
        payload["system"] = system

    last_exc: Optional[Exception] = RuntimeError("LLM call failed")
    for attempt in range(3):
        try:
            text = await _raw_create(payload)
            if text.strip():
                return text.strip()
            last_exc = RuntimeError("empty completion")
        except Exception as e:  # ponytail: router error bentuknya macam2 (403/5xx/SSE putus); persemp saat stabil
            last_exc = e
        await asyncio.sleep(1.5 * (attempt + 1))
    raise last_exc
