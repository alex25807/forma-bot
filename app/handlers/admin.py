"""Admin commands & VIP invite system."""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.config import settings
from app.services.database import (
    a_add_to_whitelist as add_to_whitelist,
    a_is_whitelisted as is_whitelisted,
    a_add_subscriber as add_subscriber,
    a_is_subscribed as is_subscribed,
    a_get_all_reviews as get_all_reviews,
    a_get_review_count as get_review_count,
    a_delete_user_data as delete_user_data,
    a_get_api_stats as get_api_stats,
    a_get_growth_funnel as get_growth_funnel,
    a_get_d1_reactivation_candidates as get_d1_reactivation_candidates,
    a_log_growth_event as log_growth_event,
    _conn,
)

logger = logging.getLogger(__name__)

router = Router()


def _is_admin(user_id: int) -> bool:
    return settings.ADMIN_ID != 0 and user_id == settings.ADMIN_ID


async def _can_use_growth(user_id: int) -> bool:
    if _is_admin(user_id):
        return True
    return await is_whitelisted(user_id)


# ── /myid — любой пользователь узнаёт свой ID ───────────────────

@router.message(Command("myid"))
async def my_id(m: Message):
    await m.answer(
        f"🆔 Ваш Telegram ID:\n\n"
        f"<code>{m.from_user.id}</code>\n\n"
        "<i>Нажмите на число, чтобы скопировать</i>",
        parse_mode="HTML",
    )


# ── /addvip — админ добавляет в whitelist ────────────────────────

@router.message(Command("addvip"))
async def add_vip(m: Message):
    if not _is_admin(m.from_user.id):
        await m.answer("⛔ Эта команда доступна только администратору.")
        return

    # /addvip 123456789 Имя (опционально)
    parts = m.text.split(maxsplit=2)
    if len(parts) < 2:
        await m.answer(
            "Использование:\n"
            "<code>/addvip 123456789</code>\n"
            "<code>/addvip 123456789 Имя друга</code>\n\n"
            "Или перешлите мне сообщение от пользователя\n"
            "и ответьте на него командой /addvip",
            parse_mode="HTML",
        )
        return

    try:
        vip_id = int(parts[1])
    except ValueError:
        await m.answer("❌ Неверный ID. Используйте число.")
        return

    note = parts[2] if len(parts) > 2 else ""
    await add_to_whitelist(vip_id, str(m.from_user.id), note)

    status = "✅ уже был" if await is_whitelisted(vip_id) else "✅"
    await m.answer(
        f"✅ Пользователь <code>{vip_id}</code> добавлен в VIP-список\n"
        f"{f'Заметка: {note}' if note else ''}",
        parse_mode="HTML",
    )


# ── /addvip на reply к пересланному сообщению ────────────────────

@router.message(Command("addvip"), F.reply_to_message)
async def add_vip_reply(m: Message):
    if not _is_admin(m.from_user.id):
        await m.answer("⛔ Эта команда доступна только администратору.")
        return

    reply = m.reply_to_message
    if reply.forward_from:
        vip_id = reply.forward_from.id
        name = reply.forward_from.first_name or ""
    else:
        vip_id = reply.from_user.id
        name = reply.from_user.first_name or ""

    await add_to_whitelist(vip_id, str(m.from_user.id), name)
    await m.answer(
        f"✅ {name} (<code>{vip_id}</code>) добавлен в VIP-список",
        parse_mode="HTML",
    )


# ── /viplist — список VIP-пользователей ──────────────────────────

@router.message(Command("viplist"))
async def vip_list(m: Message):
    if not _is_admin(m.from_user.id):
        await m.answer("⛔ Эта команда доступна только администратору.")
        return

    import asyncio, sqlite3
    def _fetch_vips():
        conn = _conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM whitelist ORDER BY added_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    rows = await asyncio.to_thread(_fetch_vips)

    if not rows:
        await m.answer("VIP-список пуст.")
        return

    lines = ["📋 <b>VIP-список:</b>\n"]
    for r in rows:
        note = f" — {r['note']}" if r.get("note") else ""
        lines.append(f"  • <code>{r['user_id']}</code>{note}  ({r['added_at'][:10]})")

    await m.answer("\n".join(lines), parse_mode="HTML")


