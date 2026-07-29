"""
Oddiy foydalanuvchilar uchun:
- /report — shikoyat/muammo yuborish (admin panelda "Shikoyatlar" bo'limida ko'rinadi)
- /promo — promo kod kiritib premium olish
"""
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services import db_service
from utils.states import UserStates, ContactAdminStates, AdminReplyStates
from utils.keyboards import BTN_CONTACT_ADMIN, ALL_MENU_BUTTONS
from handlers.admin import IsAdmin
from config import config

router = Router(name="support")


@router.message(F.text == BTN_CONTACT_ADMIN)
async def start_contact_admin(message: Message, state: FSMContext):
    await state.set_state(ContactAdminStates.waiting_for_message)
    await message.answer("✉️ Adminga yubormoqchi bo'lgan xabaringizni yozing.")


# ~F.text.in_(ALL_MENU_BUTTONS) — boshqa funksiya tugmasi bosilganda bu
# handler uni "adminga xabar" deb qabul qilib olmasligi uchun.
@router.message(ContactAdminStates.waiting_for_message, F.text, ~F.text.in_(ALL_MENU_BUTTONS))
async def forward_to_admin(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    uname = f"@{user.username}" if user.username else "(username yo'q)"
    text = (
        f"✉️ <b>Yangi xabar</b>\n"
        f"👤 {uname} — <code>{user.id}</code>\n\n"
        f"{message.text}"
    )

    reply_kb = InlineKeyboardBuilder()
    reply_kb.button(text="✍️ Javob yozish", callback_data=f"admin_reply:{user.id}")

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_kb.as_markup(), parse_mode="HTML")
        except Exception:
            pass
    await message.answer("✅ Xabaringiz adminga yuborildi. Tez orada javob berishadi.")
    await state.set_state(ContactAdminStates.waiting_for_message)


# ---------- Admin javob yozishi ----------

@router.callback_query(IsAdmin(), F.data.startswith("admin_reply:"))
async def choose_reply_mode(callback: CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split(":")[1])
    await state.update_data(target_user_id=target_user_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Javob berish", callback_data=f"admin_reply_mode:reply:{target_user_id}")
    kb.button(text="❌ Bekor qilish", callback_data=f"admin_reply_mode:cancel:{target_user_id}")
    kb.adjust(1)

    await callback.message.answer(
        "Nima qilmoqchisiz?",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("admin_reply_mode:"))
async def ask_reply_text(callback: CallbackQuery, state: FSMContext):
    _, mode, target_user_id = callback.data.split(":")
    await state.set_state(AdminReplyStates.waiting_for_reply_text)
    await state.update_data(target_user_id=int(target_user_id), mode=mode)

    if mode == "reply":
        prompt = "✍️ Javobingizni yozing."
    else:
        prompt = "✍️ Bekor qilish sababini yozing."

    await callback.message.answer(prompt)
    await callback.answer()


@router.message(AdminReplyStates.waiting_for_reply_text, IsAdmin(), F.text)
async def send_admin_reply(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    mode = data.get("mode", "reply")

    if mode == "reply":
        text_to_send = f"👨‍💻 <b>Admin javobi:</b>\n\n{message.text}"
    else:
        text_to_send = f"❌ <b>Murojaatingiz bekor qilindi.</b>\n\nSababi: {message.text}"

    try:
        await bot.send_message(target_user_id, text_to_send, parse_mode="HTML")
        await message.answer("✅ Yuborildi.")
    except Exception:
        await message.answer("❌ Xabar yuborilmadi — foydalanuvchi botni bloklagan bo'lishi mumkin.")

    await state.clear()


@router.message(Command("report"))
async def start_report(message: Message, state: FSMContext):
    await state.set_state(UserStates.waiting_for_complaint_text)
    await message.answer("🚨 Muammo yoki shikoyatingizni batafsil yozing.")


@router.message(UserStates.waiting_for_complaint_text, F.text, ~F.text.in_(ALL_MENU_BUTTONS))
async def receive_report(message: Message, state: FSMContext):
    db_service.add_complaint(message.from_user.id, message.text)
    await message.answer("✅ Qabul qilindi, admin tez orada ko'rib chiqadi. Rahmat!")
    await state.clear()


@router.message(Command("promo"))
async def start_promo(message: Message, state: FSMContext):
    await state.set_state(UserStates.waiting_for_promo_code)
    await message.answer("🎁 Promo kodni yuboring.")


@router.message(UserStates.waiting_for_promo_code, F.text, ~F.text.in_(ALL_MENU_BUTTONS))
async def receive_promo(message: Message, state: FSMContext):
    days = db_service.redeem_promo_code(message.text.strip(), message.from_user.id)
    if days is None:
        await message.answer("❌ Bu kod noto'g'ri yoki allaqachon ishlatilgan.")
    else:
        await message.answer(f"🎉 Tabriklaymiz! {days} kunlik premium faollashtirildi.")
    await state.clear()