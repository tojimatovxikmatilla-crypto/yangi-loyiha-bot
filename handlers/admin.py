"""
To'liq admin panel.
"""
import asyncio
import logging
import os
import platform
import random
import string
import sys
import time
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter, BaseFilter
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from services import db_service
from utils.states import AdminStates, PromoLinkStates
from config import config

logger = logging.getLogger(__name__)
router = Router(name="admin")

START_TIME = datetime.now()

CAT_MAIN = "📊 Asosiy boshqaruv"
CAT_FUNCTIONS = "🤖 Bot funksiyalari"
CAT_PREMIUM = "💎 Premium"
CAT_SECURITY = "🛡 Xavfsizlik"
CAT_CONTENT = "📁 Kontent"
CAT_TECH = "🔧 Texnik"
CAT_LINKS = "🔗 Silkalar"

BTN_BACK = "⬅️ Orqaga"

BTN_USERS = "👤 Foydalanuvchilar"
BTN_STATS = "📈 Statistika"
BTN_BROADCAST = "📢 Xabar yuborish"
BTN_BAN = "🚫 Ban"
BTN_UNBAN = "✅ Unban"
BTN_SETTINGS = "⚙️ Sozlamalar"

BTN_TOGGLE_MAINT = "🛠 Texnik ishlar rejimini almashtirish"
BTN_EDIT_WELCOME = "📝 Xush kelibsiz matnini tahrirlash"

BTN_ADD_FEATURE_INFO = "➕ Funksiya qo'shish"
BTN_TOGGLE_FEATURES = "🔁 Funksiyalarni yoqish/o'chirish"

BTN_GRANT_PREMIUM = "💎 Premium berish"
BTN_REVOKE_PREMIUM = "❌ Premiumni bekor qilish"
BTN_CREATE_PROMO = "🎁 Promo kod yaratish"
BTN_SUBSCRIPTIONS = "💳 Obunalar ro'yxati"

BTN_SPAM_INFO = "🚫 Spam nazorati"
BTN_COMPLAINTS = "🚨 Shikoyatlar"
BTN_LOGS = "📋 Loglar"
BTN_ADMINS = "🔑 Adminlar"

BTN_FILES = "📁 Fayllar"
BTN_MEDIA = "🖼 Media statistikasi"
BTN_API_STATUS = "🔗 API holati"
BTN_SERVER_STATUS = "🌐 Server holati"

BTN_RESTART = "♻️ Botni qayta ishga tushirish"
BTN_RESTART_CONFIRM = "⚠️ Ha, qayta ishga tushirish"
BTN_BACKUP = "📦 Zaxira (Backup)"
BTN_RESTORE = "📥 Restore"
BTN_PING = "📡 Ping"

BTN_ADD_LINK = "➕ Silka qo'shish"
BTN_LIST_LINKS = "📋 Silkalar ro'yxati"
BTN_LINK_CAT_ALL = "📢 Barcha xabarlar"
BTN_LINK_CAT_MUSIC = "🎵 Musiqa xabarlari"
BTN_LINK_CAT_VIDEO = "🎬 Video xabarlari"
BTN_LINK_CAT_ADMIN = "👤 Admin xabarlari"

_LINK_CATEGORY_MAP = {
    BTN_LINK_CAT_ALL: "all",
    BTN_LINK_CAT_MUSIC: "music",
    BTN_LINK_CAT_VIDEO: "video",
    BTN_LINK_CAT_ADMIN: "admin",
}

CATEGORY_LABELS = {
    "all": "📢 Barcha xabarlar",
    "music": "🎵 Musiqa",
    "video": "🎬 Video",
    "admin": "👤 Admin xabarlari",
}


class IsAdmin(BaseFilter):
    async def __call__(self, event) -> bool:
        user = event.from_user
        return bool(user) and user.id in config.ADMIN_IDS


def _kb(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
        resize_keyboard=True,
        is_persistent=False,
    )


def admin_reply_kb() -> ReplyKeyboardMarkup:
    return _kb([
        [CAT_MAIN, CAT_FUNCTIONS],
        [CAT_PREMIUM, CAT_SECURITY],
        [CAT_CONTENT, CAT_TECH],
        [CAT_LINKS],
    ])


