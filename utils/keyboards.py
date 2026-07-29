"""
Umumiy klaviaturalar (asosiy menyu, til tanlash va h.k.).
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config


BTN_DOWNLOADER = "⬇️ Media yuklab olish"
BTN_AI = "🤖 AI yordamchi"
BTN_IMAGE_TRANSLATE = "🖼 Rasm tarjimoni (OCR)"
BTN_VOICE = "🎙 Ovoz ↔ Matn"
BTN_QR = "📌 QR kod"
BTN_HASHTAG = "#️⃣ Hashtag Generator"
BTN_CRYPTO = "🔒 Matn shifrlash"
BTN_WEATHER = "🌤 Ob-havo"
BTN_MUSIC = "🎵 Musiqa yuklash"
BTN_SHAZAM = "🎧 Shazam"
BTN_IMAGE_GEN = "🖼 Rasm yaratish"
BTN_CONTACT_ADMIN = "☎️ Admin bilan bog'lanish"
BTN_ABOUT = "ℹ️ Bot haqida"

# Pastdagi doimiy menyu tugmalarining barcha matnlari — funksiya ichidagi
# "matn kutish" holatlari (masalan shahar nomi, qidiruv so'zi va h.k.) bu
# matnlarni HECH QACHON o'z ma'lumoti sifatida qabul qilmasligi kerak.
# Aks holda boshqa funksiya tugmasi bosilganda, avvalgi funksiya uni
# "shahar nomi" yoki "qidiruv so'zi" deb tushunib, xato beradi va yangi
# funksiya umuman ochilmaydi.
ALL_MENU_BUTTONS = frozenset({
    BTN_DOWNLOADER,
    BTN_AI,
    BTN_IMAGE_TRANSLATE,
    BTN_VOICE,
    BTN_QR,
    BTN_HASHTAG,
    BTN_CRYPTO,
    BTN_WEATHER,
    BTN_MUSIC,
    BTN_SHAZAM,
    BTN_IMAGE_GEN,
    BTN_CONTACT_ADMIN,
    BTN_ABOUT,
})


def main_menu_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_AI), KeyboardButton(text=BTN_CONTACT_ADMIN)],
            [KeyboardButton(text=BTN_ABOUT)],
        ],
        resize_keyboard=True,
        # is_persistent=False — bu, aksincha, Telegram'ga klaviatura yonida
        # ⌨️ (almashtirish) belgisini KO'RSATISHNI buyuradi: foydalanuvchi
        # shu belgini bossa tugmalar yashiriladi, yana bossa qaytadan
        # ko'rsatiladi. Aynan shu "bossa-chiqadi, bossa-yashirinadi" xatti-
        # harakati kerak bo'lgani uchun True dan qaytarildi.
        is_persistent=False,
    )


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬇️ Media yuklab olish", callback_data="menu:downloader")
    builder.button(text="🤖 AI yordamchi", callback_data="menu:ai")
    builder.button(text="🖼 Rasm tarjimoni (OCR)", callback_data="menu:image_translate")
    builder.button(text="🎙 Ovoz ↔ Matn", callback_data="menu:voice")
    builder.button(text="📌 QR kod", callback_data="menu:qr")
    builder.button(text="#️⃣ Hashtag Generator", callback_data="menu:hashtag")
    builder.button(text="🔒 Matn shifrlash", callback_data="menu:crypto")
    builder.button(text="🌤 Ob-havo", callback_data="menu:weather")
    builder.button(text="ℹ️ Bot haqida", callback_data="menu:about")
    builder.adjust(1)
    return builder.as_markup()


def language_choice_kb(callback_prefix: str) -> InlineKeyboardMarkup:
    """
    Tarjima uchun til tanlash klaviaturasi.
    callback_prefix: masalan 'tr_lang' yoki 'img_lang' — qaysi oqimdan chaqirilganini bilish uchun.
    """
    builder = InlineKeyboardBuilder()
    for code, label in config.SUPPORTED_LANGUAGES.items():
        builder.button(text=label, callback_data=f"{callback_prefix}:{code}")
    builder.adjust(2)
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Bosh menyu", callback_data="menu:main")
    return builder.as_markup()