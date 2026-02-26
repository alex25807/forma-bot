from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from app.config import settings
from app.keyboards import kb_start, kb_consent, kb_quick_start
from app.services.database import (
    a_add_subscriber as add_subscriber,
    a_is_subscribed as is_subscribed,
    a_get_profile as get_profile,
    a_is_whitelisted as is_whitelisted,
    a_get_menu_count as get_menu_count,
    a_days_since_last_menu as days_since_last_menu,
    a_has_consent as has_consent,
    a_save_consent as save_consent,
    a_get_user_plan as get_user_plan,
    a_log_growth_event as log_growth_event,
    a_get_growth_funnel as get_growth_funnel,
)

router = Router()

MENU_PERIOD = 3


async def _kb(user_id: int):
    sub = await is_subscribed(user_id)
    profile = await get_profile(user_id)
    has_profile = profile is not None
    plan = await get_user_plan(user_id)
    days = await days_since_last_menu(user_id)
    can_renew = (
        has_profile
        and (sub or plan != "free")
        and days is not None
        and days >= MENU_PERIOD
    )
    return kb_start(sub, has_profile, can_renew, plan=plan)


WELCOME_TEXT = (
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "       <b>F O R M A</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Спокойный сервис по питанию.\n"
    "Помогает изменить форму тела\n"
    "без крайностей и чувства вины.\n\n"
    "Выберите действие 👇"
)

CONSENT_TEXT = (
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "       <b>F O R M A</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Добро пожаловать! 👋\n\n"
    "Для работы сервиса нам понадобятся\n"
    "некоторые ваши данные:\n"
    "пол, возраст, рост, вес,\n"
    "ограничения по здоровью.\n\n"
    "Все данные хранятся конфиденциально\n"
    "и используются <b>только</b> для\n"
    "персонализации вашего питания.\n\n"
    "Вы можете удалить свои данные\n"
    "в любой момент командой /deletedata\n\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "<i>Нажмите «Принимаю», чтобы начать.</i>"
)

PRIVACY_POLICY = (
    "📄 <b>Политика конфиденциальности FORMA</b>\n\n"
    "━━━━━━━━━━━━━━━━━━━━━\n\n"
    "<b>1. Какие данные мы собираем</b>\n"
    "  • Telegram ID, имя пользователя\n"
    "  • Пол, возраст, рост, вес\n"
    "  • Ограничения по здоровью\n"
    "  • Предпочтения по питанию\n"
    "  • История веса и дневник питания\n"
    "  • Отзывы\n\n"
    "<b>2. Зачем мы их собираем</b>\n"
    "  • Расчёт персонального ориентира КБЖУ\n"
    "  • Составление индивидуального меню\n"
    "  • Отслеживание прогресса\n"
    "  • Ежедневная поддержка\n\n"
    "<b>3. Кому мы передаём данные</b>\n"
    "  • OpenAI API — для генерации меню\n"
    "    и анализа питания (передаются\n"
    "    обезличенные параметры: КБЖУ,\n"
    "    ограничения, предпочтения —\n"
    "    без привязки к личности)\n"
    "  • Третьим лицам данные\n"
    "    <b>не передаются</b>\n\n"
    "<b>4. Как мы храним данные</b>\n"
    "  • База данных на защищённом сервере\n"
    "  • Доступ только у администратора\n\n"
    "<b>5. Ваши права</b>\n"
    "  • Запросить удаление всех данных:\n"
    "    команда /deletedata\n"
    "  • Отказаться от использования\n"
    "    в любой момент\n\n"
    "<b>6. Специальные категории</b>\n"
    "  Данные о здоровье (ограничения)\n"
    "  обрабатываются с вашего явного\n"
    "  согласия (ст. 10 152-ФЗ).\n\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "<i>Оператор: сервис FORMA\n"
    "Основание: согласие субъекта (ст. 6, 9 152-ФЗ)</i>"
)


@router.message(CommandStart())
async def start(m: Message):
    await log_growth_event(m.from_user.id, "start", {"source": "command"})
    if not await has_consent(m.from_user.id):
        await m.answer("⬇️ Быстрый доступ к меню включён.", reply_markup=kb_quick_start())
        await m.answer(CONSENT_TEXT, parse_mode="HTML", reply_markup=kb_consent())
        return
    await m.answer("⬇️ Кнопка «🏠 Старт» доступна внизу.", reply_markup=kb_quick_start())
    await m.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=await _kb(m.from_user.id))


