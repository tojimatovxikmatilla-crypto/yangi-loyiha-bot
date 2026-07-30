"""
Botni ishga tushirish nuqtasi.

Ishga tushirish: python main.py
Talab: .env faylida BOT_TOKEN ko'rsatilgan bo'lishi kerak.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat, MenuButtonDefault, MenuButtonCommands

from config import config
from services import db_service
from utils.middlewares import UserTrackingMiddleware, BanMiddleware, SpamControlMiddleware, MaintenanceMiddleware
from utils.session_timeout import SessionTimeoutMiddleware, router as session_timeout_router
from handlers import (
    start,
    downloader,
    ai_assistant,
    music,
    shazam,
    admin,
    support,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """
    Xabar yozish maydonining yonidagi "Menyu" tugmasi uchun buyruqlar ro'yxati.
    Oddiy foydalanuvchilar faqat /start ni ko'radi, adminlar esa /start va /admin ikkalasini.
    """
    # Oddiy foydalanuvchilar uchun buyruqlar ro'yxatini bo'shatamiz va
    # "Menyu" tugmasini standart (oddiy) rejimga o'tkazamiz — shunda chap
    # pastda "☰ Menyu" tugmasi umuman ko'rinmaydi, faqat oddiy "+" biriktirish
    # belgisi qoladi.
    await bot.set_my_commands([], scope=BotCommandScopeDefault())
    await bot.set_chat_menu_button(menu_button=MenuButtonDefault())

    admin_commands = [
        BotCommand(command="start", description="🚀 Foydalanuvchi rejimi"),
        BotCommand(command="admin", description="🔐 Admin panel"),
    ]
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            await bot.set_chat_menu_button(
                chat_id=admin_id, menu_button=MenuButtonCommands()
            )
        except Exception:
            logger.warning(f"Admin uchun buyruqlar o'rnatilmadi: {admin_id}")


async def main() -> None:
    config.validate()
    db_service.init_db()

    bot_kwargs = {
        "token": config.BOT_TOKEN,
        "default": DefaultBotProperties(parse_mode=ParseMode.HTML),
    }

    # Agar local Bot API Server manzili berilgan bo'lsa, katta fayllar
    # (50 MB dan ortiq, 2 GB gacha) yuborish/qabul qilish uchun shunga
    # ulanamiz. Bo'lmasa, standart Telegram serveri ishlatiladi.
    if config.TELEGRAM_LOCAL_API_URL:
        local_server = TelegramAPIServer.from_base(
            config.TELEGRAM_LOCAL_API_URL, is_local=True
        )
        bot_kwargs["session"] = None  # quyida to'g'ri session bilan qayta o'rnatiladi
        from aiogram.client.session.aiohttp import AiohttpSession
        bot_kwargs["session"] = AiohttpSession(api=local_server)
        logger.info(f"Local Bot API Server ishlatilmoqda: {config.TELEGRAM_LOCAL_API_URL}")

    bot = Bot(**bot_kwargs)
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware'lar — har bir xabar/callback shu qatlamlardan o'tadi.
    # Tartib muhim: avval foydalanuvchini ro'yxatga olamiz, keyin texnik ishlar
    # rejimini tekshiramiz (shunda statistikaga texnik ishlar paytida ham
    # yozilib boradi).
    dp.message.middleware(UserTrackingMiddleware())
    dp.callback_query.middleware(UserTrackingMiddleware())
    dp.message.middleware(BanMiddleware())
    dp.callback_query.middleware(BanMiddleware())
    dp.message.middleware(SpamControlMiddleware())
    dp.callback_query.middleware(SpamControlMiddleware())
    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())
    dp.message.middleware(SessionTimeoutMiddleware())
    dp.callback_query.middleware(SessionTimeoutMiddleware())

    # Har bir funksiya alohida router (modul) sifatida ulanadi.
    # Yangi funksiya qo'shish uchun: handlers/ ichida yangi fayl yozib, shu yerga qo'shish kifoya.
    dp.include_router(session_timeout_router)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(downloader.router)
    dp.include_router(ai_assistant.router)
    dp.include_router(music.router)
    dp.include_router(shazam.router)
    dp.include_router(support.router)

    await setup_bot_commands(bot)

    logger.info("Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")
