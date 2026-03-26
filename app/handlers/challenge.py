"""D1-D3 onboarding challenge flow with soft upsell."""

from datetime import datetime

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
    a_get_last_menu as get_last_menu,
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

CONFETTI_EFFECT = "5046509860389126442"


def _progress(step: str) -> str:
    """Small progress header used across all challenge screens."""
    day_map = {
        "d1_morning": 1,
        "d1_menu_pending": 1,
        "d1_evening": 1,
        "d2_menu_pending": 2,
        "d2_evening": 2,
        "d3_menu_pending": 3,
        "d3_evening": 3,
        "completed": 3,
    }
    day = day_map.get(step, 1)
    pct = {1: 33, 2: 67, 3: 100}.get(day, 33)
    if step == "completed":
        return "🏁 <b>Мини‑челлендж завершён</b> · 100%\n\n"
    return f"🔥 <b>Мини‑челлендж 3 дня</b> · День {day} из 3 · {pct}%\n\n"


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


async def _has_fresh_menu_since(uid: int, since_iso: str | None) -> bool:
    """Check menu exists and was generated after current day-step started."""
    last = await get_last_menu(uid)
    if not last:
        return False
    if not since_iso:
        return True
    try:
        return datetime.fromisoformat(last["created_at"]) >= datetime.fromisoformat(since_iso)
    except Exception:
        return True


async def _require_step(cb: CallbackQuery, expected_step: str) -> dict | None:
    """Guard against out-of-order clicks from old/forwarded messages."""
    st = await get_challenge_state(cb.from_user.id)
    if not st or not st.get("active"):
        await cb.answer(
            "Откройте «🎯 Мини-челлендж 3 дня», чтобы продолжить.",
            show_alert=True,
        )
        return None
    if st.get("step") != expected_step:
        await cb.answer(
            "Сначала завершите текущий шаг челленджа.",
            show_alert=True,
        )
        return None
    return st


