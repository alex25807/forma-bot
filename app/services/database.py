import asyncio
import json
import sqlite3
import logging
from datetime import datetime, date
from functools import partial
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "forma.db"


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, isolation_level=None, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS subscribers (
            user_id    INTEGER PRIMARY KEY,
            username   TEXT,
            first_name TEXT,
            joined_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS profiles (
            user_id      INTEGER PRIMARY KEY,
            gender       TEXT,
            height_cm    REAL,
            weight_kg    REAL,
            age          INTEGER,
            activity     TEXT,
            target       TEXT,
            goal_weight  REAL,
            restrictions TEXT,
            soup_pref    INTEGER DEFAULT 1,
            calories     INTEGER,
            protein_g    INTEGER,
            fat_g        INTEGER,
            carbs_g      INTEGER,
            updated_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS weight_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            weight_kg REAL NOT NULL,
            logged_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_log (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            log_date         TEXT NOT NULL,
            morning_state    TEXT,
            evening_result   TEXT,
            deviation_reason TEXT,
            food_text        TEXT,
            gpt_review       TEXT,
            logged_at        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS menu_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            calories   INTEGER,
            protein_g  INTEGER,
            fat_g      INTEGER,
            carbs_g    INTEGER,
            menu_text  TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id    INTEGER PRIMARY KEY,
            plan       TEXT NOT NULL DEFAULT 'free',
            expires_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS whitelist (
            user_id    INTEGER PRIMARY KEY,
            added_by   TEXT,
            note       TEXT,
            added_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            username   TEXT,
            first_name TEXT,
            text       TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    # Migrations
    for col, typ in [("goal_weight", "REAL"), ("food_prefs", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE profiles ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
    conn.close()


# ── Subscribers ───────────────────────────────────────────────────

def add_subscriber(user_id: int, username: str | None, first_name: str | None) -> bool:
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO subscribers (user_id, username, first_name, joined_at) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, datetime.now().isoformat()),
        )
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def is_subscribed(user_id: int) -> bool:
    conn = _conn()
    row = conn.execute("SELECT 1 FROM subscribers WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row is not None


def subscriber_count() -> int:
    conn = _conn()
    count = conn.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]
    conn.close()
    return count


# ── Profiles ──────────────────────────────────────────────────────

def save_profile(
    user_id: int,
    gender: str,
    height_cm: float,
    weight_kg: float,
    age: int,
    activity: str,
    target: str,
    restrictions: list[str],
    soup_pref: bool,
    calories: int,
    protein_g: int,
    fat_g: int,
    carbs_g: int,
    goal_weight: float | None = None,
    food_prefs: list[str] | None = None,
):
    conn = _conn()
    conn.execute(
        """
        INSERT INTO profiles
            (user_id, gender, height_cm, weight_kg, age, activity, target,
             goal_weight, restrictions, food_prefs, soup_pref,
             calories, protein_g, fat_g, carbs_g, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            gender=excluded.gender, height_cm=excluded.height_cm,
            weight_kg=excluded.weight_kg, age=excluded.age,
            activity=excluded.activity, target=excluded.target,
            goal_weight=excluded.goal_weight,
            restrictions=excluded.restrictions, food_prefs=excluded.food_prefs,
            soup_pref=excluded.soup_pref,
            calories=excluded.calories, protein_g=excluded.protein_g,
            fat_g=excluded.fat_g, carbs_g=excluded.carbs_g,
            updated_at=excluded.updated_at
        """,
        (
            user_id, gender, height_cm, weight_kg, age, activity, target,
            goal_weight, json.dumps(restrictions, ensure_ascii=False),
            json.dumps(food_prefs or [], ensure_ascii=False), int(soup_pref),
            calories, protein_g, fat_g, carbs_g,
            datetime.now().isoformat(),
        ),
    )
    conn.close()


def get_profile(user_id: int) -> dict | None:
    conn = _conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["restrictions"] = json.loads(d["restrictions"]) if d["restrictions"] else []
    d["food_prefs"] = json.loads(d["food_prefs"]) if d.get("food_prefs") else []
    d["soup_pref"] = bool(d["soup_pref"])
    return d


# ── Weight log ────────────────────────────────────────────────────

def log_weight(user_id: int, weight_kg: float):
    conn = _conn()
    conn.execute(
        "INSERT INTO weight_log (user_id, weight_kg, logged_at) VALUES (?, ?, ?)",
        (user_id, weight_kg, datetime.now().isoformat()),
    )
    conn.close()


def get_latest_weight(user_id: int) -> float | None:
    """Return the most recent logged weight, or None."""
    conn = _conn()
    row = conn.execute(
        "SELECT weight_kg FROM weight_log WHERE user_id = ? ORDER BY logged_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return row[0] if row else None


def get_weight_history(user_id: int, limit: int = 30) -> list[dict]:
    conn = _conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT weight_kg, logged_at FROM weight_log WHERE user_id = ? ORDER BY logged_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Daily log ─────────────────────────────────────────────────────

def _today_str():
    return date.today().isoformat()


def _get_or_create_daily(conn, user_id: int) -> int:
    row = conn.execute(
        "SELECT id FROM daily_log WHERE user_id = ? AND log_date = ?",
        (user_id, _today_str()),
    ).fetchone()
    if row:
        return row[0]
    conn.execute(
        "INSERT INTO daily_log (user_id, log_date, logged_at) VALUES (?, ?, ?)",
        (user_id, _today_str(), datetime.now().isoformat()),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def save_morning_state(user_id: int, state: str):
    conn = _conn()
    row_id = _get_or_create_daily(conn, user_id)
    conn.execute(
        "UPDATE daily_log SET morning_state = ?, logged_at = ? WHERE id = ?",
        (state, datetime.now().isoformat(), row_id),
    )
    conn.close()


def save_evening_result(user_id: int, result: str, deviation_reason: str | None = None):
    conn = _conn()
    row_id = _get_or_create_daily(conn, user_id)
    conn.execute(
        "UPDATE daily_log SET evening_result = ?, deviation_reason = ?, logged_at = ? WHERE id = ?",
        (result, deviation_reason, datetime.now().isoformat(), row_id),
    )
    conn.close()


def save_food_log(user_id: int, food_text: str, gpt_review: str):
    conn = _conn()
    row_id = _get_or_create_daily(conn, user_id)
    conn.execute(
        "UPDATE daily_log SET food_text = ?, gpt_review = ?, logged_at = ? WHERE id = ?",
        (food_text, gpt_review, datetime.now().isoformat(), row_id),
    )
    conn.close()


def get_daily_streak(user_id: int) -> int:
    """Count consecutive days with at least one check-in."""
    conn = _conn()
    rows = conn.execute(
        "SELECT DISTINCT log_date FROM daily_log WHERE user_id = ? ORDER BY log_date DESC",
        (user_id,),
    ).fetchall()
    conn.close()

    if not rows:
        return 0

    streak = 0
    check = date.today()
    for (d_str,) in rows:
        d = date.fromisoformat(d_str)
        if d == check:
            streak += 1
            check = check.replace(day=check.day)  # same day
            from datetime import timedelta
            check -= timedelta(days=1)
        else:
            break
    return streak


def get_daily_count(user_id: int) -> int:
    conn = _conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM daily_log WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


# ── Menu log ──────────────────────────────────────────────────────

def save_menu(user_id: int, calories: int, protein_g: int, fat_g: int, carbs_g: int, menu_text: str):
    conn = _conn()
    conn.execute(
        "INSERT INTO menu_log (user_id, calories, protein_g, fat_g, carbs_g, menu_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, calories, protein_g, fat_g, carbs_g, menu_text, datetime.now().isoformat()),
    )
    conn.close()


def get_menu_count(user_id: int) -> int:
    conn = _conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM menu_log WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def get_last_menu(user_id: int) -> dict | None:
    conn = _conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM menu_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def days_since_last_menu(user_id: int) -> int | None:
    """Return number of full days since last menu, or None if no menu exists."""
    last = get_last_menu(user_id)
    if not last:
        return None
    try:
        created = datetime.fromisoformat(last["created_at"])
        delta = datetime.now() - created
        return delta.days
    except Exception:
        return None


# ── Subscriptions ─────────────────────────────────────────────────

def set_subscription(user_id: int, plan: str, expires_at: str | None = None):
    conn = _conn()
    conn.execute(
        """
        INSERT INTO subscriptions (user_id, plan, expires_at, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            plan=excluded.plan, expires_at=excluded.expires_at
        """,
        (user_id, plan, expires_at, datetime.now().isoformat()),
    )
    conn.close()


def get_subscription(user_id: int) -> dict | None:
    conn = _conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Whitelist (free access) ───────────────────────────────────────

def add_to_whitelist(user_id: int, added_by: str = "owner", note: str = ""):
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO whitelist (user_id, added_by, note, added_at) VALUES (?, ?, ?, ?)",
            (user_id, added_by, note, datetime.now().isoformat()),
        )
    except sqlite3.IntegrityError:
        pass
    conn.close()


def is_whitelisted(user_id: int) -> bool:
    conn = _conn()
    row = conn.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row is not None


def has_premium_access(user_id: int) -> bool:
    """Check if user has paid subscription or is whitelisted."""
    if is_whitelisted(user_id):
        return True
    sub = get_subscription(user_id)
    if not sub or sub["plan"] == "free":
        return False
    if sub["expires_at"]:
        return datetime.fromisoformat(sub["expires_at"]) > datetime.now()
    return True


# ── Full history for export ───────────────────────────────────────

def get_full_daily_history(user_id: int) -> list[dict]:
    conn = _conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM daily_log WHERE user_id = ? ORDER BY log_date ASC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_full_weight_history(user_id: int) -> list[dict]:
    conn = _conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT weight_kg, logged_at FROM weight_log WHERE user_id = ? ORDER BY logged_at ASC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_start_date(user_id: int) -> str | None:
    """Return the date when the user first interacted (profile creation or first daily log)."""
    conn = _conn()
    profile = conn.execute("SELECT updated_at FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    daily = conn.execute("SELECT MIN(log_date) FROM daily_log WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()

    dates = []
    if profile and profile[0]:
        dates.append(profile[0][:10])
    if daily and daily[0]:
        dates.append(daily[0])
    return min(dates) if dates else None


# ── Reviews ──────────────────────────────────────────────────────

def save_review(user_id: int, username: str | None, first_name: str | None, text: str):
    conn = _conn()
    conn.execute(
        "INSERT INTO reviews (user_id, username, first_name, text, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, first_name, text, datetime.now().isoformat()),
    )
    conn.close()


def get_all_reviews(limit: int = 50) -> list[dict]:
    conn = _conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_review_count() -> int:
    conn = _conn()
    count = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    conn.close()
    return count


# ── Init on import ────────────────────────────────────────────────

init_db()


# ── Async wrappers (prevent blocking the event loop) ─────────────

async def arun(fn, *args, **kwargs):
    """Run a sync DB function in a thread so it won't block the bot."""
    return await asyncio.to_thread(partial(fn, *args, **kwargs))


async def a_add_subscriber(user_id, username, first_name):
    return await arun(add_subscriber, user_id, username, first_name)

async def a_is_subscribed(user_id):
    return await arun(is_subscribed, user_id)

async def a_subscriber_count():
    return await arun(subscriber_count)

async def a_save_profile(**kwargs):
    return await arun(save_profile, **kwargs)

async def a_get_profile(user_id):
    return await arun(get_profile, user_id)

async def a_log_weight(user_id, weight_kg):
    return await arun(log_weight, user_id, weight_kg)

async def a_get_latest_weight(user_id):
    return await arun(get_latest_weight, user_id)

async def a_get_weight_history(user_id, limit=30):
    return await arun(get_weight_history, user_id, limit)

async def a_save_morning_state(user_id, state):
    return await arun(save_morning_state, user_id, state)

async def a_save_evening_result(user_id, result, deviation_reason=None):
    return await arun(save_evening_result, user_id, result, deviation_reason)

async def a_save_food_log(user_id, food_text, gpt_review):
    return await arun(save_food_log, user_id, food_text, gpt_review)

async def a_get_daily_streak(user_id):
    return await arun(get_daily_streak, user_id)

async def a_get_daily_count(user_id):
    return await arun(get_daily_count, user_id)

async def a_save_menu(user_id, calories, protein_g, fat_g, carbs_g, menu_text):
    return await arun(save_menu, user_id, calories, protein_g, fat_g, carbs_g, menu_text)

async def a_get_menu_count(user_id):
    return await arun(get_menu_count, user_id)

async def a_get_last_menu(user_id):
    return await arun(get_last_menu, user_id)

async def a_days_since_last_menu(user_id):
    return await arun(days_since_last_menu, user_id)

async def a_set_subscription(user_id, plan, expires_at=None):
    return await arun(set_subscription, user_id, plan, expires_at)

async def a_get_subscription(user_id):
    return await arun(get_subscription, user_id)

async def a_add_to_whitelist(user_id, added_by="owner", note=""):
    return await arun(add_to_whitelist, user_id, added_by, note)

async def a_is_whitelisted(user_id):
    return await arun(is_whitelisted, user_id)

async def a_has_premium_access(user_id):
    return await arun(has_premium_access, user_id)

async def a_get_full_daily_history(user_id):
    return await arun(get_full_daily_history, user_id)

async def a_get_full_weight_history(user_id):
    return await arun(get_full_weight_history, user_id)

async def a_get_start_date(user_id):
    return await arun(get_start_date, user_id)

async def a_save_review(user_id, username, first_name, text):
    return await arun(save_review, user_id, username, first_name, text)

async def a_get_all_reviews(limit=50):
    return await arun(get_all_reviews, limit)

async def a_get_review_count():
    return await arun(get_review_count)
