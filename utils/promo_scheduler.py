"""
Silkalar (promo linklar) muddati tugashini kuzatuvchi fon vazifasi.
Har 60 soniyada bazani tekshiradi, muddati tugagan silkalarni avtomatik
nofaol qiladi va har bir adminga xabar beradi.
"""
import asyncio
import logging

from aiogram import Bot

from services import db_service
from config import config

logger = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "all": "📢 Barcha xabarlar",
    "music": "🎵 Musiqa",
    "video": "🎬 Video",
    "photo": "🖼 Rasm",
    "admin": "👤 Admin xabarlari",
}


async def promo_link_expiry_watcher(bot: Bot) -> None:
    while True:
        try:
            expired = db_service.pop_expired_promo_links()
            for link in expired:
                cat_label = CATEGORY_LABELS.get(link["category"], link["category"])
                text = (
                    f"⏰ <b>Silka muddati tugadi</b>\n\n"
                    f"🔘 {link['button_text']}\n"
                    f"📂 {cat_label}\n"
                    f"⏳ Belgilangan muddat: {link['duration_label']}\n\n"
                    f"Bu silka endi avtomatik ravishda ro'yxatdan olib tashlandi."
                )
                for admin_id in config.ADMIN_IDS:
                    try:
                        await bot.send_message(admin_id, text, parse_mode="HTML")
                    except Exception:
                        logger.warning(f"Adminga ({admin_id}) silka muddati xabari yuborilmadi")
        except Exception:
            logger.exception("Promo link expiry watcher xatosi")
        await asyncio.sleep(60)