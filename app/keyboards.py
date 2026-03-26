from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)


# ── Главное меню ──────────────────────────────────────────────────

def kb_start(
    subscribed: bool = False,
    has_profile: bool = False,
    can_renew: bool = False,
    plan: str = "free",
    newbie_mode: bool = False,
):
    rows = [
        [InlineKeyboardButton(text="📊 Рассчитать ориентир", callback_data="main:calc")],
        [InlineKeyboardButton(text="🎯 Мини-челлендж 3 дня", callback_data="main:challenge")],
        [InlineKeyboardButton(text="ℹ️ Как это работает", callback_data="main:info")],
    ]
    if has_profile:
        rows.append([InlineKeyboardButton(text="☀️ Утренний чек-ин", callback_data="main:support")])
        rows.append([InlineKeyboardButton(text="🌙 Вечерний чек-ин", callback_data="main:review")])
    if can_renew and not newbie_mode:
        rows.append([InlineKeyboardButton(text="🔄 Обновить меню на 3 дня", callback_data="main:renew_menu")])
    if has_profile:
        rows.append([
            InlineKeyboardButton(text="📈 Мой прогресс", callback_data="main:progress"),
            InlineKeyboardButton(text="⚖️ Обновить вес", callback_data="main:weight"),
        ])
    if plan == "premium" and not newbie_mode:
        rows.append([InlineKeyboardButton(text="📷 Анализ фото еды", callback_data="main:photo")])
    if not newbie_mode:
        rows.append([InlineKeyboardButton(text="✍️ Отзыв", callback_data="main:review_send")])
    if plan in ("standard", "premium"):
        label = "Стандарт" if plan == "standard" else "Премиум"
        rows.append([InlineKeyboardButton(text=f"✅ {label}", callback_data="main:subscribed_info")])
        rows.append([InlineKeyboardButton(text="🧪 Проверить оплату", callback_data="pay:choose")])
    elif subscribed:
        rows.append([InlineKeyboardButton(text="💎 Тарифы", callback_data="pay:choose")])
    else:
        rows.append([InlineKeyboardButton(text="✨ Подписаться", callback_data="main:subscribe")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_quick_start():
    """One-tap launcher shown in the input area (one-time)."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Старт")]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажмите «🏠 Старт» для главного меню",
    )


# ── Согласие на обработку данных ──────────────────────────────────

def kb_consent():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="consent:policy")],
        [InlineKeyboardButton(text="✅ Принимаю", callback_data="consent:accept")],
    ])


def kb_photo_camera():
    """Shows a camera button in the input area to send a photo."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📷 Сделать фото блюда", request_photo=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Сфотографируйте блюдо для оценки КБЖУ",
    )


# ── Утреннее состояние ────────────────────────────────────────────

def kb_morning_state():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 Спокойное", callback_data="morning:calm"),
            InlineKeyboardButton(text="😐 Обычное", callback_data="morning:normal"),
        ],
        [InlineKeyboardButton(text="😓 Напряжённое", callback_data="morning:tense")],
        [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
    ])


# ── Вечерний итог ─────────────────────────────────────────────────

def kb_evening_summary():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👍 Всё по ориентиру", callback_data="evening:ok")],
        [InlineKeyboardButton(text="🤔 Были отклонения", callback_data="evening:deviation")],
        [InlineKeyboardButton(text="📝 Написать, что ел(а)", callback_data="evening:write")],
        [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
    ])


# ── Причина отклонения ────────────────────────────────────────────

def kb_deviation_reason():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍽 Голод", callback_data="reason:hunger"),
            InlineKeyboardButton(text="😓 Усталость", callback_data="reason:tired"),
        ],
        [
            InlineKeyboardButton(text="😔 Стресс", callback_data="reason:stress"),
            InlineKeyboardButton(text="🎉 Ситуация", callback_data="reason:social"),
        ],
        [InlineKeyboardButton(text="🤷 Случайно", callback_data="reason:random")],
        [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
    ])


# ── Опрос: пол ───────────────────────────────────────────────────

def kb_gender():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨 Мужской", callback_data="gender:male"),
            InlineKeyboardButton(text="👩 Женский", callback_data="gender:female"),
        ],
        [InlineKeyboardButton(text="✕ Отмена", callback_data="calc:cancel")],
    ])


