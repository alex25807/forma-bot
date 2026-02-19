"""Middleware to enforce consent before any interaction."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update

from app.services.database import a_has_consent as has_consent
from app.keyboards import kb_consent

CONSENT_TEXT = (
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "       <b>F O R M A</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Для продолжения необходимо\n"
    "принять условия обработки\n"
    "персональных данных.\n\n"
    "Нажмите /start"
)

ALLOWED_CALLBACKS = {"consent:accept", "consent:policy"}
ALLOWED_COMMANDS = {"/start", "/deletedata", "/myid"}


class ConsentMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user = event.from_user
        if not user:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            if event.data in ALLOWED_CALLBACKS:
                return await handler(event, data)

        if isinstance(event, Message) and event.text:
            cmd = event.text.split()[0].lower()
            if cmd in ALLOWED_COMMANDS:
                return await handler(event, data)

        if await has_consent(user.id):
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer(
                "Необходимо принять условия.\nНажмите /start",
                show_alert=True,
            )
            return
        elif isinstance(event, Message):
            await event.answer(
                CONSENT_TEXT,
                parse_mode="HTML",
                reply_markup=kb_consent(),
            )
            return
