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


def _pot_provider_opt() -> dict:
    """
    bgutil-ytdlp-pot-provider orqali PO Token oladi — YouTube'ning
    "Sign in to confirm you're not a bot" bloklashini cookie'siz ham
    yechishga yordam beradi. android_vr kabi POT ishlatmaydigan
    mijozlarni chetlab, web_safari/tv'ga majburlaymiz.
    """
    base_url = getattr(config, "YTDLP_POT_PROVIDER_URL", "") or ""
    if not base_url:
        return {}
    return {
        "extractor_args": {
            "youtubepot-bgutilhttp": {"base_url": [base_url]},
            "youtube": {"player_client": ["web_safari"]},
        },
    }


# Sarlavhada bo'lsa ustuvorlikni OSHIRADIGAN so'zlar (faqat tinglash uchun mos).
# "mp3" va "audio" eng yuqori ustuvorlikka ega, chunki foydalanuvchi aynan
# tinglash uchun mo'ljallangan versiyani xohlaydi, klip/video emas.
_AUDIO_BOOST_KEYWORDS = [
    "mp3", "official audio", "audio only", "full audio", "audio",
    "lyrics", "lyric video", "visualizer", "no video",
]

# Sarlavhada bo'lsa ustuvorlikni PASAYTIRADIGAN so'zlar (video-markazli/"haqiqiy"
# klip kontenti) — bular kuchliroq jazolanadi, chunki foydalanuvchi ularni
# emas, tinglash versiyasini xohlaydi.
_AUDIO_PENALTY_KEYWORDS = [
    "official video", "official mv", "official music video", "music video",
    "m/v", "mv", "live", "reaction", "cover", "behind the scenes", "shorts",
    "clip", "teaser", "trailer", "concert", "performance", "dance practice",
]


def _audio_priority_score(title: str) -> int:
    """Sarlavha qanchalik 'faqat tinglash uchun' versiyaga o'xshasa, shuncha yuqori ball."""
    lowered = title.lower()
    score = 0
    for keyword in _AUDIO_BOOST_KEYWORDS:
        if keyword in lowered:
            # "mp3" eng aniq belgi bo'lgani uchun qo'shimcha ustuvorlik beramiz.
            score += 15 if keyword == "mp3" else 10
    for keyword in _AUDIO_PENALTY_KEYWORDS:
        if keyword in lowered:
            score -= 8
    return score


def search_music(query: str, limit: int = 5) -> list[MusicSearchItem]:
    """
    YouTube'dan berilgan nom bo'yicha bir nechta natija qidiradi (yuklamasdan).
    Faqat tinglash uchun mos versiyalarni (Official Audio, Lyrics va h.k.)
    ustuvor qilib qaytaradi.
    """
    ydl_opts = {
        "verbose": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "default_search": "ytsearch",
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
        **_browser_cookies_opt(),
        **_pot_provider_opt(),
    }

    fetch_count = max(limit * 3, 10)
    search_query = f"ytsearch{fetch_count}:{query} audio mp3"

    throttle_youtube_request()

    try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
        except yt_dlp.utils.DownloadError as e:
            # Diqqat: faqat cookie FAYLI buzuq/o'qib bo'lmaydigan holatlarda True
            # bo'lishi kerak. "Sign in to confirm you're not a bot" xabarining
            # o'zida ham maslahat sifatida "cookies" so'zi uchraydi, shuning uchun
            # oddiy "cookie" so'zini emas, aniq xato turlarini tekshiramiz.
            if "DPAPI" in str(e) or "cookie database" in str(e).lower():
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
        "verbose": True,
        "outtmpl": output_template,
        "format": "bestaudio[ext=m4a][abr<=128]/bestaudio[abr<=128]/bestaudio[ext=m4a]/bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": config.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024,
        "js_runtimes": {"deno": {}},
        "remote_components": {"ejs:github"},
        "concurrent_fragment_downloads": 16,
        "socket_timeout": 10,
        "nocheckcertificate": True,
        "http_chunk_size": 10485760,
        "external_downloader": "aria2c",
        "external_downloader_args": {
            "aria2c": ["-x", "16", "-s", "16", "-k", "1M", "--max-connection-per-server=16"],
        },
        **_browser_cookies_opt(),
        **_pot_provider_opt(),
    }

    throttle_youtube_request()

    try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
        except yt_dlp.utils.DownloadError as e:
            if "DPAPI" in str(e) or "cookie database" in str(e).lower():
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
        if "Sign in to confirm you" in error_text and "bot" in error_text.lower():
            logger.warning(f"YouTube bot-tekshiruvi bloklandi for '{video_id}': {e}")
            return MusicResult(
                success=False,
                error="YouTube bu qo'shiqni bot-tekshiruvidan o'tkazmadi. Boshqa natija tanlab ko'ring.",
            )
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


def download_music_with_fallback(candidates: list[MusicSearchItem], max_attempts: int = 5) -> MusicResult:
    """
    Berilgan nomzodlar ro'yxatidan birinchisini yuklashga urinadi. Agar YouTube
    bot-tekshiruvi sabab muvaffaqiyatsiz bo'lsa, avtomatik ravishda keyingi
    nomzodni sinaydi (muvaffaqiyatli topilguncha yoki max_attempts tugaguncha).
    Boshqa turdagi xatolarda (masalan fayl juda katta) darhol to'xtaydi.
    """
    last_error = "Hech qanday natija topilmadi."

    for item in candidates[:max_attempts]:
        result = download_music_by_id(item.video_id)
        if result.success:
            return result

        last_error = result.error or last_error
        # Faqat bot-tekshiruvi xatosida keyingisiga o'tamiz — boshqa xatolarda
        # (masalan hajm chegarasi) qayta urinish foydasiz.
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