# ── Опрос: активность ────────────────────────────────────────────

def kb_activity():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛋 Сидячий", callback_data="act:sedentary")],
        [InlineKeyboardButton(text="🚶 Лёгкая", callback_data="act:light")],
        [InlineKeyboardButton(text="🏃 Умеренная", callback_data="act:moderate")],
        [InlineKeyboardButton(text="💪 Высокая", callback_data="act:high")],
        [InlineKeyboardButton(text="🔥 Очень высокая", callback_data="act:very_high")],
        [InlineKeyboardButton(text="✕ Отмена", callback_data="calc:cancel")],
    ])


# ── Опрос: цель ──────────────────────────────────────────────────

def kb_target():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📉 Снижение веса", callback_data="target:cut")],
        [InlineKeyboardButton(text="⚖️ Поддержание", callback_data="target:maintain")],
        [InlineKeyboardButton(text="📈 Набор массы", callback_data="target:gain")],
        [InlineKeyboardButton(text="✕ Отмена", callback_data="calc:cancel")],
    ])


# ── Опрос: желаемый вес ──────────────────────────────────────────

def kb_goal_weight_skip():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏩ Пропустить", callback_data="goal:skip")],
        [InlineKeyboardButton(text="✏️ Исправить данные", callback_data="calc:edit_restart")],
        [InlineKeyboardButton(text="✕ Отмена", callback_data="calc:cancel")],
    ])


# ── Опрос: ограничения ───────────────────────────────────────────

def kb_restrictions():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🩺 Гипертония", callback_data="restr:hypertension")],
        [InlineKeyboardButton(text="💉 Диабет", callback_data="restr:diabetes")],
        [InlineKeyboardButton(text="🫁 Язва / гастрит", callback_data="restr:ulcer")],
        [InlineKeyboardButton(text="🫘 Болезни почек", callback_data="restr:kidney")],
        [InlineKeyboardButton(text="🥛 Непереносимость лактозы", callback_data="restr:lactose")],
        [InlineKeyboardButton(text="🌾 Без глютена", callback_data="restr:gluten")],
        [InlineKeyboardButton(text="✏️ Другое (напишу)", callback_data="restr:custom")],
        [InlineKeyboardButton(text="✅ Нет ограничений", callback_data="restr:none")],
    ])


def kb_restrictions_done():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🩺 Гипертония", callback_data="restr:hypertension")],
        [InlineKeyboardButton(text="💉 Диабет", callback_data="restr:diabetes")],
        [InlineKeyboardButton(text="🫁 Язва / гастрит", callback_data="restr:ulcer")],
        [InlineKeyboardButton(text="🫘 Болезни почек", callback_data="restr:kidney")],
        [InlineKeyboardButton(text="🥛 Непереносимость лактозы", callback_data="restr:lactose")],
        [InlineKeyboardButton(text="🌾 Без глютена", callback_data="restr:gluten")],
        [InlineKeyboardButton(text="✏️ Другое (напишу)", callback_data="restr:custom")],
        [InlineKeyboardButton(text="✅ ГОТОВО", callback_data="restr:done")],
    ])


RESTRICTION_LABELS = {
    "hypertension": "🩺 Гипертония",
    "diabetes": "💉 Диабет",
    "ulcer": "🫁 Язва / гастрит",
    "kidney": "🫘 Болезни почек",
    "lactose": "🥛 Непереносимость лактозы",
    "gluten": "🌾 Без глютена",
}


# ── Опрос: предпочтения по продуктам ────────────────────────────

FOOD_PREF_LABELS = {
    "meat": "🥩 Мясо",
    "poultry": "🐔 Птица",
    "fish": "🐟 Рыба",
    "potato": "🥔 Картофель",
    "pasta": "🍝 Макароны",
    "cereals": "🌾 Крупы",
    "vegs": "🥬 Овощи",
    "fruits": "🍎 Фрукты",
    "coffee": "☕ Кофе",
    "tea": "🍵 Чай",
    "compot": "🧃 Компот/сок",
    "kefir": "🥛 Кефир/ряженка",
    "tvorog": "🥣 Творог/йогурт",
    "milk": "🥛 Молоко",
}


