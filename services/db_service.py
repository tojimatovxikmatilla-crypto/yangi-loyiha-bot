"""
Kengaytirilgan SQLite ma'lumotlar bazasi.

Jadvallar:
- users: foydalanuvchilar, ban holati, premium muddati
- bot_settings: umumiy sozlamalar (texnik ishlar rejimi va h.k.)
- feature_flags: har bir funksiyani alohida yoqish/o'chirish
- promo_codes: promo kodlar (premium berish uchun)
- complaints: foydalanuvchi shikoyatlari
- logs: admin harakatlari tarixi
- counters: turli hisoblagichlar (media qayta ishlangan soni va h.k.)
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)

import os

DB_PATH = os.path.join(os.getenv("DATA_DIR", "."), "bot_data.db")

ALL_FEATURES = {
    "downloader": "⬇️ Universal Downloader",
    "ai": "🤖 AI yordamchi",
    "music": "🎵 Musiqa yuklash",
    "shazam": "🎧 Shazam",
}


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                banned INTEGER DEFAULT 0,
                premium_until TEXT
            )
            """
        )
        try:
            conn.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
        except sqlite3.OperationalError:
            pass  # ustun allaqachon mavjud
        conn.execute(
            "CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS feature_flags (feature_key TEXT PRIMARY KEY, enabled INTEGER DEFAULT 1)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                days INTEGER,
                used_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                used_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS music_cache (
                query_normalized TEXT PRIMARY KEY,
                video_id TEXT,
                title TEXT,
                uploader TEXT,
                duration INTEGER,
                file_path TEXT,
                cached_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS counters (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS promo_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                button_text TEXT,
                url TEXT,
                category TEXT,
                duration_label TEXT,
                expires_at TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('maintenance', '0')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('welcome_text', '')"
        )
        for key in ALL_FEATURES:
            conn.execute(
                "INSERT OR IGNORE INTO feature_flags (feature_key, enabled) VALUES (?, 1)",
                (key,),
            )


# ---------- Foydalanuvchilar ----------

def add_user(user_id: int, username: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, last_seen) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (user_id, username),
        )
        # Foydalanuvchi oldin ham mavjud bo'lsa ham, har safar xabar yozganda
        # so'nggi faollik vaqtini yangilaymiz — statistikada faol/passiv
        # ajratish shu ma'lumotga asoslanadi.
        conn.execute(
            "UPDATE users SET last_seen = CURRENT_TIMESTAMP, username = COALESCE(?, username) WHERE user_id = ?",
            (username, user_id),
        )


def get_user_count() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_all_user_ids() -> list[int]:
    with _connect() as conn:
        return [row[0] for row in conn.execute("SELECT user_id FROM users").fetchall()]


def get_recent_users(limit: int = 10) -> list[tuple]:
    with _connect() as conn:
        return conn.execute(
            "SELECT user_id, username, first_seen FROM users ORDER BY first_seen DESC LIMIT ?",
            (limit,),
        ).fetchall()


def ban_user(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,))


def unban_user(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (user_id,))


def is_banned(user_id: int) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return bool(row and row[0] == 1)


def get_banned_count() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE banned = 1").fetchone()[0]


def get_user_activity_counts(active_days: int = 3, average_days: int = 14) -> dict:
    """
    Foydalanuvchilarni oxirgi faollik vaqtiga (last_seen) qarab uch guruhga
    ajratadi:
    - faol: so'nggi `active_days` kun ichida yozgan
    - o'rtacha: `active_days`–`average_days` kun oralig'ida yozgan
    - passiv: `average_days` kundan ortiq yozmagan (yoki umuman ma'lumot yo'q)
    """
    now = datetime.now()
    active, average, passive = 0, 0, 0
    with _connect() as conn:
        rows = conn.execute("SELECT last_seen FROM users").fetchall()
    for (last_seen,) in rows:
        if not last_seen:
            passive += 1
            continue
        try:
            delta_days = (now - datetime.fromisoformat(last_seen)).total_seconds() / 86400
        except ValueError:
            passive += 1
            continue
        if delta_days <= active_days:
            active += 1
        elif delta_days <= average_days:
            average += 1
        else:
            passive += 1
    return {"active": active, "average": average, "passive": passive}


