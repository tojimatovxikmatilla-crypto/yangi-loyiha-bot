import asyncio
import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from services.music_service import search_music, download_music_by_id, cleanup_file, _format_duration
from services import db_service
from utils.keyboards import BTN_MUSIC, ALL_MENU_BUTTONS
from utils.states import MusicStates

router = Router(name="music")

PROMPT_TEXT = (
    "🎵 <b>Musiqa yuklash</b>\n\n"
    "Qo'shiq nomini yoki ijrochisini yozing (masalan: \"Imagine Dragons Believer\") — "
    "men bir nechta natija topib beraman."
)

DISABLED_TEXT = "🔧 Bu funksiya admin tomonidan vaqtincha o'chirilgan."

PAGE_SIZE = 10
MAX_RESULTS = 30
NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def _build_page_text_and_kb(query: str, results: list, page: int):
    total_pages = max(1, (len(results) + PAGE_SIZE - 1) // PAGE_SIZE)
    start = page * PAGE_SIZE
    page_items = results[start:start + PAGE_SIZE]

    lines = [f"🔎 <b>\"{query}\"</b> bo'yicha natijalar ({page + 1}/{total_pages}-sahifa):\n"]
    kb = InlineKeyboardBuilder()

    for i, item in enumerate(page_items, start=1):
        emoji = NUMBER_EMOJIS[i - 1] if i <= len(NUMBER_EMOJIS) else f"{i}."
        duration_str = _format_duration(item["duration"])
        uploader = f" — {item['uploader']}" if item.get("uploader") else ""
        lines.append(f"{emoji} {item['title']}{uploader} <code>[{duration_str}]</code>")
        kb.button(text=str(i), callback_data=f"music_pick:{item['video_id']}")

    kb.adjust(5)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(("⬅️ Oldingi", f"music_page:{page - 1}"))
    has_more_possible = len(page_items) == PAGE_SIZE and start + PAGE_SIZE < MAX_RESULTS
    if has_more_possible:
        nav_buttons.append(("Keyingi ➡️", f"music_page:{page + 1}"))

    if nav_buttons:
        kb.row(*[InlineKeyboardButton(text=t, callback_data=d) for t, d in nav_buttons])

    return "\n".join(lines), kb.as_markup()


@router.message(StateFilter(None), F.text == BTN_MUSIC)
async def open_music_reply(message: Message, state: FSMContext, bot):
    if not db_service.get_feature_enabled("music"):
        await message.answer(DISABLED_TEXT)
        return
    await state.set_state(MusicStates.waiting_for_query)
    await message.answer(PROMPT_TEXT, parse_mode="HTML")


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"), ~F.text.regexp(r"https?://"), ~F.text.in_(ALL_MENU_BUTTONS))
async def handle_music_query(message: Message, state: FSMContext, bot):
    if not db_service.get_feature_enabled("music"):
        await message.answer(DISABLED_TEXT)
        await state.clear()
        return

    cached = db_service.get_cached_music_query(message.text)
    if cached and os.path.exists(cached["file_path"]):
        status_msg = await message.answer("⚡ Bazadan topildi, darhol yuborilmoqda...")
        me = await bot.me()
        add_group_kb = InlineKeyboardBuilder()
        add_group_kb.button(
            text="➕ Guruhga qo'shish",
            url=f"https://t.me/{me.username}?startgroup=true",
        )
        await message.answer_audio(
            FSInputFile(cached["file_path"]),
            title=cached["title"],
            caption=f"📥 @{me.username} orqali istagan musiqangizni tez va oson toping!",
            parse_mode="HTML",
            reply_markup=add_group_kb.as_markup(),
        )
        await status_msg.delete()
        db_service.increment_counter("music_downloaded")
        db_service.increment_counter("music_served_from_cache")
        return

    status_msg = await message.answer("🔎 Qidirilmoqda...")

    results = await asyncio.to_thread(search_music, message.text, PAGE_SIZE)

    if not results:
        await status_msg.edit_text("❌ Hech narsa topilmadi. Boshqa nom bilan urinib ko'ring.")
        return

    results_data = [
        {
            "video_id": r.video_id,
            "title": r.title,
            "duration": r.duration,
            "uploader": r.uploader,
        }
        for r in results
    ]

    await state.update_data(query=message.text, results=results_data)

    text, kb = _build_page_text_and_kb(message.text, results_data, page=0)
    await status_msg.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("music_page:"))
async def handle_music_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    results_data = data.get("results", [])
    query = data.get("query", "")

    if not results_data:
        await callback.answer("❌ Natijalar eskirgan, qayta qidiring.", show_alert=True)
        return

    needed = min((page + 1) * PAGE_SIZE, MAX_RESULTS)

    if needed > len(results_data):
        await callback.answer("⏳ Yuklanmoqda...")
        results = await asyncio.to_thread(search_music, query, needed)
        results_data = [
            {
                "video_id": r.video_id,
                "title": r.title,
                "duration": r.duration,
                "uploader": r.uploader,
            }
            for r in results
        ]
        await state.update_data(results=results_data)
    else:
        await callback.answer()

    text, kb = _build_page_text_and_kb(query, results_data, page)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("music_pick:"))
async def handle_music_pick(callback: CallbackQuery, state: FSMContext, bot):
    if not db_service.get_feature_enabled("music"):
        await callback.answer(DISABLED_TEXT, show_alert=True)
        return

    video_id = callback.data.split(":", 1)[1]
    fsm_data = await state.get_data()
    original_query = fsm_data.get("query", "")
    await callback.answer()
    status_msg = await callback.message.answer("⏳ Yuklanmoqda...")

    result = await asyncio.to_thread(download_music_by_id, video_id)

    if not result.success:
        await status_msg.edit_text(f"❌ {result.error}")
        return

    try:
        file = FSInputFile(result.file_path)

        me = await bot.me()
        add_group_kb = InlineKeyboardBuilder()
        add_group_kb.button(
            text="➕ Guruhga qo'shish",
            url=f"https://t.me/{me.username}?startgroup=true",
        )

        await callback.message.answer_audio(
            file,
            title=result.title,
            caption=f"📥 @{me.username} orqali istagan musiqangizni tez va oson toping!",
            parse_mode="HTML",
            reply_markup=add_group_kb.as_markup(),
        )
        await status_msg.delete()
        db_service.increment_counter("music_downloaded")

        if original_query:
            db_service.save_cached_music_query(
                original_query, video_id, result.title, "", 0, result.file_path
            )
    except Exception:
        pass