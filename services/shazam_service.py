<<<<<<< HEAD
"""
Shazam orqali qo'shiqni tovushidan aniqlash servisi.
shazamio kutubxonasi Shazam'ning o'z (norasmiy) xizmatiga ulanadi — API kalit shart emas.
"""
import os
import logging
import subprocess
from dataclasses import dataclass

from shazamio import Shazam
from pydub import AudioSegment
from config import config as _cfg

AudioSegment.converter = _cfg.FFMPEG_PATH

logger = logging.getLogger(__name__)


def _convert_to_wav(input_path: str) -> str | None:
    """Kirish faylini ffmpeg orqali toza WAV formatga aylantiradi (Shazam yaxshiroq o'qishi uchun)."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    try:
        result = subprocess.run(
            [
                _cfg.FFMPEG_PATH, "-y", "-i", input_path,
                "-ar", "44100", "-ac", "1",
                output_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0 or not os.path.exists(output_path):
            logger.warning(f"ffmpeg convert failed: {result.stderr.decode(errors='ignore')}")
            return None
        return output_path
    except Exception:
        logger.exception("ffmpeg conversion error")
        return None


@dataclass
class ShazamResult:
    success: bool
    title: str | None = None
    artist: str | None = None
    cover_url: str | None = None
    error: str | None = None


async def recognize_music(file_path: str) -> ShazamResult:
    converted_path = _convert_to_wav(file_path)
    recognize_path = converted_path or file_path

    try:
        shazam = Shazam()
        out = await shazam.recognize(recognize_path)
        track = out.get("track")

        if not track:
            return ShazamResult(
                success=False,
                error="Qo'shiq aniqlanmadi. Aniqroq va uzunroq (10+ soniya) parcha yuboring.",
            )

        title = track.get("title", "Noma'lum")
        artist = track.get("subtitle", "Noma'lum ijrochi")

        cover_url = None
        images = track.get("images", {})
        if images:
            cover_url = images.get("coverart") or images.get("background")

        return ShazamResult(success=True, title=title, artist=artist, cover_url=cover_url)

    except Exception as e:
        logger.exception("Shazam recognition error")
        return ShazamResult(success=False, error=f"Kutilmagan xatolik: {e}")
    finally:
        if converted_path and os.path.exists(converted_path):
            try:
                os.remove(converted_path)
            except OSError:
=======
"""
Shazam orqali qo'shiqni tovushidan aniqlash servisi.
shazamio kutubxonasi Shazam'ning o'z (norasmiy) xizmatiga ulanadi — API kalit shart emas.
"""
import os
import logging
import subprocess
from dataclasses import dataclass

from shazamio import Shazam
from pydub import AudioSegment
from config import config as _cfg

AudioSegment.converter = _cfg.FFMPEG_PATH

logger = logging.getLogger(__name__)


def _convert_to_wav(input_path: str) -> str | None:
    """Kirish faylini ffmpeg orqali toza WAV formatga aylantiradi (Shazam yaxshiroq o'qishi uchun)."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    try:
        result = subprocess.run(
            [
                _cfg.FFMPEG_PATH, "-y", "-i", input_path,
                "-ar", "44100", "-ac", "1",
                output_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0 or not os.path.exists(output_path):
            logger.warning(f"ffmpeg convert failed: {result.stderr.decode(errors='ignore')}")
            return None
        return output_path
    except Exception:
        logger.exception("ffmpeg conversion error")
        return None


@dataclass
class ShazamResult:
    success: bool
    title: str | None = None
    artist: str | None = None
    cover_url: str | None = None
    error: str | None = None


async def recognize_music(file_path: str) -> ShazamResult:
    converted_path = _convert_to_wav(file_path)
    recognize_path = converted_path or file_path

    try:
        shazam = Shazam()
        out = await shazam.recognize(recognize_path)
        track = out.get("track")

        if not track:
            return ShazamResult(
                success=False,
                error="Qo'shiq aniqlanmadi. Aniqroq va uzunroq (10+ soniya) parcha yuboring.",
            )

        title = track.get("title", "Noma'lum")
        artist = track.get("subtitle", "Noma'lum ijrochi")

        cover_url = None
        images = track.get("images", {})
        if images:
            cover_url = images.get("coverart") or images.get("background")

        return ShazamResult(success=True, title=title, artist=artist, cover_url=cover_url)

    except Exception as e:
        logger.exception("Shazam recognition error")
        return ShazamResult(success=False, error=f"Kutilmagan xatolik: {e}")
    finally:
        if converted_path and os.path.exists(converted_path):
            try:
                os.remove(converted_path)
            except OSError:
>>>>>>> f77d8220abf3a100f0a5668206524cc5a53bdd6c
                pass