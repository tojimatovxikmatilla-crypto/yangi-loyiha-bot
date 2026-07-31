import asyncio

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.downloader_service import extract_url, detect_platform, download_media, download_audio_from_url, cleanup_file
from services.music_service import search_music, download_music_by_id, download_music_with_fallback, cleanup_file as cleanup_music_file
from services.shazam_service import recognize_music
from services import db_service
from aiogram.filters import StateFilter
from utils.keyboards import back_to_menu_kb, BTN_DOWNLOADER
from handlers.music import _search_with_auto_retry

router = Router(name="downloader")

_pending_audio_urls: dict[str, str] = {}
_pending_titles: dict[str, str] = {}

PROMPT_TEXT = (
    "⬇️ <b>Universal Downloader</b>\n\n"
    "Instagram, TikTok, Facebook, X, Pinterest yoki YouTube havolasini yuboring — "
    "men videoni/rasmni yuklab beraman."
)

DISABLED_TEXT = "🔧 Bu funksiya admin tomonidan vaqtincha o'chirilgan."


def _append_promo_links(kb: InlineKeyboardBuilder, category: str) -> None:
    """Admin tomonidan shu turdagi xabarlar uchun qo'shilgan faol silkalarni tugma sifatida qo'shadi."""
    for link in db_service.get_active_promo_links(category):
        kb.button(text=link["button_text"], url=link["url"])


async def _download_media_with_auto_retry(status_msg: Message, url: str, attempts: int = 3, delay: float = 4.0):
    """
    Video/rasm yuklash ko'pincha vaqtinchalik sabablarga (cookie/bot-tekshiruv,
    tarmoq) ko'ra muvaffaqiyatsiz bo'lishi mumkin. Foydalanuvchiga darhol xato
    ko'rsatish o'rniga, bot avtomatik ravishda bir necha marta qayta urinadi.
    """
    result = None
    for attempt in range(1, attempts + 1):
        result = await asyncio.to_thread(download_media, url)
        if result.success:
            return result
        if attempt < attempts:
            await status_msg.edit_text(f"🔁 Avtomatik qayta urinilmoqda ({attempt}/{attempts - 1})...")
            await asyncio.sleep(delay)
    return result


async def _download_audio_with_auto_retry(status_msg: Message, url: str, attempts: int = 3, delay: float = 4.0):
    """download_audio_from_url uchun xuddi shu avtomatik qayta urinish mantiqi."""
    result = None
    for attempt in range(1, attempts + 1):
        result = await asyncio.to_thread(download_audio_from_url, url)
        if result.success:
            return result
        if attempt < attempts:
            await status_msg.edit_text(f"🔁 Avtomatik qayta urinilmoqda ({attempt}/{attempts - 1})...")
            await asyncio.sleep(delay)
    return result


@router.message(F.text == BTN_DOWNLOADER)
async def open_downloader_reply(message: Message, state: FSMContext):
    if not db_service.get_feature_enabled("downloader"):
        await message.answer(DISABLED_TEXT)
        return
    await state.clear()
    await message.answer(PROMPT_TEXT, parse_mode="HTML")


