"""
AI yordamchi servisi.

Hozircha AI_API_KEY .env faylida yo'q — shu sababli PLACEHOLDER_MODE yoqilgan.
API kalit qo'shilgach, .env ga AI_API_KEY=... yozing va bot avtomatik ravishda
haqiqiy AI javoblariga o'tadi (kodni o'zgartirish shart emas).

Anthropic Claude API misolida yozilgan (istalgan boshqa providerga moslash oson).
"""
import logging
from anthropic import Anthropic, APIError

from config import config

logger = logging.getLogger(__name__)

PLACEHOLDER_MODE = not bool(config.AI_API_KEY)

_client: Anthropic | None = None
if not PLACEHOLDER_MODE:
    _client = Anthropic(api_key=config.AI_API_KEY)


def _placeholder_reply(kind: str) -> str:
    return (
        "🔧 AI funksiyasi hali ulanmagan.\n\n"
        f"Bu yerda \"{kind}\" natijasi chiqishi kerak edi. "
        "Admin AI_API_KEY ni .env fayliga qo'shishi bilan bu funksiya avtomatik ishga tushadi."
    )


def ask_ai(prompt: str, system: str | None = None) -> str:
    """Erkin savol-javob uchun."""
    if PLACEHOLDER_MODE:
        return _placeholder_reply("AI javobi")

    try:
        response = _client.messages.create(
            model=config.AI_MODEL,
            max_tokens=1000,
            system=system or "Siz foydali, qisqa va aniq javob beruvchi yordamchisiz.",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except APIError as e:
        logger.error(f"AI API error: {e}")
        return "AI xizmatida vaqtinchalik xatolik. Birozdan so'ng qayta urinib ko'ring."


def translate_text(text: str, target_lang_label: str) -> str:
    """Matnni tanlangan tilga tarjima qilish."""
    if PLACEHOLDER_MODE:
        return _placeholder_reply(f"'{target_lang_label}' tiliga tarjima")

    prompt = f"Quyidagi matnni {target_lang_label} tiliga tarjima qiling, faqat tarjimani qaytaring:\n\n{text}"
    return ask_ai(prompt, system="Siz professional tarjimonsiz. Faqat tarjima natijasini yozing, izoh bermang.")


def generate_caption(context_hint: str = "") -> str:
    """Video/rasm uchun sarlavha (AI Caption funksiyasi)."""
    if PLACEHOLDER_MODE:
        return _placeholder_reply("AI qisqa sarlavha")
    prompt = f"Quyidagi kontent uchun qisqa va chiroyli sarlavha yozing: {context_hint}"
    return ask_ai(prompt)


def summarize_text(text: str) -> str:
    if PLACEHOLDER_MODE:
        return _placeholder_reply("Matn xulosasi")
    prompt = f"Quyidagi matnni 5-10 ta band (bullet point) shaklida qisqartiring:\n\n{text}"
    return ask_ai(prompt)


def generate_hashtags(topic: str) -> str:
    """Berilgan mavzu/tavsif asosida mos hashtaglar ro'yxatini yaratadi."""
    if PLACEHOLDER_MODE:
        return _placeholder_reply("Mos hashtaglar ro'yxati")
    prompt = (
        f"Quyidagi mavzu/post tavsifi uchun 15-20 ta mos, mashhur va samarali "
        f"hashtag tavsiya qiling (aralash: umumiy + tor nishonli). "
        f"Faqat hashtaglarni bo'shliq bilan ajratib qaytaring, izoh bermang:\n\n{topic}"
    )
    return ask_ai(prompt, system="Siz ijtimoiy tarmoqlar uchun hashtag mutaxassisisiz.")