def main_category_kb() -> ReplyKeyboardMarkup:
    return _kb([
        [BTN_USERS, BTN_STATS],
        [BTN_BROADCAST],
        [BTN_BAN, BTN_UNBAN],
        [BTN_SETTINGS],
        [BTN_BACK],
    ])


def settings_kb() -> ReplyKeyboardMarkup:
    return _kb([[BTN_TOGGLE_MAINT], [BTN_EDIT_WELCOME], [BTN_BACK]])


def functions_category_kb() -> ReplyKeyboardMarkup:
    return _kb([[BTN_ADD_FEATURE_INFO], [BTN_TOGGLE_FEATURES], [BTN_EDIT_WELCOME], [BTN_BACK]])


def _features_kb() -> ReplyKeyboardMarkup:
    rows = [[label] for label in db_service.ALL_FEATURES.values()]
    rows.append([BTN_BACK])
    return _kb(rows)


def premium_category_kb() -> ReplyKeyboardMarkup:
    return _kb([
        [BTN_GRANT_PREMIUM, BTN_REVOKE_PREMIUM],
        [BTN_CREATE_PROMO],
        [BTN_SUBSCRIPTIONS],
        [BTN_BACK],
    ])


def security_category_kb() -> ReplyKeyboardMarkup:
    return _kb([
        [BTN_SPAM_INFO],
        [BTN_COMPLAINTS],
        [BTN_LOGS, BTN_ADMINS],
        [BTN_BACK],
    ])


def _complaints_kb(complaint_ids: list[int]) -> ReplyKeyboardMarkup:
    rows = [[f"✅ Yopish #{cid}"] for cid in complaint_ids]
    rows.append([BTN_BACK])
    return _kb(rows)


def content_category_kb() -> ReplyKeyboardMarkup:
    return _kb([
        [BTN_FILES, BTN_MEDIA],
        [BTN_API_STATUS, BTN_SERVER_STATUS],
        [BTN_BACK],
    ])


def tech_category_kb() -> ReplyKeyboardMarkup:
    return _kb([
        [BTN_RESTART],
        [BTN_BACKUP, BTN_RESTORE],
        [BTN_PING],
        [BTN_BACK],
    ])


def restart_confirm_kb() -> ReplyKeyboardMarkup:
    return _kb([[BTN_RESTART_CONFIRM], [BTN_BACK]])


def links_category_kb() -> ReplyKeyboardMarkup:
    return _kb([[BTN_ADD_LINK], [BTN_LIST_LINKS], [BTN_BACK]])


def link_type_kb() -> ReplyKeyboardMarkup:
    return _kb([[BTN_LINK_CAT_ALL], [BTN_LINK_CAT_MUSIC], [BTN_LINK_CAT_VIDEO], [BTN_LINK_CAT_ADMIN], [BTN_BACK]])


def _format_remaining(expires_at: str | None) -> str:
    if not expires_at:
        return "♾ Muddatsiz"
    delta = datetime.fromisoformat(expires_at) - datetime.now()
    total_seconds = delta.total_seconds()
    if total_seconds <= 0:
        return "⏰ Muddati tugagan"
    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)
    parts = []
    if days:
        parts.append(f"{days} kun")
    if hours:
        parts.append(f"{hours} soat")
    if not days and minutes:
        parts.append(f"{minutes} daqiqa")
    return " ".join(parts) if parts else "1 daqiqadan kam"


_DURATION_UNITS = [
    ("hafta", 604800),
    ("kun", 86400),
    ("soat", 3600),
    ("daqiqa", 60),
    ("minut", 60),
    ("oy", 2592000),
    ("soniya", 1),
]


def _parse_duration(text: str) -> tuple[int | None, str]:
    normalized = text.strip().lower()
    if normalized in ("doim", "cheksiz", "-", "muddatsiz", "hech qachon"):
        return None, "Muddatsiz"

    import re
    match = re.search(r"(\d+)\s*([a-zA-Zʻʼ'`]+)", text)
    if not match:
        return None, text.strip()

    amount = int(match.group(1))
    unit_raw = match.group(2).lower()

    for unit, seconds in _DURATION_UNITS:
        if unit_raw.startswith(unit):
            return amount * seconds, text.strip()

    return None, text.strip()


