import asyncio
import io
import logging
from datetime import date, datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from aiogram.fsm.context import FSMContext

from app.keyboards import (
    kb_start,
    kb_morning_state,
    kb_evening_summary,
    kb_deviation_reason,
    kb_progress,
    kb_photo_camera,
    remove_kb,
)
from app.states import DailyForm, WeightForm, ReviewForm
from app import texts
from app.services.llm import chat_completion, vision_completion
from app.services.database import (
    a_is_subscribed as is_subscribed,
    a_is_whitelisted as is_whitelisted,
    a_get_profile as get_profile,
    a_save_morning_state as save_morning_state,
    a_save_evening_result as save_evening_result,
    a_save_food_log as save_food_log,
    a_save_review as save_review,
    a_log_weight as log_weight,
    a_get_weight_history as get_weight_history,
    a_get_full_weight_history as get_full_weight_history,
    a_get_full_daily_history as get_full_daily_history,
    a_get_daily_count as get_daily_count,
    a_get_daily_streak as get_daily_streak,
    a_get_menu_count as get_menu_count,
    a_get_start_date as get_start_date,
    a_has_standard_access as has_standard_access,
    a_get_user_plan as get_user_plan,
    a_is_newbie_mode as is_newbie_mode,
    a_days_since_last_menu as days_since_last_menu,
)
from app.services.charts import generate_weight_chart
from app.services.export import generate_history_xlsx
from app.services.access import can_export
from app.services.database import a_has_premium_access as has_premium_access
from app.prompts import DAILY_REVIEW_SYSTEM, PHOTO_ANALYSIS_SYSTEM

logger = logging.getLogger(__name__)

router = Router()

TARGET_LABEL = {"cut": "снижение", "maintain": "поддержание", "gain": "набор"}
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


# ── Возврат в меню ────────────────────────────────────────────────

@router.callback_query(F.data == "back:menu")
async def back_to_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "       <b>F O R M A</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выберите действие 👇",
        parse_mode="HTML",
        reply_markup=await _kb(cb.from_user.id),
    )
    await cb.answer()


# ── Утреннее сопровождение ────────────────────────────────────────

