import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.states import CalcForm, RecipeForm
from aiogram.types import BufferedInputFile

from app.keyboards import (
    kb_gender,
    kb_activity,
    kb_after_recipe,
    kb_target,
    kb_goal_weight_skip,
    kb_restrictions,
    kb_restrictions_done,
    kb_food_prefs,
    kb_food_prefs_done,
    kb_cuisine,
    kb_cuisine_done,
    CUISINE_LABELS,
    kb_soup_pref,
    kb_menu_confirm,
    kb_after_menu,
    kb_start,
    RESTRICTION_LABELS,
    FOOD_PREF_LABELS,
)
from app.services.nutrition import compute_kbju
from app.services.llm import chat_completion
from app.services.database import (
    a_is_subscribed as is_subscribed,
    a_get_profile as get_profile,
    a_is_whitelisted as is_whitelisted,
    a_get_menu_count as get_menu_count,
    a_days_since_last_menu as days_since_last_menu,
    a_save_profile as save_profile,
    a_save_menu as save_menu,
    a_get_latest_weight as get_latest_weight,
    a_get_last_menu as get_last_menu,
    a_has_standard_access as has_standard_access,
    a_get_user_plan as get_user_plan,
)
from app.prompts import MENU_SYSTEM_SOUP, MENU_SYSTEM_NO_SOUP, RECIPE_SYSTEM

logger = logging.getLogger(__name__)

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

GENDER_LABEL = {"male": "мужской", "female": "женский"}
ACTIVITY_LABEL = {
    "sedentary": "сидячий",
    "light": "лёгкая",
    "moderate": "умеренная",
    "high": "высокая",
    "very_high": "очень высокая",
}
TARGET_LABEL = {"cut": "снижение", "maintain": "поддержание", "gain": "набор"}


def _build_cuisine_prompt(cuisine: list[str]) -> str:
    """Convert cuisine list into a prompt line for LLM."""
    if not cuisine or cuisine == ["any"]:
        return ""
    labels = [CUISINE_LABELS.get(c, c) for c in cuisine]
    return f"Предпочитаемая кухня: {', '.join(labels)}. Приоритет блюдам этих кухонь.\n"


def _build_prefs_prompt(food_prefs: list[str]) -> str:
    """Convert food_prefs list into a human-readable prompt line for LLM."""
    if not food_prefs or food_prefs == ["all"]:
        return "Предпочтения по продуктам: без особых предпочтений, всё подходит."
    labels = []
    for p in food_prefs:
        if p in FOOD_PREF_LABELS:
            labels.append(FOOD_PREF_LABELS[p].split(" ", 1)[1])
        else:
            labels.append(p)
    return (
        "Предпочтения по продуктам (ОБЯЗАТЕЛЬНО учитывать — "
        "включать эти продукты в меню приоритетно): " + ", ".join(labels) + "."
    )


def _format_selected_restrictions(selected: list[str]) -> str:
    if not selected:
        return ""
    labels = []
    for r in selected:
        if r in RESTRICTION_LABELS:
            labels.append(RESTRICTION_LABELS[r])
        else:
            labels.append(f"✏️ {r}")
    return ", ".join(labels)


# ── Отмена ────────────────────────────────────────────────────────

@router.callback_query(F.data == "calc:cancel")
async def cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Расчёт отменён.")
    await cb.message.answer(
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "       <b>F O R M A</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выберите действие 👇",
        parse_mode="HTML",
        reply_markup=await _kb(cb.from_user.id),
    )
    await cb.answer()


# ── Шаг 1: Пол ───────────────────────────────────────────────────

@router.callback_query(F.data == "main:calc")
async def calc_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(CalcForm.gender)
    await cb.message.edit_text(
        "📊 <b>Расчёт ориентира</b>\n\n"
        "Укажите ваш пол:",
        parse_mode="HTML",
        reply_markup=kb_gender(),
    )
    await cb.answer()


@router.callback_query(CalcForm.gender, F.data.startswith("gender:"))
async def set_gender(cb: CallbackQuery, state: FSMContext):
    gender = cb.data.split(":")[1]
    await state.update_data(gender=gender)
    await state.set_state(CalcForm.height)

    label = "👨 Мужской" if gender == "male" else "👩 Женский"
    await cb.message.edit_text(f"Пол: {label} ✓")
    await cb.message.answer(
        "Укажите <b>рост</b> в см\n<i>например: 175</i>",
        parse_mode="HTML",
    )
    await cb.answer()