# ================= /admin — panelni ochish =================

@router.message(Command("admin"), IsAdmin())
async def open_admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔐 <b>Admin panel</b>\n\nPastdagi bo'limlardan birini tanlang 👇",
        reply_markup=admin_reply_kb(),
        parse_mode="HTML",
    )


# ================= UNIVERSAL "ORQAGA" =================

@router.message(IsAdmin(), F.text == BTN_BACK)
async def go_back_to_root(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔐 <b>Admin panel</b>\n\nPastdagi bo'limlardan birini tanlang 👇",
        reply_markup=admin_reply_kb(),
        parse_mode="HTML",
    )


# ================= 1) ASOSIY BOSHQARUV =================

@router.message(StateFilter(None), IsAdmin(), F.text == CAT_MAIN)
async def show_main_category(message: Message):
    await message.answer("📊 <b>Asosiy boshqaruv</b>\n\nKerakli bo'limni tanlang 👇", reply_markup=main_category_kb(), parse_mode="HTML")


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_USERS)
async def show_users(message: Message):
    count = db_service.get_user_count()
    recent = db_service.get_recent_users(10)
    lines = [f"👥 <b>Jami: {count} ta foydalanuvchi</b>\n", "So'nggi 10 tasi:"]
    for user_id, username, first_seen in recent:
        uname = f"@{username}" if username else "(username yo'q)"
        lines.append(f"• <code>{user_id}</code> — {uname}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_STATS)
async def show_stats(message: Message):
    total = db_service.get_user_count()
    banned = db_service.get_banned_count()
    premium = len(db_service.get_premium_users())
    maintenance = "🔴 Yoqilgan" if db_service.is_maintenance_mode() else "🟢 O'chirilgan"
    activity = db_service.get_user_activity_counts()

    await message.answer(
        f"📈 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total}</b>\n"
        f"⛔ Bloklanganlar: <b>{banned}</b>\n"
        f"💎 Premium foydalanuvchilar: <b>{premium}</b>\n"
        f"🛠 Texnik ishlar rejimi: {maintenance}\n\n"
        f"<b>Foydalanuvchilar faolligi:</b>\n"
        f"🟢 Faol (so'nggi 3 kun): <b>{activity['active']}</b>\n"
        f"🟡 O'rtacha (3–14 kun): <b>{activity['average']}</b>\n"
        f"🔴 Passiv (14 kundan ortiq): <b>{activity['passive']}</b>",
        parse_mode="HTML",
    )


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_BROADCAST)
async def ask_broadcast_message(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await message.answer("📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing.\n\n(Bekor qilish uchun \"⬅️ Orqaga\" bosing)")


@router.message(AdminStates.waiting_for_broadcast_message, IsAdmin())
async def do_broadcast(message: Message, state: FSMContext):
    user_ids = db_service.get_all_user_ids()
    status = await message.answer(f"⏳ {len(user_ids)} ta foydalanuvchiga yuborilmoqda...")

    links = db_service.get_active_promo_links("admin")
    extra_kb = None
    if links:
        b = InlineKeyboardBuilder()
        for link in links:
            b.button(text=link["button_text"], url=link["url"])
        b.adjust(1)
        extra_kb = b.as_markup()

    sent, failed = 0, 0
    for user_id in user_ids:
        try:
            await message.copy_to(chat_id=user_id, reply_markup=extra_kb)
            sent += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        except Exception:
            logger.exception(f"Broadcast xatosi (user_id={user_id})")
            failed += 1
        await asyncio.sleep(0.05)

    db_service.add_log("broadcast", f"sent={sent} failed={failed}")
    await status.edit_text(f"✅ Yuborish tugadi.\n\n📤 Yuborildi: {sent}\n❌ Yuborilmadi: {failed}")
    await state.clear()


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_BAN)
async def ask_ban_id(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_ban_id)
    await message.answer("🚫 Bloklanadigan foydalanuvchining Telegram ID raqamini yuboring.")