@router.callback_query(F.data == "main:support")
async def morning(cb: CallbackQuery):
    profile = await get_profile(cb.from_user.id)
    if not profile:
        await cb.message.edit_text(
            "Сначала сделаем базу 👇\n\n"
            "Нажмите «📊 Рассчитать ориентир»,\n"
            "чтобы я смог давать персональные чек-ины.",
            reply_markup=await _kb(cb.from_user.id),
        )
        await cb.answer()
        return
    await cb.message.edit_text(
        texts.MORNING_PROMPT,
        reply_markup=kb_morning_state(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("morning:"))
async def morning_state(cb: CallbackQuery):
    key = cb.data.split(":")[1]
    await save_morning_state(cb.from_user.id, key)
    reply = texts.MORNING_REPLY.get(key, "Принято.")
    await cb.message.edit_text(reply, reply_markup=await _kb(cb.from_user.id))
    await cb.answer()


# ── Вечерний итог дня ─────────────────────────────────────────────

@router.callback_query(F.data == "main:review")
async def evening(cb: CallbackQuery):
    profile = await get_profile(cb.from_user.id)
    if not profile:
        await cb.message.edit_text(
            "Разбор дня работает после настройки профиля.\n\n"
            "Нажмите «📊 Рассчитать ориентир»,\n"
            "и я включу персональный вечерний разбор.",
            reply_markup=await _kb(cb.from_user.id),
        )
        await cb.answer()
        return
    await cb.message.edit_text(
        texts.EVENING_PROMPT,
        reply_markup=kb_evening_summary(),
    )
    await cb.answer()


@router.callback_query(F.data == "evening:ok")
async def evening_ok(cb: CallbackQuery):
    await save_evening_result(cb.from_user.id, "ok")
    await cb.message.edit_text(texts.EVENING_OK, reply_markup=await _kb(cb.from_user.id))
    await cb.answer()


@router.callback_query(F.data == "evening:deviation")
async def evening_deviation(cb: CallbackQuery):
    await cb.message.edit_text(
        texts.DEVIATION_OPEN,
        reply_markup=kb_deviation_reason(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("reason:"))
async def deviation_reason(cb: CallbackQuery):
    key = cb.data.split(":")[1]
    await save_evening_result(cb.from_user.id, "deviation", key)
    reply = texts.REASON_REPLY.get(key, "Принято.")
    await cb.message.edit_text(
        f"{reply}\n\n{texts.POST_SLIP_CLOSE}",
        parse_mode="HTML",
        reply_markup=await _kb(cb.from_user.id),
    )
    await cb.answer()


# ── Пользователь пишет что ел ────────────────────────────────────

@router.callback_query(F.data == "evening:write")
async def ask_food_text(cb: CallbackQuery, state: FSMContext):
    await state.set_state(DailyForm.food_log)
    await cb.message.edit_text(texts.FOOD_LOG_PROMPT, parse_mode="HTML")
    await cb.answer()


@router.message(DailyForm.food_log)
async def process_food_log(m: Message, state: FSMContext):
    await state.clear()

    wait_msg = await m.answer("⏳ Анализирую...")

    review = await chat_completion(
        system=DAILY_REVIEW_SYSTEM,
        user=m.text,
        user_id=m.from_user.id, action="food_review",
    )

    await save_food_log(m.from_user.id, m.text, review)

    await wait_msg.delete()
    await m.answer(review, parse_mode="HTML")
    await m.answer(
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "       <b>F O R M A</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выберите действие 👇",
        parse_mode="HTML",
        reply_markup=await _kb(m.from_user.id),
    )


# ── Мой прогресс ─────────────────────────────────────────────────

def _days_since(start_str: str | None) -> int | None:
    if not start_str:
        return None
    try:
        start = datetime.fromisoformat(start_str).date()
        return (date.today() - start).days
    except Exception:
        return None


@router.callback_query(F.data == "main:progress")
async def show_progress(cb: CallbackQuery):
    profile = await get_profile(cb.from_user.id)
    if not profile:
        await cb.message.edit_text(
            "Сначала рассчитайте ориентир 📊",
            reply_markup=await _kb(cb.from_user.id),
        )
        await cb.answer()
        return

    weights = await get_weight_history(cb.from_user.id, 10)
    daily_count = await get_daily_count(cb.from_user.id)
    streak = await get_daily_streak(cb.from_user.id)
    menu_count = await get_menu_count(cb.from_user.id)

    target_label = TARGET_LABEL.get(profile["target"], profile["target"])
    start = await get_start_date(cb.from_user.id)
    days = _days_since(start)
    premium = await has_standard_access(cb.from_user.id)

    goal_w = profile.get("goal_weight")

    text = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📈  <b>МОЙ ПРОГРЕСС</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if days is not None:
        text += f"  📆  В программе: <b>{days}</b> дн. (с {start})\n"

    text += (
        f"  🎯  Цель: {target_label}\n"
        f"  🔥  Ориентир: {profile['calories']} ккал\n"
        f"  ⚖️  Стартовый вес: {profile['weight_kg']} кг\n"
    )

    if goal_w:
        text += f"  🏁  Желаемый вес: {goal_w} кг\n"

    if weights:
        current = weights[0]["weight_kg"]
        diff = current - profile["weight_kg"]
        sign = "+" if diff > 0 else ""
        text += f"  ⚖️  Текущий вес: {current} кг ({sign}{diff:.1f})\n"

        if goal_w:
            remaining = abs(current - goal_w)
            if (profile.get("target") == "cut" and current > goal_w) or \
               (profile.get("target") == "gain" and current < goal_w):
                text += f"  🏁  Осталось: <b>{remaining:.1f}</b> кг\n"
            elif (profile.get("target") == "cut" and current <= goal_w) or \
                 (profile.get("target") == "gain" and current >= goal_w):
                text += "  🎉  <b>Цель достигнута!</b>\n"

        if len(weights) >= 2:
            text += "\n  📉 <b>Динамика веса:</b>\n"
            for w in weights[:7]:
                d = w["logged_at"][:10]
                text += f"        {d}  →  {w['weight_kg']} кг\n"

    text += (
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"  📅  Дней с чек-ином: <b>{daily_count}</b>\n"
        f"  🔥  Текущая серия: <b>{streak}</b> дн.\n"
        f"  📋  Меню составлено: <b>{menu_count}</b> раз\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выберите действие 👇"
    )

    await cb.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=kb_progress(has_premium=premium),
    )
    await cb.answer()


# ── График веса ──────────────────────────────────────────────────

@router.callback_query(F.data == "prog:chart")
async def send_chart(cb: CallbackQuery):
    profile = await get_profile(cb.from_user.id)
    weights = await get_full_weight_history(cb.from_user.id)

    if not weights:
        await cb.answer("Нет данных о весе. Сначала обновите вес ⚖️", show_alert=True)
        return

    target_w = None
    if profile:
        if profile.get("goal_weight"):
            target_w = profile["goal_weight"]
        elif profile.get("target") == "cut":
            target_w = profile["weight_kg"] * 0.9
        elif profile.get("target") == "gain":
            target_w = profile["weight_kg"] * 1.1

    start = await get_start_date(cb.from_user.id)

    chart_bytes = await asyncio.to_thread(generate_weight_chart, weights, target_w, start)
    if not chart_bytes:
        await cb.answer("Недостаточно данных для графика.", show_alert=True)
        return

    photo = BufferedInputFile(chart_bytes, filename="progress.png")
    await cb.message.answer_photo(
        photo,
        caption="📊 <b>Ваш прогресс</b>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "prog:save_chart")
async def save_chart_file(cb: CallbackQuery):
    if not await can_export(cb.from_user.id):
        await cb.answer("Эта функция доступна по подписке ✨", show_alert=True)
        return

    profile = await get_profile(cb.from_user.id)
    weights = await get_full_weight_history(cb.from_user.id)

    if not weights:
        await cb.answer("Нет данных о весе.", show_alert=True)
        return

    target_w = None
    if profile:
        if profile.get("goal_weight"):
            target_w = profile["goal_weight"]
        elif profile.get("target") == "cut":
            target_w = profile["weight_kg"] * 0.9
        elif profile.get("target") == "gain":
            target_w = profile["weight_kg"] * 1.1

    start = await get_start_date(cb.from_user.id)
    chart_bytes = await asyncio.to_thread(generate_weight_chart, weights, target_w, start)
    if not chart_bytes:
        await cb.answer("Недостаточно данных.", show_alert=True)
        return

    doc = BufferedInputFile(chart_bytes, filename=f"forma_chart_{date.today().isoformat()}.png")
    await cb.message.answer_document(doc, caption="📊 График прогресса FORMA")
    await cb.answer()


# ── Экспорт истории (Excel) ──────────────────────────────────────

@router.callback_query(F.data == "prog:export")
async def export_history(cb: CallbackQuery):
    if not await can_export(cb.from_user.id):
        await cb.answer("Эта функция доступна по подписке ✨", show_alert=True)
        return

    daily = await get_full_daily_history(cb.from_user.id)
    weights = await get_full_weight_history(cb.from_user.id)
    profile = await get_profile(cb.from_user.id)

    xlsx_bytes = await asyncio.to_thread(generate_history_xlsx,
        daily_history=daily,
        weight_history=weights,
        profile=profile,
        first_name=cb.from_user.first_name or "",
    )

    doc = BufferedInputFile(
        xlsx_bytes,
        filename=f"forma_history_{date.today().isoformat()}.xlsx",
    )
    await cb.message.answer_document(doc, caption="📥 Ваша история FORMA")
    await cb.answer()


@router.callback_query(F.data == "prog:need_premium")
async def need_premium(cb: CallbackQuery):
    await cb.answer(
        "📥 Экспорт истории и сохранение графика доступны по подписке.\n"
        "Свяжитесь с нами для оформления ✨",
        show_alert=True,
    )


# ── Обновить вес ──────────────────────────────────────────────────

@router.callback_query(F.data == "main:weight")
async def ask_weight(cb: CallbackQuery, state: FSMContext):
    await state.set_state(WeightForm.weight)
    await cb.message.edit_text(
        "⚖️ Введите ваш <b>текущий вес</b> в кг\n"
        "<i>например: 74.5</i>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(WeightForm.weight)
async def save_new_weight(m: Message, state: FSMContext):
    try:
        weight = float(m.text.replace(",", "."))
        if not (30 <= weight <= 300):
            raise ValueError
    except (ValueError, AttributeError):
        await m.answer("Введите число от 30 до 300.\n<i>Например: 74.5</i>", parse_mode="HTML")
        return

    await state.clear()
    await log_weight(m.from_user.id, weight)

    profile = await get_profile(m.from_user.id)
    if profile:
        diff = weight - profile["weight_kg"]
        sign = "+" if diff > 0 else ""
        text = (
            f"⚖️ Вес записан: <b>{weight}</b> кг\n"
            f"От старта: {sign}{diff:.1f} кг\n\n"
            "Так держать!"
        )
    else:
        text = f"⚖️ Вес записан: <b>{weight}</b> кг"

    await m.answer(text, parse_mode="HTML", reply_markup=await _kb(m.from_user.id))


# ── Отзыв ────────────────────────────────────────────────────────

@router.callback_query(F.data == "main:review_send")
async def ask_review(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ReviewForm.text)
    await cb.message.edit_text(
        "✍️ <b>Оставьте отзыв</b>\n\n"
        "Напишите, что думаете о FORMA.\n"
        "Ваше мнение поможет сделать сервис лучше.\n\n"
        "<i>Просто напишите текст в следующем сообщении.</i>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(ReviewForm.text)
async def save_user_review(m: Message, state: FSMContext):
    await state.clear()

    review_text = m.text.strip() if m.text else ""
    if not review_text:
        await m.answer("Отзыв не может быть пустым. Попробуйте ещё раз.")
        return

    await save_review(
        m.from_user.id,
        m.from_user.username,
        m.from_user.first_name,
        review_text,
    )

    await m.answer(
        "🙏 <b>Спасибо за отзыв!</b>\n\n"
        "Ваше мнение очень ценно для нас.",
        parse_mode="HTML",
        reply_markup=await _kb(m.from_user.id),
    )


# ── Фото-анализ еды (Premium) ───────────────────────────────────

@router.callback_query(F.data == "main:photo")
async def ask_photo(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    if not await has_premium_access(uid):
        await cb.answer(
            "📷 Анализ фото доступен в тарифе «Премиум»",
            show_alert=True,
        )
        return

    from app.states import PhotoForm
    await state.set_state(PhotoForm.waiting)
    await cb.message.answer(
        "📷 <b>Анализ фото еды</b>\n\n"
        "Нажмите кнопку с фотоаппаратом снизу и сделайте снимок блюда.\n"
        "Или отправьте готовое фото из галереи.\n\n"
        "Можно добавить подпись: например «это ужин».\n\n"
        "Отправьте фото того, что вы едите\n"
        "или планируете съесть.\n\n"
        "AI оценит блюда и подсчитает\n"
        "примерный КБЖУ.\n\n"
        "<i>Поддерживаются фото блюд,\n"
        "тарелок, продуктов</i>",
        parse_mode="HTML",
        reply_markup=kb_photo_camera(),
    )
    await cb.answer()


from app.states import PhotoForm          # noqa: E402


@router.message(PhotoForm.waiting, F.photo)
async def analyze_photo(m: Message, state: FSMContext):
    uid = m.from_user.id
    await state.clear()
    wait_msg = await m.answer("🔍 Анализирую фото...", reply_markup=remove_kb)

    from app.bot import bot
    photo = m.photo[-1]
    file = await bot.get_file(photo.file_id)
    bio = await bot.download_file(file.file_path)
    image_bytes = bio.read()

    caption = m.caption or ""
    result = await vision_completion(
        system=PHOTO_ANALYSIS_SYSTEM,
        image_bytes=image_bytes,
        user_text=caption,
        user_id=uid,
        action="photo_analysis",
    )

    await wait_msg.delete()
    await m.answer(result, parse_mode="HTML", reply_markup=await _kb(uid))


@router.message(PhotoForm.waiting)
async def photo_wrong_type(m: Message):
    await m.answer("Пожалуйста, отправьте именно фото (не файл и не текст).")
