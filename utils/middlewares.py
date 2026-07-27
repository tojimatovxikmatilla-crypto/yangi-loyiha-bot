"""
Middleware'lar — har bir kiruvchi xabar/callback shu qatlamlardan ketma-ket o'tadi.

Tartib (main.py da ro'yxatdan o'tkaziladigan tartib muhim):
1. UserTrackingMiddleware — foydalanuvchini bazaga yozadi
2. BanMiddleware — bloklangan foydalanuvchini butunlay to'xtatadi
3. SpamControlMiddleware — juda tez-tez yozayotgan foydalanuvchini vaqtincha sekinlashtiradi
4. MaintenanceMiddleware — texnik ishlar rejimida oddiy foydalanuvchilarni to'xtatadi
"""
import time
from collections import defaultdict
from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from services import db_service
from config import config

# Foydalanuvchi ID -> so'nggi xabar vaqtlari ro'yxati (xotirada, oddiy flood-control uchun yetarli)
_message_timestamps: dict[int, list[float]] = defaultdict(list)

SPAM_WINDOW_SECONDS = 10
SPAM_MAX_MESSAGES = 8


class UserTrackingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict,
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            db_service.add_user(user.id, user.username)
        return await handler(event, data)


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict,
    ) -> Any:
        user = data.get("event_from_user")
        if user and db_service.is_banned(user.id):
            text = "⛔ Siz botdan foydalanishdan chetlatilgansiz."
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            return
        return await handler(event, data)


class SpamControlMiddleware(BaseMiddleware):
    """
    Oddiy flood-control: bir foydalanuvchi SPAM_WINDOW_SECONDS ichida
    SPAM_MAX_MESSAGES dan ko'p xabar yuborsa, vaqtincha e'tiborsiz qoldiriladi.
    Adminlar bu cheklovdan ozod.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict,
    ) -> Any:
        user = data.get("event_from_user")
        if not user or user.id in config.ADMIN_IDS:
            return await handler(event, data)

        now = time.time()
        timestamps = _message_timestamps[user.id]
        timestamps.append(now)
        # Faqat oxirgi oyna ichidagilarni saqlaymiz
        _message_timestamps[user.id] = [t for t in timestamps if now - t < SPAM_WINDOW_SECONDS]

        if len(_message_timestamps[user.id]) > SPAM_MAX_MESSAGES:
            db_service.add_log("spam_detected", f"user_id={user.id}")
            text = "⏳ Juda tez-tez yozyapsiz, biroz kuting."
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            return

        return await handler(event, data)


class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict,
    ) -> Any:
        user = data.get("event_from_user")

        if user and user.id not in config.ADMIN_IDS and db_service.is_maintenance_mode():
            text = (
                "🛠 Bot hozirda texnik ishlar tufayli vaqtincha ishlamayapti.\n"
                "Iltimos, birozdan so'ng qayta urinib ko'ring."
            )
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            return

        return await handler(event, data)
