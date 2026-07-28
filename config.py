"""
Bot konfiguratsiyasi.
Barcha maxfiy ma'lumotlar (token, API kalitlar) .env faylidan o'qiladi.
"""
import os
import base64
import tempfile
from dataclasses import dataclass, field
from dotenv import load_dotenv

from utils.ffmpeg_finder import find_ffmpeg

load_dotenv()


def _write_cookie_file(content: str, filename: str) -> str:
    if not content:
        return ""
    path = os.path.join(tempfile.gettempdir(), filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _write_session_file(b64_content: str, filename: str) -> str:
    """
    Instaloader sessiya faylini (base64 ko'rinishida saqlangan) qayta tiklaydi.
    """
    if not b64_content:
        return ""
    path = os.path.join(tempfile.gettempdir(), filename)
    try:
        raw = base64.b64decode(b64_content)
        with open(path, "wb") as f:
            f.write(raw)
        return path
    except Exception:
        return ""


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "claude-sonnet-4-6")

    MAX_DOWNLOAD_SIZE_MB: int = int(os.getenv("MAX_DOWNLOAD_SIZE_MB", "50"))
    DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "downloads")

    USE_BROWSER_COOKIES: str = os.getenv("USE_BROWSER_COOKIES", "")

    INSTAGRAM_COOKIES_FILE: str = field(default_factory=lambda: _write_cookie_file(
        os.getenv("INSTAGRAM_COOKIES", ""), "instagram_cookies.txt"
    ))
    YOUTUBE_COOKIES_FILE: str = field(default_factory=lambda: _write_cookie_file(
        os.getenv("YOUTUBE_COOKIES", ""), "youtube_cookies.txt"
    ))

    # --- Instaloader fallback (Instagram uchun qo'shimcha usul) ---
    INSTAGRAM_USERNAME: str = os.getenv("INSTAGRAM_USERNAME", "")
    INSTAGRAM_SESSION_FILE: str = field(default_factory=lambda: _write_session_file(
        os.getenv("INSTAGRAM_SESSION_B64", ""), "instagram.session"
    ))

    FFMPEG_PATH: str = field(default_factory=lambda: find_ffmpeg(os.getenv("FFMPEG_PATH", "")))

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    ADMIN_IDS: list[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
    ])

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