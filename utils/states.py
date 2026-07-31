"""
FSM holatlar (states).

Muhim: foydalanuvchi tajribasi uchun — matn yoki rasm yuborilganda,
bot "qaysi tilga tarjima qilay?" deb SO'RASHI kerak, avtomatik taxmin qilmasligi kerak.
Shu sabab tarjima oqimi har doim 2 bosqichli: 1) manba qabul qilinadi 2) til tanlanadi.
"""
from aiogram.fsm.state import State, StatesGroup


class TranslateStates(StatesGroup):
    waiting_for_text = State()          # AI yordamchi: tarjima uchun matn kutilmoqda
    waiting_for_target_lang = State()   # matn keldi, endi qaysi tilga -- tanlanmoqda


class ImageTranslateStates(StatesGroup):
    waiting_for_image = State()
    waiting_for_target_lang = State()


class AIAssistantStates(StatesGroup):
    chatting = State()                  # erkin savol-javob rejimi


class VoiceStates(StatesGroup):
    waiting_for_voice = State()


class QRStates(StatesGroup):
    waiting_for_create_data = State()   # QR yaratish uchun matn kutilmoqda
    waiting_for_read_image = State()    # QR o'qish uchun rasm kutilmoqda


class HashtagStates(StatesGroup):
    waiting_for_topic = State()


class CryptoStates(StatesGroup):
    waiting_for_encrypt_text = State()
    waiting_for_encrypt_password = State()
    waiting_for_decrypt_token = State()
    waiting_for_decrypt_password = State()


class WeatherStates(StatesGroup):
    waiting_for_city = State()


class MusicStates(StatesGroup):
    waiting_for_query = State()


class AdminStates(StatesGroup):
    waiting_for_broadcast_message = State()
    waiting_for_ban_id = State()
    waiting_for_unban_id = State()
    waiting_for_premium_grant_id = State()
    waiting_for_premium_grant_days = State()
    waiting_for_premium_revoke_id = State()
    waiting_for_promo_days = State()
    waiting_for_welcome_text = State()
    waiting_for_restore_file = State()


class UserStates(StatesGroup):
    waiting_for_complaint_text = State()   # /report — foydalanuvchi shikoyati
    waiting_for_promo_code = State()       # foydalanuvchi promo kod kiritishi


class ShazamStates(StatesGroup):
    waiting_for_audio = State()


class ContactAdminStates(StatesGroup):
    waiting_for_message = State()


class AdminReplyStates(StatesGroup):
    waiting_for_reply_text = State()


class ImageGenStates(StatesGroup):
    waiting_for_prompt = State()


class ImageEditStates(StatesGroup):
    waiting_for_image = State()
    waiting_for_edit_prompt = State()


class PromoLinkStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_button_text = State()
    waiting_for_duration = State()
