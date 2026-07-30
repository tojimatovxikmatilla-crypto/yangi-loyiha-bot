"""
Universal Downloader servisi.
yt-dlp kutubxonasi orqali Instagram, TikTok, Facebook, X (Twitter), Pinterest
havolalaridan video/rasm yuklab oladi. Instagram uchun yt-dlp ishlamasa,
Instaloader orqali zaxira (fallback) usul ishlatiladi.
"""
import os
import re
import uuid
import shutil
import logging
from dataclasses import dataclass

import shutil as _shutil
import yt_dlp
import requests
from PIL import Image
from io import BytesIO
import pillow_heif
pillow_heif.register_heif_opener()

import subprocess as _subprocess
import time
import threading

logging.getLogger(__name__).warning(f"yt-dlp versiyasi: {yt_dlp.version.__version__}")
logging.getLogger(__name__).warning(
    f"node yo'li: {_shutil.which('node')!r}, nodejs yo'li: {_shutil.which('nodejs')!r}"
)
try:
    _node_ver = _subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
    logging.getLogger(__name__).warning(f"node versiyasi: {_node_ver.stdout.strip()} {_node_ver.stderr.strip()}")
except Exception as _e:
    logging.getLogger(__name__).warning(f"node versiyasini tekshirishda xato: {_e}")

from config import config

logger = logging.getLogger(__name__)

# YouTube so'rovlari orasidagi minimal bo'shliq (soniya). Bitta server
# IP'sidan juda tez-tez so'rov ketishi YouTube'ning "429 Too Many Requests"
# cheklovini keltirib chiqaradi — bu barcha foydalanuvchilar uchun umumiy
# (global) kechikish, chunki cheklov IP darajasida qo'yiladi.
_YT_MIN_INTERVAL_SECONDS = 3.0
_yt_last_request_lock = threading.Lock()
_yt_last_request_time = 0.0


def throttle_youtube_request() -> None:
    global _yt_last_request_time
    with _yt_last_request_lock:
        now = time.monotonic()
        wait = _YT_MIN_INTERVAL_SECONDS - (now - _yt_last_request_time)
        if wait > 0:
            time.sleep(wait)
        _yt_last_request_time = time.monotonic()

SUPPORTED_DOMAINS = {
    "instagram.com": "Instagram",
    "tiktok.com": "TikTok",
    "facebook.com": "Facebook",
    "fb.watch": "Facebook",
    "twitter.com": "X (Twitter)",
    "x.com": "X (Twitter)",
    "pinterest.com": "Pinterest",
    "pin.it": "Pinterest",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
}

URL_REGEX = re.compile(r"https?://[^\s]+")
INSTAGRAM_SHORTCODE_REGEX = re.compile(r"instagram\.com/(?:reel|p|tv)/([^/?#]+)")
YOUTUBE_ID_REGEX = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/|embed/))([A-Za-z0-9_-]{6,})"
)

VIDEO_CACHE_DIR = "video_cache"


def _extract_youtube_id(url: str) -> str | None:
    match = YOUTUBE_ID_REGEX.search(url)
    return match.group(1) if match else None


def _video_cache_lookup(video_id: str) -> "DownloadResult | None":
    """
    Agar bu YouTube video oldin yuklab olingan bo'lsa, keshdagi nusxadan
    (asl faylni o'chirmasdan, yangi nusxa chiqarib) qaytaradi.
    """
    import json
    meta_path = os.path.join(VIDEO_CACHE_DIR, f"{video_id}.json")
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        media_path = meta.get("media_path")
        if not media_path or not os.path.exists(media_path):
            return None
        ext = os.path.splitext(media_path)[1]
        os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
        copy_path = os.path.join(config.DOWNLOAD_DIR, f"{uuid.uuid4()}{ext}")
        shutil.copyfile(media_path, copy_path)
        return DownloadResult(
            success=True, file_path=copy_path, platform="YouTube",
            is_video=meta.get("is_video", True), title=meta.get("title", ""),
            duration=meta.get("duration"), width=meta.get("width"), height=meta.get("height"),
        )
    except Exception:
        logger.exception(f"Video kesh o'qishda xato: {video_id}")
        return None