# ── Шаг 2: Рост ──────────────────────────────────────────────────

@router.message(CalcForm.height)
async def set_height(m: Message, state: FSMContext):
    try:
        height = float(m.text.replace(",", "."))
        if not (100 <= height <= 250):
            raise ValueError
    except (ValueError, AttributeError):
        await m.answer("Введите число от 100 до 250.\n<i>Например: 175</i>", parse_mode="HTML")
        return
    await state.update_data(height=height)
    await state.set_state(CalcForm.weight)
    await m.answer(
        "Укажите <b>вес</b> в кг\n<i>например: 70</i>",
        parse_mode="HTML",
    )


# ── Шаг 3: Вес ───────────────────────────────────────────────────

@router.message(CalcForm.weight)
async def set_weight(m: Message, state: FSMContext):
    try:
        weight = float(m.text.replace(",", "."))
        if not (30 <= weight <= 300):
            raise ValueError
    except (ValueError, AttributeError):
        await m.answer("Введите число от 30 до 300.\n<i>Например: 70</i>", parse_mode="HTML")
        return
    await state.update_data(weight=weight)
    await state.set_state(CalcForm.age)
    await m.answer(
        "Укажите <b>возраст</b> (полных лет)\n<i>например: 30</i>",
        parse_mode="HTML",
    )


# ── Шаг 4: Возраст ───────────────────────────────────────────────

@router.message(CalcForm.age)
async def set_age(m: Message, state: FSMContext):
    try:
        age = int(m.text)
        if not (14 <= age <= 100):
            raise ValueError
    except (ValueError, AttributeError):
        await m.answer("Введите число от 14 до 100.\n<i>Например: 30</i>", parse_mode="HTML")
        return
    await state.update_data(age=age)
    await state.set_state(CalcForm.activity)
    await m.answer(
        "Выберите уровень <b>активности</b>:",
        parse_mode="HTML",
        reply_markup=kb_activity(),
    )


# ── Шаг 5: Активность ────────────────────────────────────────────

@router.callback_query(CalcForm.activity, F.data.startswith("act:"))
async def set_activity(cb: CallbackQuery, state: FSMContext):
    activity = cb.data.split(":")[1]
    await state.update_data(activity=activity)
    await state.set_state(CalcForm.target)

    await cb.message.edit_text(f"Активность: {ACTIVITY_LABEL[activity]} ✓")
    await cb.message.answer(
        "Какая у вас <b>цель</b>?",
        parse_mode="HTML",
        reply_markup=kb_target(),
    )
    await cb.answer()


# ── Шаг 6: Цель ──────────────────────────────────────────────────

@router.callback_query(CalcForm.target, F.data.startswith("target:"))
async def set_target(cb: CallbackQuery, state: FSMContext):
    target = cb.data.split(":")[1]
    await state.update_data(target=target, restrictions=[])
    await state.set_state(CalcForm.goal_weight)

    await cb.message.edit_text(f"Цель: {TARGET_LABEL[target]} ✓")

    if target == "maintain":
        hint = "Если хотите зафиксировать желаемый вес — введите его.\nИначе нажмите <b>«Пропустить»</b>."
    elif target == "cut":
        hint = "Какой вес вы хотите достичь?\n<i>Например: 65</i>\n\nИли нажмите <b>«Пропустить»</b>."
    else:
        hint = "Какой вес вы хотите набрать?\n<i>Например: 80</i>\n\nИли нажмите <b>«Пропустить»</b>."

    await cb.message.answer(
        f"🎯 <b>Желаемый результат</b>\n\n{hint}",
        parse_mode="HTML",
        reply_markup=kb_goal_weight_skip(),
    )
    await cb.answer()


# ── Шаг 6b: Желаемый вес ────────────────────────────────────────

@router.message(CalcForm.goal_weight)
async def set_goal_weight(m: Message, state: FSMContext):
    try:
        goal = float(m.text.replace(",", "."))
        if not (30 <= goal <= 300):
            raise ValueError
    except (ValueError, AttributeError):
        await m.answer("Введите число от 30 до 300.\n<i>Например: 65</i>", parse_mode="HTML")
        return

    await state.update_data(goal_weight=goal)
    await state.set_state(CalcForm.restrictions)
    await m.answer(
        f"🎯 Желаемый вес: <b>{goal}</b> кг ✓\n\n"
        "⚕️ <b>Есть ли ограничения по здоровью?</b>\n\n"
        "Выберите все подходящие.\n"
        "Когда закончите — нажмите <b>«Готово»</b>.",
        parse_mode="HTML",
        reply_markup=kb_restrictions(),
    )