@router.message(AdminStates.waiting_for_ban_id, IsAdmin(), F.text)
async def do_ban(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam yuboring.")
        return
    user_id = int(message.text.strip())
    db_service.ban_user(user_id)
    db_service.add_log("ban", f"user_id={user_id} by={message.from_user.id}")
    await message.answer(f"✅ <code>{user_id}</code> bloklandi.", parse_mode="HTML")
    await state.clear()


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_UNBAN)
async def ask_unban_id(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_unban_id)
    await message.answer("✅ Blokdan chiqariladigan foydalanuvchining Telegram ID raqamini yuboring.")


@router.message(AdminStates.waiting_for_unban_id, IsAdmin(), F.text)
async def do_unban(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam yuboring.")
        return
    user_id = int(message.text.strip())
    db_service.unban_user(user_id)
    db_service.add_log("unban", f"user_id={user_id} by={message.from_user.id}")
    await message.answer(f"✅ <code>{user_id}</code> blokdan chiqarildi.", parse_mode="HTML")
    await state.clear()


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_SETTINGS)
async def show_settings(message: Message):
    maintenance = "🔴 Yoqilgan" if db_service.is_maintenance_mode() else "🟢 O'chirilgan"
    await message.answer(
        f"⚙️ <b>Sozlamalar</b>\n\n🛠 Texnik ishlar rejimi hozir: {maintenance}",
        reply_markup=settings_kb(),
        parse_mode="HTML",
    )


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_TOGGLE_MAINT)
async def toggle_maintenance(message: Message):
    current = db_service.is_maintenance_mode()
    db_service.set_maintenance_mode(not current)
    db_service.add_log("maintenance_toggle", f"enabled={not current} by={message.from_user.id}")
    new_status = "🔴 Yoqilgan" if not current else "🟢 O'chirilgan"
    await message.answer(f"✅ Texnik ishlar rejimi endi: {new_status}", reply_markup=settings_kb())


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_EDIT_WELCOME)
async def ask_welcome_text(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_welcome_text)
    await message.answer(
        "✏️ Yangi xush kelibsiz (/start) matnini yuboring.\n\n"
        "Standart matnga qaytarish uchun \"-\" yuboring."
    )


@router.message(AdminStates.waiting_for_welcome_text, IsAdmin(), F.text)
async def do_edit_welcome(message: Message, state: FSMContext):
    new_text = "" if message.text.strip() == "-" else message.text
    db_service.set_setting("welcome_text", new_text)
    await message.answer("✅ Xush kelibsiz matni yangilandi.")
    await state.clear()


# ================= 2) BOT FUNKSIYALARI =================

@router.message(StateFilter(None), IsAdmin(), F.text == CAT_FUNCTIONS)
async def show_functions_category(message: Message):
    await message.answer("🤖 <b>Bot funksiyalari</b>", reply_markup=functions_category_kb(), parse_mode="HTML")


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_ADD_FEATURE_INFO)
async def add_feature_info(message: Message):
    await message.answer(
        "➕ <b>Yangi funksiya qo'shish</b>\n\n"
        "Yangi funksiya (masalan yangi buyruq yoki xizmat) qo'shish — bu kod darajasidagi "
        "o'zgarish, botni qayta yozishni talab qiladi. Buni ishlab chiquvchi bilan "
        "(shu suhbat orqali) amalga oshirish mumkin — bot ishlab turganda avtomatik qo'shib "
        "bo'lmaydi.\n\n"
        "Mavjud funksiyalarni esa \"🔁 Funksiyalarni yoqish/o'chirish\" orqali "
        "istalgan vaqt boshqarishingiz mumkin.",
        parse_mode="HTML",
    )


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_TOGGLE_FEATURES)
async def show_features(message: Message):
    flags = db_service.get_all_feature_flags()
    lines = ["🔁 <b>Funksiyalarni yoqish/o'chirish</b>\n", "Holatlar:"]
    for key, label in db_service.ALL_FEATURES.items():
        status = "🟢" if flags.get(key, True) else "🔴"
        lines.append(f"{status} {label}")
    lines.append("\nYoqish/o'chirish uchun pastdagi tugmalardan birini bosing:")
    await message.answer("\n".join(lines), reply_markup=_features_kb(), parse_mode="HTML")


_FEATURE_LABEL_TO_KEY = {label: key for key, label in db_service.ALL_FEATURES.items()}


