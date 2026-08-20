import anthropic
from typing import List, Dict, Any, Optional
from app.config import settings

_anthropic_client: Optional[anthropic.AsyncAnthropic] = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
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

    response = await client.messages.create(**kwargs)
    
    # Text extraction
    text_content = ""
    for block in response.content:
        if block.type == "text":
            text_content += block.text
    return text_content