@router.callback_query(CalcForm.goal_weight, F.data == "goal:skip")
async def skip_goal_weight(cb: CallbackQuery, state: FSMContext):
    await state.update_data(goal_weight=None)
    await state.set_state(CalcForm.restrictions)

    await cb.message.edit_text("🎯 Желаемый вес: <i>не указан</i> ✓", parse_mode="HTML")
    await cb.message.answer(
        "⚕️ <b>Есть ли ограничения по здоровью?</b>\n\n"
        "Выберите все подходящие.\n"
        "Когда закончите — нажмите <b>«Готово»</b>.",
        parse_mode="HTML",
        reply_markup=kb_restrictions(),
    )
    await cb.answer()


# ── Шаг 7: Ограничения (множественный выбор) ─────────────────────

@router.callback_query(CalcForm.restrictions, F.data == "restr:none")
async def no_restrictions(cb: CallbackQuery, state: FSMContext):
    await state.update_data(restrictions=[])
    await _ask_food_prefs(cb, state)


@router.callback_query(CalcForm.restrictions, F.data == "restr:done")
async def restrictions_done(cb: CallbackQuery, state: FSMContext):
    await _ask_food_prefs(cb, state)


@router.callback_query(CalcForm.restrictions, F.data == "restr:custom")
async def custom_restriction(cb: CallbackQuery, state: FSMContext):
    await state.set_state(CalcForm.restrictions_detail)
    await cb.message.edit_text(
        "✏️ Напишите ваши ограничения текстом.\n"
        "<i>Например: аллергия на орехи, вегетарианство</i>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(CalcForm.restrictions, F.data.startswith("restr:"))
async def toggle_restriction(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":")[1]
    data = await state.get_data()
    selected: list = data.get("restrictions", [])

    if key in selected:
        selected.remove(key)
    else:
        selected.append(key)

    await state.update_data(restrictions=selected)

    summary = _format_selected_restrictions(selected)
    text = (
        "⚕️ <b>Ограничения по здоровью</b>\n\n"
        f"Выбрано: {summary}\n\n"
        "Нажмите ещё или <b>«Готово»</b>."
    ) if selected else (
        "⚕️ <b>Есть ли ограничения по здоровью?</b>\n\n"
        "Выберите все подходящие.\n"
        "Когда закончите — нажмите <b>«Готово»</b>."
    )

    kb = kb_restrictions_done() if selected else kb_restrictions()
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


# ── Шаг 7b: Ввод своих ограничений текстом ───────────────────────

@router.message(CalcForm.restrictions_detail)
async def set_custom_restriction(m: Message, state: FSMContext):
    data = await state.get_data()
    selected: list = data.get("restrictions", [])
    selected.append(m.text.strip())
    await state.update_data(restrictions=selected)
    await state.set_state(CalcForm.restrictions)

    summary = _format_selected_restrictions(selected)
    await m.answer(
        f"⚕️ <b>Ограничения по здоровью</b>\n\n"
        f"Выбрано: {summary}\n\n"
        "Добавьте ещё или нажмите <b>«Готово»</b>.",
        parse_mode="HTML",
        reply_markup=kb_restrictions_done(),
    )


# ── Шаг 8: Предпочтения по продуктам ─────────────────────────────

async def _ask_food_prefs(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    restrictions = data.get("restrictions", [])
    summary = _format_selected_restrictions(restrictions) if restrictions else "нет"
    await cb.message.edit_text(f"Ограничения: {summary} ✓")

    await state.update_data(food_prefs=[])
    await state.set_state(CalcForm.food_prefs)
    await cb.message.answer(
        "🍽 <b>Предпочтения по продуктам</b>\n\n"
        "Выберите, что вы любите и хотите\n"
        "видеть в меню. Нажимайте на кнопки —\n"
        "выбранные отметятся ✅\n\n"
        "Или нажмите <b>«Всё подходит»</b>.",
        parse_mode="HTML",
        reply_markup=kb_food_prefs(),
    )
    await cb.answer()


def _format_food_prefs(selected: list[str]) -> str:
    labels = []
    for p in selected:
        if p in FOOD_PREF_LABELS:
            labels.append(FOOD_PREF_LABELS[p])
        else:
            labels.append(f"✏️ {p}")
    return ", ".join(labels)


@router.callback_query(CalcForm.food_prefs, F.data == "pref:all")
async def food_prefs_all(cb: CallbackQuery, state: FSMContext):
    await state.update_data(food_prefs=["all"])
    await _ask_cuisine(cb, state)


@router.callback_query(CalcForm.food_prefs, F.data == "pref:done")
async def food_prefs_done(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("food_prefs", [])
    await _ask_cuisine(cb, state)


@router.callback_query(CalcForm.food_prefs, F.data == "pref:custom")
async def food_prefs_custom(cb: CallbackQuery, state: FSMContext):
    await state.set_state(CalcForm.food_prefs_custom)
    await cb.message.edit_text(
        "✏️ Напишите ваши предпочтения текстом.\n"
        "<i>Например: люблю индейку, не ем свинину,\n"
        "утром обязательно кофе с молоком</i>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(CalcForm.food_prefs_custom)
async def set_food_prefs_custom(m: Message, state: FSMContext):
    data = await state.get_data()
    selected: list = data.get("food_prefs", [])
    selected.append(m.text.strip())
    await state.update_data(food_prefs=selected)
    await state.set_state(CalcForm.food_prefs)

    summary = _format_food_prefs(selected)
    await m.answer(
        f"🍽 <b>Предпочтения</b>\n\n"
        f"Выбрано: {summary}\n\n"
        "Добавьте ещё или нажмите <b>«Готово»</b>.",
        parse_mode="HTML",
        reply_markup=kb_food_prefs_done(selected),
    )


@router.callback_query(CalcForm.food_prefs, F.data.startswith("pref:"))
async def toggle_food_pref(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":")[1]
    data = await state.get_data()
    selected: list = data.get("food_prefs", [])

    if key in selected:
        selected.remove(key)
    else:
        selected.append(key)

    await state.update_data(food_prefs=selected)

    if selected:
        summary = _format_food_prefs(selected)
        text = (
            f"🍽 <b>Предпочтения</b>\n\n"
            f"Выбрано: {summary}\n\n"
            "Нажмите ещё или <b>«Готово»</b>."
        )
        kb = kb_food_prefs_done(selected)
    else:
        text = (
            "🍽 <b>Предпочтения по продуктам</b>\n\n"
            "Выберите, что вы любите и хотите\n"
            "видеть в меню.\n\n"
            "Или нажмите <b>«Всё подходит»</b>."
        )
        kb = kb_food_prefs(selected)

    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


# ── Шаг 6.5: Предпочитаемая кухня ─────────────────────────────────

async def _ask_cuisine(cb: CallbackQuery, state: FSMContext):
    await state.set_state(CalcForm.cuisine)
    await cb.message.answer(
        "🍽 <b>Предпочитаемая кухня</b>\n\n"
        "Выберите одну или несколько кухонь.\n"
        "Меню будет составлено с акцентом\n"
        "на блюда выбранных кухонь.",
        parse_mode="HTML",
        reply_markup=kb_cuisine(),
    )
    await cb.answer()


@router.callback_query(CalcForm.cuisine, F.data == "cuisine:any")
async def cuisine_any(cb: CallbackQuery, state: FSMContext):
    await state.update_data(cuisine=["any"])
    data = await state.get_data()
    prefs = data.get("food_prefs", [])
    summary = _format_food_prefs(prefs) if prefs and prefs != ["all"] else "всё подходит"
    await _show_kbju(cb, state, prefs_summary=summary)


@router.callback_query(CalcForm.cuisine, F.data == "cuisine:done")
async def cuisine_done(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("cuisine", [])
    prefs = data.get("food_prefs", [])
    summary = _format_food_prefs(prefs) if prefs and prefs != ["all"] else "всё подходит"
    await _show_kbju(cb, state, prefs_summary=summary)


@router.callback_query(CalcForm.cuisine, F.data == "cuisine:custom")
async def cuisine_custom(cb: CallbackQuery, state: FSMContext):
    await state.set_state(CalcForm.cuisine_custom)
    await cb.message.edit_text(
        "✏️ Напишите предпочитаемую кухню.\n"
        "<i>Например: узбекская, мексиканская,\n"
        "средиземноморская</i>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(CalcForm.cuisine_custom)
async def set_cuisine_custom(m: Message, state: FSMContext):
    data = await state.get_data()
    selected: list = data.get("cuisine", [])
    selected.append(m.text.strip())
    await state.update_data(cuisine=selected)
    await state.set_state(CalcForm.cuisine)
    labels = [CUISINE_LABELS.get(c, c) for c in selected]
    await m.answer(
        f"🍽 <b>Кухня</b>\n\nВыбрано: {', '.join(labels)}\n\n"
        "Добавьте ещё или нажмите <b>«Готово»</b>.",
        parse_mode="HTML",
        reply_markup=kb_cuisine_done(selected),
    )


@router.callback_query(CalcForm.cuisine, F.data.startswith("cuisine:"))
async def toggle_cuisine(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":")[1]
    data = await state.get_data()
    selected: list = data.get("cuisine", [])
    if key in selected:
        selected.remove(key)
    else:
        selected.append(key)
    await state.update_data(cuisine=selected)

    if selected:
        await cb.message.edit_reply_markup(reply_markup=kb_cuisine_done(selected))
    else:
        await cb.message.edit_reply_markup(reply_markup=kb_cuisine())
    await cb.answer()


# ── Показ КБЖУ ───────────────────────────────────────────────────

async def _show_kbju(cb: CallbackQuery, state: FSMContext, prefs_summary: str = ""):
    data = await state.get_data()
    restrictions = data.get("restrictions", [])
    goal_weight = data.get("goal_weight")
    food_prefs = data.get("food_prefs", [])
    cuisine = data.get("cuisine", [])

    cuisine_labels = [CUISINE_LABELS.get(c, c) for c in cuisine if c != "any"]
    cuisine_text = ", ".join(cuisine_labels) if cuisine_labels else "любая"
    await cb.message.edit_text(f"Кухня: {cuisine_text} ✓")

    result = compute_kbju(
        height_cm=data["height"],
        weight_kg=data["weight"],
        age=data["age"],
        gender=data["gender"],
        activity_level=data["activity"],
        target=data["target"],
    )

    await state.update_data(kbju=result.__dict__)

    await save_profile(
        user_id=cb.from_user.id,
        gender=data["gender"],
        height_cm=data["height"],
        weight_kg=data["weight"],
        age=data["age"],
        activity=data["activity"],
        target=data["target"],
        restrictions=restrictions,
        soup_pref=True,
        calories=result.calories,
        protein_g=result.protein_g,
        fat_g=result.fat_g,
        carbs_g=result.carbs_g,
        goal_weight=goal_weight,
        food_prefs=food_prefs,
        cuisine=cuisine,
    )

    restr_summary = _format_selected_restrictions(restrictions) if restrictions else "нет"
    gender_icon = "👨" if data["gender"] == "male" else "👩"

    text = (
        f"  {gender_icon}  {GENDER_LABEL[data['gender']]}  ·  {int(data['height'])} см\n"
        f"  ⚖️  {data['weight']} кг  ·  {data['age']} лет\n"
        f"  🎯  {TARGET_LABEL[data['target']]}\n"
    )

    if goal_weight:
        text += f"  🏁  Желаемый вес: {goal_weight} кг\n"

    if restrictions:
        text += f"  ⚕️  {restr_summary}\n"

    if prefs_summary and prefs_summary != "всё подходит":
        text += f"  🍽  {prefs_summary}\n"

    if cuisine_labels:
        text += f"  🌍  {', '.join(cuisine_labels)}\n"

    text += (
        "\n"
        "╔═══════════════════════╗\n"
        "║  📊  <b>ВАШИ ОРИЕНТИРЫ</b>          ║\n"
        "╠═══════════════════════╣\n"
        "║                                              ║\n"
        f"║  🔥  <b>{result.calories}</b> ккал                  ║\n"
        "║                                              ║\n"
        f"║  🥩  Белки         <b>{result.protein_g}</b> г         ║\n"
        f"║  🧈  Жиры          <b>{result.fat_g}</b> г         ║\n"
        f"║  🍞  Углеводы   <b>{result.carbs_g}</b> г         ║\n"
        "║                                              ║\n"
        "╚═══════════════════════╝\n"
        "\n"
        "<i>Хотите примерное меню на 3 дня?</i>"
    )

    await state.set_state(CalcForm.soup_pref)
    await cb.message.answer(text, parse_mode="HTML", reply_markup=kb_soup_pref())
    await cb.answer()


# ── Шаг 8: Супы ──────────────────────────────────────────────────

@router.callback_query(CalcForm.soup_pref, F.data.startswith("soup:"))
async def set_soup_pref(cb: CallbackQuery, state: FSMContext):
    wants_soup = cb.data.split(":")[1] == "yes"
    await state.update_data(wants_soup=wants_soup)

    label = "🥣 С супами" if wants_soup else "🚫 Без супов"
    await cb.message.edit_text(
        f"{label} ✓\n\n"
        "<i>Хотите примерное меню на 3 дня?</i>",
        parse_mode="HTML",
        reply_markup=kb_menu_confirm(),
    )
    await state.set_state(CalcForm.menu_confirm)
    await cb.answer()


# ── Генерация меню ────────────────────────────────────────────────

@router.callback_query(CalcForm.menu_confirm, F.data == "menu:yes")
async def generate_menu(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    kbju = data["kbju"]
    restrictions = data.get("restrictions", [])
    food_prefs = data.get("food_prefs", [])
    wants_soup = data.get("wants_soup", True)
    await state.clear()

    await cb.message.edit_reply_markup(reply_markup=None)
    wait_msg = await cb.message.answer("⏳ Составляю меню, это займёт ~15 секунд...")
    await cb.answer()

    restrictions_text = _format_selected_restrictions(restrictions) if restrictions else "нет"
    prefs_text = _build_prefs_prompt(food_prefs)
    cuisine_text = _build_cuisine_prompt(data.get("cuisine", []))

    system_prompt = (MENU_SYSTEM_SOUP if wants_soup else MENU_SYSTEM_NO_SOUP).format(
        plan_duration=3,
    )
    user_prompt = (
        f"Дневной ориентир: {kbju['calories']} ккал, "
        f"Б {kbju['protein_g']} г, Ж {kbju['fat_g']} г, У {kbju['carbs_g']} г.\n"
        f"Пол: {GENDER_LABEL[data['gender']]}, "
        f"возраст {data['age']}, вес {data['weight']} кг.\n"
        f"Ограничения по здоровью: {restrictions_text}.\n"
        f"{cuisine_text}"
        f"{prefs_text}"
    )

    menu_text = await chat_completion(
        system=system_prompt, user=user_prompt,
        user_id=cb.from_user.id, action="menu_generate",
    )

    await save_menu(
        cb.from_user.id,
        kbju["calories"],
        kbju["protein_g"],
        kbju["fat_g"],
        kbju["carbs_g"],
        menu_text,
    )

    await wait_msg.delete()

    standard = await has_standard_access(cb.from_user.id)
    kb = kb_after_menu(has_premium=standard)
    if len(menu_text) <= 4096:
        await cb.message.answer(menu_text, reply_markup=kb)
    else:
        chunks = [menu_text[i : i + 4096] for i in range(0, len(menu_text), 4096)]
        for i, chunk in enumerate(chunks):
            markup = kb if i == len(chunks) - 1 else None
            await cb.message.answer(chunk, reply_markup=markup)


@router.callback_query(CalcForm.menu_confirm, F.data == "menu:no")
async def skip_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(
        "Хорошо! Если что — я здесь 👇",
        reply_markup=await _kb(cb.from_user.id),
    )
    await cb.answer()


# ── Обновить меню (на следующие 3 дня) ──────────────────────────

@router.callback_query(F.data == "main:renew_menu")
async def renew_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    profile = await get_profile(uid)

    if not profile:
        await cb.answer("Сначала рассчитайте ориентир 📊", show_alert=True)
        return

    if not (await is_subscribed(uid) or await is_whitelisted(uid)):
        await cb.answer(
            "Обновление меню доступно подписчикам.\n"
            "Нажмите «✨ Подписаться» в главном меню.",
            show_alert=True,
        )
        return

    days = await days_since_last_menu(uid)
    if days is not None and days < MENU_PERIOD:
        left = MENU_PERIOD - days
        word = "день" if left == 1 else ("дня" if left in (2, 3, 4) else "дней")
        await cb.answer(
            f"⏳ Текущее меню ещё действует.\n"
            f"Новое будет доступно через {left} {word}.",
            show_alert=True,
        )
        return

    await cb.message.edit_reply_markup(reply_markup=None)
    wait_msg = await cb.message.answer("⏳ Составляю новое меню на 3 дня...")
    await cb.answer()

    latest_weight = await get_latest_weight(uid)
    current_weight = latest_weight if latest_weight else profile["weight_kg"]

    if current_weight != profile["weight_kg"]:
        result = compute_kbju(
            height_cm=profile["height_cm"],
            weight_kg=current_weight,
            age=profile["age"],
            gender=profile["gender"],
            activity_level=profile["activity"],
            target=profile["target"],
        )
        calories, protein_g, fat_g, carbs_g = (
            result.calories, result.protein_g, result.fat_g, result.carbs_g,
        )
        await save_profile(
            user_id=uid,
            gender=profile["gender"],
            height_cm=profile["height_cm"],
            weight_kg=current_weight,
            age=profile["age"],
            activity=profile["activity"],
            target=profile["target"],
            restrictions=profile.get("restrictions", []),
            soup_pref=profile.get("soup_pref", True),
            calories=calories,
            protein_g=protein_g,
            fat_g=fat_g,
            carbs_g=carbs_g,
            goal_weight=profile.get("goal_weight"),
            food_prefs=profile.get("food_prefs", []),
            cuisine=profile.get("cuisine", []),
        )
    else:
        calories = profile["calories"]
        protein_g = profile["protein_g"]
        fat_g = profile["fat_g"]
        carbs_g = profile["carbs_g"]

    restrictions = profile.get("restrictions", [])
    restrictions_text = _format_selected_restrictions(restrictions) if restrictions else "нет"
    food_prefs = profile.get("food_prefs", [])
    prefs_text = _build_prefs_prompt(food_prefs)
    cuisine = profile.get("cuisine", [])
    cuisine_text = _build_cuisine_prompt(cuisine if isinstance(cuisine, list) else [])
    wants_soup = profile.get("soup_pref", True)

    system_prompt = (MENU_SYSTEM_SOUP if wants_soup else MENU_SYSTEM_NO_SOUP).format(
        plan_duration=3,
    )

    user_prompt = (
        f"Дневной ориентир: {calories} ккал, "
        f"Б {protein_g} г, Ж {fat_g} г, У {carbs_g} г.\n"
        f"Пол: {GENDER_LABEL[profile['gender']]}, "
        f"возраст {profile['age']}, вес {current_weight} кг.\n"
        f"Ограничения по здоровью: {restrictions_text}.\n"
        f"{cuisine_text}"
        f"{prefs_text}\n"
        "ВАЖНО: составьте НОВОЕ меню, с другими блюдами. Разнообразие важно!"
    )

    menu_text = await chat_completion(
        system=system_prompt, user=user_prompt,
        user_id=uid, action="menu_renew",
    )

    await save_menu(uid, calories, protein_g, fat_g, carbs_g, menu_text)

    await wait_msg.delete()

    total = await get_menu_count(uid)

    weight_note = ""
    if latest_weight and latest_weight != profile["weight_kg"]:
        diff = latest_weight - profile["weight_kg"]
        sign = "+" if diff > 0 else ""
        weight_note = (
            f"⚖️ Вес обновлён: <b>{current_weight}</b> кг ({sign}{diff:.1f})\n"
            f"🔥 Новый ориентир: <b>{calories}</b> ккал "
            f"(Б {protein_g} / Ж {fat_g} / У {carbs_g})\n"
        )

    header = (
        "🔄 <b>Новое меню готово!</b>\n"
        f"{weight_note}"
        f"📋 Всего меню составлено: {total}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    full_text = header + menu_text
    standard = await has_standard_access(uid)
    kb = kb_after_menu(has_premium=standard)

    if len(full_text) <= 4096:
        await cb.message.answer(full_text, parse_mode="HTML", reply_markup=kb)
    else:
        chunks = [full_text[i : i + 4096] for i in range(0, len(full_text), 4096)]
        for i, chunk in enumerate(chunks):
            markup = kb if i == len(chunks) - 1 else None
            pm = "HTML" if i == 0 else None
            await cb.message.answer(chunk, parse_mode=pm, reply_markup=markup)


# ── Скачать меню ─────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities for plain-text export."""
    import re
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text


def _make_html_doc(title: str, header_info: str, body_html: str) -> str:
    """Wrap content in a styled HTML document for nice viewing."""
    return (
        "<!DOCTYPE html>\n<html><head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        "<style>\n"
        "  body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 700px;\n"
        "         margin: 30px auto; padding: 0 20px; line-height: 1.6;\n"
        "         color: #333; background: #fafafa; }\n"
        "  h1 { color: #2d6a4f; border-bottom: 2px solid #2d6a4f; padding-bottom: 8px; }\n"
        "  .info { background: #e8f5e9; padding: 12px 16px; border-radius: 8px;\n"
        "          margin-bottom: 20px; font-size: 14px; }\n"
        "  .content { background: #fff; padding: 20px; border-radius: 8px;\n"
        "             box-shadow: 0 1px 3px rgba(0,0,0,0.1); white-space: pre-wrap; }\n"
        "</style>\n</head><body>\n"
        f"<h1>{title}</h1>\n"
        f'<div class="info">{header_info}</div>\n'
        f'<div class="content">{body_html}</div>\n'
        "</body></html>"
    )


@router.callback_query(F.data == "menu:download")
async def download_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    standard = await has_standard_access(uid)
    if not standard:
        await cb.answer("📥 Скачивание доступно по подписке / VIP", show_alert=True)
        return

    last = await get_last_menu(uid)
    if not last or not last.get("menu_text"):
        await cb.answer("Меню не найдено. Сначала сгенерируйте.", show_alert=True)
        return

    menu_text = last["menu_text"]
    date_str = last["created_at"][:10]
    header_info = (
        f"Ориентир: {last['calories']} ккал "
        f"(Б {last['protein_g']} / Ж {last['fat_g']} / У {last['carbs_g']})<br>"
        f"Дата: {date_str}"
    )

    html = _make_html_doc("FORMA — Меню на 3 дня", header_info, menu_text)
    file_bytes = html.encode("utf-8")
    doc = BufferedInputFile(file_bytes, filename=f"forma_menu_{date_str}.html")
    await cb.message.answer_document(doc, caption="📥 Ваше меню FORMA\n<i>Откройте в браузере</i>", parse_mode="HTML")
    await cb.answer()


# ── Рецепт блюда ────────────────────────────────────────────────

@router.callback_query(F.data == "menu:recipe")
async def ask_recipe(cb: CallbackQuery, state: FSMContext):
    await state.set_state(RecipeForm.dish_name)
    await cb.message.answer(
        "👨‍🍳 <b>Рецепт блюда</b>\n\n"
        "Скопируйте из меню название\n"
        "нужного блюда целиком\n"
        "и вставьте сюда.\n\n"
        "Я дам подробный рецепт\n"
        "со всеми ингредиентами:\n"
        "специи, масло, соусы и т.д.",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(RecipeForm.dish_name)
async def generate_recipe(m: Message, state: FSMContext):
    dish = m.text.strip() if m.text else ""
    if not dish:
        await m.answer("Введите название блюда.")
        return

    await state.clear()
    wait_msg = await m.answer("👨‍🍳 Готовлю рецепт...")

    profile = await get_profile(m.from_user.id)
    restrictions_hint = ""
    if profile:
        restrictions = profile.get("restrictions", [])
        if restrictions:
            from app.keyboards import RESTRICTION_LABELS
            labels = [RESTRICTION_LABELS.get(r, r) for r in restrictions]
            restrictions_hint = f"\nУ пользователя ограничения: {', '.join(labels)}. Учтите их в рецепте."

    recipe = await chat_completion(
        system=RECIPE_SYSTEM,
        user=f"Рецепт блюда: {dish}{restrictions_hint}",
        user_id=m.from_user.id, action="recipe",
    )

    await wait_msg.delete()

    await state.update_data(last_recipe=recipe, last_recipe_dish=dish)

    standard = await has_standard_access(m.from_user.id)
    kb = kb_after_recipe(has_premium=standard)

    if len(recipe) <= 4096:
        await m.answer(recipe, parse_mode="HTML", reply_markup=kb)
    else:
        chunks = [recipe[i : i + 4096] for i in range(0, len(recipe), 4096)]
        for i, chunk in enumerate(chunks):
            markup = kb if i == len(chunks) - 1 else None
            await m.answer(chunk, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "recipe:download")
async def download_recipe(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    standard = await has_standard_access(uid)
    if not standard:
        await cb.answer("📥 Скачивание доступно по подписке", show_alert=True)
        return

    data = await state.get_data()
    recipe_text = data.get("last_recipe")
    dish_name = data.get("last_recipe_dish", "рецепт")

    if not recipe_text:
        await cb.answer("Рецепт не найден. Запросите новый.", show_alert=True)
        return

    html = _make_html_doc(
        f"FORMA — Рецепт: {dish_name}",
        f"Блюдо: {dish_name}",
        recipe_text,
    )
    file_bytes = html.encode("utf-8")
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in dish_name)[:40]
    doc = BufferedInputFile(file_bytes, filename=f"forma_recipe_{safe_name}.html")
    await cb.message.answer_document(doc, caption="📥 Рецепт FORMA\n<i>Откройте в браузере</i>", parse_mode="HTML")
    await cb.answer()
