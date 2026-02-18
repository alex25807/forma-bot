"""Admin commands & VIP invite system."""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from app.config import settings
from app.services.database import (
    a_add_to_whitelist as add_to_whitelist,
    a_is_whitelisted as is_whitelisted,
    a_add_subscriber as add_subscriber,
    a_is_subscribed as is_subscribed,
    a_get_all_reviews as get_all_reviews,
    a_get_review_count as get_review_count,
    _conn,
)

logger = logging.getLogger(__name__)

router = Router()


def _is_admin(user_id: int) -> bool:
    return settings.ADMIN_ID != 0 and user_id == settings.ADMIN_ID


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
        "Нажмите /start чтобы начать 👇",
        parse_mode="HTML",
    )
    logger.info("VIP code redeemed by user %s (%s)", uid, m.from_user.first_name)


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