@router.message(StateFilter(None), IsAdmin(), F.text.in_(_FEATURE_LABEL_TO_KEY.keys()))
async def toggle_feature(message: Message):
    key = _FEATURE_LABEL_TO_KEY[message.text]
    current = db_service.get_feature_enabled(key)
    db_service.set_feature_enabled(key, not current)
    db_service.add_log("feature_toggle", f"{key}={not current} by={message.from_user.id}")

    flags = db_service.get_all_feature_flags()
    lines = ["✅ Holat yangilandi.\n", "Joriy holatlar:"]
    for k, label in db_service.ALL_FEATURES.items():
        status = "🟢" if flags.get(k, True) else "🔴"
        lines.append(f"{status} {label}")
    await message.answer("\n".join(lines), reply_markup=_features_kb())


# ================= 3) PREMIUM =================

@router.message(StateFilter(None), IsAdmin(), F.text == CAT_PREMIUM)
async def show_premium_category(message: Message):
    await message.answer("💎 <b>Premium</b>", reply_markup=premium_category_kb(), parse_mode="HTML")


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_GRANT_PREMIUM)
async def ask_grant_premium_id(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_premium_grant_id)
    await message.answer("💎 Premium beriladigan foydalanuvchi ID raqamini yuboring.")


@router.message(AdminStates.waiting_for_premium_grant_id, IsAdmin(), F.text)
async def ask_grant_premium_days(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam yuboring.")
        return
    await state.update_data(grant_user_id=int(message.text.strip()))
    await state.set_state(AdminStates.waiting_for_premium_grant_days)
    await message.answer("📅 Nechchi kunga premium berilsin? (raqam yuboring, masalan 30)")


@router.message(AdminStates.waiting_for_premium_grant_days, IsAdmin(), F.text)
async def do_grant_premium(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam yuboring.")
        return
    days = int(message.text.strip())
    data = await state.get_data()
    user_id = data.get("grant_user_id")
    db_service.grant_premium(user_id, days)
    db_service.add_log("premium_grant", f"user_id={user_id} days={days} by={message.from_user.id}")
    await message.answer(f"✅ <code>{user_id}</code> uchun {days} kunlik premium berildi.", parse_mode="HTML")
    await state.clear()


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_REVOKE_PREMIUM)
async def ask_revoke_premium_id(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_premium_revoke_id)
    await message.answer("❌ Premiumi bekor qilinadigan foydalanuvchi ID raqamini yuboring.")


@router.message(AdminStates.waiting_for_premium_revoke_id, IsAdmin(), F.text)
async def do_revoke_premium(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam yuboring.")
        return
    user_id = int(message.text.strip())
    db_service.revoke_premium(user_id)
    db_service.add_log("premium_revoke", f"user_id={user_id} by={message.from_user.id}")
    await message.answer(f"✅ <code>{user_id}</code> uchun premium bekor qilindi.", parse_mode="HTML")
    await state.clear()


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_CREATE_PROMO)
async def ask_promo_days(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_promo_days)
    await message.answer("🎁 Promo kod nechchi kunlik premium bersin? (raqam yuboring)")


@router.message(AdminStates.waiting_for_promo_days, IsAdmin(), F.text)
async def do_create_promo(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam yuboring.")
        return
    days = int(message.text.strip())
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    db_service.create_promo_code(code, days)
    db_service.add_log("promo_create", f"code={code} days={days} by={message.from_user.id}")
    await message.answer(
        f"✅ Promo kod yaratildi:\n\n<code>{code}</code>\n\n"
        f"({days} kunlik premium beradi, foydalanuvchi buni /promo buyrug'i orqali kiritadi)",
        parse_mode="HTML",
    )
    await state.clear()


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_SUBSCRIPTIONS)
async def show_subscriptions(message: Message):
    premium_users = db_service.get_premium_users()
    if not premium_users:
        text = "💳 Hozircha faol premium obunalar yo'q."
    else:
        lines = ["💳 <b>Faol obunalar:</b>\n"]
        for user_id, username, until in premium_users:
            uname = f"@{username}" if username else "(username yo'q)"
            until_str = datetime.fromisoformat(until).strftime("%Y-%m-%d")
            lines.append(f"• <code>{user_id}</code> {uname} — {until_str} gacha")
        text = "\n".join(lines)
    await message.answer(text, parse_mode="HTML")


# ================= 4) XAVFSIZLIK =================

@router.message(StateFilter(None), IsAdmin(), F.text == CAT_SECURITY)
async def show_security_category(message: Message):
    await message.answer("🛡 <b>Xavfsizlik</b>", reply_markup=security_category_kb(), parse_mode="HTML")


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_SPAM_INFO)
async def show_spam_info(message: Message):
    from utils.middlewares import SPAM_WINDOW_SECONDS, SPAM_MAX_MESSAGES
    await message.answer(
        f"🚫 <b>Spam nazorati</b>\n\n"
        f"Holat: 🟢 Faol\n"
        f"Chegara: {SPAM_WINDOW_SECONDS} soniyada {SPAM_MAX_MESSAGES} tadan ortiq xabar "
        f"yuborgan foydalanuvchi vaqtincha sekinlashtiriladi.\n"
        f"Adminlar bu cheklovdan ozod.",
        parse_mode="HTML",
    )


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_COMPLAINTS)
async def show_complaints(message: Message):
    complaints = db_service.get_complaints(only_unresolved=True, limit=10)
    if not complaints:
        await message.answer("🚨 Hal qilinmagan shikoyatlar yo'q.")
        return
    lines = ["🚨 <b>Hal qilinmagan shikoyatlar:</b>\n"]
    ids = []
    for cid, user_id, text_, created_at, resolved in complaints:
        preview = text_[:80] + ("..." if len(text_) > 80 else "")
        lines.append(f"#{cid} — <code>{user_id}</code>: {preview}")
        ids.append(cid)
    await message.answer("\n".join(lines), reply_markup=_complaints_kb(ids), parse_mode="HTML")