# ---------- Premium ----------

def grant_premium(user_id: int, days: int) -> None:
    until = (datetime.now() + timedelta(days=days)).isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET premium_until = ? WHERE user_id = ?", (until, user_id)
        )


def revoke_premium(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET premium_until = NULL WHERE user_id = ?", (user_id,))


def is_premium(user_id: int) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT premium_until FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row or not row[0]:
            return False
        return datetime.fromisoformat(row[0]) > datetime.now()


def get_premium_users() -> list[tuple]:
    with _connect() as conn:
        return conn.execute(
            "SELECT user_id, username, premium_until FROM users "
            "WHERE premium_until IS NOT NULL AND premium_until > ? ORDER BY premium_until DESC",
            (datetime.now().isoformat(),),
        ).fetchall()


# ---------- Promo kodlar ----------

def create_promo_code(code: str, days: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO promo_codes (code, days) VALUES (?, ?)", (code.upper(), days)
        )


def redeem_promo_code(code: str, user_id: int) -> int | None:
    """Kod ishlatilsa kunlar sonini qaytaradi, aks holda None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT days, used_by FROM promo_codes WHERE code = ?", (code.upper(),)
        ).fetchone()
        if not row or row[1] is not None:
            return None
        days = row[0]
        conn.execute(
            "UPDATE promo_codes SET used_by = ?, used_at = CURRENT_TIMESTAMP WHERE code = ?",
            (user_id, code.upper()),
        )
        conn.execute(
            "UPDATE users SET premium_until = ? WHERE user_id = ?",
            ((datetime.now() + timedelta(days=days)).isoformat(), user_id),
        )
        return days


# ---------- Feature flags ----------

def get_feature_enabled(feature_key: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT enabled FROM feature_flags WHERE feature_key = ?", (feature_key,)
        ).fetchone()
        return row is None or row[0] == 1  # topilmasa ham yoqilgan deb hisoblaymiz


def set_feature_enabled(feature_key: str, enabled: bool) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO feature_flags (feature_key, enabled) VALUES (?, ?)",
            (feature_key, 1 if enabled else 0),
        )


def get_all_feature_flags() -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT feature_key, enabled FROM feature_flags").fetchall()
        return {key: bool(enabled) for key, enabled in rows}


# ---------- Texnik ishlar rejimi ----------

def is_maintenance_mode() -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key = 'maintenance'").fetchone()
        return row is not None and row[0] == "1"


def set_maintenance_mode(enabled: bool) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE bot_settings SET value = ? WHERE key = 'maintenance'",
            ("1" if enabled else "0",),
        )


# ---------- Shikoyatlar ----------

def add_complaint(user_id: int, text: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO complaints (user_id, text) VALUES (?, ?)", (user_id, text)
        )


def get_complaints(only_unresolved: bool = True, limit: int = 20) -> list[tuple]:
    with _connect() as conn:
        query = "SELECT id, user_id, text, created_at, resolved FROM complaints"
        if only_unresolved:
            query += " WHERE resolved = 0"
        query += " ORDER BY created_at DESC LIMIT ?"
        return conn.execute(query, (limit,)).fetchall()


def resolve_complaint(complaint_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE complaints SET resolved = 1 WHERE id = ?", (complaint_id,))


# ---------- Loglar ----------

def add_log(action: str, details: str = "") -> None:
    with _connect() as conn:
        conn.execute("INSERT INTO logs (action, details) VALUES (?, ?)", (action, details))


def get_recent_logs(limit: int = 15) -> list[tuple]:
    with _connect() as conn:
        return conn.execute(
            "SELECT action, details, created_at FROM logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


# ---------- Hisoblagichlar ----------

def increment_counter(key: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO counters (key, value) VALUES (?, 1) "
            "ON CONFLICT(key) DO UPDATE SET value = value + 1",
            (key,),
        )


def get_counter(key: str) -> int:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM counters WHERE key = ?", (key,)).fetchone()
        return row[0] if row else 0


# ---------- Sozlamalar (matn saqlash uchun umumiy) ----------

def get_setting(key: str, default: str = "") -> str:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row and row[0] else default


def set_setting(key: str, value: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value)
        )


# ---------- Musiqa keshi (qidiruv matni -> tayyor fayl) ----------

def _normalize_music_query(query: str) -> str:
    return query.strip().lower()


def get_cached_music_query(query: str) -> dict | None:
    """
    Berilgan qidiruv matni oldin so'ralgan bo'lsa, saqlangan natijani qaytaradi.
    Aniq (harflar registri va bo'sh joylardan tashqari) mos kelishi kerak.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT video_id, title, uploader, duration, file_path FROM music_cache "
            "WHERE query_normalized = ?",
            (_normalize_music_query(query),),
        ).fetchone()
        if not row:
            return None
        return {
            "video_id": row[0],
            "title": row[1],
            "uploader": row[2],
            "duration": row[3],
            "file_path": row[4],
        }


def save_cached_music_query(
    query: str, video_id: str, title: str, uploader: str, duration: int, file_path: str
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO music_cache "
            "(query_normalized, video_id, title, uploader, duration, file_path, cached_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (_normalize_music_query(query), video_id, title, uploader, duration, file_path),
        )


# ---------- Silkalar (promo linklar) ----------

def add_promo_link(button_text: str, url: str, category: str, duration_label: str, expires_at: str | None) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO promo_links (button_text, url, category, duration_label, expires_at, active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (button_text, url, category, duration_label, expires_at),
        )
        return cursor.lastrowid


def get_active_promo_links(category: str | None = None) -> list[dict]:
    """
    Faol (muddati o'tmagan) silkalarni qaytaradi.
    - category berilsa: shu category'ga mos YOKI 'all' (barcha xabarlar) turidagilarni qaytaradi.
    - category berilmasa: barcha faol silkalarni (admin ro'yxati uchun) qaytaradi.
    """
    now = datetime.now().isoformat()
    with _connect() as conn:
        if category:
            rows = conn.execute(
                "SELECT id, button_text, url, category, duration_label, expires_at FROM promo_links "
                "WHERE active = 1 AND (category = ? OR category = 'all') "
                "AND (expires_at IS NULL OR expires_at > ?) "
                "ORDER BY created_at DESC",
                (category, now),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, button_text, url, category, duration_label, expires_at FROM promo_links "
                "WHERE active = 1 AND (expires_at IS NULL OR expires_at > ?) "
                "ORDER BY created_at DESC",
                (now,),
            ).fetchall()
    return [
        {
            "id": r[0], "button_text": r[1], "url": r[2],
            "category": r[3], "duration_label": r[4], "expires_at": r[5],
        }
        for r in rows
    ]


def deactivate_promo_link(link_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE promo_links SET active = 0 WHERE id = ?", (link_id,))


def pop_expired_promo_links() -> list[dict]:
    """
    Muddati ENDI tugagan (lekin hali 'active=1' bo'lib turgan) silkalarni topadi,
    ularni avtomatik nofaol qiladi va admin xabar berishi uchun ro'yxatini qaytaradi.
    """
    now = datetime.now().isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, button_text, category, duration_label FROM promo_links "
            "WHERE active = 1 AND expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        ).fetchall()
        ids = [r[0] for r in rows]
        if ids:
            conn.executemany("UPDATE promo_links SET active = 0 WHERE id = ?", [(i,) for i in ids])
    return [
        {"id": r[0], "button_text": r[1], "category": r[2], "duration_label": r[3]}
        for r in rows
    ]