def _pref_rows(selected: list[str]):
    """Build preference button rows with ✅ markers for selected items."""
    all_items = [
        # row 1: proteins
        [("meat", "🥩 Мясо"), ("poultry", "🐔 Птица"), ("fish", "🐟 Рыба")],
        # row 2: sides
        [("potato", "🥔 Картофель"), ("pasta", "🍝 Макароны"), ("cereals", "🌾 Крупы")],
        # row 3: vegs & fruits
        [("vegs", "🥬 Овощи"), ("fruits", "🍎 Фрукты")],
        # row 4: drinks
        [("coffee", "☕ Кофе"), ("tea", "🍵 Чай"), ("compot", "🧃 Сок")],
        # row 5: dairy
        [("kefir", "🥛 Кефир"), ("tvorog", "🥣 Творог"), ("milk", "🥛 Молоко")],
    ]
    rows = []
    for group in all_items:
        row = []
        for key, label in group:
            mark = "✅ " if key in selected else ""
            row.append(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"pref:{key}"))
        rows.append(row)
    return rows


def kb_food_prefs(selected: list[str] | None = None):
    selected = selected or []
    rows = _pref_rows(selected)
    rows.append([InlineKeyboardButton(text="✏️ Другое (напишу)", callback_data="pref:custom")])
    rows.append([InlineKeyboardButton(text="✅ Всё подходит", callback_data="pref:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_food_prefs_done(selected: list[str]):
    rows = _pref_rows(selected)
    rows.append([InlineKeyboardButton(text="✏️ Другое (напишу)", callback_data="pref:custom")])
    rows.append([InlineKeyboardButton(text="✅ ГОТОВО", callback_data="pref:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Опрос: предпочитаемая кухня ──────────────────────────────────

CUISINE_LABELS = {
    "russian": "🇷🇺 Русская",
    "european": "🇪🇺 Европейская",
    "italian": "🇮🇹 Итальянская",
    "greek": "🇬🇷 Греческая",
    "french": "🇫🇷 Французская",
    "asian": "🇯🇵 Азиатская",
    "caucasian": "🇬🇪 Кавказская",
}


def kb_cuisine(selected: list[str] | None = None):
    selected = selected or []
    rows = []
    for key, label in CUISINE_LABELS.items():
        mark = "✅ " if key in selected else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"cuisine:{key}")])
    rows.append([InlineKeyboardButton(text="✏️ Другое (напишу)", callback_data="cuisine:custom")])
    rows.append([InlineKeyboardButton(text="🌍 Любая кухня", callback_data="cuisine:any")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_cuisine_done(selected: list[str]):
    rows = []
    for key, label in CUISINE_LABELS.items():
        mark = "✅ " if key in selected else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"cuisine:{key}")])
    rows.append([InlineKeyboardButton(text="✏️ Другое (напишу)", callback_data="cuisine:custom")])
    rows.append([InlineKeyboardButton(text="✅ ГОТОВО", callback_data="cuisine:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Опрос: супы в меню? ──────────────────────────────────────────

def kb_soup_pref():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥣 Да, с супами", callback_data="soup:yes")],
        [InlineKeyboardButton(text="🚫 Нет, без супов", callback_data="soup:no")],
        [InlineKeyboardButton(text="✏️ Исправить данные", callback_data="calc:edit_restart")],
    ])


# ── Подтверждение меню ────────────────────────────────────────────

def kb_menu_confirm():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Составить меню на 3 дня", callback_data="menu:yes")],
        [InlineKeyboardButton(text="✏️ Исправить данные", callback_data="calc:edit_restart")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu:no")],
    ])


def kb_accelerate():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Да, хочу ускорить", callback_data="accel:yes")],
        [InlineKeyboardButton(text="🙂 Нет, комфортный режим", callback_data="accel:no")],
        [InlineKeyboardButton(text="✕ Отмена", callback_data="calc:cancel")],
    ])


