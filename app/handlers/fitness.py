"""Soft fitness module: daily exercises for sedentary users."""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from app.states import FitnessForm
from app.keyboards import kb_fitness_level, kb_fitness_done, kb_start
from app.services.llm import chat_completion
from app.services.database import (
    a_get_profile as get_profile,
    a_get_fitness_level as get_fitness_level,
    a_set_fitness_level as set_fitness_level,
    a_save_fitness_log as save_fitness_log,
    a_mark_fitness_done as mark_fitness_done,
    a_get_fitness_stats as get_fitness_stats,
    a_get_today_fitness as get_today_fitness,
    a_has_standard_access as has_standard_access,
    a_is_subscribed as is_subscribed,
    a_get_user_plan as get_user_plan,
    a_is_newbie_mode as is_newbie_mode,
    a_days_since_last_menu as days_since_last_menu,
)
from app.prompts import FITNESS_SYSTEM
from app.keyboards import RESTRICTION_LABELS

logger = logging.getLogger(__name__)

router = Router()

MENU_PERIOD = 3

FITNESS_LEVEL_LABELS = {
    "beginner": "🌱 Начинающий",
    "basic": "🚶 Базовый",
    "confident": "💪 Уверенный",
}

ACTIVITY_LABEL = {
    "sedentary": "сидячий",
    "light": "лёгкая активность",
    "moderate": "умеренная активность",
    "high": "высокая активность",
    "very_high": "очень высокая активность",
}

GENDER_LABEL = {"male": "мужской", "female": "женский"}


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


@router.callback_query(F.data == "main:fitness_locked")
async def fitness_locked(cb: CallbackQuery):
    await cb.answer(
        "🏃 Упражнения доступны по подписке.\n"
        "Нажмите «💎 Тарифы» для оформления.",
        show_alert=True,
    )


@router.callback_query(F.data == "main:fitness")
async def fitness_start(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id

    if not await has_standard_access(uid):
        await cb.answer("🏃 Упражнения доступны по подписке", show_alert=True)
        return

    profile = await get_profile(uid)
    if not profile:
        await cb.answer("Сначала рассчитайте ориентир 📊", show_alert=True)
        return

    today = await get_today_fitness(uid)
    if today:
        if today["completed"]:
            stats = await get_fitness_stats(uid)
            await cb.message.answer(
                "✅ <b>Сегодня уже выполнено!</b>\n\n"
                f"За эту неделю: {stats['week']} из 7 дней\n"
                f"Всего тренировок: {stats['done']}\n\n"
                "Завтра будет новый комплекс 💪",
                parse_mode="HTML",
                reply_markup=await _kb(uid),
            )
        else:
            await cb.message.answer(
                today["exercises"],
                parse_mode="HTML",
                reply_markup=kb_fitness_done(),
            )
        await cb.answer()
        return

    level = await get_fitness_level(uid)
    if not level:
        await cb.message.answer(
            "🏃 <b>Мягкий фитнес</b>\n\n"
            "Подберём упражнения на 5-10 минут\n"
            "с учётом вашего здоровья.\n\n"
            "Выберите ваш уровень подготовки:",
            parse_mode="HTML",
            reply_markup=kb_fitness_level(),
        )
        await cb.answer()
        return

    await cb.answer()
    await _generate_exercises(cb.message, uid, profile, level)


@router.callback_query(F.data.startswith("fitlvl:"))
async def set_level(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    level = cb.data.split(":")[1]

    await set_fitness_level(uid, level)

    profile = await get_profile(uid)
    if not profile:
        await cb.answer("Сначала рассчитайте ориентир", show_alert=True)
        return

    await cb.answer()
    await _generate_exercises(cb.message, uid, profile, level)


async def _generate_exercises(msg: Message, uid: int, profile: dict, level: str):
    wait_msg = await msg.answer("🏃 Подбираю упражнения...")

    gender = GENDER_LABEL.get(profile.get("gender", ""), "")
    age = profile.get("age", "")
    weight = profile.get("weight_kg", "")
    activity = ACTIVITY_LABEL.get(profile.get("activity", ""), "")
    level_label = FITNESS_LEVEL_LABELS.get(level, level)

    restrictions = profile.get("restrictions", [])
    if isinstance(restrictions, str):
        import json
        try:
            restrictions = json.loads(restrictions)
        except (json.JSONDecodeError, TypeError):
            restrictions = []

    restrictions_text = "нет"
    if restrictions:
        labels = [RESTRICTION_LABELS.get(r, r) for r in restrictions]
        restrictions_text = ", ".join(labels)

    user_prompt = (
        f"Пол: {gender}, возраст: {age}, вес: {weight} кг.\n"
        f"Активность: {activity}.\n"
        f"Уровень подготовки: {level_label}.\n"
        f"Ограничения по здоровью: {restrictions_text}.\n"
        f"Составьте новый разнообразный комплекс на сегодня."
    )

    exercises = await chat_completion(
        system=FITNESS_SYSTEM,
        user=user_prompt,
        user_id=uid,
        action="fitness",
    )

    await save_fitness_log(uid, exercises)
    await wait_msg.delete()

    await msg.answer(exercises, parse_mode="HTML", reply_markup=kb_fitness_done())


@router.callback_query(F.data == "fit:done")
async def fitness_done(cb: CallbackQuery):
    uid = cb.from_user.id
    await mark_fitness_done(uid)
    stats = await get_fitness_stats(uid)

    week = stats["week"]
    total = stats["done"]

    fire = "🔥" * min(week, 7)
    text = (
        f"🎉 <b>Отлично, вы молодец!</b>\n\n"
        f"📅 На этой неделе: {week}/7 {fire}\n"
        f"📊 Всего тренировок: {total}\n\n"
    )

    if week >= 5:
        text += "Потрясающая регулярность! 💪"
    elif week >= 3:
        text += "Хороший темп, продолжайте! 🌟"
    else:
        text += "Каждый день — маленькая победа 🌱"

    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=await _kb(uid))
    await cb.answer("✅ Записано!")


@router.callback_query(F.data == "fit:skip")
async def fitness_skip(cb: CallbackQuery):
    await cb.message.edit_text(
        "Ничего страшного, отдых тоже важен.\n"
        "Завтра попробуем снова 🌱",
        reply_markup=await _kb(cb.from_user.id),
    )
    await cb.answer()