@router.message(StateFilter(None), IsAdmin(), F.text.startswith("✅ Yopish #"))
async def resolve_complaint_btn(message: Message):
    try:
        complaint_id = int(message.text.split("#", 1)[1])
    except (IndexError, ValueError):
        return
    db_service.resolve_complaint(complaint_id)
    await message.answer(f"✅ #{complaint_id} yopildi.")
    await show_complaints(message)


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_LOGS)
async def show_logs(message: Message):
    logs = db_service.get_recent_logs(15)
    if not logs:
        text = "📋 Hali loglar yo'q."
    else:
        lines = ["📋 <b>So'nggi harakatlar:</b>\n"]
        for action, details, created_at in logs:
            lines.append(f"• <code>{created_at}</code> — {action}: {details}")
        text = "\n".join(lines)
    await message.answer(text, parse_mode="HTML")


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_ADMINS)
async def show_admins(message: Message):
    lines = ["🔑 <b>Adminlar ro'yxati:</b>\n"]
    for admin_id in config.ADMIN_IDS:
        lines.append(f"• <code>{admin_id}</code>")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ================= 5) KONTENT =================

@router.message(StateFilter(None), IsAdmin(), F.text == CAT_CONTENT)
async def show_content_category(message: Message):
    await message.answer("📁 <b>Kontent</b>", reply_markup=content_category_kb(), parse_mode="HTML")


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_FILES)
async def show_files(message: Message):
    folder = config.DOWNLOAD_DIR
    count, total_size = 0, 0
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if os.path.isfile(path):
                count += 1
                total_size += os.path.getsize(path)
    await message.answer(
        f"📁 <b>Fayllar</b>\n\n"
        f"Vaqtinchalik papkada hozir: <b>{count}</b> ta fayl\n"
        f"Umumiy hajm: <b>{total_size / 1024 / 1024:.2f} MB</b>\n\n"
        f"(Fayllar har bir amaldan keyin avtomatik o'chiriladi, shu sabab bu odatda 0 bo'lishi kerak)",
        parse_mode="HTML",
    )


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_MEDIA)
async def show_media_stats(message: Message):
    downloads = db_service.get_counter("downloads_completed")
    ocr = db_service.get_counter("ocr_processed")
    qr_created = db_service.get_counter("qr_created")
    voice = db_service.get_counter("voice_processed")
    await message.answer(
        f"🖼 <b>Media statistikasi</b> (bot ishga tushgandan buyon)\n\n"
        f"⬇️ Yuklab olingan medialar: <b>{downloads}</b>\n"
        f"🖼 OCR orqali o'qilgan rasmlar: <b>{ocr}</b>\n"
        f"📌 Yaratilgan QR kodlar: <b>{qr_created}</b>\n"
        f"🎙 Qayta ishlangan ovozli xabarlar: <b>{voice}</b>",
        parse_mode="HTML",
    )


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_API_STATUS)
async def show_api_status(message: Message):
    ai_status = "🟢 Ulangan" if config.AI_API_KEY else "🔴 Ulanmagan"
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        ocr_status = "🟢 O'rnatilgan"
    except Exception:
        ocr_status = "🔴 Topilmadi"
    await message.answer(
        f"🔗 <b>API holati</b>\n\n"
        f"🤖 AI (Claude) API: {ai_status}\n"
        f"🖼 Tesseract OCR: {ocr_status}\n"
        f"🌤 Ob-havo (Open-Meteo): 🟢 Doim ochiq (kalit shart emas)",
        parse_mode="HTML",
    )


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_SERVER_STATUS)
async def show_server_status(message: Message):
    uptime = datetime.now() - START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    await message.answer(
        f"🌐 <b>Server holati</b>\n\n"
        f"⏱ Ishlab turgan vaqti: {hours}s {minutes}m {seconds}soniya\n"
        f"🐍 Python versiyasi: {platform.python_version()}\n"
        f"💻 OS: {platform.system()} {platform.release()}",
        parse_mode="HTML",
    )


