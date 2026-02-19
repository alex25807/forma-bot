from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)


# ── Главное меню ──────────────────────────────────────────────────

def kb_start(
    subscribed: bool = False,
    has_profile: bool = False,
    can_renew: bool = False,
    plan: str = "free",
):
    rows = [
        [InlineKeyboardButton(text="ℹ️ Как это работает", callback_data="main:info")],
        [InlineKeyboardButton(text="💬 Поддержка сегодня", callback_data="main:support")],
        [InlineKeyboardButton(text="📝 Разобрать день", callback_data="main:review")],
        [InlineKeyboardButton(text="📊 Рассчитать ориентир", callback_data="main:calc")],
    ]
    if can_renew:
        rows.append([InlineKeyboardButton(text="🔄 Обновить меню на 3 дня", callback_data="main:renew_menu")])
    if has_profile:
        rows.append([
            InlineKeyboardButton(text="📈 Мой прогресс", callback_data="main:progress"),
            InlineKeyboardButton(text="⚖️ Обновить вес", callback_data="main:weight"),
        ])
    if plan == "premium":
        rows.append([InlineKeyboardButton(text="📷 Анализ фото еды", callback_data="main:photo")])
    rows.append([InlineKeyboardButton(text="✍️ Отзыв", callback_data="main:review_send")])
    if plan in ("standard", "premium"):
        label = "Стандарт" if plan == "standard" else "Премиум"
        rows.append([InlineKeyboardButton(text=f"✅ {label}", callback_data="main:subscribed_info")])
    elif subscribed:
        rows.append([InlineKeyboardButton(text="💎 Тарифы", callback_data="pay:choose")])
    else:
        rows.append([InlineKeyboardButton(text="✨ Подписаться", callback_data="main:subscribe")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Согласие на обработку данных ──────────────────────────────────

def kb_consent():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="consent:policy")],
        [InlineKeyboardButton(text="✅ Принимаю", callback_data="consent:accept")],
    ])


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
        [InlineKeyboardButton(text="➡️ Готово, продолжить", callback_data="restr:done")],
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
    "tvorog": "🧀 Творог/йогурт",
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
        [("kefir", "🥛 Кефир"), ("tvorog", "🧀 Творог"), ("milk", "🥛 Молоко")],
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
    rows.append([InlineKeyboardButton(text="➡️ Готово, продолжить", callback_data="pref:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Опрос: супы в меню? ──────────────────────────────────────────

def kb_soup_pref():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥣 Да, с супами", callback_data="soup:yes")],
        [InlineKeyboardButton(text="🚫 Нет, без супов", callback_data="soup:no")],
    ])


# ── Подтверждение меню ────────────────────────────────────────────

def kb_menu_confirm():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Составить меню на 3 дня", callback_data="menu:yes")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu:no")],
    ])


def kb_after_menu(has_premium: bool = False):
    """Keyboard shown right after menu generation."""
    rows = [
        [InlineKeyboardButton(text="👨‍🍳 Получить рецепт", callback_data="menu:recipe")],
    ]
    if has_premium:
        rows.append([InlineKeyboardButton(text="📥 Скачать меню", callback_data="menu:download")])
    rows.append([InlineKeyboardButton(text="↩️ В главное меню", callback_data="back:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_cancel_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
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


def kb_payment_plans():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔹 Стандарт — 299 ₽/мес", callback_data="pay:plan:standard")],
        [InlineKeyboardButton(text="🔸 Премиум — 499 ₽/мес", callback_data="pay:plan:premium")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back:menu")],
    ])


remove_kb = ReplyKeyboardRemove()
