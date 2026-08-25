import asyncio
import anthropic
from typing import List, Dict, Any, Optional
from app.config import settings

_anthropic_client: Optional[anthropic.AsyncAnthropic] = None


def _make_http_client():
    """httpx client yang menyamarkan header SDK (9router WAF memblok
    user-agent/x-stainless khas Anthropic SDK dengan 403)."""
    try:
        import httpx2
    except ImportError:
        import httpx as httpx2

    async def _scrub_sdk_headers(request):
        request.headers["user-agent"] = "sga-notion-agent/1.0"
        for h in [k for k in request.headers.keys() if k.lower().startswith("x-stainless")]:
            del request.headers[h]

    return httpx2.AsyncClient(timeout=120.0, event_hooks={"request": [_scrub_sdk_headers]})


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
            http_client=_make_http_client(),
        )
    return _anthropic_client


async def create_message(
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    max_tokens: int = 1000,
    model: Optional[str] = None,
) -> str:
    client = get_anthropic_client()
    target_model = model or settings.ai_model

    kwargs: Dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if system:
        kwargs["system"] = system

    # 9router selalu membalas text/event-stream meski non-streaming diminta;
    # gunakan mode streaming agar SDK mem-parse SSE dengan benar.
    last_exc: Optional[Exception] = RuntimeError("LLM call failed")
    for attempt in range(3):
        try:
            async with client.messages.stream(**kwargs) as stream:
                msg = await stream.get_final_message()
            text = "".join(b.text for b in (msg.content or []) if getattr(b, "type", "") == "text")
            # 9router kadang menutup stream prematur: tanpa stop_reason & teks terpotong
            if not text and getattr(msg, "stop_reason", "end_turn") != "end_turn":
                last_exc = RuntimeError(f"stream truncated (stop_reason={msg.stop_reason})")
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            return text
        except (anthropic.PermissionDeniedError, anthropic.InternalServerError, anthropic.APIConnectionError) as e:
            last_exc = e
            await asyncio.sleep(2 * (attempt + 1))
    raise last_exc