def kb_accelerate_level():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌱 Мягкий старт (~100 ккал/день)", callback_data="accel_level:easy")],
        [InlineKeyboardButton(text="🚶 Умеренно (~160 ккал/день)", callback_data="accel_level:medium")],
        [InlineKeyboardButton(text="💪 Уверенно (~220 ккал/день)", callback_data="accel_level:active")],
        [InlineKeyboardButton(text="✕ Отмена", callback_data="calc:cancel")],
    ])


def kb_after_menu(
    has_standard_access: bool = False,
    show_fitness: bool = False,
    fitness_locked: bool = False,
    show_challenge_continue: bool = False,
):
    """Keyboard shown right after menu generation."""
    rows = [
        [InlineKeyboardButton(text="🎯 Продолжить челлендж", callback_data="main:challenge")] if show_challenge_continue else None,
        [InlineKeyboardButton(text="👨‍🍳 Получить рецепт", callback_data="menu:recipe")],
        [InlineKeyboardButton(text="📝 Разобрать день", callback_data="main:review")],
    ]
    rows = [r for r in rows if r is not None]
    if show_fitness:
        rows.append([InlineKeyboardButton(text="🏃 Упражнения на сегодня", callback_data="main:fitness")])
    elif fitness_locked:
        rows.append([InlineKeyboardButton(text="🔒 Упражнения (подписка)", callback_data="main:fitness_locked")])
    if has_standard_access:
        rows.append([InlineKeyboardButton(text="📥 Скачать меню", callback_data="menu:download")])
    else:
        rows.append([InlineKeyboardButton(text="🔒 Скачать меню (подписка)", callback_data="menu:download_locked")])
    rows.append([InlineKeyboardButton(text="↩️ В главное меню", callback_data="back:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_after_recipe(has_premium: bool = False):
    """Keyboard shown after recipe generation."""
    rows = [
        [InlineKeyboardButton(text="👨‍🍳 Ещё рецепт", callback_data="menu:recipe")],
    ]
    if has_premium:
        rows.append([InlineKeyboardButton(text="📥 Скачать рецепт", callback_data="recipe:download")])
    else:
        rows.append([InlineKeyboardButton(text="🔒 Скачать рецепт (подписка)", callback_data="recipe:download_locked")])
    rows.append([InlineKeyboardButton(text="↩️ В главное меню", callback_data="back:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_cancel_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Исправить данные", callback_data="calc:edit_restart")],
        [InlineKeyboardButton(text="✕ Отмена", callback_data="calc:cancel")],
    ])


# ── Прогресс: подменю ───────────────────────────────────────────

def kb_progress(has_premium: bool = False):
    rows = [
        [InlineKeyboardButton(text="📊 График веса", callback_data="prog:chart")],
    ]
    if has_premium:
        rows.append([
            InlineKeyboardButton(text="💾 Сохранить график", callback_data="prog:save_chart"),
        ])
        rows.append([
            InlineKeyboardButton(text="📥 Скачать историю (Excel)", callback_data="prog:export"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(text="🔒 Скачать историю (подписка)", callback_data="prog:need_premium"),
        ])
    rows.append([InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_fitness_level():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌱 Начинающий", callback_data="fitlvl:beginner")],
        [InlineKeyboardButton(text="🚶 Базовый", callback_data="fitlvl:basic")],
        [InlineKeyboardButton(text="💪 Уверенный", callback_data="fitlvl:confident")],
        [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
    ])


def kb_fitness_done():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сделал(а)!", callback_data="fit:done")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="fit:skip")],
        [InlineKeyboardButton(text="↩️ В меню", callback_data="back:menu")],
    ])


def kb_payment_plans():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔹 Стандарт — 299 ₽/мес", callback_data="pay:plan:standard")],
        [InlineKeyboardButton(text="🔸 Премиум — 499 ₽/мес", callback_data="pay:plan:premium")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back:menu")],
    ])


def kb_post_menu_upsell():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Открыть тарифы", callback_data="pay:choose")],
        [InlineKeyboardButton(text="Позже", callback_data="upsell:later")],
    ])


def kb_locked_offer():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Открыть тарифы", callback_data="pay:choose")],
        [InlineKeyboardButton(text="↩️ Назад в меню", callback_data="back:menu")],
    ])


remove_kb = ReplyKeyboardRemove()