@router.message(F.text == "🏠 Старт")
async def quick_start(m: Message):
    await log_growth_event(m.from_user.id, "start", {"source": "quick_button"})
    if not await has_consent(m.from_user.id):
        await m.answer(CONSENT_TEXT, parse_mode="HTML", reply_markup=kb_consent())
        return
    await m.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=await _kb(m.from_user.id))


@router.callback_query(F.data == "consent:policy")
async def show_policy(cb: CallbackQuery):
    await cb.message.edit_text(PRIVACY_POLICY, parse_mode="HTML", reply_markup=kb_consent())
    await cb.answer()


@router.callback_query(F.data == "consent:accept")
async def accept_consent(cb: CallbackQuery):
    await save_consent(cb.from_user.id)
    await cb.message.edit_text("✅ Спасибо! Согласие принято.")
    await cb.message.answer("⬇️ Кнопка «🏠 Старт» доступна внизу.", reply_markup=kb_quick_start())
    await cb.message.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=await _kb(cb.from_user.id))
    await cb.answer()


@router.callback_query(F.data == "main:info")
async def how_it_works(cb: CallbackQuery):
    await log_growth_event(cb.from_user.id, "info_open")
    text = (
        "📌 <b>Как работает FORMA</b>\n\n"
        "  📊  Рассчитываем ваш ориентир\n"
        "        по калориям и БЖУ\n\n"
        "  ⚕️  Учитываем ограничения\n"
        "        по здоровью\n\n"
        "  📋  Составляем меню на 3 дня\n"
        "        с точными граммовками\n\n"
        "  👨‍🍳  Рецепты блюд из меню\n"
        "        пошаговые, с граммовками\n\n"
        "  💬  Поддерживаем каждый день:\n"
        "        утренний настрой + разбор вечером\n\n"
        "  ⚖️  Отслеживаем вес\n"
        "        и показываем динамику\n\n"
        "  📈  Ведём статистику прогресса:\n"
        "        серии чек-инов, отклонения, путь к цели\n\n"
        "  📊  Красочный график веса\n"
        "        наглядная динамика по дням\n\n"
        "  🏃  Мягкий фитнес (Стандарт+)\n"
        "        упражнения на 5-10 мин с учётом\n"
        "        здоровья + трекер выполнения\n\n"
        "  📷  Анализ фото еды (Премиум)\n"
        "        AI считает КБЖУ по фотографии\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 <b>Тарифы</b>\n\n"
        "🆓 <b>Бесплатно (0 ₽)</b>\n"
        "  ✅ Расчёт КБЖУ\n"
        "  ✅ 1 меню на 3 дня\n"
        "  ✅ Ежедневная поддержка\n"
        "  ✅ Трекер веса + график\n"
        "  ✅ Статистика прогресса\n"
        "  ❌ Обновление меню\n"
        "  ❌ Рецепты блюд\n"
        "  ❌ Скачивание меню\n"
        "  ❌ Фитнес-модуль\n"
        "  ❌ Анализ фото еды\n\n"
        "🔹 <b>Стандарт (299 ₽/мес)</b>\n"
        "  ✅ Всё из бесплатного\n"
        "  ✅ Безлимитные меню на 3 дня\n"
        "  ✅ Выбор кухни (7+ вариантов)\n"
        "  ✅ Рецепты блюд с граммовками\n"
        "  ✅ Скачивание меню и рецептов\n"
        "  ✅ Фитнес-модуль (5-10 мин/день)\n"
        "  ✅ Экспорт истории в Excel\n"
        "  ❌ Анализ фото еды\n\n"
        "🔸 <b>Премиум (499 ₽/мес)</b>\n"
        "  ✅ Всё из Стандарт\n"
        "  ✅ Анализ фото еды через AI\n"
        "  ✅ Подсчёт КБЖУ по фото\n"
        "  ✅ Персональные рекомендации\n"
        "  ✅ Приоритетная поддержка\n\n"
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
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=await _kb(cb.from_user.id))
    await cb.answer()


