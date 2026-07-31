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
from services.downloader_service import throttle_youtube_request
from services import youtube_cookie_pool

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


def _pot_provider_opt() -> dict:
    base_url = getattr(config, "YTDLP_POT_PROVIDER_URL", "") or ""
    if not base_url:
        return {}
    return {
        "extractor_args": {
            "youtubepot-bgutilhttp": {"base_url": [base_url]},
            "youtube": {"player_client": ["web_safari", "tv"]},
        },
    }


_AUDIO_BOOST_KEYWORDS = [
    "mp3", "official audio", "audio only", "full audio", "audio",
    "lyrics", "lyric video", "visualizer", "no video",
]

_AUDIO_PENALTY_KEYWORDS = [
    "official video", "official mv", "official music video", "music video",
    "m/v", "mv", "live", "reaction", "cover", "behind the scenes", "shorts",
    "clip", "teaser", "trailer", "concert", "performance", "dance practice",
]


def _audio_priority_score(title: str) -> int:
    lowered = title.lower()
    score = 0
    for keyword in _AUDIO_BOOST_KEYWORDS:
        if keyword in lowered:
            score += 15 if keyword == "mp3" else 10
    for keyword in _AUDIO_PENALTY_KEYWORDS:
        if keyword in lowered:
            score -= 8
    return score


def search_music(query: str, limit: int = 5) -> list[MusicSearchItem]:
    """
    YouTube'dan berilgan nom bo'yicha bir nechta natija qidiradi (yuklamasdan).
    Cookie pool orqali, agar bitta cookie bot-tekshiruvga uchrasa, avtomatik
    keyingisiga o'tadi.
    """
    fetch_count = max(limit * 3, 10)
    search_query = f"ytsearch{fetch_count}:{query} audio mp3"

    attempts = max(1, min(youtube_cookie_pool.pool_size() or 1, 9))
    last_error: Exception | None = None

    for _ in range(attempts):
        cookie_file = youtube_cookie_pool.get_cookie_file()

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "default_search": "ytsearch",
            "js_runtimes": {"deno": {}},
            **_pot_provider_opt(),
        }
        if cookie_file:
            ydl_opts["cookiefile"] = cookie_file

        throttle_youtube_request()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)

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

        except yt_dlp.utils.DownloadError as e:
            if cookie_file and youtube_cookie_pool.is_bot_check_error(str(e)):
                youtube_cookie_pool.mark_rate_limited(cookie_file)
                last_error = e
                logger.warning(f"Qidiruvda cookie bloklandi, keyingisiga o'tilmoqda: {e}")
                continue
            logger.exception(f"Music search error for '{query}'")
            return []
        except Exception:
            logger.exception(f"Music search error for '{query}'")
            return []

    logger.warning(f"Barcha cookie'lar bloklandi, qidiruv muvaffaqiyatsiz: {last_error}")
    return []


CACHE_DIR = "music_cache"


def _cached_file_path(video_id: str) -> str | None:
    if not os.path.isdir(CACHE_DIR):
        return None
    for f in os.listdir(CACHE_DIR):
        if f.startswith(video_id + "."):
            return os.path.join(CACHE_DIR, f)
    return None


def download_music_by_id(video_id: str) -> MusicResult:
    """
    Berilgan YouTube video ID bo'yicha audio yuklab oladi. Agar bir cookie
    bot-tekshiruvga uchrasa, avtomatik keyingi cookie bilan qayta urinadi.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cached = _cached_file_path(video_id)
    if cached:
        return MusicResult(success=True, file_path=cached, title="Noma'lum qo'shiq")

    url = f"https://www.youtube.com/watch?v={video_id}"
    file_id = video_id
    output_template = os.path.join(CACHE_DIR, f"{file_id}.%(ext)s")

    attempts = max(1, min(youtube_cookie_pool.pool_size() or 1, 9))
    last_error: Exception | None = None
    last_error_text = ""

    for _ in range(attempts):
        cookie_file = youtube_cookie_pool.get_cookie_file()

        ydl_opts = {
            "outtmpl": output_template,
            "format": "bestaudio[ext=m4a][abr<=128]/bestaudio[abr<=128]/bestaudio[ext=m4a]/bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "max_filesize": config.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024,
            "js_runtimes": {"deno": {}},
            "remote_components": ["ejs:github"],
            "concurrent_fragment_downloads": 16,
            "socket_timeout": 10,
            "nocheckcertificate": True,
            "http_chunk_size": 10485760,
            "external_downloader": "aria2c",
            "external_downloader_args": {
                "aria2c": ["-x", "16", "-s", "16", "-k", "1M", "--max-connection-per-server=16"],
            },
            **_pot_provider_opt(),
        }
        if cookie_file:
            ydl_opts["cookiefile"] = cookie_file

        throttle_youtube_request()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)

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
            last_error = e
            last_error_text = error_text

            if cookie_file and youtube_cookie_pool.is_bot_check_error(error_text):
                youtube_cookie_pool.mark_rate_limited(cookie_file)
                logger.warning(f"'{video_id}' uchun cookie bloklandi, keyingisiga o'tilmoqda")
                continue

            if "Sign in to confirm your age" in error_text:
                return MusicResult(
                    success=False,
                    error="Bu qo'shiq yosh cheklovli. Boshqa natija/versiya tanlab ko'ring.",
                )
            logger.warning(f"Music download error for '{video_id}': {e}")
            return MusicResult(success=False, error="Qo'shiqni yuklab bo'lmadi.")

        except Exception as e:
            logger.exception(f"Unexpected error downloading music for '{video_id}'")
            return MusicResult(success=False, error=f"Kutilmagan xatolik: {e}")

    if last_error and youtube_cookie_pool.is_bot_check_error(last_error_text):
        return MusicResult(
            success=False,
            error="YouTube barcha cookie'larni bot-tekshiruvidan o'tkazmadi. Birozdan keyin qayta urinib ko'ring.",
        )
    return MusicResult(success=False, error="Qo'shiqni yuklab bo'lmadi.")


def download_music_with_fallback(candidates: list[MusicSearchItem], max_attempts: int = 5) -> MusicResult:
    last_error = "Hech qanday natija topilmadi."

    for item in candidates[:max_attempts]:
        result = download_music_by_id(item.video_id)
        if result.success:
            return result

        last_error = result.error or last_error
        if "bot-tekshiruvidan" not in (result.error or ""):
            return result

        logger.info(f"'{item.video_id}' bloklandi, keyingi nomzodga o'tilmoqda...")

    return MusicResult(success=False, error=last_error)


def cleanup_file(file_path: str) -> None:
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass