"""
To'liq admin panel.

/admin buyrug'i pastda doimiy ko'rinadigan 6 ta bo'lim tugmasini chiqaradi.
Har bir bo'lim o'ziga oid inline submenyuni ochadi.

Bo'limlar:
1. 📊 Asosiy boshqaruv — foydalanuvchilar, statistika, broadcast, ban/unban, sozlamalar
2. 🤖 Bot funksiyalari — har bir funksiyani alohida yoqish/o'chirish, xush kelibsiz matnini tahrirlash
3. 💎 Premium — premium berish/bekor qilish, promo kodlar, obunalar ro'yxati
4. 🛡 Xavfsizlik — spam nazorati holati, shikoyatlar, loglar, adminlar ro'yxati
5. 📁 Kontent — fayllar/media statistikasi, API holati, server holati
6. 🔧 Texnik — botni qayta ishga tushirish, zaxira/tiklash, ping
"""
import asyncio
import logging
import os
import platform
import random
import string
import sys
import time
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter, BaseFilter
from aiogram.types import Message, CallbackQuery, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from services import db_service
from utils.states import AdminStates
from config import config

logger = logging.getLogger(__name__)
router = Router(name="admin")

START_TIME = datetime.now()

# ---------- Bo'lim nomlari (pastdagi doimiy tugmalar matni) ----------
CAT_MAIN = "📊 Asosiy boshqaruv"
CAT_FUNCTIONS = "🤖 Bot funksiyalari"
CAT_PREMIUM = "💎 Premium"
CAT_SECURITY = "🛡 Xavfsizlik"
CAT_CONTENT = "📁 Kontent"
CAT_TECH = "🔧 Texnik"


class IsAdmin(BaseFilter):
    async def __call__(self, event) -> bool:
        user = event.from_user
        return bool(user) and user.id in config.ADMIN_IDS