# ================= 6) TEXNIK =================

@router.message(StateFilter(None), IsAdmin(), F.text == CAT_TECH)
async def show_tech_category(message: Message):
    await message.answer("🔧 <b>Texnik</b>", reply_markup=tech_category_kb(), parse_mode="HTML")


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_RESTART)
async def confirm_restart(message: Message):
    await message.answer(
        "♻️ Botni qayta ishga tushirmoqchimisiz? Bot bir necha soniyaga o'chib qoladi.",
        reply_markup=restart_confirm_kb(),
    )


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_RESTART_CONFIRM)
async def do_restart(message: Message):
    db_service.add_log("restart", f"by={message.from_user.id}")
    await message.answer("♻️ Bot qayta ishga tushirilmoqda...", reply_markup=tech_category_kb())
    os.execv(sys.executable, [sys.executable] + sys.argv)


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_BACKUP)
async def do_backup(message: Message, bot: Bot):
    if not os.path.exists(db_service.DB_PATH):
        await message.answer("❌ Ma'lumotlar bazasi hali yaratilmagan.")
        return
    await bot.send_document(
        chat_id=message.from_user.id,
        document=FSInputFile(db_service.DB_PATH),
        caption=f"📦 Zaxira nusxa — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )
    db_service.add_log("backup", f"by={message.from_user.id}")


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_RESTORE)
async def ask_restore_file(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_restore_file)
    await message.answer(
        "📥 Tiklash uchun avval yuborilgan .db zaxira faylini shu yerga yuboring.\n\n"
        "⚠️ Diqqat: bu joriy ma'lumotlar bazasini butunlay almashtiradi!"
    )


@router.message(AdminStates.waiting_for_restore_file, IsAdmin(), F.document)
async def do_restore(message: Message, state: FSMContext, bot: Bot):
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, destination=db_service.DB_PATH)
    db_service.add_log("restore", f"by={message.from_user.id}")
    await message.answer("✅ Ma'lumotlar bazasi tiklandi.")
    await state.clear()


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_PING)
async def do_ping(message: Message, bot: Bot):
    start = time.monotonic()
    await bot.get_me()
    elapsed_ms = (time.monotonic() - start) * 1000
    await message.answer(f"📡 Pong! Telegram API javob vaqti: <b>{elapsed_ms:.0f} ms</b>", parse_mode="HTML")


# ================= 7) SILKALAR =================

@router.message(StateFilter(None), IsAdmin(), F.text == CAT_LINKS)
async def show_links_category(message: Message):
    await message.answer("🔗 <b>Silkalar</b>", reply_markup=links_category_kb(), parse_mode="HTML")


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_ADD_LINK)
async def ask_link_category(message: Message):
    await message.answer(
        "🔗 Bu silka qaysi turdagi xabarlar ostida ko'rinsin?",
        reply_markup=link_type_kb(),
    )