def _video_cache_store(video_id: str, result: "DownloadResult") -> None:
    import json
    try:
        os.makedirs(VIDEO_CACHE_DIR, exist_ok=True)
        ext = os.path.splitext(result.file_path)[1]
        cached_media_path = os.path.join(VIDEO_CACHE_DIR, f"{video_id}{ext}")
        shutil.copyfile(result.file_path, cached_media_path)
        meta = {
            "media_path": cached_media_path,
            "title": result.title,
            "duration": result.duration,
            "width": result.width,
            "height": result.height,
            "is_video": result.is_video,
        }
        with open(os.path.join(VIDEO_CACHE_DIR, f"{video_id}.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f)
    except Exception:
        logger.exception(f"Video keshga yozishda xato: {video_id}")


@dataclass
class DownloadResult:
    success: bool
    file_path: str | None = None
    platform: str | None = None
    error: str | None = None
    is_video: bool = True
    title: str | None = None
    duration: int | None = None
    width: int | None = None
    height: int | None = None


def extract_url(text: str) -> str | None:
    match = URL_REGEX.search(text)
    return match.group(0) if match else None


def detect_platform(url: str) -> str | None:
    for domain, name in SUPPORTED_DOMAINS.items():
        if domain in url:
            return name
    return None


def _instagram_cookie_opts() -> dict:
    cookies_file = getattr(config, "INSTAGRAM_COOKIES_FILE", "") or ""
    if cookies_file:
        return {"cookiefile": cookies_file}
    if config.USE_BROWSER_COOKIES:
        return {"cookiesfrombrowser": (config.USE_BROWSER_COOKIES,)}
    return {}


def _youtube_cookie_opts() -> dict:
    cookies_file = getattr(config, "YOUTUBE_COOKIES_FILE", "") or ""
    logger.warning(f"YouTube cookie debug: file={cookies_file!r}")
    if cookies_file:
        return {"cookiefile": cookies_file}
    return {}


def _youtube_js_runtime_opts() -> dict:
    """
    yt-dlp'ning yangi EJS (challenge solver) tizimi uchun: qaysi JS runtime
    ishlatilishini (node — konteynerda mavjud) va solver skriptini qayerdan
    yuklab olishni (GitHub) aniq ko'rsatamiz. Buni bermasak, yt-dlp signature/n
    challenge'larini yecha olmay, "Only images are available" xatosiga tushadi.
    """
    return {
        "js_runtimes": {"node": {}},
        "remote_components": {"ejs:github"},
    }


def _youtube_pot_provider_opts() -> dict:
    """
    bgutil-ytdlp-pot-provider orqali PO Token oladi — bu YouTube'ning
    "Sign in to confirm you're not a bot" bloklashini cookie'siz ham
    yechishga yordam beradi. Provider manzili YTDLP_POT_PROVIDER_URL
    environment o'zgaruvchisidan olinadi (Railway'dagi alohida xizmat).

    Shu bilan birga, yt-dlp'ga aynan qaysi YouTube "mijozlar"ni (player
    client) ishlatishni ham qattiq belgilaymiz: android_vr kabi mijozlar
    POT token ishlatmaydi va endi tez-tez qattiq bot-tekshiruv xatosi
    bilan to'xtaydi — shu sabab web_safari/tv (POT bilan ishlaydigan)
    urinishga hech qachon yetib bormaydi. Shuning uchun android_vr'ni
    chetlab, to'g'ridan-to'g'ri POT-mos mijozlarni ishlatamiz.
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


def _instaloader_fallback(url: str, file_id: str) -> "DownloadResult | None":
    """
    yt-dlp Instagram'ni o'qiy olmagan hollarda ishlatiladigan zaxira usul.
    Instaloader mustaqil kod bilan ishlagani uchun, ba'zan yt-dlp ishlamay
    qolgan paytlarda ham ishlashda davom etadi.
    """
    logger.warning(
        f"Instaloader debug: username={bool(config.INSTAGRAM_USERNAME)}, "
        f"session_file={config.INSTAGRAM_SESSION_FILE!r}"
    )
    if not (config.INSTAGRAM_USERNAME and config.INSTAGRAM_SESSION_FILE):
        return None

    match = INSTAGRAM_SHORTCODE_REGEX.search(url)
    if not match:
        return None
    shortcode = match.group(1)

    try:
        import instaloader

        target_dir = os.path.join(config.DOWNLOAD_DIR, f"ig_{file_id}")
        os.makedirs(target_dir, exist_ok=True)

        L = instaloader.Instaloader(
            dirname_pattern=target_dir,
            save_metadata=False,
            download_comments=False,
            download_geotags=False,
            post_metadata_txt_pattern="",
            quiet=True,
        )
        L.load_session_from_file(config.INSTAGRAM_USERNAME, config.INSTAGRAM_SESSION_FILE)

        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=target_dir)

        media_file = None
        is_video = True
        for f in os.listdir(target_dir):
            if f.lower().endswith((".mp4",)):
                media_file = os.path.join(target_dir, f)
                is_video = True
                break
            if f.lower().endswith((".jpg", ".jpeg", ".png")) and not media_file:
                media_file = os.path.join(target_dir, f)
                is_video = False

        if not media_file:
            shutil.rmtree(target_dir, ignore_errors=True)
            return None

        final_path = os.path.join(config.DOWNLOAD_DIR, f"{file_id}{os.path.splitext(media_file)[1]}")
        shutil.move(media_file, final_path)
        shutil.rmtree(target_dir, ignore_errors=True)

        return DownloadResult(success=True, file_path=final_path, platform="Instagram", is_video=is_video)

    except Exception:
        logger.exception(f"Instaloader fallback error for {url}")
        return None


def _download_pinterest_image(url: str, file_id: str) -> str | None:
    try:
        pinterest_opts = {
            "quiet": True,
            "no_warnings": True,
            "ignore_no_formats_error": True,
        }
        with yt_dlp.YoutubeDL(pinterest_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        image_url = info.get("thumbnail")
        if not image_url:
            thumbnails = info.get("thumbnails") or []
            if thumbnails:
                image_url = thumbnails[-1].get("url")
        if not image_url:
            image_url = info.get("url")

        if not image_url:
            return None

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(image_url, timeout=15, headers=headers)
        if resp.status_code != 200:
            return None

        content_type = resp.headers.get("Content-Type", "")
        logger.warning(
            f"Pinterest rasm debug: image_url={image_url!r}, "
            f"content_type={content_type!r}, bytes={len(resp.content)}, "
            f"first_bytes={resp.content[:16]!r}"
        )
        if "image" not in content_type:
            logger.warning(f"Pinterest javobi rasm emas ({content_type}): {url}")
            return None

        # Pinterest ba'zan webp yoki boshqa format qaytaradi, buni oddiy
        # Content-Type asosida .jpg deb nomlash Telegram'da IMAGE_PROCESS_FAILED
        # xatosiga olib keladi. Shu uchun Pillow bilan qayta ochib, har doim
        # haqiqiy JPEG (RGB) sifatida saqlaymiz.
        try:
            image = Image.open(BytesIO(resp.content))
            image = image.convert("RGB")
        except Exception:
            logger.exception(f"Pinterest rasmni ochib bo'lmadi (buzuq fayl?): {url}")
            return None

        if image.width < 10 or image.height < 10:
            logger.warning(f"Pinterest rasmi juda kichik ({image.width}x{image.height}): {url}")
            return None

        os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
        file_path = os.path.join(config.DOWNLOAD_DIR, f"{file_id}.jpg")
        image.save(file_path, "JPEG", quality=90)
        return file_path

    except Exception:
        logger.exception(f"Pinterest rasm yuklashda xatolik: {url}")
        return None


def download_media(url: str) -> DownloadResult:
    platform = detect_platform(url)
    if not platform:
        return DownloadResult(
            success=False,
            error="Bu havola qo'llab-quvvatlanmaydi. Instagram, TikTok, Facebook, "
                  "X yoki Pinterest havolasini yuboring.",
        )

    youtube_video_id = _extract_youtube_id(url) if platform == "YouTube" else None
    if youtube_video_id:
        cached = _video_cache_lookup(youtube_video_id)
        if cached:
            logger.info(f"Video keshdan berildi: {youtube_video_id}")
            return cached

    os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    output_template = os.path.join(config.DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    ydl_opts = {
        "outtmpl": output_template,
        "format": (
            "best[height<=480][ext=mp4][filesize<50M]"
            "/bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]"
            "/best[height<=480][filesize<50M]"
            "/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=720]+bestaudio/best"
        ),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": config.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024,
        "concurrent_fragment_downloads": 16,
        "socket_timeout": 10,
        "nocheckcertificate": True,
        "http_chunk_size": 10485760,
        "ffmpeg_location": config.FFMPEG_PATH,
        "external_downloader": "aria2c",
        "external_downloader_args": {
            "aria2c": ["-x", "16", "-s", "16", "-k", "1M", "--max-connection-per-server=16"],
        },
    }

    if platform == "Pinterest":
        # Pinterest postlari ko'pincha rasm bo'ladi — video-ga xos format
        # zanjiri (ext=mp4/bestvideo+bestaudio) ularga mos kelmaydi va
        # noto'g'ri xato qaytaradi. Shu uchun bu yerda soddaroq formatga
        # qaytamiz, haqiqiy rasm holatini pastdagi fallback aniqlaydi.
        # retries/socket_timeout'ni qattiq cheklab qo'yamiz — aks holda
        # video formati topilmaganda yt-dlp uzoq vaqt qayta urinib,
        # foydalanuvchiga bot "qotgandek" ko'rinishi mumkin.
        ydl_opts["format"] = "best/bestvideo+bestaudio"
        ydl_opts["ignore_no_formats_error"] = True
        ydl_opts["retries"] = 1
        ydl_opts["fragment_retries"] = 1
        ydl_opts["socket_timeout"] = 8
        ydl_opts["extractor_retries"] = 1
    elif platform == "Instagram":
        ydl_opts.update(_instagram_cookie_opts())
    elif platform == "YouTube":
        ydl_opts.update(_youtube_cookie_opts())
        ydl_opts.update(_youtube_pot_provider_opts())
        ydl_opts.update(_youtube_js_runtime_opts())
        ydl_opts["no_warnings"] = False
        ydl_opts["quiet"] = False
        throttle_youtube_request()

    try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
        except yt_dlp.utils.DownloadError as e:
            if "Requested format is not available" in str(e):
                try:
                    debug_opts = {k: v for k, v in ydl_opts.items() if k != "format"}
                    with yt_dlp.YoutubeDL(debug_opts) as ydl_debug:
                        debug_info = ydl_debug.extract_info(url, download=False)
                        formats = debug_info.get("formats", [])
                        logger.warning(f"Mavjud formatlar: {[(f.get('format_id'), f.get('height'), f.get('filesize') or f.get('filesize_approx')) for f in formats]}")
                except Exception as debug_e:
                    logger.warning(f"Format debug xatosi: {debug_e}")
            if "cookie" in str(e).lower() or "DPAPI" in str(e):
                logger.warning(f"Cookie xatosi, cookie'siz qayta urinilmoqda: {e}")
                fallback_opts = {k: v for k, v in ydl_opts.items() if k not in ("cookiesfrombrowser", "cookiefile")}
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file_path = ydl.prepare_filename(info)
            else:
                raise

        if not os.path.exists(file_path):
            return DownloadResult(success=False, error="Yuklashda xatolik yuz berdi.")

        # merge_output_format tufayli haqiqiy fayl kengaytmasi info["ext"]dan farq
        # qilishi mumkin (masalan webm+m4a → mp4ga birlashtiriladi) — shuning uchun
        # haqiqiy fayl yo'lidan tekshiramiz.
        actual_ext = os.path.splitext(file_path)[1].lstrip(".").lower()
        is_video = actual_ext in ("mp4", "mkv", "webm", "mov")
        result = DownloadResult(
            success=True, file_path=file_path, platform=platform, is_video=is_video,
            title=info.get("title", ""),
            duration=info.get("duration"),
            width=info.get("width"),
            height=info.get("height"),
        )
        if youtube_video_id:
            _video_cache_store(youtube_video_id, result)
        return result

    except yt_dlp.utils.DownloadError as e:
        error_text = str(e)

        if platform == "Pinterest" and (
            "No video formats found" in error_text
            or "Requested format is not available" in error_text
        ):
            image_path = _download_pinterest_image(url, file_id)
            if image_path:
                return DownloadResult(success=True, file_path=image_path, platform=platform, is_video=False)
            return DownloadResult(success=False, error="Bu Pinterest pin'ni yuklab bo'lmadi.")

        if platform == "Instagram":
            logger.warning(f"yt-dlp Instagram xatosi, Instaloader bilan sinalmoqda: {url}")
            fallback_result = _instaloader_fallback(url, file_id)
            if fallback_result:
                return fallback_result

        logger.warning(f"Download error for {url}: {e}")
        return DownloadResult(
            success=False,
            error="Video juda katta yoki havola yopiq/xususiy bo'lishi mumkin.",
        )
    except Exception as e:
        logger.exception(f"Unexpected error downloading {url}")
        return DownloadResult(success=False, error=f"Kutilmagan xatolik: {e}")


def cleanup_file(file_path: str) -> None:
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass


def download_audio_from_url(url: str) -> DownloadResult:
    os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    output_template = os.path.join(config.DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestaudio[ext=m4a][abr<=128]/bestaudio[abr<=128]/bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": config.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024,
        "nocheckcertificate": True,
        "ffmpeg_location": config.FFMPEG_PATH,
        "external_downloader": "aria2c",
        "external_downloader_args": {
            "aria2c": ["-x", "16", "-s", "16", "-k", "1M", "--max-connection-per-server=16"],
        },
    }

    platform = detect_platform(url)
    if platform == "Instagram":
        ydl_opts.update(_instagram_cookie_opts())
    elif platform == "YouTube":
        ydl_opts.update(_youtube_cookie_opts())
        ydl_opts.update(_youtube_pot_provider_opts())
        ydl_opts.update(_youtube_js_runtime_opts())
        throttle_youtube_request()

    try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
        except yt_dlp.utils.DownloadError as e:
            if "cookie" in str(e).lower() or "DPAPI" in str(e):
                fallback_opts = {k: v for k, v in ydl_opts.items() if k not in ("cookiesfrombrowser", "cookiefile")}
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file_path = ydl.prepare_filename(info)
            else:
                raise

        if not os.path.exists(file_path):
            return DownloadResult(success=False, error="Audio ajratib bo'lmadi.")

        return DownloadResult(success=True, file_path=file_path, platform=platform, is_video=False)

    except Exception:
        logger.exception(f"Audio extraction error for {url}")
        return DownloadResult(success=False, error="Bu havoladan audio ajratib bo'lmadi.")