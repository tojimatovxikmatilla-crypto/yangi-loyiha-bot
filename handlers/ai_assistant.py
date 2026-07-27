from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.ai_service import ask_ai, translate_text, summarize_text
from services import db_service
from aiogram.filters import StateFilter
from utils.keyboards import back_to_menu_kb, language_choice_kb, BTN_AI, ALL_MENU_BUTTONS
from utils.states import AIAssistantStates, TranslateStates
from config import config

router = Router(name="ai_assistant")

MENU_TEXT = (
    "🤖 <b>AI yordamchi</b>\n\n"
    "Nima qilishni tanlang, yoki menyudan tashqari ham menga to'g'ridan-to'g'ri "
    "savol yozishingiz mumkin — javob beraman."
)


def ai_action_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Matnni tarjima qilish", callback_data="ai:translate")
    builder.button(text="📝 Matnni qisqartirish", callback_data="ai:summarize")
    builder.button(text="💬 Savol berish", callback_data="ai:ask")
    builder.button(text="⬅️ Bosh menyu", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


@router.message(F.text == BTN_AI)
async def open_ai_menu_reply(message: Message, state: FSMContext):
    if not db_service.get_feature_enabled("ai"):
        await message.answer("🔧 Bu funksiya admin tomonidan vaqtincha o'chirilgan.")
        return
    await state.clear()
    await message.answer(MENU_TEXT, reply_markup=ai_action_kb(), parse_mode="HTML")


@router.callback_query(F.data == "menu:ai")
async def open_ai_menu(callback: CallbackQuery, state: FSMContext):
    if not db_service.get_feature_enabled("ai"):
        await callback.answer("🔧 Bu funksiya admin tomonidan vaqtincha o'chirilgan.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(MENU_TEXT, reply_markup=ai_action_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ai:translate")
async def start_translate(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TranslateStates.waiting_for_text)
    await callback.message.edit_text(
        "✍️ Tarjima qilinadigan matnni yuboring.\n\n"
        "(Matnni yuborganingizdan keyin men sizdan <b>qaysi tilga</b> tarjima qilishni so'rayman.)",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ~F.text.in_(ALL_MENU_BUTTONS) — boshqa funksiya tugmasi bosilganda bu
# handler uni "tarjima qilinadigan matn" deb qabul qilib olmasligi uchun.
@router.message(TranslateStates.waiting_for_text, F.text, ~F.text.in_(ALL_MENU_BUTTONS))
async def receive_text_for_translation(message: Message, state: FSMContext):
    # Muhim: bu yerda AVTOMATIK tilni taxmin qilmaymiz — har doim so'raymiz.
    await state.update_data(source_text=message.text)
    await state.set_state(TranslateStates.waiting_for_target_lang)
    await message.answer(
        "🌍 Qaysi tilga tarjima qilib beraymi?",
        reply_markup=language_choice_kb("tr_lang"),
    )


@router.callback_query(TranslateStates.waiting_for_target_lang, F.data.startswith("tr_lang:"))
async def do_translate(callback: CallbackQuery, state: FSMContext):
    lang_code = callback.data.split(":")[1]
    lang_label = config.SUPPORTED_LANGUAGES.get(lang_code, lang_code)
    data = await state.get_data()
    source_text = data.get("source_text", "")

    await callback.message.edit_text("⏳ Tarjima qilinmoqda...")
    result = translate_text(source_text, lang_label)

    await callback.message.edit_text(
        f"🌍 <b>{lang_label}</b>:\n\n{result}",
        parse_mode="HTML",
    )
    # state.clear() o'rniga qayta matn kutish holatiga qaytaramiz — foydalanuvchi
    # tugmani qayta bosmasdan keyingi matnni to'g'ridan-to'g'ri yuborishi mumkin.
    await state.set_state(TranslateStates.waiting_for_text)
    await callback.answer()


@router.callback_query(F.data == "ai:summarize")
async def start_summarize(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIAssistantStates.chatting)
    await state.update_data(mode="summarize")
    await callback.message.edit_text(
        "📝 Qisqartirish kerak bo'lgan matnni yuboring.",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "ai:ask")
async def start_ask(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIAssistantStates.chatting)
    await state.update_data(mode="ask")
    await callback.message.edit_text(
        "💬 Savolingizni yozing.",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


# ~F.text.in_(ALL_MENU_BUTTONS) — boshqa funksiya tugmasi bosilganda bu
# handler uni AI'ga savol/matn deb qabul qilib olmasligi uchun. Shuningdek
# F.text qo'shildi — ilgari bu handler HAR QANDAY xabar turini (rasm,
# ovoz va h.k.) ham ushlab olar edi, endi faqat matnga ishlaydi.
@router.message(AIAssistantStates.chatting, F.text, ~F.text.in_(ALL_MENU_BUTTONS))
async def handle_chat_mode(message: Message, state: FSMContext):
    data = await state.get_data()
    mode = data.get("mode", "ask")

    await message.answer("⏳ O'ylanmoqda...")
    if mode == "summarize":
        result = summarize_text(message.text)
    else:
        result = ask_ai(message.text)

    await message.answer(result)
    # Bu handler state.clear() chaqirmaydi — foydalanuvchi AIAssistantStates.chatting
    # holatida qolib, keyingi xabarini ham to'g'ridan-to'g'ri AI'ga yuborishda davom etadi.