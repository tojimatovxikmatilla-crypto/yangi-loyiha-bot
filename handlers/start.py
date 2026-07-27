from aiogram import Router, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from utils.keyboards import main_menu_kb, back_to_menu_kb, main_menu_reply_kb, BTN_ABOUT
from services import db_service

router = Router(name="start")

DEFAULT_WELCOME_TEXT = (
    "🤖 <b>Universal AI Bot</b>\n\n"
    "✨ Sun'iy intellekt yordamchisi – savollarga javob, tarjima, matn yozish\n"
    "⬇️ Instagram, TikTok, Facebook, X, Pinterest, YouTube'dan yuklab olish\n"
    "🎵 Musiqa yuklab olish (YouTube)\n"
    "🎧 Shazam — qo'shiqni ovozidan aniqlash\n\n"
    "Quyidagi menyudan birini tanlang 👇"
)

ABOUT_TEXT = (
    "ℹ️ <b>Universal AI Bot</b>\n\n"
    "Quyidagi funksiyalarni taqdim etadi:\n"
    "⬇️ Video/rasm yuklab olish (Instagram, TikTok, Facebook, X, Pinterest, YouTube)\n"
    "🤖 AI yordamchi — savol-javob, tarjima, matn yozish\n"
    "🎵 Musiqa qidirish va yuklash\n"
    "🎧 Shazam — qo'shiqni ovozidan aniqlash\n\n"
    "Savol yoki taklif bo'lsa, \"☎️ Admin bilan bog'lanish\" tugmasidan foydalaning."
)


def _welcome_text() -> str:
    """Admin panelda tahrirlangan matn bo'lsa o'shani, aks holda standartini qaytaradi."""
    custom = db_service.get_setting("welcome_text", "")
    return custom if custom else DEFAULT_WELCOME_TEXT


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(_welcome_text(), reply_markup=main_menu_reply_kb())


@router.message(F.text == BTN_ABOUT)
async def show_about_reply(message: Message):
    await message.answer(ABOUT_TEXT)


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(_welcome_text(), reply_markup=None)
    await callback.answer()


@router.callback_query(F.data == "menu:about")
async def show_about(callback: CallbackQuery):
    await callback.message.edit_text(ABOUT_TEXT, reply_markup=back_to_menu_kb())
    await callback.answer()