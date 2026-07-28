"""
Sessiya vaqt tekshiruvi.

Foydalanuvchi biror funksiya ichida (FSM holatida) turganda, agar oxirgi
faoliyatidan 10 daqiqadan ko'proq vaqt o'tgan bo'lsa, yangi xabar to'g'ridan-
to'g'ri funksiyaga yuborilmaydi — avval "davom etasizmi?" deb so'raladi.
"""
import time

from aiogram import BaseMiddleware, Router, F
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

SESSION_TIMEOUT_SECONDS = 10 * 60  # 10 daqiqa

router = Router(name="session_timeout")


def _confirm_kb():
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, davom etaman", callback_data="session:continue")
    b.button(text="❌ Yo'q, to'xtataman", callback_data="session:stop")
    b.adjust(2)
    return b.as_markup()


class SessionTimeoutMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        state: FSMContext = data.get("state")

        if isinstance(event, Message) and state:
            current_state = await state.get_state()
            if current_state is not None:
                fsm_data = await state.get_data()
                last_activity = fsm_data.get("_last_activity")
                now = time.time()

                if last_activity and (now - last_activity) > SESSION_TIMEOUT_SECONDS:
                    await event.answer(
                        "⏳ Oxirgi amaldan 10 daqiqadan ko'proq vaqt o'tdi.\n\n"
                        "Shu funksiya bilan davom etasizmi?",
                        reply_markup=_confirm_kb(),
                    )
                    return  # xabarni funksiyaga o'tkazmaymiz — javob kutamiz

                await state.update_data(_last_activity=now)

        elif isinstance(event, CallbackQuery) and state:
            current_state = await state.get_state()
            if current_state is not None:
                await state.update_data(_last_activity=time.time())

        return await handler(event, data)


@router.callback_query(F.data == "session:continue")
async def session_continue(callback: CallbackQuery, state: FSMContext):
    await state.update_data(_last_activity=time.time())
    await callback.message.edit_text("✅ Davom etamiz — endi xabaringizni qayta yuboring.")
    await callback.answer()


@router.callback_query(F.data == "session:stop")
async def session_stop(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🔚 To'xtatildi. Istalgan funksiyani pastdagi menyudan tanlashingiz mumkin."
    )

"""
Sessiya vaqt tekshiruvi.

Foydalanuvchi biror funksiya ichida (FSM holatida) turganda, agar oxirgi
faoliyatidan 10 daqiqadan ko'proq vaqt o'tgan bo'lsa, yangi xabar to'g'ridan-
to'g'ri funksiyaga yuborilmaydi — avval "davom etasizmi?" deb so'raladi.
"""
import time

from aiogram import BaseMiddleware, Router, F
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

SESSION_TIMEOUT_SECONDS = 10 * 60  # 10 daqiqa

router = Router(name="session_timeout")


def _confirm_kb():
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, davom etaman", callback_data="session:continue")
    b.button(text="❌ Yo'q, to'xtataman", callback_data="session:stop")
    b.adjust(2)
    return b.as_markup()


class SessionTimeoutMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        state: FSMContext = data.get("state")

        if isinstance(event, Message) and state:
            current_state = await state.get_state()
            if current_state is not None:
                fsm_data = await state.get_data()
                last_activity = fsm_data.get("_last_activity")
                now = time.time()

                if last_activity and (now - last_activity) > SESSION_TIMEOUT_SECONDS:
                    await event.answer(
                        "⏳ Oxirgi amaldan 10 daqiqadan ko'proq vaqt o'tdi.\n\n"
                        "Shu funksiya bilan davom etasizmi?",
                        reply_markup=_confirm_kb(),
                    )
                    return  # xabarni funksiyaga o'tkazmaymiz — javob kutamiz

                await state.update_data(_last_activity=now)

        elif isinstance(event, CallbackQuery) and state:
            current_state = await state.get_state()
            if current_state is not None:
                await state.update_data(_last_activity=time.time())

        return await handler(event, data)


@router.callback_query(F.data == "session:continue")
async def session_continue(callback: CallbackQuery, state: FSMContext):
    await state.update_data(_last_activity=time.time())
    await callback.message.edit_text("✅ Davom etamiz — endi xabaringizni qayta yuboring.")
    await callback.answer()


@router.callback_query(F.data == "session:stop")
async def session_stop(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🔚 To'xtatildi. Istalgan funksiyani pastdagi menyudan tanlashingiz mumkin."
    )

    await callback.answer()