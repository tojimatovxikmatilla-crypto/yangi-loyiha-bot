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

import yt_dlp
import requests

logging.getLogger(__name__).warning(f"yt-dlp versiyasi: {yt_dlp.version.__version__}")

from config import config

logger = logging.getLogger(__name__)

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


@dataclass
class DownloadResult:
    success: bool
    file_path: str | None = None
    platform: str | None = None
    error: str | None = None
    is_video: bool = True


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
        if "image" not in content_type:
            logger.warning(f"Pinterest javobi rasm emas ({content_type}): {url}")
            return None

        ext = "png" if "png" in content_type else "jpg"

        os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
        file_path = os.path.join(config.DOWNLOAD_DIR, f"{file_id}.{ext}")
        with open(file_path, "wb") as f:
            f.write(resp.content)
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

    os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    output_template = os.path.join(config.DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    ydl_opts = {
        "outtmpl": output_template,
        "format": "best[height<=480][filesize<50M]/best[filesize<50M]/bestvideo[height<=720]+bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "js_runtimes": {"node": {}},
        "max_filesize": config.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024,
        "concurrent_fragment_downloads": 8,
        "socket_timeout": 10,
        "nocheckcertificate": True,
        "http_chunk_size": 10485760,
        "ffmpeg_location": config.FFMPEG_PATH,
    }

    if platform == "Instagram":
        ydl_opts.update(_instagram_cookie_opts())
    elif platform == "YouTube":
        ydl_opts.update(_youtube_cookie_opts())
        ydl_opts["no_warnings"] = False
        ydl_opts["quiet"] = False

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

        is_video = info.get("ext") in ("mp4", "mkv", "webm", "mov")
        return DownloadResult(success=True, file_path=file_path, platform=platform, is_video=is_video)

    except yt_dlp.utils.DownloadError as e:
        error_text = str(e)

        if platform == "Pinterest" and "No video formats found" in error_text:
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
        "js_runtimes": {"node": {}},
        "max_filesize": config.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024,
        "nocheckcertificate": True,
        "ffmpeg_location": config.FFMPEG_PATH,
    }

    platform = detect_platform(url)
    if platform == "Instagram":
        ydl_opts.update(_instagram_cookie_opts())
    elif platform == "YouTube":
        ydl_opts.update(_youtube_cookie_opts())

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