import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"


async def chat_completion(
    system: str,
    user: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.4,
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
            return data["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        logger.error("OpenAI request timed out")
        return "Сервис временно недоступен. Попробуйте позже."
    except httpx.HTTPStatusError as e:
        logger.error("OpenAI HTTP error %s: %s", e.response.status_code, e.response.text[:200])
        return "Ошибка при обращении к сервису. Попробуйте позже."
    except Exception as e:
        logger.exception("Unexpected LLM error: %s", e)
        return "Произошла непредвиденная ошибка. Попробуйте позже."