def admin_reply_kb() -> ReplyKeyboardMarkup:
    """Admin panelga kirgach pastda DOIMIY ko'rinadigan 6 ta bo'lim tugmasi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CAT_MAIN), KeyboardButton(text=CAT_FUNCTIONS)],
            [KeyboardButton(text=CAT_PREMIUM), KeyboardButton(text=CAT_SECURITY)],
            [KeyboardButton(text=CAT_CONTENT), KeyboardButton(text=CAT_TECH)],
        ],
        resize_keyboard=True,
        is_persistent=False,
    )


def _back_kb(callback_data: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Orqaga", callback_data=callback_data)
    return builder.as_markup()


# ================= /admin — panelni ochish =================

@router.message(Command("admin"), IsAdmin())
async def open_admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔐 <b>Admin panel</b>\n\nPastdagi bo'limlardan birini tanlang 👇",
        reply_markup=admin_reply_kb(),
        parse_mode="HTML",
    )


# ================= 1) ASOSIY BOSHQARUV =================

def main_category_kb():
    b = InlineKeyboardBuilder()
    b.button(text="👤 Foydalanuvchilar", callback_data="admin:users")
    b.button(text="📈 Statistika", callback_data="admin:stats")
    b.button(text="📢 Xabar yuborish", callback_data="admin:broadcast")
    b.button(text="🚫 Ban", callback_data="admin:ban")
    b.button(text="✅ Unban", callback_data="admin:unban")
    b.button(text="⚙️ Sozlamalar", callback_data="admin:settings")
    b.adjust(1)
    return b.as_markup()


@router.message(StateFilter(None), IsAdmin(), F.text == CAT_MAIN)
async def show_main_category(message: Message):
    await message.answer("📊 <b>Asosiy boshqaruv</b>", reply_markup=main_category_kb(), parse_mode="HTML")


@router.callback_query(IsAdmin(), F.data == "admin:users")
async def show_users(callback: CallbackQuery):
    count = db_service.get_user_count()
    recent = db_service.get_recent_users(10)
    lines = [f"👥 <b>Jami: {count} ta foydalanuvchi</b>\n", "So'nggi 10 tasi:"]
    for user_id, username, first_seen in recent:
        uname = f"@{username}" if username else "(username yo'q)"
        lines.append(f"• <code>{user_id}</code> — {uname}")
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=_back_kb("admin:back_main"), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:stats")
async def show_stats(callback: CallbackQuery):
    total = db_service.get_user_count()
    banned = db_service.get_banned_count()
    premium = len(db_service.get_premium_users())
    maintenance = "🔴 Yoqilgan" if db_service.is_maintenance_mode() else "🟢 O'chirilgan"
    await callback.message.edit_text(
        f"📈 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total}</b>\n"
        f"⛔ Bloklanganlar: <b>{banned}</b>\n"
        f"💎 Premium foydalanuvchilar: <b>{premium}</b>\n"
        f"🛠 Texnik ishlar rejimi: {maintenance}",
        reply_markup=_back_kb("admin:back_main"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:broadcast")
async def ask_broadcast_message(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await callback.message.edit_text(
        "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing.",
        reply_markup=_back_kb("admin:back_main"),
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_broadcast_message, IsAdmin())
async def do_broadcast(message: Message, state: FSMContext):
    user_ids = db_service.get_all_user_ids()
    status = await message.answer(f"⏳ {len(user_ids)} ta foydalanuvchiga yuborilmoqda...")

    sent, failed = 0, 0
    for user_id in user_ids:
        try:
            await message.copy_to(chat_id=user_id)
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


@router.callback_query(IsAdmin(), F.data == "admin:ban")
async def ask_ban_id(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_ban_id)
    await callback.message.edit_text(
        "🚫 Bloklanadigan foydalanuvchining Telegram ID raqamini yuboring.",
        reply_markup=_back_kb("admin:back_main"),
    )
    await callback.answer()


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


@router.callback_query(IsAdmin(), F.data == "admin:unban")
async def ask_unban_id(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_unban_id)
    await callback.message.edit_text(
        "✅ Blokdan chiqariladigan foydalanuvchining Telegram ID raqamini yuboring.",
        reply_markup=_back_kb("admin:back_main"),
    )
    await callback.answer()


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


@router.callback_query(IsAdmin(), F.data == "admin:settings")
async def show_settings(callback: CallbackQuery):
    maintenance = "🔴 Yoqilgan" if db_service.is_maintenance_mode() else "🟢 O'chirilgan"
    b = InlineKeyboardBuilder()
    b.button(text=f"🛠 Texnik ishlar: {maintenance}", callback_data="admin:toggle_maintenance")
    b.button(text="✏️ Xush kelibsiz matnini tahrirlash", callback_data="admin:edit_welcome")
    b.button(text="⬅️ Orqaga", callback_data="admin:back_main")
    b.adjust(1)
    await callback.message.edit_text("⚙️ <b>Sozlamalar</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:toggle_maintenance")
async def toggle_maintenance(callback: CallbackQuery):
    current = db_service.is_maintenance_mode()
    db_service.set_maintenance_mode(not current)
    db_service.add_log("maintenance_toggle", f"enabled={not current} by={callback.from_user.id}")
    await show_settings(callback)


@router.callback_query(IsAdmin(), F.data == "admin:edit_welcome")
async def ask_welcome_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_welcome_text)
    await callback.message.edit_text(
        "✏️ Yangi xush kelibsiz (/start) matnini yuboring.\n\n"
        "Standart matnga qaytarish uchun \"-\" yuboring.",
        reply_markup=_back_kb("admin:back_main"),
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_welcome_text, IsAdmin(), F.text)
async def do_edit_welcome(message: Message, state: FSMContext):
    new_text = "" if message.text.strip() == "-" else message.text
    db_service.set_setting("welcome_text", new_text)
    await message.answer("✅ Xush kelibsiz matni yangilandi.")
    await state.clear()


@router.callback_query(IsAdmin(), F.data == "admin:back_main")
async def back_to_main_category(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("📊 <b>Asosiy boshqaruv</b>", reply_markup=main_category_kb(), parse_mode="HTML")
    await callback.answer()


# ================= 2) BOT FUNKSIYALARI =================

def functions_category_kb():
    b = InlineKeyboardBuilder()
    b.button(text="➕ Funksiya qo'shish", callback_data="admin:add_feature_info")
    b.button(text="🔁 Funksiyalarni yoqish/o'chirish", callback_data="admin:features")
    b.button(text="📝 Xush kelibsiz matnini tahrirlash", callback_data="admin:edit_welcome")
    b.adjust(1)
    return b.as_markup()


@router.message(StateFilter(None), IsAdmin(), F.text == CAT_FUNCTIONS)
async def show_functions_category(message: Message):
    await message.answer("🤖 <b>Bot funksiyalari</b>", reply_markup=functions_category_kb(), parse_mode="HTML")


@router.callback_query(IsAdmin(), F.data == "admin:add_feature_info")
async def add_feature_info(callback: CallbackQuery):
    await callback.message.edit_text(
        "➕ <b>Yangi funksiya qo'shish</b>\n\n"
        "Yangi funksiya (masalan yangi buyruq yoki xizmat) qo'shish — bu kod darajasidagi "
        "o'zgarish, botni qayta yozishni talab qiladi. Buni ishlab chiquvchi bilan "
        "(shu suhbat orqali) amalga oshirish mumkin — bot ishlab turganda avtomatik qo'shib "
        "bo'lmaydi.\n\n"
        "Mavjud funksiyalarni esa pastdagi \"Funksiyalarni yoqish/o'chirish\" orqali "
        "istalgan vaqt boshqarishingiz mumkin.",
        reply_markup=_back_kb("admin:back_functions"),
        parse_mode="HTML",
    )
    await callback.answer()


def _features_kb():
    b = InlineKeyboardBuilder()
    flags = db_service.get_all_feature_flags()
    for key, label in db_service.ALL_FEATURES.items():
        enabled = flags.get(key, True)
        status = "🟢" if enabled else "🔴"
        b.button(text=f"{status} {label}", callback_data=f"admin:toggle_feature:{key}")
    b.button(text="⬅️ Orqaga", callback_data="admin:back_functions")
    b.adjust(1)
    return b.as_markup()


@router.callback_query(IsAdmin(), F.data == "admin:features")
async def show_features(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔁 <b>Funksiyalarni yoqish/o'chirish</b>\n\nBosib holatini almashtiring:",
        reply_markup=_features_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("admin:toggle_feature:"))
async def toggle_feature(callback: CallbackQuery):
    key = callback.data.split(":")[2]
    current = db_service.get_feature_enabled(key)
    db_service.set_feature_enabled(key, not current)
    db_service.add_log("feature_toggle", f"{key}={not current} by={callback.from_user.id}")
    await callback.message.edit_reply_markup(reply_markup=_features_kb())
    await callback.answer("Holat yangilandi ✅")


@router.callback_query(IsAdmin(), F.data == "admin:back_functions")
async def back_to_functions_category(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🤖 <b>Bot funksiyalari</b>", reply_markup=functions_category_kb(), parse_mode="HTML")
    await callback.answer()


# ================= 3) PREMIUM =================

def premium_category_kb():
    b = InlineKeyboardBuilder()
    b.button(text="💎 Premium berish", callback_data="admin:grant_premium")
    b.button(text="❌ Premiumni bekor qilish", callback_data="admin:revoke_premium")
    b.button(text="🎁 Promo kod yaratish", callback_data="admin:create_promo")
    b.button(text="💳 Obunalar ro'yxati", callback_data="admin:subscriptions")
    b.adjust(1)
    return b.as_markup()


@router.message(StateFilter(None), IsAdmin(), F.text == CAT_PREMIUM)
async def show_premium_category(message: Message):
    await message.answer("💎 <b>Premium</b>", reply_markup=premium_category_kb(), parse_mode="HTML")


@router.callback_query(IsAdmin(), F.data == "admin:grant_premium")
async def ask_grant_premium_id(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_premium_grant_id)
    await callback.message.edit_text(
        "💎 Premium beriladigan foydalanuvchi ID raqamini yuboring.",
        reply_markup=_back_kb("admin:back_premium"),
    )
    await callback.answer()


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


@router.callback_query(IsAdmin(), F.data == "admin:revoke_premium")
async def ask_revoke_premium_id(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_premium_revoke_id)
    await callback.message.edit_text(
        "❌ Premiumi bekor qilinadigan foydalanuvchi ID raqamini yuboring.",
        reply_markup=_back_kb("admin:back_premium"),
    )
    await callback.answer()


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


@router.callback_query(IsAdmin(), F.data == "admin:create_promo")
async def ask_promo_days(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_promo_days)
    await callback.message.edit_text(
        "🎁 Promo kod nechchi kunlik premium bersin? (raqam yuboring)",
        reply_markup=_back_kb("admin:back_premium"),
    )
    await callback.answer()


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


@router.callback_query(IsAdmin(), F.data == "admin:subscriptions")
async def show_subscriptions(callback: CallbackQuery):
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
    await callback.message.edit_text(text, reply_markup=_back_kb("admin:back_premium"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:back_premium")
async def back_to_premium_category(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("💎 <b>Premium</b>", reply_markup=premium_category_kb(), parse_mode="HTML")
    await callback.answer()


# ================= 4) XAVFSIZLIK =================

def security_category_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🚫 Spam nazorati", callback_data="admin:spam_info")
    b.button(text="🚨 Shikoyatlar", callback_data="admin:complaints")
    b.button(text="📋 Loglar", callback_data="admin:logs")
    b.button(text="🔑 Adminlar", callback_data="admin:admins")
    b.adjust(1)
    return b.as_markup()


@router.message(StateFilter(None), IsAdmin(), F.text == CAT_SECURITY)
async def show_security_category(message: Message):
    await message.answer("🛡 <b>Xavfsizlik</b>", reply_markup=security_category_kb(), parse_mode="HTML")


@router.callback_query(IsAdmin(), F.data == "admin:spam_info")
async def show_spam_info(callback: CallbackQuery):
    from utils.middlewares import SPAM_WINDOW_SECONDS, SPAM_MAX_MESSAGES
    await callback.message.edit_text(
        f"🚫 <b>Spam nazorati</b>\n\n"
        f"Holat: 🟢 Faol\n"
        f"Chegara: {SPAM_WINDOW_SECONDS} soniyada {SPAM_MAX_MESSAGES} tadan ortiq xabar "
        f"yuborgan foydalanuvchi vaqtincha sekinlashtiriladi.\n"
        f"Adminlar bu cheklovdan ozod.",
        reply_markup=_back_kb("admin:back_security"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:complaints")
async def show_complaints(callback: CallbackQuery):
    complaints = db_service.get_complaints(only_unresolved=True, limit=10)
    if not complaints:
        text = "🚨 Hal qilinmagan shikoyatlar yo'q."
        kb = _back_kb("admin:back_security")
    else:
        lines = ["🚨 <b>Hal qilinmagan shikoyatlar:</b>\n"]
        b = InlineKeyboardBuilder()
        for cid, user_id, text_, created_at, resolved in complaints:
            preview = text_[:80] + ("..." if len(text_) > 80 else "")
            lines.append(f"#{cid} — <code>{user_id}</code>: {preview}")
            b.button(text=f"✅ #{cid} yopish", callback_data=f"admin:resolve:{cid}")
        b.button(text="⬅️ Orqaga", callback_data="admin:back_security")
        b.adjust(1)
        text = "\n".join(lines)
        kb = b.as_markup()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("admin:resolve:"))
async def resolve_complaint(callback: CallbackQuery):
    complaint_id = int(callback.data.split(":")[2])
    db_service.resolve_complaint(complaint_id)
    await callback.answer("✅ Yopildi")
    await show_complaints(callback)


@router.callback_query(IsAdmin(), F.data == "admin:logs")
async def show_logs(callback: CallbackQuery):
    logs = db_service.get_recent_logs(15)
    if not logs:
        text = "📋 Hali loglar yo'q."
    else:
        lines = ["📋 <b>So'nggi harakatlar:</b>\n"]
        for action, details, created_at in logs:
            lines.append(f"• <code>{created_at}</code> — {action}: {details}")
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=_back_kb("admin:back_security"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:admins")
async def show_admins(callback: CallbackQuery):
    lines = ["🔑 <b>Adminlar ro'yxati:</b>\n"]
    for admin_id in config.ADMIN_IDS:
        lines.append(f"• <code>{admin_id}</code>")
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=_back_kb("admin:back_security"), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:back_security")
async def back_to_security_category(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🛡 <b>Xavfsizlik</b>", reply_markup=security_category_kb(), parse_mode="HTML")
    await callback.answer()


# ================= 5) KONTENT =================

def content_category_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📁 Fayllar", callback_data="admin:files")
    b.button(text="🖼 Media statistikasi", callback_data="admin:media")
    b.button(text="🔗 API holati", callback_data="admin:api_status")
    b.button(text="🌐 Server holati", callback_data="admin:server_status")
    b.adjust(1)
    return b.as_markup()


@router.message(StateFilter(None), IsAdmin(), F.text == CAT_CONTENT)
async def show_content_category(message: Message):
    await message.answer("📁 <b>Kontent</b>", reply_markup=content_category_kb(), parse_mode="HTML")


@router.callback_query(IsAdmin(), F.data == "admin:files")
async def show_files(callback: CallbackQuery):
    folder = config.DOWNLOAD_DIR
    count, total_size = 0, 0
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if os.path.isfile(path):
                count += 1
                total_size += os.path.getsize(path)
    await callback.message.edit_text(
        f"📁 <b>Fayllar</b>\n\n"
        f"Vaqtinchalik papkada hozir: <b>{count}</b> ta fayl\n"
        f"Umumiy hajm: <b>{total_size / 1024 / 1024:.2f} MB</b>\n\n"
        f"(Fayllar har bir amaldan keyin avtomatik o'chiriladi, shu sabab bu odatda 0 bo'lishi kerak)",
        reply_markup=_back_kb("admin:back_content"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:media")
async def show_media_stats(callback: CallbackQuery):
    downloads = db_service.get_counter("downloads_completed")
    ocr = db_service.get_counter("ocr_processed")
    qr_created = db_service.get_counter("qr_created")
    voice = db_service.get_counter("voice_processed")
    await callback.message.edit_text(
        f"🖼 <b>Media statistikasi</b> (bot ishga tushgandan buyon)\n\n"
        f"⬇️ Yuklab olingan medialar: <b>{downloads}</b>\n"
        f"🖼 OCR orqali o'qilgan rasmlar: <b>{ocr}</b>\n"
        f"📌 Yaratilgan QR kodlar: <b>{qr_created}</b>\n"
        f"🎙 Qayta ishlangan ovozli xabarlar: <b>{voice}</b>",
        reply_markup=_back_kb("admin:back_content"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:api_status")
async def show_api_status(callback: CallbackQuery):
    ai_status = "🟢 Ulangan" if config.AI_API_KEY else "🔴 Ulanmagan"
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        ocr_status = "🟢 O'rnatilgan"
    except Exception:
        ocr_status = "🔴 Topilmadi"
    await callback.message.edit_text(
        f"🔗 <b>API holati</b>\n\n"
        f"🤖 AI (Claude) API: {ai_status}\n"
        f"🖼 Tesseract OCR: {ocr_status}\n"
        f"🌤 Ob-havo (Open-Meteo): 🟢 Doim ochiq (kalit shart emas)",
        reply_markup=_back_kb("admin:back_content"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:server_status")
async def show_server_status(callback: CallbackQuery):
    uptime = datetime.now() - START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    await callback.message.edit_text(
        f"🌐 <b>Server holati</b>\n\n"
        f"⏱ Ishlab turgan vaqti: {hours}s {minutes}m {seconds}soniya\n"
        f"🐍 Python versiyasi: {platform.python_version()}\n"
        f"💻 OS: {platform.system()} {platform.release()}",
        reply_markup=_back_kb("admin:back_content"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:back_content")
async def back_to_content_category(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("📁 <b>Kontent</b>", reply_markup=content_category_kb(), parse_mode="HTML")
    await callback.answer()


# ================= 6) TEXNIK =================

def tech_category_kb():
    b = InlineKeyboardBuilder()
    b.button(text="♻️ Botni qayta ishga tushirish", callback_data="admin:restart_confirm")
    b.button(text="📦 Zaxira (Backup)", callback_data="admin:backup")
    b.button(text="📥 Restore", callback_data="admin:restore")
    b.button(text="📡 Ping", callback_data="admin:ping")
    b.adjust(1)
    return b.as_markup()


@router.message(StateFilter(None), IsAdmin(), F.text == CAT_TECH)
async def show_tech_category(message: Message):
    await message.answer("🔧 <b>Texnik</b>", reply_markup=tech_category_kb(), parse_mode="HTML")


@router.callback_query(IsAdmin(), F.data == "admin:restart_confirm")
async def confirm_restart(callback: CallbackQuery):
    b = InlineKeyboardBuilder()
    b.button(text="⚠️ Ha, qayta ishga tushirish", callback_data="admin:restart_do")
    b.button(text="⬅️ Bekor qilish", callback_data="admin:back_tech")
    b.adjust(1)
    await callback.message.edit_text(
        "♻️ Botni qayta ishga tushirmoqchimisiz? Bot bir necha soniyaga o'chib qoladi.",
        reply_markup=b.as_markup(),
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:restart_do")
async def do_restart(callback: CallbackQuery):
    db_service.add_log("restart", f"by={callback.from_user.id}")
    await callback.message.edit_text("♻️ Bot qayta ishga tushirilmoqda...")
    await callback.answer()
    os.execv(sys.executable, [sys.executable] + sys.argv)


@router.callback_query(IsAdmin(), F.data == "admin:backup")
async def do_backup(callback: CallbackQuery, bot: Bot):
    if not os.path.exists(db_service.DB_PATH):
        await callback.answer("❌ Ma'lumotlar bazasi hali yaratilmagan.", show_alert=True)
        return
    await bot.send_document(
        chat_id=callback.from_user.id,
        document=FSInputFile(db_service.DB_PATH),
        caption=f"📦 Zaxira nusxa — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )
    db_service.add_log("backup", f"by={callback.from_user.id}")
    await callback.answer("✅ Yuborildi")


@router.callback_query(IsAdmin(), F.data == "admin:restore")
async def ask_restore_file(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_restore_file)
    await callback.message.edit_text(
        "📥 Tiklash uchun avval yuborilgan .db zaxira faylini shu yerga yuboring.\n\n"
        "⚠️ Diqqat: bu joriy ma'lumotlar bazasini butunlay almashtiradi!",
        reply_markup=_back_kb("admin:back_tech"),
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_restore_file, IsAdmin(), F.document)
async def do_restore(message: Message, state: FSMContext, bot: Bot):
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, destination=db_service.DB_PATH)
    db_service.add_log("restore", f"by={message.from_user.id}")
    await message.answer("✅ Ma'lumotlar bazasi tiklandi.")
    await state.clear()


@router.callback_query(IsAdmin(), F.data == "admin:ping")
async def do_ping(callback: CallbackQuery, bot: Bot):
    start = time.monotonic()
    await bot.get_me()
    elapsed_ms = (time.monotonic() - start) * 1000
    await callback.message.edit_text(
        f"📡 Pong! Telegram API javob vaqti: <b>{elapsed_ms:.0f} ms</b>",
        reply_markup=_back_kb("admin:back_tech"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "admin:back_tech")
async def back_to_tech_category(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🔧 <b>Texnik</b>", reply_markup=tech_category_kb(), parse_mode="HTML")
    await callback.answer()