CONFETTI_EFFECT = "5046509860389126442"

@router.callback_query(F.data == "main:subscribe")
async def subscribe(cb: CallbackQuery):
    is_new = await add_subscriber(
        cb.from_user.id,
        cb.from_user.username,
        cb.from_user.first_name,
    )

    profile = await get_profile(cb.from_user.id)
    has_profile = profile is not None
    plan = await get_user_plan(cb.from_user.id)
    days = await days_since_last_menu(cb.from_user.id)
    can_renew = has_profile and days is not None and days >= MENU_PERIOD
    kb = kb_start(subscribed=True, has_profile=has_profile, can_renew=can_renew, plan=plan)

    if is_new:
        await cb.message.edit_text("✨ Оформляем подписку...")

        try:
            await cb.message.answer(
                "🎉🎊🎉🎊🎉🎊🎉🎊🎉🎊\n\n"
                "🥳  <b>Поздравляю!</b>\n\n"
                "✨ <b>Вы подписались на FORMA!</b>\n\n"
                "🎉🎊🎉🎊🎉🎊🎉🎊🎉🎊",
                parse_mode="HTML",
                message_effect_id=CONFETTI_EFFECT,
            )
        except Exception:
            await cb.message.answer(
                "🎉🎊🎉🎊🎉🎊🎉🎊🎉🎊\n\n"
                "🥳  <b>Поздравляю!</b>\n\n"
                "✨ <b>Вы подписались на FORMA!</b>\n\n"
                "🎉🎊🎉🎊🎉🎊🎉🎊🎉🎊",
                parse_mode="HTML",
            )

        await cb.message.answer(
            "Спасибо за доверие! 🙌\n"
            "Пользуйтесь, пробуйте, оценивайте.\n\n"
            "Если FORMA окажется полезной —\n"
            "вы сможете оформить полный доступ\n"
            "и продолжить путь к своей цели 💪\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Выберите действие 👇",
            parse_mode="HTML",
            reply_markup=kb,
        )
    else:
        await cb.message.edit_text(
            "Вы уже подписаны ✓\n\n"
            "Выберите действие 👇",
            reply_markup=kb,
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
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=await _kb(cb.from_user.id))
    await cb.answer()


@router.message(F.text.regexp(r"^/growth(@\w+)?$"))
async def growth_fallback_in_start(m: Message):
    """Safety fallback: serve growth even if admin router command filter misses."""
    is_admin = bool(settings.ADMIN_ID and m.from_user.id == settings.ADMIN_ID)
    is_vip = await is_whitelisted(m.from_user.id)
    if not (is_admin or is_vip):
        await m.answer("⛔ Эта команда доступна только администратору.")
        return

    try:
        f = await get_growth_funnel(7)
    except Exception:
        await m.answer("⚠️ Growth-отчёт временно недоступен. Попробуйте позже.")
        return

    c = f.get("counts", {})
    start_cnt = c.get("start", 0)
    calc_cnt = c.get("calc_done", 0)
    menu_cnt = c.get("menu_done", 0)
    pay_open_cnt = c.get("pay_open", 0)
    invoice_cnt = c.get("invoice_open", 0)
    paid_cnt = c.get("pay_success", 0)

    calc_cr = (calc_cnt / start_cnt * 100) if start_cnt else 0.0
    menu_cr = (menu_cnt / calc_cnt * 100) if calc_cnt else 0.0
    paid_cr = (paid_cnt / pay_open_cnt * 100) if pay_open_cnt else 0.0

    text = (
        "📈 <b>Growth Funnel (7 дней)</b>\n\n"
        f"start: <b>{start_cnt}</b>\n"
        f"calc_done: <b>{calc_cnt}</b> ({calc_cr:.1f}%)\n"
        f"menu_done: <b>{menu_cnt}</b> ({menu_cr:.1f}%)\n"
        f"pay_open: <b>{pay_open_cnt}</b>\n"
        f"invoice_open: <b>{invoice_cnt}</b>\n"
        f"pay_success: <b>{paid_cnt}</b> ({paid_cr:.1f}%)\n\n"
        f"recipe_open: {c.get('recipe_open', 0)}\n"
        f"download_click: {c.get('download_click', 0)}\n"
    )
    await m.answer(text, parse_mode="HTML")
