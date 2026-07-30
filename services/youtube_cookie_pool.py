"""
YouTube uchun bir nechta cookie fayli orasida navbat bilan almashtirib
foydalanish tizimi (cookie "pool").

Ishlash tartibi:
- Har bir so'rovda navbatdagi (round-robin) ishlaydigan cookie tanlanadi.
- Agar YouTube shu cookie uchun bot-tekshiruv/chegara xatosi bersa, o'sha
  cookie 1 soatga "dam olish" holatiga o'tkaziladi va keyingi ishlaydigan
  cookie avtomatik tanlanadi — foydalanuvchi buni sezmaydi.
- 1 soatdan keyin cookie avtomatik yana faol ro'yxatga qaytadi (hech qanday
  qo'lda aralashuv shart emas).
"""
import threading
import time
import logging

from config import config

logger = logging.getLogger(__name__)

_COOLDOWN_SECONDS = 3600  # 1 soat

_lock = threading.Lock()
_cooldown_until: dict[str, float] = {}
_rr_index = 0


def pool_size() -> int:
    return len(config.YOUTUBE_COOKIES_FILES)


def get_cookie_file() -> str | None:
    """
    Hozir ishlatish uchun mavjud (dam olish holatida bo'lmagan) cookie
    faylini navbat bilan (round-robin) tanlab qaytaradi. Agar hech qanday
    cookie sozlanmagan bo'lsa, None qaytaradi (cookie'siz davom etiladi).
    Agar barcha cookie'lar dam olish holatida bo'lsa, eng tez tiklanadigan
    birini baribir qaytaradi (butunlay to'xtab qolmaslik uchun).
    """
    global _rr_index
    files = list(config.YOUTUBE_COOKIES_FILES)
    if not files:
        return None

    with _lock:
        now = time.monotonic()
        n = len(files)
        for _ in range(n):
            candidate = files[_rr_index % n]
            _rr_index += 1
            if _cooldown_until.get(candidate, 0) <= now:
                return candidate
        soonest = min(files, key=lambda f: _cooldown_until.get(f, 0))
        return soonest


def mark_rate_limited(cookie_file: str) -> None:
    """Berilgan cookie faylini 1 soatga 'dam olish' holatiga o'tkazadi."""
    if not cookie_file:
        return
    with _lock:
        _cooldown_until[cookie_file] = time.monotonic() + _COOLDOWN_SECONDS
    logger.warning(f"YouTube cookie dam olish holatiga o'tkazildi (1 soat): {cookie_file}")


def is_bot_check_error(error_text: str) -> bool:
    """Xato matni YouTube'ning bot-tekshiruvi/login talabi ekanligini aniqlaydi."""
    lowered = error_text.lower()
    return (
        ("sign in to confirm" in lowered and "bot" in lowered)
        or "login_required" in lowered
        or "the provided youtube account cookies are no longer valid" in lowered
    )