def _step_kb(step: str, uid: int, standard: bool = False, premium: bool = False):
    if step == "d1_morning":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать День 1", callback_data="ch:d1:go")],
            [InlineKeyboardButton(text="👀 Что я получу за 3 дня?", callback_data="main:info")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ])
    if step == "d1_menu_pending":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Получить меню на 3 дня", callback_data="main:calc")],
            [InlineKeyboardButton(text="✅ Отметить: День 1 выполнен", callback_data="ch:d1:menu_done")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ])
    if step == "d1_evening":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌙 Закрыть день (2 минуты)", callback_data="ch:d1e:start")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ])
    if step == "d2_menu_pending":
        rows = [
            [InlineKeyboardButton(text="⚖️ Обновить вес", callback_data="main:weight")],
            [InlineKeyboardButton(text="✅ Отметить: День 2 выполнен", callback_data="ch:d2:menu_done")],
        ]
        if standard:
            rows.append([InlineKeyboardButton(text="🏃 Показать упражнения", callback_data="main:fitness")])
        rows.append([InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")])
        return InlineKeyboardMarkup(inline_keyboard=rows)
    if step == "d2_evening":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌙 Закрыть день (2 минуты)", callback_data="ch:d2e:start")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ])
    if step == "d3_menu_pending":
        rows = [
            [InlineKeyboardButton(text="⚖️ Обновить вес", callback_data="main:weight")],
        ]
        if premium:
            rows.append([InlineKeyboardButton(text="📷 Отправить фото еды", callback_data="main:photo")])
        rows.append([InlineKeyboardButton(text="✅ Отметить: День 3 выполнен", callback_data="ch:d3:menu_done")])
        rows.append([InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")])
        return InlineKeyboardMarkup(inline_keyboard=rows)
    if step == "d3_evening":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏁 Финал (2 минуты)", callback_data="ch:d3e:start")],
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
        text = _progress(step) + (
            "🚀 <b>День 1 — старт и фокус</b>\n\n"
            "Сделаем мягкий заход без «идеальности».\n"
            "Твоя задача — просто начать и зафиксировать опору.\n\n"
            "<b>Сегодня</b> мы:\n"
            "• посчитаем ориентир КБЖУ\n"
            "• соберём меню на 3 дня\n"
            "• при желании отметим вес\n\n"
            "<i>Правило челленджа:</i> лучше на 1 шаг, чем на 0."
        )
    elif step == "d1_menu_pending":
        text = _progress(step) + (
            "📋 <b>День 1 — выполнить по меню</b>\n\n"
            "Сначала получи меню на 3 дня.\n"
            "Дальше — просто проживи <b>1 день</b> по нему.\n\n"
            "В конце дня нажми:\n"
            "«✅ Отметить: День 1 выполнен».\n\n"
            "<i>Подсказка:</i> если сорвался(лась) — не отмена. Продолжаем со следующего приёма пищи."
        )
    elif step == "d1_evening":
        text = _progress(step) + (
            "🌙 <b>День 1 — закрываем день</b>\n\n"
            "2 минуты — и у нас будет понятный фокус на завтра.\n"
            "Отвечай честно, без оценки себя."
        )
    elif step == "d2_menu_pending":
        text = _progress(step) + (
            "🌞 <b>День 2 — стабилизация</b>\n\n"
            "Задача дня — удержать ритм.\n"
            "Ничего «усиливать» не нужно — важно продолжать.\n\n"
            "Когда день прожит по меню — нажми:\n"
            "«✅ Отметить: День 2 выполнен»."
        )
        if standard:
            text += "\n\nЕсли хочешь — добавь 5–10 минут мягкого фитнеса (у тебя он доступен)."
    elif step == "d2_evening":
        text = _progress(step) + (
            "🌙 <b>День 2 — закрываем день</b>\n\n"
            "Коротко разберём: что было легче/сложнее\n"
            "и где главный барьер."
        )
    elif step == "d3_menu_pending":
        text = _progress(step) + (
            "🎯 <b>День 3 — закрепление</b>\n\n"
            "Финальный день. Твоя цель — закрыть цикл\n"
            "и почувствовать: «я могу держать ритм»."
        )
        if premium:
            text += "\n\nМожно отправить фото еды — оценю КБЖУ по фото и дам короткую корректировку."
    elif step == "d3_evening":
        text = _progress(step) + (
            "🏁 <b>Финал — подведём итог</b>\n\n"
            "Сейчас закрепим результат и выберем,\n"
            "как удобнее продолжать дальше."
        )
    else:
        text = _progress("completed") + (
            "✅ Ты уже сделал(а) важный шаг: зафиксировал(а) ориентиры,\n"
            "прошёл(шла) цикл и укрепил(а) привычку.\n\n"
            "Дальше можно повторить цикл или продолжить в режиме поддержки."
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
    # Backward compatibility with earlier step names.
    if step == "d2_morning":
        step = "d2_menu_pending"
        await set_challenge_step(cb.from_user.id, step, active=True)
    elif step == "d3_morning":
        step = "d3_menu_pending"
        await set_challenge_step(cb.from_user.id, step, active=True)
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
    await set_challenge_step(cb.from_user.id, "d1_menu_pending", active=True)
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


@router.callback_query(F.data == "ch:d1:menu_done")
async def d1_menu_done(cb: CallbackQuery):
    st = await _require_step(cb, "d1_menu_pending")
    if not st:
        return
    if not await _has_fresh_menu_since(cb.from_user.id, st.get("updated_at")):
        await cb.answer("Сначала получите меню на 3 дня для текущего шага 📋", show_alert=True)
        return
    await set_challenge_step(cb.from_user.id, "d1_evening", active=True)
    await log_growth_event(cb.from_user.id, "challenge_d1_menu_day_done")
    await _render_step(cb.message, cb.from_user.id, "d1_evening", edit=True)
    await cb.answer()


@router.callback_query(F.data == "ch:d1e:start")
async def d1_evening_start(cb: CallbackQuery):
    st = await _require_step(cb, "d1_evening")
    if not st:
        return
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
    st = await _require_step(cb, "d1_evening")
    if not st:
        return
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
    st = await _require_step(cb, "d1_evening")
    if not st:
        return
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
    st = await _require_step(cb, "d1_evening")
    if not st:
        return
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

    await set_challenge_step(cb.from_user.id, "d2_menu_pending", active=True)
    await log_growth_event(
        cb.from_user.id,
        "challenge_d1_evening_done",
        {"score": score, "snacks": snacks, "water": water},
    )
    try:
        await cb.message.answer(
            "🎉 День 1 закрыт!",
            message_effect_id=CONFETTI_EFFECT,
        )
    except Exception:
        pass
    await cb.message.edit_text(
        "Класс, спасибо за честность 🙌\n\n"
        f"Что уже хорошо: {strengths[0]}, {strengths[1]}.\n"
        f"Фокус на завтра: {focus}.\n\n"
        "Продолжаем?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Перейти к Дню 2", callback_data="main:challenge")],
            [InlineKeyboardButton(text="⏸️ Сделаю паузу", callback_data="back:menu")],
        ]),
    )
    await cb.answer()


@router.callback_query(F.data == "ch:d2:menu_done")
async def d2_menu_done(cb: CallbackQuery):
    st = await _require_step(cb, "d2_menu_pending")
    if not st:
        return
    if not await _has_fresh_menu_since(cb.from_user.id, st.get("updated_at")):
        await cb.answer("Сначала получите меню на 3 дня для текущего шага 📋", show_alert=True)
        return
    await set_challenge_step(cb.from_user.id, "d2_evening", active=True)
    await log_growth_event(cb.from_user.id, "challenge_d2_menu_day_done")
    await cb.message.edit_text(
        "✅ День 2 отмечен.\n"
        "Теперь быстро закроем день — и перейдём к финальному Дню 3.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌙 Закрыть День 2", callback_data="main:challenge")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ]),
    )
    await cb.answer()