# ── /removevip — удалить из whitelist ────────────────────────────

@router.message(Command("removevip"))
async def remove_vip(m: Message):
    if not _is_admin(m.from_user.id):
        await m.answer("⛔ Эта команда доступна только администратору.")
        return

    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        await m.answer("Использование: <code>/removevip 123456789</code>", parse_mode="HTML")
        return

    try:
        vip_id = int(parts[1])
    except ValueError:
        await m.answer("❌ Неверный ID.")
        return

    import asyncio
    def _del_vip():
        conn = _conn()
        conn.execute("DELETE FROM whitelist WHERE user_id = ?", (vip_id,))
        conn.close()
    await asyncio.to_thread(_del_vip)

    await m.answer(f"🗑 Пользователь <code>{vip_id}</code> удалён из VIP-списка.", parse_mode="HTML")


# ── VIP-код (инвайт) — пользователь вводит код и получает доступ ─

@router.message(F.text == settings.VIP_CODE)
async def redeem_vip_code(m: Message):
    if settings.VIP_CODE == "":
        return

    uid = m.from_user.id

    if await is_whitelisted(uid):
        await m.answer("Вы уже в VIP-списке ✅")
        return

    await add_to_whitelist(uid, "invite_code", m.from_user.first_name or "")

    if not await is_subscribed(uid):
        await add_subscriber(uid, m.from_user.username, m.from_user.first_name)

    await m.answer(
        "🎉 <b>Добро пожаловать в VIP!</b>\n\n"
        "Вам доступны все функции FORMA\n"
        "без ограничений:\n\n"
        "  ✅  Безлимитные меню\n"
        "  ✅  Графики и экспорт\n"
        "  ✅  Полное сопровождение\n\n"
        "Вернитесь в главное меню и выберите действие 👇",
        parse_mode="HTML",
    )
    logger.info("VIP code redeemed by user %s (%s)", uid, m.from_user.first_name)


# ── /stats — финансовая статистика ─────────────────────────────

@router.message(Command("stats"))
async def show_stats(m: Message):
    if not _is_admin(m.from_user.id):
        await m.answer("⛔ Эта команда доступна только администратору.")
        return

    s = await get_api_stats()
    plans = s.get("plans", {})
    plans_text = "\n".join(
        f"    {p}: {c}" for p, c in sorted(plans.items())
    ) or "    нет данных"
    text = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "  📊 <b>FORMA — Статистика</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 <b>Пользователи</b>\n"
        f"  Подписчиков: {s['subscribers']}\n"
        f"  С профилем: {s['profiles']}\n"
        f"  VIP: {s['vip']}\n"
        f"  Согласий: {s['consents']}\n\n"
        "💎 <b>Тарифы</b>\n"
        f"{plans_text}\n\n"
        "📋 <b>Контент</b>\n"
        f"  Меню сгенерировано: {s['menus_total']}\n"
        f"  Рецептов выдано: {s['recipes_total']}\n"
        f"  Тренировок: {s['fitness_total']} (выполнено: {s['fitness_done']})\n\n"
        "🤖 <b>API за всё время</b>\n"
        f"  Вызовов: {s['total_calls']}\n"
        f"  Токенов: {s['total_tokens_in'] + s['total_tokens_out']:,}\n"
        f"  Расход: ${s['total_cost']:.4f}\n\n"
        "📅 <b>За текущий месяц</b>\n"
        f"  Вызовов: {s['month_calls']}\n"
        f"  Расход: ${s['month_cost']:.4f}\n\n"
        "📆 <b>За сегодня</b>\n"
        f"  Вызовов: {s['today_calls']}\n"
        f"  Расход: ${s['today_cost']:.4f}\n"
    )
    await m.answer(text, parse_mode="HTML")


