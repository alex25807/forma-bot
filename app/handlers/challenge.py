"""D1-D3 onboarding challenge flow with soft upsell."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.keyboards import kb_start, kb_gender
from app.states import CalcForm, ChallengeForm
from app.services.database import (
    a_is_subscribed as is_subscribed,
    a_get_profile as get_profile,
    a_get_user_plan as get_user_plan,
    a_days_since_last_menu as days_since_last_menu,
    a_is_newbie_mode as is_newbie_mode,
    a_has_standard_access as has_standard_access,
    a_has_premium_access as has_premium_access,
    a_get_challenge_state as get_challenge_state,
    a_set_challenge_step as set_challenge_step,
    a_reset_challenge as reset_challenge,
    a_log_growth_event as log_growth_event,
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
    newbie = await is_newbie_mode(user_id)
    return kb_start(sub, has_profile, can_renew, plan=plan, newbie_mode=newbie)


def _step_kb(step: str, uid: int, standard: bool = False, premium: bool = False):
    if step == "d1_morning":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, поехали", callback_data="ch:d1:go")],
            [InlineKeyboardButton(text="👀 Посмотреть, что умеет FORMA", callback_data="main:info")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ])
    if step == "d1_evening":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌙 Пройти вечерний чек-ин", callback_data="ch:d1e:start")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ])
    if step == "d2_morning":
        rows = [
            [InlineKeyboardButton(text="⚖️ Обновить вес", callback_data="main:weight")],
            [InlineKeyboardButton(text="✅ Утро D2 отмечено", callback_data="ch:d2m:done")],
        ]
        if standard:
            rows.append([InlineKeyboardButton(text="🏃 Показать упражнения", callback_data="main:fitness")])
        rows.append([InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")])
        return InlineKeyboardMarkup(inline_keyboard=rows)
    if step == "d2_evening":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌙 Пройти вечерний чек-ин", callback_data="ch:d2e:start")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ])
    if step == "d3_morning":
        rows = [
            [InlineKeyboardButton(text="⚖️ Обновить вес", callback_data="main:weight")],
        ]
        if premium:
            rows.append([InlineKeyboardButton(text="📷 Отправить фото еды", callback_data="main:photo")])
        rows.append([InlineKeyboardButton(text="✅ Утро D3 отмечено", callback_data="ch:d3m:done")])
        rows.append([InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")])
        return InlineKeyboardMarkup(inline_keyboard=rows)
    if step == "d3_evening":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏁 Завершить челлендж", callback_data="ch:d3e:start")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Пройти челлендж заново", callback_data="ch:restart")],
        [InlineKeyboardButton(text="💎 Тарифы", callback_data="pay:choose")],
        [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
    ])


async def _render_step(msg: Message, uid: int, step: str, edit: bool = True):
    standard = await has_standard_access(uid)
    premium = await has_premium_access(uid)
    if step == "d1_morning":
        text = (
            "🚀 <b>День 1 / утро</b>\n\n"
            "Привет! Это FORMA — твой бот-нутрициолог 👋\n"
            "Стартуем бесплатный 3-дневный мини-челлендж:\n"
            "мягкий заход в снижение веса без жёстких диет.\n\n"
            "Сегодня ты:\n"
            "• узнаешь свой ориентир КБЖУ\n"
            "• получишь меню на 3 дня\n"
            "• сможешь отметить стартовый вес\n\n"
            "Достаточно быть чуть лучше, чем вчера."
        )
    elif step == "d1_evening":
        text = (
            "🌙 <b>День 1 / вечер</b>\n\n"
            "Подведём итог первого дня.\n"
            "Короткий честный чек-ин даст понятный фокус на завтра."
        )
    elif step == "d2_morning":
        text = (
            "🌞 <b>День 2 / утро</b>\n\n"
            "Отлично, продолжаем.\n"
            "Взвесься и отправь вес, чтобы обновить динамику.\n"
            "Затем отметь утро D2 и двигаемся дальше."
        )
        if standard:
            text += "\n\nУ тебя доступен фитнес-модуль 5-10 минут — можно подключить сегодня."
    elif step == "d2_evening":
        text = (
            "🌙 <b>День 2 / вечер</b>\n\n"
            "Сделаем короткий разбор:\n"
            "что было проще/сложнее и где главный барьер."
        )
    elif step == "d3_morning":
        text = (
            "🎯 <b>День 3 / утро</b>\n\n"
            "Финальный день челленджа.\n"
            "Обнови вес и закрепи ритм: план, вода, спокойный режим."
        )
        if premium:
            text += "\n\nМожно отправить фото еды — получишь оценку КБЖУ по фото."
    elif step == "d3_evening":
        text = (
            "🎉 <b>День 3 / вечер</b>\n\n"
            "Финишная прямая. Осталось подвести итог\n"
            "и выбрать формат продолжения."
        )
    else:
        text = (
            "✅ <b>Мини-челлендж завершён</b>\n\n"
            "Ты уже сделал(а) важный шаг: зафиксировал(а) ориентиры,\n"
            "прошёл(шла) цикл и укрепил(а) привычку.\n\n"
            "Можно пройти цикл ещё раз или перейти к тарифам."
        )

    if edit:
        await msg.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=_step_kb(step, uid, standard=standard, premium=premium),
        )
    else:
        await msg.answer(
            text,
            parse_mode="HTML",
            reply_markup=_step_kb(step, uid, standard=standard, premium=premium),
        )


@router.callback_query(F.data == "main:challenge")
async def open_challenge(cb: CallbackQuery):
    state = await get_challenge_state(cb.from_user.id)
    if not state:
        await reset_challenge(cb.from_user.id)
        await log_growth_event(cb.from_user.id, "challenge_started", {"entry": "menu"})
        step = "d1_morning"
    else:
        step = state.get("step", "d1_morning")
    await _render_step(cb.message, cb.from_user.id, step, edit=True)
    await cb.answer()


@router.callback_query(F.data == "ch:restart")
async def restart_challenge(cb: CallbackQuery):
    await reset_challenge(cb.from_user.id)
    await log_growth_event(cb.from_user.id, "challenge_restarted")
    await _render_step(cb.message, cb.from_user.id, "d1_morning", edit=True)
    await cb.answer()


@router.callback_query(F.data == "ch:d1:go")
async def d1_go(cb: CallbackQuery, state: FSMContext):
    await set_challenge_step(cb.from_user.id, "d1_evening", active=True)
    await log_growth_event(cb.from_user.id, "challenge_d1_morning_done")
    await state.set_state(CalcForm.gender)
    await cb.message.edit_text(
        "📊 <b>Поехали!</b>\n\n"
        "Сейчас быстро соберём анкету.\n"
        "Укажи ваш пол:",
        parse_mode="HTML",
        reply_markup=kb_gender(),
    )
    await cb.answer()


@router.callback_query(F.data == "ch:d1e:start")
async def d1_evening_start(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="😊 8-10", callback_data="ch:d1e:s:high"),
            InlineKeyboardButton(text="🙂 5-7", callback_data="ch:d1e:s:mid"),
            InlineKeyboardButton(text="😕 0-4", callback_data="ch:d1e:s:low"),
        ],
    ])
    await cb.message.edit_text(
        "Насколько получилось следовать меню сегодня?\n"
        "<i>Выбери оценку по шкале 0-10.</i>",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ch:d1e:s:"))
async def d1_evening_score(cb: CallbackQuery):
    score = cb.data.rsplit(":", 1)[-1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data=f"ch:d1e:n:{score}:y"),
            InlineKeyboardButton(text="Нет", callback_data=f"ch:d1e:n:{score}:n"),
        ],
    ])
    await cb.message.edit_text(
        "Были перекусы вне плана?",
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ch:d1e:n:"))
async def d1_evening_snacks(cb: CallbackQuery):
    _, _, _, score, snacks = cb.data.split(":")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data=f"ch:d1e:w:{score}:{snacks}:y"),
            InlineKeyboardButton(text="Нет", callback_data=f"ch:d1e:w:{score}:{snacks}:n"),
        ],
    ])
    await cb.message.edit_text(
        "Удалось держать воду примерно на рекомендованном уровне?",
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ch:d1e:w:"))
async def d1_evening_finish(cb: CallbackQuery):
    _, _, _, score, snacks, water = cb.data.split(":")
    strengths = []
    if score == "high":
        strengths.append("держали меню большую часть дня")
    elif score == "mid":
        strengths.append("сохранили хороший базовый ритм")
    else:
        strengths.append("честно зафиксировали реальную картину дня")
    if snacks == "n":
        strengths.append("обошлись без лишних перекусов")
    if water == "y":
        strengths.append("удержали фокус на воде")
    while len(strengths) < 2:
        strengths.append("не прервали работу с планом")

    if snacks == "y":
        focus = "сократить перекусы между приёмами пищи"
    elif water == "n":
        focus = "добрать воду до ориентира"
    elif score == "low":
        focus = "чуть ближе держаться меню завтра"
    else:
        focus = "повторить текущий ритм и закрепить его"

    await set_challenge_step(cb.from_user.id, "d2_morning", active=True)
    await log_growth_event(
        cb.from_user.id,
        "challenge_d1_evening_done",
        {"score": score, "snacks": snacks, "water": water},
    )
    await cb.message.edit_text(
        "Класс, спасибо за честность 🙌\n\n"
        f"Что уже хорошо: {strengths[0]}, {strengths[1]}.\n"
        f"Фокус на завтра: {focus}.\n\n"
        "Переходим к Дню 2 утром.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Ок, идём дальше", callback_data="main:challenge")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ]),
    )
    await cb.answer()


@router.callback_query(F.data == "ch:d2m:done")
async def d2_morning_done(cb: CallbackQuery):
    await set_challenge_step(cb.from_user.id, "d2_evening", active=True)
    await log_growth_event(cb.from_user.id, "challenge_d2_morning_done")
    await cb.message.edit_text(
        "✅ Утро Дня 2 отмечено.\n"
        "К вечеру сделаем короткий разбор и перейдём к Дню 3.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть вечер D2", callback_data="main:challenge")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ]),
    )
    await cb.answer()


@router.callback_query(F.data == "ch:d2e:start")
async def d2_evening_start(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Проще", callback_data="ch:d2e:d:easy")],
        [InlineKeyboardButton(text="Так же", callback_data="ch:d2e:d:same")],
        [InlineKeyboardButton(text="Сложнее", callback_data="ch:d2e:d:hard")],
    ])
    await cb.message.edit_text(
        "По ощущениям сегодня было проще или сложнее, чем вчера?",
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ch:d2e:d:"))
async def d2_evening_diff(cb: CallbackQuery):
    diff = cb.data.rsplit(":", 1)[-1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Стресс", callback_data=f"ch:d2e:r:{diff}:stress")],
        [InlineKeyboardButton(text="Усталость", callback_data=f"ch:d2e:r:{diff}:tired")],
        [InlineKeyboardButton(text="Привычка/компания", callback_data=f"ch:d2e:r:{diff}:habit")],
        [InlineKeyboardButton(text="Срывов не было", callback_data=f"ch:d2e:r:{diff}:none")],
    ])
    await cb.message.edit_text(
        "Если были срывы/переедание, что стало главной причиной?",
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ch:d2e:r:"))
async def d2_evening_finish(cb: CallbackQuery):
    _, _, _, diff, reason = cb.data.split(":")
    diff_txt = {"easy": "стало проще", "same": "уровень нагрузки стабильный", "hard": "день был сложнее"}
    reason_txt = {
        "stress": "стресс",
        "tired": "усталость",
        "habit": "привычки/контекст",
        "none": "без срывов",
    }
    focus = {
        "stress": "планируй один простой «безопасный» перекус заранее",
        "tired": "подготовь 1-2 быстрых блюда на день",
        "habit": "держи под рукой альтернативу перекусам",
        "none": "сохрани тот же режим ещё один день",
    }[reason]
    await set_challenge_step(cb.from_user.id, "d3_morning", active=True)
    await log_growth_event(
        cb.from_user.id,
        "challenge_d2_evening_done",
        {"diff": diff, "reason": reason},
    )
    await cb.message.edit_text(
        "Супер, второй день закрыт 👏\n\n"
        f"По ощущениям: {diff_txt.get(diff, 'движемся по плану')}.\n"
        f"Главный барьер: {reason_txt.get(reason, 'не указан')}.\n"
        f"Фокус на завтра: {focus}.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Жду День 3", callback_data="main:challenge")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ]),
    )
    await cb.answer()


@router.callback_query(F.data == "ch:d3m:done")
async def d3_morning_done(cb: CallbackQuery):
    await set_challenge_step(cb.from_user.id, "d3_evening", active=True)
    await log_growth_event(cb.from_user.id, "challenge_d3_morning_done")
    await cb.message.edit_text(
        "✅ Утро Дня 3 отмечено.\n"
        "Вечером закроем челлендж и выберем удобный формат продолжения.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть финал", callback_data="main:challenge")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ]),
    )
    await cb.answer()


@router.callback_query(F.data == "ch:d3e:start")
async def d3_evening_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ChallengeForm.final_feedback)
    await cb.message.edit_text(
        "Напиши в двух словах, что больше всего помогло за эти 3 дня.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ]),
    )
    await cb.answer()


@router.message(ChallengeForm.final_feedback)
async def d3_final_feedback(m: Message, state: FSMContext):
    feedback = (m.text or "").strip()
    if not feedback:
        await m.answer("Напиши коротко 2-6 слов, что было полезнее всего.")
        return
    await state.clear()
    await set_challenge_step(m.from_user.id, "completed", active=False)
    await log_growth_event(m.from_user.id, "challenge_completed", {"feedback": feedback[:120]})
    await m.answer(
        "🎉 <b>Ты прошёл(ла) 3 дня с FORMA!</b>\n\n"
        "Дальше есть три варианта:\n"
        "• Остаться на бесплатном\n"
        "• Перейти на <b>Стандарт</b> — рекомендуемый для системной работы\n"
        "• Взять Премиум для максимального контроля\n\n"
        "Для большинства задач хватает «Стандарта»: питание + движение + контроль прогресса.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Остаться на бесплатном", callback_data="ch:offer:free")],
            [InlineKeyboardButton(text="⭐ Перейти на Стандарт", callback_data="ch:offer:standard")],
            [InlineKeyboardButton(text="Хочу Премиум", callback_data="ch:offer:premium")],
        ]),
    )


@router.callback_query(F.data == "ch:offer:free")
async def offer_free(cb: CallbackQuery):
    await log_growth_event(cb.from_user.id, "challenge_offer_free")
    await cb.message.edit_text(
        "Отлично, остаёмся на бесплатном режиме.\n"
        "Нажми «🏠 Старт», когда будешь готов(а) к следующему шагу.",
        reply_markup=await _kb(cb.from_user.id),
    )
    await cb.answer()


@router.callback_query(F.data.in_({"ch:offer:standard", "ch:offer:premium"}))
async def offer_paid(cb: CallbackQuery):
    offer = cb.data.split(":")[-1]
    await log_growth_event(cb.from_user.id, f"challenge_offer_{offer}")
    await cb.message.edit_text(
        "Отличный выбор 🙌\n"
        "Открываю тарифы — выбери подходящий вариант.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Открыть тарифы", callback_data="pay:choose")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ]),
    )
    await cb.answer()
