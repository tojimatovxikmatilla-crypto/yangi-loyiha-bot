<<<<<<< HEAD
"""
ffmpeg dasturining yo'lini avtomatik topish.
Tartib: 1) .env dagi FFMPEG_PATH  2) tizim PATH'i  3) Windows'dagi odatiy joylar.
"""
import os
import shutil
import logging

logger = logging.getLogger(__name__)

WINDOWS_COMMON_PATHS = [
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"D:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
]


def find_ffmpeg(configured_path: str = "") -> str:
    """
    ffmpeg.exe (yoki ffmpeg) ning ishlaydigan yo'lini qaytaradi.
    Hech qayerdan topilmasa, oddiy "ffmpeg" qaytaradi (xato chiqsa, foydalanuvchi
    PATH'ga qo'shishi yoki .env ga FFMPEG_PATH yozishi kerakligini bildiradi).
    """
    # 1) .env orqali aniq ko'rsatilgan bo'lsa
    if configured_path and os.path.exists(configured_path):
        return configured_path

    # 2) Tizim PATH'ida bo'lsa (Linux/macOS serverlarda odatda shunday)
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 3) Windows'dagi eng ko'p uchraydigan joylar
    for path in WINDOWS_COMMON_PATHS:
        if os.path.exists(path):
            return path

    logger.warning(
        "ffmpeg topilmadi! .env fayliga FFMPEG_PATH=... qo'shing yoki ffmpeg'ni "
        "tizim PATH'iga qo'shing. Hozircha 'ffmpeg' nomi bilan ishlatishga urinamiz."
    )
=======
"""
ffmpeg dasturining yo'lini avtomatik topish.
Tartib: 1) .env dagi FFMPEG_PATH  2) tizim PATH'i  3) Windows'dagi odatiy joylar.
"""
import os
import shutil
import logging

logger = logging.getLogger(__name__)

WINDOWS_COMMON_PATHS = [
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"D:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
]


def find_ffmpeg(configured_path: str = "") -> str:
    """
    ffmpeg.exe (yoki ffmpeg) ning ishlaydigan yo'lini qaytaradi.
    Hech qayerdan topilmasa, oddiy "ffmpeg" qaytaradi (xato chiqsa, foydalanuvchi
    PATH'ga qo'shishi yoki .env ga FFMPEG_PATH yozishi kerakligini bildiradi).
    """
    # 1) .env orqali aniq ko'rsatilgan bo'lsa
    if configured_path and os.path.exists(configured_path):
        return configured_path

    # 2) Tizim PATH'ida bo'lsa (Linux/macOS serverlarda odatda shunday)
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 3) Windows'dagi eng ko'p uchraydigan joylar
    for path in WINDOWS_COMMON_PATHS:
        if os.path.exists(path):
            return path

    logger.warning(
        "ffmpeg topilmadi! .env fayliga FFMPEG_PATH=... qo'shing yoki ffmpeg'ni "
        "tizim PATH'iga qo'shing. Hozircha 'ffmpeg' nomi bilan ishlatishga urinamiz."
    )
>>>>>>> f77d8220abf3a100f0a5668206524cc5a53bdd6c
    return "ffmpeg"