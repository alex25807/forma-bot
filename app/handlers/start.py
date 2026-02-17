from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from app.keyboards import kb_start
from app.services.database import (
    add_subscriber, is_subscribed, get_profile,
    has_premium_access, is_whitelisted, get_menu_count,
    days_since_last_menu,
)

router = Router()

MENU_PERIOD = 3


def _kb(user_id: int):
    sub = is_subscribed(user_id)
    profile = get_profile(user_id)
    has_profile = profile is not None
    days = days_since_last_menu(user_id)
    can_renew = (
        has_profile
        and (sub or is_whitelisted(user_id))
        and days is not None
        and days >= MENU_PERIOD
    )
    return kb_start(sub, has_profile, can_renew)


@router.message(CommandStart())
async def start(m: Message):
    text = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "       <b>F O R M A</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Спокойный сервис по питанию.\n"
        "Помогает изменить форму тела\n"
        "без крайностей и чувства вины.\n\n"
        "Выберите действие 👇"
    )
    await m.answer(text, parse_mode="HTML", reply_markup=_kb(m.from_user.id))


@router.callback_query(F.data == "main:info")
async def how_it_works(cb: CallbackQuery):
    text = (
        "📌 <b>Как работает FORMA</b>\n\n"
        "  📊  Рассчитываем ваш ориентир\n"
        "        по калориям и БЖУ\n\n"
        "  ⚕️  Учитываем ограничения\n"
        "        по здоровью\n\n"
        "  📋  Составляем меню на 3 дня\n"
        "        с точными граммовками\n\n"
        "  💬  Поддерживаем каждый день:\n"
        "        утренний настрой + разбор вечером\n\n"
        "  ⚖️  Отслеживаем вес\n"
        "        и показываем динамику\n\n"
        "  📈  Ведём статистику прогресса:\n"
        "        серии чек-инов, отклонения, путь к цели\n\n"
        "  📊  Красочный график веса\n"
        "        наглядная динамика по дням\n\n"
        "  📥  Экспорт истории в Excel\n"
        "        для платной подписки / VIP\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>Уровни активности</b>\n\n"
        "  🚶 <b>Лёгкая</b> — прогулки 2-3 р/нед,\n"
        "        лёгкая работа по дому\n\n"
        "  🏃 <b>Умеренная</b> — тренировки\n"
        "        3-4 р/нед или активная работа\n\n"
        "  💪 <b>Высокая</b> — тренировки\n"
        "        почти каждый день / физ. труд\n\n"
        "  🔥 <b>Очень высокая</b> — проф. спорт\n"
        "        или тяжёлый физический труд\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Без жёстких диет · Без срывов\n"
        "Без чувства вины</i>"
    )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=_kb(cb.from_user.id))
    await cb.answer()


@router.callback_query(F.data == "main:subscribe")
async def subscribe(cb: CallbackQuery):
    is_new = add_subscriber(
        user_id=cb.from_user.id,
        username=cb.from_user.username,
        first_name=cb.from_user.first_name,
    )

    if is_new:
        text = (
            "🎉🎊🎉🎊🎉🎊🎉🎊🎉🎊\n\n"
            "🥳  <b>Поздравляю!</b>\n\n"
            "✨ <b>Вы подписались на FORMA!</b>\n\n"
            "🎉🎊🎉🎊🎉🎊🎉🎊🎉🎊\n\n"
            "Спасибо за доверие.\n"
            "Пользуйтесь, пробуйте, оценивайте.\n\n"
            "Если FORMA окажется полезной —\n"
            "вы сможете оформить полный доступ\n"
            "и продолжить путь к своей цели 💪\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Выберите действие 👇"
        )
    else:
        text = (
            "Вы уже подписаны ✓\n\n"
            "Выберите действие 👇"
        )

    profile = get_profile(cb.from_user.id)
    has_profile = profile is not None
    days = days_since_last_menu(cb.from_user.id)
    can_renew = has_profile and days is not None and days >= MENU_PERIOD
    await cb.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb_start(subscribed=True, has_profile=has_profile, can_renew=can_renew),
    )
    await cb.answer()


@router.callback_query(F.data == "main:subscribed_info")
async def subscribed_info(cb: CallbackQuery):
    text = (
        "✅ <b>Вы подписаны на FORMA</b>\n\n"
        "Рады, что вы с нами! 🙌\n\n"
        "Если сервис оказался полезным\n"
        "и вы хотите продолжить путь к цели —\n"
        "у нас есть хорошая новость:\n\n"
        "С <b>полным доступом</b> вы получите:\n\n"
        "  📋  Новые меню каждые 3 дня\n"
        "  📊  Графики и экспорт истории\n"
        "  💬  Ежедневное сопровождение\n"
        "  ⚖️  Отслеживание прогресса\n"
        "  🎯  Путь до вашего результата\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Для оформления напишите нам —\n"
        "подберём удобный вариант.</i>"
    )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=_kb(cb.from_user.id))
    await cb.answer()