@router.message(StateFilter(None), IsAdmin(), F.text.in_(_LINK_CATEGORY_MAP.keys()))
async def ask_link_url(message: Message, state: FSMContext):
    category = _LINK_CATEGORY_MAP[message.text]
    await state.update_data(link_category=category)
    await state.set_state(PromoLinkStates.waiting_for_url)
    await message.answer("🔗 Silka (URL) manzilini kiriting.\n\nMasalan: https://t.me/kanalim")


@router.message(PromoLinkStates.waiting_for_url, IsAdmin(), F.text)
async def ask_link_button_text(message: Message, state: FSMContext):
    url = message.text.strip()
    if url.startswith("t.me/"):
        url = "https://" + url
    elif url.startswith("@"):
        url = "https://t.me/" + url[1:]
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("❌ Iltimos, to'g'ri havola (https://... yoki t.me/...) yuboring.")
        return
    await state.update_data(link_url=url)
    await state.set_state(PromoLinkStates.waiting_for_button_text)
    await message.answer("✏️ Endi shu silka uchun tugma matnini kiriting.\n\nMasalan: 📢 E'lonni ko'rish")


@router.message(PromoLinkStates.waiting_for_button_text, IsAdmin(), F.text)
async def ask_link_duration(message: Message, state: FSMContext):
    await state.update_data(link_button_text=message.text.strip())
    await state.set_state(PromoLinkStates.waiting_for_duration)
    await message.answer(
        "⏳ Bu silka qancha muddat amal qilsin?\n\n"
        "Masalan: <code>3 kun</code>, <code>5 soat</code>, <code>30 daqiqa</code>, <code>2 oy</code>\n"
        "Muddatsiz (doim ko'rinib tursin) uchun: <code>doim</code>",
        parse_mode="HTML",
    )


@router.message(PromoLinkStates.waiting_for_duration, IsAdmin(), F.text)
async def do_add_link(message: Message, state: FSMContext):
    seconds, duration_label = _parse_duration(message.text)
    data = await state.get_data()
    category = data.get("link_category")
    url = data.get("link_url")
    button_text = data.get("link_button_text")

    expires_at = None
    if seconds is not None:
        expires_at = (datetime.now() + timedelta(seconds=seconds)).isoformat()

    link_id = db_service.add_promo_link(button_text, url, category, duration_label, expires_at)
    db_service.add_log("promo_link_add", f"id={link_id} category={category} by={message.from_user.id}")

    await message.answer(
        f"✅ Silka qo'shildi!\n\n"
        f"🔘 Tugma: {button_text}\n"
        f"🔗 Havola: {url}\n"
        f"📂 Turi: {CATEGORY_LABELS.get(category, category)}\n"
        f"⏳ Muddat: {duration_label}",
        reply_markup=links_category_kb(),
    )
    await state.clear()


@router.message(StateFilter(None), IsAdmin(), F.text == BTN_LIST_LINKS)
async def show_links_list(message: Message):
    links = db_service.get_active_promo_links()
    if not links:
        await message.answer("📋 Hozircha faol silkalar yo'q.")
        return

    lines = ["📋 <b>Faol silkalar:</b>\n"]
    rows = []
    for link in links:
        remaining = _format_remaining(link["expires_at"])
        cat_label = CATEGORY_LABELS.get(link["category"], link["category"])
        lines.append(
            f"🔘 <b>{link['button_text']}</b>\n"
            f"   📂 {cat_label} | ⏳ {remaining}\n"
            f"   🔗 {link['url']}\n"
        )
        rows.append([f"❌ O'chirish #{link['id']}"])
    rows.append([BTN_BACK])

    await message.answer("\n".join(lines), reply_markup=_kb(rows), parse_mode="HTML")


@router.message(StateFilter(None), IsAdmin(), F.text.startswith("❌ O'chirish #"))
async def do_delete_link(message: Message):
    try:
        link_id = int(message.text.split("#", 1)[1])
    except (IndexError, ValueError):
        return
    db_service.deactivate_promo_link(link_id)
    db_service.add_log("promo_link_remove", f"id={link_id} by={message.from_user.id}")
    await message.answer("✅ Silka ro'yxatdan olib tashlandi.")
    await show_links_list(message)