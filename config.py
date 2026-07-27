"""
Bot konfiguratsiyasi.
Barcha maxfiy ma'lumotlar (token, API kalitlar) .env faylidan o'qiladi.
"""
import os
import tempfile
from dataclasses import dataclass, field
from dotenv import load_dotenv

from utils.ffmpeg_finder import find_ffmpeg

load_dotenv()


def _write_cookie_file(content: str, filename: str) -> str:
    """
    Muhit o'zgaruvchisida (masalan Railway Variables'da) saqlangan cookie
    matnini vaqtinchalik faylga yozadi va yo'lini qaytaradi. Bo'sh bo'lsa,
    bo'sh satr qaytaradi (cookie ishlatilmaydi).
    """
    if not content:
        return ""
    path = os.path.join(tempfile.gettempdir(), filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


@dataclass
class Config:
    # --- Asosiy ---
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # --- AI funksiyalari uchun (hozircha bo'sh, keyinroq to'ldiriladi) ---
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "claude-sonnet-4-6")

    # --- Fayl cheklovlari ---
    MAX_DOWNLOAD_SIZE_MB: int = int(os.getenv("MAX_DOWNLOAD_SIZE_MB", "50"))
    DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "downloads")

    # --- Instagram bloklashini kamaytirish uchun brauzer cookie'lari ---
    # FAQAT LOKAL kompyuterda ishlaydi (o'sha brauzerda Instagram'ga kirib
    # qo'yilgan bo'lishi kerak). Serverda (Railway va h.k.) bu ishlamaydi,
    # chunki serverda brauzer o'rnatilmagan — shuning uchun COOKIES_FILE
    # (pastda) ishlatiladi.
    USE_BROWSER_COOKIES: str = os.getenv("USE_BROWSER_COOKIES", "")

    # --- Cookie fayl mazmuni (Railway Variables orqali beriladi) ---
    # Bular brauzer kengaytmasi (masalan "Get cookies.txt LOCALLY") orqali
    # eksport qilingan cookie fayllarining TO'LIQ matni. Server ishga
    # tushganda shu matn vaqtinchalik faylga yoziladi va yt-dlp o'shandan
    # foydalanadi — bu serverda ham "login qilingan" holatni ta'minlaydi.
    INSTAGRAM_COOKIES_FILE: str = field(default_factory=lambda: _write_cookie_file(
        os.getenv("INSTAGRAM_COOKIES", ""), "instagram_cookies.txt"
    ))
    YOUTUBE_COOKIES_FILE: str = field(default_factory=lambda: _write_cookie_file(
        os.getenv("YOUTUBE_COOKIES", ""), "youtube_cookies.txt"
    ))

    # --- ffmpeg dasturining yo'li ---
    FFMPEG_PATH: str = field(default_factory=lambda: find_ffmpeg(os.getenv("FFMPEG_PATH", "")))

    # --- Google Gemini API (rasm tahrirlash uchun) ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # --- Admin panelga kira oladigan Telegram user ID'lar (vergul bilan ajratilgan) ---
    ADMIN_IDS: list[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
    ])

    # --- Tarjima uchun standart tillar ro'yxati (Image Translator / AI yordamchi) ---
    SUPPORTED_LANGUAGES: dict = field(default_factory=lambda: {
        "uz": "🇺🇿 O'zbekcha",
        "ru": "🇷🇺 Ruscha",
        "en": "🇬🇧 Inglizcha",
        "de": "🇩🇪 Nemischa",
        "tr": "🇹🇷 Turkcha",
        "ko": "🇰🇷 Koreyscha",
        "ar": "🇸🇦 Arabcha",
    })

    def validate(self) -> None:
        if not self.BOT_TOKEN:
            raise RuntimeError(
                "BOT_TOKEN topilmadi! .env faylida BOT_TOKEN=... qiymatini kiriting."
            )


config = Config()