"""Telegram Payments: subscription purchase via ЮKassa / Telegram Payments."""

import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message,
    LabeledPrice, PreCheckoutQuery,
)

from app.config import settings
from app.services.database import (
    a_set_subscription as save_subscription,
    a_get_subscription as get_subscription,
    a_get_user_plan as get_user_plan,
    a_is_whitelisted as is_whitelisted,
)
from app.keyboards import kb_payment_plans

logger = logging.getLogger(__name__)

router = Router()

PLAN_INFO = {
    "standard": {
        "title": "FORMA Стандарт",
        "description": (
            "Безлимитные меню, рецепты блюд, "
            "скачивание меню, экспорт истории"
        ),
        "price": settings.STANDARD_PRICE,
        "duration_days": 30,
    },
    "premium": {
        "title": "FORMA Премиум",
        "description": (
            "Всё из Стандарт + анализ фото еды, "
            "персональные рекомендации по фото"
        ),
        "price": settings.PREMIUM_PRICE,
        "duration_days": 30,
    },
}


@router.callback_query(F.data == "pay:choose")
async def choose_plan(cb: CallbackQuery):
    uid = cb.from_user.id

    if await is_whitelisted(uid):
        await cb.answer("Вы VIP — все функции уже доступны!", show_alert=True)
        return

    plan = await get_user_plan(uid)
    if plan != "free":
        sub = await get_subscription(uid)
        exp = sub["expires_at"][:10] if sub and sub.get("expires_at") else "∞"
        await cb.answer(f"У вас тариф «{plan}» до {exp}", show_alert=True)
        return

    if not settings.PAYMENT_PROVIDER_TOKEN:
        await cb.answer(
            "Оплата временно недоступна.\nОбратитесь к @admin",
            show_alert=True,
        )
        return

    await cb.message.answer(
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "   💎 <b>Тарифы FORMA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔹 <b>Стандарт</b> — 299 ₽/мес\n"
        "   • Безлимитные меню на 3 дня\n"
        "   • Рецепты блюд по запросу\n"
        "   • Скачивание меню\n"
        "   • Экспорт истории в Excel\n\n"
        "🔸 <b>Премиум</b> — 499 ₽/мес\n"
        "   • Всё из Стандарт\n"
        "   • Анализ фото еды (AI)\n"
        "   • Персональные рекомендации\n\n"
        "<i>Оплата через Telegram</i>",
        parse_mode="HTML",
        reply_markup=kb_payment_plans(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("pay:plan:"))
async def send_invoice(cb: CallbackQuery):
    plan_key = cb.data.split(":")[-1]
    info = PLAN_INFO.get(plan_key)
    if not info:
        await cb.answer("Неизвестный тариф", show_alert=True)
        return

    if not settings.PAYMENT_PROVIDER_TOKEN:
        await cb.answer("Оплата временно недоступна", show_alert=True)
        return

    prices = [LabeledPrice(label=info["title"], amount=info["price"])]

    await cb.message.answer_invoice(
        title=info["title"],
        description=info["description"],
        payload=f"sub:{plan_key}:30",
        provider_token=settings.PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter=f"forma-{plan_key}",
    )
    await cb.answer()


@router.pre_checkout_query()
async def process_pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)


@router.message(F.successful_payment)
async def process_payment(m: Message):
    payload = m.successful_payment.invoice_payload
    parts = payload.split(":")
    if len(parts) < 3 or parts[0] != "sub":
        logger.warning("Unknown payment payload: %s", payload)
        return

    plan_key = parts[1]
    days = int(parts[2])
    uid = m.from_user.id

    expires = (datetime.now() + timedelta(days=days)).isoformat()
    await save_subscription(uid, plan_key, expires)

    plan_label = "Стандарт" if plan_key == "standard" else "Премиум"
    await m.answer(
        f"🎉 <b>Подписка «{plan_label}» активирована!</b>\n\n"
        f"Действует до: {expires[:10]}\n\n"
        "Спасибо, что выбрали FORMA!\n"
        "Нажмите /start для главного меню",
        parse_mode="HTML",
    )
    logger.info(
        "Payment: user=%s plan=%s amount=%s",
        uid, plan_key, m.successful_payment.total_amount,
    )