@router.callback_query(F.data == "ch:d2e:start")
async def d2_evening_start(cb: CallbackQuery):
    st = await _require_step(cb, "d2_evening")
    if not st:
        return
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
    st = await _require_step(cb, "d2_evening")
    if not st:
        return
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
    st = await _require_step(cb, "d2_evening")
    if not st:
        return
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
    await set_challenge_step(cb.from_user.id, "d3_menu_pending", active=True)
    await log_growth_event(
        cb.from_user.id,
        "challenge_d2_evening_done",
        {"diff": diff, "reason": reason},
    )
    try:
        await cb.message.answer(
            "🎉 День 2 закрыт!",
            message_effect_id=CONFETTI_EFFECT,
        )
    except Exception:
        pass
    await cb.message.edit_text(
        "Супер, второй день закрыт 👏\n\n"
        f"По ощущениям: {diff_txt.get(diff, 'движемся по плану')}.\n"
        f"Главный барьер: {reason_txt.get(reason, 'не указан')}.\n"
        f"Фокус на завтра: {focus}.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Перейти к Дню 3", callback_data="main:challenge")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ]),
    )
    await cb.answer()


@router.callback_query(F.data == "ch:d3:menu_done")
async def d3_menu_done(cb: CallbackQuery):
    st = await _require_step(cb, "d3_menu_pending")
    if not st:
        return
    if not await _has_fresh_menu_since(cb.from_user.id, st.get("updated_at")):
        await cb.answer("Сначала получите меню на 3 дня для текущего шага 📋", show_alert=True)
        return
    await set_challenge_step(cb.from_user.id, "d3_evening", active=True)
    await log_growth_event(cb.from_user.id, "challenge_d3_menu_day_done")
    await cb.message.edit_text(
        "✅ День 3 отмечен.\n"
        "Остался финальный шаг — подведём итог и закрепим план.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏁 Перейти к финалу", callback_data="main:challenge")],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ]),
    )
    await cb.answer()


# Legacy callbacks (kept for users with older inline messages in history)
@router.callback_query(F.data == "ch:d2m:done")
async def d2_morning_done_legacy(cb: CallbackQuery):
    await d2_menu_done(cb)


@router.callback_query(F.data == "ch:d3m:done")
async def d3_morning_done_legacy(cb: CallbackQuery):
    await d3_menu_done(cb)


@router.callback_query(F.data == "ch:d3e:start")
async def d3_evening_start(cb: CallbackQuery, state: FSMContext):
    st = await _require_step(cb, "d3_evening")
    if not st:
        return
    await state.set_state(ChallengeForm.final_feedback)
    await cb.message.edit_text(
        "Финальный штрих.\n\n"
        "Напиши в 2–6 слов, что больше всего помогло за эти 3 дня.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
        ]),
    )
    await cb.answer()


@router.message(ChallengeForm.final_feedback)
async def d3_final_feedback(m: Message, state: FSMContext):
    ch = await get_challenge_state(m.from_user.id)
    if not ch or ch.get("step") != "d3_evening":
        await state.clear()
        await m.answer(
            "Откройте «🎯 Мини-челлендж 3 дня», чтобы продолжить по шагам.",
            reply_markup=await _kb(m.from_user.id),
        )
        return
    feedback = (m.text or "").strip()
    if not feedback:
        await m.answer("Напиши коротко 2-6 слов, что было полезнее всего.")
        return
    await state.clear()
    await set_challenge_step(m.from_user.id, "completed", active=False)
    await log_growth_event(m.from_user.id, "challenge_completed", {"feedback": feedback[:120]})
    try:
        await m.answer(
            "🎉 Челлендж закрыт!",
            message_effect_id=CONFETTI_EFFECT,
        )
    except Exception:
        pass
    await m.answer(
        "🏁 <b>Ты прошёл(ла) 3 дня с FORMA!</b>\n\n"
        f"Твоё главное слово: <b>{feedback[:60]}</b>\n\n"
        "Теперь самое ценное — не «закончить», а <b>продолжить</b>.\n\n"
        "📌 <b>План на 7 дней (простая версия)</b>\n"
        "1) 5 дней из 7 — держимся меню/ориентира\n"
        "2) 1 «свободный» приём пищи без вины\n"
        "3) 10 минут движения 4 раза в неделю\n"
        "4) Вечером 1 короткий разбор — что мешало/что помогло\n\n"
        "Дальше есть три варианта:\n"
        "• Остаться на бесплатном\n"
        "• Перейти на <b>Стандарт</b> — лучший баланс «питание + движение + контроль»\n"
        "• Взять Премиум для максимального контроля (включая фото)\n\n"
        "<i>Хочешь — помогу выбрать режим под твой темп.</i>",
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
        "Если захочешь продолжить — просто открой главное меню и выбери следующий шаг.",
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
