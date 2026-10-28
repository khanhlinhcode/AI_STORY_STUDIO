from __future__ import annotations

import httpx

from studio_api.core.config import get_settings


async def send_telegram(message: str, chat_id: str | None = None) -> bool:
    settings = get_settings()
    if not settings.telegram_bot_token or not (chat_id or settings.telegram_chat_id):
        return False
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id or settings.telegram_chat_id, "text": message},
        )
        response.raise_for_status()
    return True