@router.message(F.text.regexp(r"^/growth(@\w+)?$"))
async def show_growth(m: Message):
    if not await _can_use_growth(m.from_user.id):
        await m.answer("⛔ Эта команда доступна только администратору.")
        return

    try:
        f = await get_growth_funnel(7)
    except Exception as e:
        logger.exception("Growth command failed: %s", e)
        await m.answer("⚠️ Не удалось собрать growth-отчёт. Попробуйте ещё раз через минуту.")
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


@router.message(Command("reactivate_d1"))
async def reactivate_d1(m: Message):
    if not await _can_use_growth(m.from_user.id):
        await m.answer("⛔ Эта команда доступна только администратору.")
        return

    uids = await get_d1_reactivation_candidates(limit=200)
    if not uids:
        await m.answer("Кандидатов для D1-реактивации не найдено.")
        return

    sent = 0
    failed = 0
    text = (
        "👋 Небольшое напоминание от FORMA\n\n"
        "Если хотите — продолжим мягко и без стресса.\n"
        "Нажмите «↩️ Возврат в главное меню» и я подскажу следующий шаг."
    )
    for uid in uids:
        try:
            await m.bot.send_message(uid, text)
            await log_growth_event(uid, "d1_reactivation_sent")
            sent += 1
        except Exception:
            failed += 1

    await m.answer(
        f"✅ D1-реактивация завершена.\n"
        f"Отправлено: <b>{sent}</b>\n"
        f"Ошибок: <b>{failed}</b>",
        parse_mode="HTML",
    )


# ── /reviews — админ просматривает отзывы ────────────────────────

@router.message(Command("reviews"))
async def show_reviews(m: Message):
    if not _is_admin(m.from_user.id):
        await m.answer("⛔ Эта команда доступна только администратору.")
        return

    total = await get_review_count()
    reviews = await get_all_reviews(20)

    if not reviews:
        await m.answer("Отзывов пока нет.")
        return

    lines = [f"📝 <b>Отзывы ({total} всего)</b>\n"]

    for r in reviews:
        name = r.get("first_name") or "—"
        user = f"@{r['username']}" if r.get("username") else f"id:{r['user_id']}"
        dt = r["created_at"][:10]
        text = r["text"]
        if len(text) > 1000:
            text = text[:1000] + "…"
        lines.append(
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {name} ({user})\n"
            f"📅 {dt}\n"
            f"💬 {text}"
        )

    full = "\n".join(lines)
    if len(full) > 4096:
        chunks = [full[i : i + 4096] for i in range(0, len(full), 4096)]
        for chunk in chunks:
            await m.answer(chunk, parse_mode="HTML")
    else:
        await m.answer(full, parse_mode="HTML")


# ── /deletedata — удаление персональных данных (152-ФЗ) ──────────

@router.message(Command("deletedata"))
async def ask_delete_data(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Да, удалить все данные", callback_data="data:confirm_delete")],
        [InlineKeyboardButton(text="↩️ Отмена", callback_data="data:cancel_delete")],
    ])
    await m.answer(
        "⚠️ <b>Удаление персональных данных</b>\n\n"
        "Будут удалены:\n"
        "  • Профиль (пол, рост, вес, возраст)\n"
        "  • История веса\n"
        "  • Дневник питания\n"
        "  • Все сгенерированные меню\n"
        "  • Подписка и VIP-статус\n"
        "  • Отзывы\n"
        "  • Согласие на обработку\n\n"
        "<b>Это действие необратимо.</b>\n"
        "Вы уверены?",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data == "data:confirm_delete")
async def confirm_delete(cb: CallbackQuery):
    await delete_user_data(cb.from_user.id)
    await cb.message.edit_text(
        "✅ Все ваши данные удалены.\n\n"
        "Спасибо, что пользовались FORMA.\n"
        "Если захотите вернуться — просто откройте главное меню и выберите действие 👇",
    )
    await cb.answer()
    logger.info("User %s requested data deletion", cb.from_user.id)


@router.callback_query(F.data == "data:cancel_delete")
async def cancel_delete(cb: CallbackQuery):
    await cb.message.edit_text("Удаление отменено. Ваши данные на месте ✓")
    await cb.answer()
