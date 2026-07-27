"""
Musiqa qidirish va yuklash servisi.
YouTube'dan (yt-dlp orqali) qo'shiq nomi bo'yicha bir nechta natija qidiradi,
foydalanuvchi tanlagandan keyin audio (mp3) qilib yuklaydi.
"""
import os
import uuid
import logging
from dataclasses import dataclass

import yt_dlp

from config import config

logger = logging.getLogger(__name__)


@dataclass
class MusicSearchItem:
    video_id: str
    title: str
    duration: int  # soniyalarda
    uploader: str = ""


@dataclass
class MusicResult:
    success: bool
    file_path: str | None = None
    title: str | None = None
    error: str | None = None


def _format_duration(seconds: int) -> str:
    minutes, secs = divmod(int(seconds or 0), 60)
    return f"{minutes}:{secs:02d}"


def _browser_cookies_opt() -> dict:
    """
    Avval serverga mo'ljallangan cookie faylini tekshiradi (Railway
    Variables orqali berilgan), topilmasa lokal brauzer cookie'siga
    (faqat kompyuterda ishlaganda foydali) qaytadi.
    """
    cookies_file = getattr(config, "YOUTUBE_COOKIES_FILE", "") or ""
    if cookies_file:
        return {"cookiefile": cookies_file}
    browser = getattr(config, "USE_BROWSER_COOKIES", "") or ""
    if browser:
        return {"cookiesfrombrowser": (browser,)}
    return {}


# Sarlavhada bo'lsa ustuvorlikni OSHIRADIGAN so'zlar (faqat tinglash uchun mos)
_AUDIO_BOOST_KEYWORDS = ["official audio", "audio", "lyrics", "lyric video", "visualizer"]

# Sarlavhada bo'lsa ustuvorlikni PASAYTIRADIGAN so'zlar (video-markazli kontent)
_AUDIO_PENALTY_KEYWORDS = [
    "official video", "official mv", "m/v", "live", "reaction", "cover",
    "behind the scenes", "shorts", "clip", "teaser", "trailer", "concert",
    "performance", "dance practice",
]


def _audio_priority_score(title: str) -> int:
    """Sarlavha qanchalik 'faqat tinglash uchun' versiyaga o'xshasa, shuncha yuqori ball."""
    lowered = title.lower()
    score = 0
    for keyword in _AUDIO_BOOST_KEYWORDS:
        if keyword in lowered:
            score += 10
    for keyword in _AUDIO_PENALTY_KEYWORDS:
        if keyword in lowered:
            score -= 5
    return score


def search_music(query: str, limit: int = 5) -> list[MusicSearchItem]:
    """
    YouTube'dan berilgan nom bo'yicha bir nechta natija qidiradi (yuklamasdan).
    Faqat tinglash uchun mos versiyalarni (Official Audio, Lyrics va h.k.)
    ustuvor qilib qaytaradi.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "default_search": "ytsearch",
        **_browser_cookies_opt(),
    }

    fetch_count = max(limit * 3, 10)
    search_query = f"ytsearch{fetch_count}:{query} audio"

    try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
        except yt_dlp.utils.DownloadError as e:
            if "cookie" in str(e).lower() or "DPAPI" in str(e):
                logger.warning(f"Cookie xatosi, cookie'siz qayta urinilmoqda: {e}")
                fallback_opts = {k: v for k, v in ydl_opts.items() if k not in ("cookiesfrombrowser", "cookiefile")}
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    info = ydl.extract_info(search_query, download=False)
            else:
                raise

        entries = list(info.get("entries") or []) if info else []

        logger.info(f"Music search '{query}' -> {len(entries)} ta natija topildi")

        results = []
        for entry in entries:
            if not entry:
                continue
            results.append(
                MusicSearchItem(
                    video_id=entry.get("id", ""),
                    title=entry.get("title", "Noma'lum"),
                    duration=entry.get("duration", 0) or 0,
                    uploader=entry.get("uploader", "") or entry.get("channel", "") or "",
                )
            )

        results.sort(key=lambda item: _audio_priority_score(item.title), reverse=True)

        return results[:limit]

    except Exception:
        logger.exception(f"Music search error for '{query}'")
        return []


CACHE_DIR = "music_cache"


def _cached_file_path(video_id: str) -> str | None:
    """Agar bu qo'shiq oldin yuklab olingan bo'lsa, uning yo'lini qaytaradi."""
    if not os.path.isdir(CACHE_DIR):
        return None
    for f in os.listdir(CACHE_DIR):
        if f.startswith(video_id + "."):
            return os.path.join(CACHE_DIR, f)
    return None


def download_music_by_id(video_id: str) -> MusicResult:
    """
    Berilgan YouTube video ID bo'yicha audio yuklab oladi.
    Agar bu qo'shiq oldin yuklangan bo'lsa, keshdan darhol qaytaradi —
    qayta yuklamaydi (bu takroriy so'rovlarda sezilarli tezlik beradi).
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cached = _cached_file_path(video_id)
    if cached:
        return MusicResult(success=True, file_path=cached, title="Noma'lum qo'shiq")

    url = f"https://www.youtube.com/watch?v={video_id}"

    file_id = video_id
    output_template = os.path.join(CACHE_DIR, f"{file_id}.%(ext)s")

    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestaudio[ext=m4a][abr<=128]/bestaudio[abr<=128]/bestaudio[ext=m4a]/bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": config.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024,
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
        "concurrent_fragment_downloads": 8,
        "socket_timeout": 10,
        "nocheckcertificate": True,
        "http_chunk_size": 10485760,
        **_browser_cookies_opt(),
    }

    try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
        except yt_dlp.utils.DownloadError as e:
            if "cookie" in str(e).lower() or "DPAPI" in str(e):
                logger.warning(f"Cookie xatosi, cookie'siz qayta yuklanmoqda: {e}")
                fallback_opts = {k: v for k, v in ydl_opts.items() if k not in ("cookiesfrombrowser", "cookiefile")}
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file_path = ydl.prepare_filename(info)
            else:
                raise

        if not os.path.exists(file_path):
            return MusicResult(success=False, error="Yuklashda xatolik yuz berdi.")

        title = info.get("title", "Noma'lum qo'shiq")
        return MusicResult(success=True, file_path=file_path, title=title)
    except FileExistsError:
        cached = _cached_file_path(video_id)
        if cached:
            return MusicResult(success=True, file_path=cached, title="Noma'lum qo'shiq")
        return MusicResult(success=False, error="Fayl band, qayta urinib ko'ring.")

    except yt_dlp.utils.DownloadError as e:
        error_text = str(e)
        if "Sign in to confirm your age" in error_text:
            hint = (
                "Bu qo'shiq YouTube tomonidan yosh cheklovi qo'yilgan. "
                if not getattr(config, "USE_BROWSER_COOKIES", "")
                else "Bu qo'shiq yosh cheklovli, brauzer cookie orqali ham ochilmadi. "
            )
            logger.warning(f"Music download error (age-restricted) for '{video_id}': {e}")
            return MusicResult(success=False, error=hint + "Boshqa natija/versiya tanlab ko'ring.")
        logger.warning(f"Music download error for '{video_id}': {e}")
        return MusicResult(success=False, error="Qo'shiqni yuklab bo'lmadi.")
    except Exception as e:
        logger.exception(f"Unexpected error downloading music for '{video_id}'")
        return MusicResult(success=False, error=f"Kutilmagan xatolik: {e}")


def cleanup_file(file_path: str) -> None:
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass