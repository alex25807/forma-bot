import base64
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
}


async def chat_completion(
    system: str,
    user: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.4,
    user_id: int = 0,
    action: str = "chat",
) -> str:
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(OPENAI_URL, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

            content = data["choices"][0]["message"]["content"]

            usage = data.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)

            pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
            cost = tokens_in * pricing["input"] + tokens_out * pricing["output"]

            if user_id:
                try:
                    from app.services.database import a_log_api_usage
                    await a_log_api_usage(user_id, action, model, tokens_in, tokens_out, cost)
                except Exception:
                    logger.warning("Failed to log API usage", exc_info=True)

            return content
    except httpx.TimeoutException:
        logger.error("OpenAI request timed out")
        return "Сервис временно недоступен. Попробуйте позже."
    except httpx.HTTPStatusError as e:
        logger.error("OpenAI HTTP error %s: %s", e.response.status_code, e.response.text[:200])
        return "Ошибка при обращении к сервису. Попробуйте позже."
    except Exception as e:
        logger.exception("Unexpected LLM error: %s", e)
        return "Произошла непредвиденная ошибка. Попробуйте позже."


async def vision_completion(
    system: str,
    image_bytes: bytes,
    user_text: str = "",
    model: str = "gpt-4o",
    user_id: int = 0,
    action: str = "photo_analysis",
) -> str:
    """Send an image to GPT-4o vision for analysis."""
    b64 = base64.b64encode(image_bytes).decode()
    user_content = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}},
    ]
    if user_text:
        user_content.insert(0, {"type": "text", "text": user_text})

    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
    payload = {
        "model": model,
        "temperature": 0.3,
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(OPENAI_URL, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

            content = data["choices"][0]["message"]["content"]

            usage = data.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)

            pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
            cost = tokens_in * pricing["input"] + tokens_out * pricing["output"]

            if user_id:
                try:
                    from app.services.database import a_log_api_usage
                    await a_log_api_usage(user_id, action, model, tokens_in, tokens_out, cost)
                except Exception:
                    logger.warning("Failed to log API usage", exc_info=True)

            return content
    except httpx.TimeoutException:
        logger.error("Vision request timed out")
        return "Сервис временно недоступен. Попробуйте позже."
    except httpx.HTTPStatusError as e:
        logger.error("Vision HTTP error %s: %s", e.response.status_code, e.response.text[:200])
        return "Ошибка при обращении к сервису. Попробуйте позже."
    except Exception as e:
        logger.exception("Unexpected vision error: %s", e)
        return "Произошла непредвиденная ошибка. Попробуйте позже."