@router.callback_query(F.data == "menu:downloader")
async def open_downloader(callback: CallbackQuery, state: FSMContext):
    if not db_service.get_feature_enabled("downloader"):
        await callback.answer(DISABLED_TEXT, show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(PROMPT_TEXT, reply_markup=back_to_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.message(F.text.regexp(r"https?://").as_("_match"))
async def handle_link(message: Message, state: FSMContext, bot: Bot, **kwargs):
    url = extract_url(message.text)
    if not url:
        return

    platform = detect_platform(url)
    if not platform:
        return

    if not db_service.get_feature_enabled("downloader"):
        await message.answer(DISABLED_TEXT)
        return

    status_msg = await message.answer(f"⏳ {platform} havolasi qabul qilindi, yuklanmoqda...")

    result = await _download_media_with_auto_retry(status_msg, url)

    if not result.success:
        await status_msg.edit_text(f"❌ {result.error}\n\nBir necha marta avtomatik urinib ko'rdik.")
        return

    try:
        file = FSInputFile(result.file_path)

        me = await bot.me()
        action_kb = InlineKeyboardBuilder()

        if result.is_video:
            import uuid as _uuid
            short_id = _uuid.uuid4().hex[:12]
            _pending_audio_urls[short_id] = url
            _pending_titles[short_id] = result.title or ""

            if result.title:
                action_kb.button(text="🎵 Musiqani yuklash", callback_data=f"dl_music_search:{short_id}")
            action_kb.button(text="✂️ Musiqani ajratib olish", callback_data=f"dl_audio:{short_id}")

        action_kb.button(text="➕ Guruhga qo'shish", url=f"https://t.me/{me.username}?startgroup=true")

        _append_promo_links(action_kb, "video" if result.is_video else "photo")

        action_kb.adjust(1)

        caption = f"📥 @{me.username} orqali yuklab olindi"

        if result.is_video:
            await message.answer_video(
                file,
                caption=caption,
                reply_markup=action_kb.as_markup(),
                duration=result.duration or 0,
                width=result.width or 0,
                height=result.height or 0,
                supports_streaming=True,
            )
        else:
            await message.answer_photo(file, caption=caption, reply_markup=action_kb.as_markup())
        await status_msg.delete()
        db_service.increment_counter("downloads_completed")
    finally:
        cleanup_file(result.file_path)


@router.callback_query(F.data.startswith("dl_audio:"))
async def handle_extract_audio(callback: CallbackQuery, bot: Bot):
    short_id = callback.data.split(":", 1)[1]
    url = _pending_audio_urls.get(short_id)

    if not url:
        await callback.answer("⚠️ Havola eskirgan, videoni qayta yuboring.", show_alert=True)
        return

    await callback.answer("⏳ Qo'shiq ajratilmoqda...")
    status_msg = await callback.message.answer("⏳ Qo'shiq ajratilmoqda...")

    result = await _download_audio_with_auto_retry(status_msg, url)

    if not result.success:
        await status_msg.edit_text(f"❌ {result.error}\n\nBir necha marta avtomatik urinib ko'rdik.")
        return

    try:
        me = await bot.me()
        audio_kb = InlineKeyboardBuilder()
        audio_kb.button(text="➕ Guruhga qo'shish", url=f"https://t.me/{me.username}?startgroup=true")
        _append_promo_links(audio_kb, "music")

        await callback.message.answer_audio(
            FSInputFile(result.file_path),
            caption=f"📥 @{me.username} orqali yuklab olindi",
            reply_markup=audio_kb.as_markup(),
        )
        await status_msg.delete()
        db_service.increment_counter("music_downloaded")
    finally:
        cleanup_file(result.file_path)


@router.callback_query(F.data.startswith("dl_music_search:"))
async def handle_music_search_from_video(callback: CallbackQuery, bot: Bot):
    short_id = callback.data.split(":", 1)[1]
    url = _pending_audio_urls.get(short_id)
    fallback_title = _pending_titles.get(short_id)

    if not url:
        await callback.answer("⚠️ Ma'lumot eskirgan, videoni qayta yuboring.", show_alert=True)
        return

    await callback.answer("⏳ Videodagi qo'shiq aniqlanmoqda...")
    status_msg = await callback.message.answer("🎧 Videodagi qo'shiq aniqlanmoqda...")

    extracted = await _download_audio_with_auto_retry(status_msg, url)

    search_query = fallback_title or ""
    if extracted.success:
        recognized = await recognize_music(extracted.file_path)
        cleanup_file(extracted.file_path)
        if recognized.success:
            search_query = f"{recognized.title} {recognized.artist}".strip()

    if not search_query:
        await status_msg.edit_text("❌ Bu video bo'yicha qo'shiq aniqlanmadi.")
        return

    await status_msg.edit_text("🔎 Qo'shiq qidirilmoqda...")
    search_results = await _search_with_auto_retry(status_msg, search_query, 5)

    if not search_results:
        await status_msg.edit_text("❌ Bu video bo'yicha qo'shiq bir necha marta urinib ko'rsak ham topilmadi.")
        return

    result = await asyncio.to_thread(download_music_with_fallback, search_results)

    if not result.success:
        await status_msg.edit_text(f"❌ {result.error}")
        return

    try:
        me = await bot.me()
        audio_kb = InlineKeyboardBuilder()
        audio_kb.button(text="➕ Guruhga qo'shish", url=f"https://t.me/{me.username}?startgroup=true")
        _append_promo_links(audio_kb, "music")

        await callback.message.answer_audio(
            FSInputFile(result.file_path),
            title=result.title,
            caption=f"📥 @{me.username} orqali yuklab olindi",
            reply_markup=audio_kb.as_markup(),
        )
        await status_msg.delete()
        db_service.increment_counter("music_downloaded")
    finally:
        cleanup_music_file(result.file_path)