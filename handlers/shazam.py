import os
import uuid
import asyncio

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.shazam_service import recognize_music
from services.music_service import search_music, download_music_by_id, download_music_with_fallback, cleanup_file
from services import db_service
from utils.keyboards import BTN_SHAZAM
from utils.states import ShazamStates
from config import config

router = Router(name="shazam")

PROMPT_TEXT = (
    "🎧 <b>Shazam — qo'shiqni aniqlash</b>\n\n"
    "Menga qo'shiq jarangini (ovozli xabar yoki audio fayl) yuboring — "
    "men uni tanib, nomi va ijrochisini aytib beraman."
)

DISABLED_TEXT = "🔧 Bu funksiya admin tomonidan vaqtincha o'chirilgan."


@router.message(F.text == BTN_SHAZAM)
async def open_shazam_reply(message: Message, state: FSMContext, bot: Bot):
    if not db_service.get_feature_enabled("shazam"):
        await message.answer(DISABLED_TEXT)
        return
    await state.set_state(ShazamStates.waiting_for_audio)
    await message.answer(PROMPT_TEXT, parse_mode="HTML")


@router.message(StateFilter(None), F.voice | F.audio | F.video | F.video_note)
async def handle_shazam_audio(message: Message, state: FSMContext, bot: Bot):
    if not db_service.get_feature_enabled("shazam"):
        await message.answer(DISABLED_TEXT)
        await state.clear()
        return

    os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
    media_obj = message.voice or message.audio or message.video or message.video_note
    is_video_input = bool(message.video or message.video_note)
    file_ext = ".mp4" if is_video_input else ".ogg"
    file_path = os.path.join(config.DOWNLOAD_DIR, f"{uuid.uuid4()}{file_ext}")

    tg_file = await bot.get_file(media_obj.file_id)
    await bot.download_file(tg_file.file_path, destination=file_path)

    status = await message.answer("🎧 Tinglanmoqda, qo'shiq aniqlanmoqda...")

    result = await recognize_music(file_path)

    try:
        os.remove(file_path)
    except OSError:
        pass

    if not result.success:
        await status.edit_text(f"❌ {result.error}")
        return

    db_service.increment_counter("shazam_recognized")
    caption = f"🎵 <b>{result.title}</b>\n👤 {result.artist}"

    if result.cover_url:
        await message.answer_photo(result.cover_url, caption=caption, parse_mode="HTML")
        await status.edit_text("⏳ Qo'shiq topilib, yuklanmoqda...")
    else:
        await status.edit_text(caption + "\n\n⏳ Qo'shiq topilib, yuklanmoqda...", parse_mode="HTML")

    search_query = f"{result.title} {result.artist}".strip()

    cached = db_service.get_cached_music_query(search_query)
    if cached and os.path.exists(cached["file_path"]):
        me = await bot.me()
        add_group_kb = InlineKeyboardBuilder()
        add_group_kb.button(
            text="➕ Guruhga qo'shish",
            url=f"https://t.me/{me.username}?startgroup=true",
        )
        await message.answer_audio(
            FSInputFile(cached["file_path"]),
            title=result.title,
            performer=result.artist,
            caption=f"📥 @{me.username} orqali istagan musiqangizni tez va oson toping!",
            parse_mode="HTML",
            reply_markup=add_group_kb.as_markup(),
        )
        await status.delete()
        db_service.increment_counter("music_downloaded")
        db_service.increment_counter("music_served_from_cache")
        return

    search_results = await asyncio.to_thread(search_music, search_query, 5)

    if not search_results:
        await status.edit_text(f"⚠️ Qo'shiq aniqlandi, lekin YouTube'dan topilmadi.")
        return

    music_result = await asyncio.to_thread(download_music_with_fallback, search_results)

    if not music_result.success:
        await status.edit_text(f"⚠️ Qo'shiq aniqlandi, lekin yuklab bo'lmadi: {music_result.error}")
    else:
        try:
            audio_file = FSInputFile(music_result.file_path)

            me = await bot.me()
            add_group_kb = InlineKeyboardBuilder()
            add_group_kb.button(
                text="➕ Guruhga qo'shish",
                url=f"https://t.me/{me.username}?startgroup=true",
            )

            await message.answer_audio(
                audio_file,
                title=result.title,
                performer=result.artist,
                caption=f"📥 @{me.username} orqali istagan musiqangizni tez va oson toping!",
                parse_mode="HTML",
                reply_markup=add_group_kb.as_markup(),
            )
            await status.delete()
            db_service.increment_counter("music_downloaded")
            db_service.save_cached_music_query(
                search_query, search_results[0].video_id, result.title, result.artist, 0,
                music_result.file_path,
            )
        except Exception:
            pass
