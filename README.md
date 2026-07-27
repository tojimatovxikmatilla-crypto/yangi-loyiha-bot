# Ko'p funksiyali Telegram bot

Instagram/TikTok/Facebook/X/Pinterest yuklab olish, AI yordamchi, rasm tarjimoni (OCR)
va ovoz ↔ matn funksiyalarini bitta botda jamlaydi. Har bir funksiya alohida modul
(router) sifatida yozilgan, shuning uchun yangi funksiya qo'shish oson va boshqa
qismlarni buzmaydi.

## Tuzilma

```
telegram_bot/
├── main.py                  # Botni ishga tushiruvchi fayl
├── config.py                 # .env dan sozlamalarni o'qiydi
├── handlers/                 # Har bir funksiya uchun alohida fayl
│   ├── start.py               # /start, asosiy menyu
│   ├── downloader.py           # Universal Downloader
│   ├── ai_assistant.py         # AI yordamchi (tarjima, savol-javob, xulosa)
│   ├── image_translator.py     # Rasm ichidagi matnni tarjima qilish (OCR)
│   └── voice_text.py           # Ovoz ↔ Matn
├── services/                 # "Miya" qismi — tashqi kutubxona/API bilan ishlash
│   ├── downloader_service.py   # yt-dlp orqali yuklab olish
│   ├── ai_service.py           # Claude API (hozircha placeholder rejimida)
│   ├── ocr_service.py          # Tesseract OCR
│   └── voice_service.py        # faster-whisper + gTTS
└── utils/
    ├── states.py               # FSM holatlar (masalan, tarjima oqimi)
    └── keyboards.py            # Umumiy klaviaturalar
```

## O'rnatish

1. Python 3.11+ kerak.
2. Kutubxonalarni o'rnating:
   ```bash
   pip install -r requirements.txt
   ```
3. OCR uchun tizimga Tesseract o'rnating (Ubuntu/Debian misolida):
   ```bash
   sudo apt-get install tesseract-ocr tesseract-ocr-uzb tesseract-ocr-rus
   ```
4. `.env.example` faylidan nusxa oling va to'ldiring:
   ```bash
   cp .env.example .env
   ```
   `BOT_TOKEN` ni @BotFather'dan oling va `.env` fayliga yozing.

5. Botni ishga tushiring:
   ```bash
   python main.py
   ```

## AI funksiyalarini keyinroq ulash

Hozircha `AI_API_KEY` bo'sh — shu sabab AI yordamchi va tarjima funksiyalari
"🔧 AI funksiyasi hali ulanmagan" degan xabar qaytaradi, lekin butun oqim
(tugmalar, til tanlash va h.k.) to'liq ishlaydi. Kalitni qo'shishning o'zi
yetarli — kodni o'zgartirish shart emas:

```env
AI_API_KEY=sk-ant-...
```

## Muhim dizayn qarori: til har doim so'raladi

Tarjima funksiyalarida (AI yordamchi va Image Translator) bot hech qachon
maqsad tilni o'zi taxmin qilmaydi — matn yoki rasm qabul qilingandan keyin
har doim "Qaysi tilga tarjima qilib beraymi?" deb so'raydi va tugmalar orqali
tanlatadi. Bu andoza `utils/states.py` va tegishli handlerlarda amalga
oshirilgan.

## Yangi funksiya qo'shish

1. `services/` ichida yangi fayl yozing (masalan `logo_service.py`) — bu yerda
   asosiy logika bo'ladi.
2. `handlers/` ichida yangi fayl yozing — bu yerda Telegram bilan muloqot
   (xabarlar, tugmalar) bo'ladi.
3. `main.py` da yangi routerni `dp.include_router(...)` orqali ulang.
4. Kerak bo'lsa, `utils/keyboards.py` dagi `main_menu_kb()` ga yangi tugma
   qo'shing.

## Hozirgi funksiyalar holati

| Funksiya | Holat |
|---|---|
| Universal Downloader (IG/TikTok/FB/X/Pinterest) | ✅ To'liq ishlaydi |
| AI yordamchi (savol-javob, tarjima, xulosa) | 🔧 Struktura tayyor, AI kalit kutilmoqda |
| Image Translator / OCR | ✅ Matn aniqlash ishlaydi, tarjima AI kalitga bog'liq |
| Voice → Text | ✅ To'liq ishlaydi (lokal, internet shart emas) |
| Text → Voice | ✅ To'liq ishlaydi (internet talab qiladi) |
| QR kod yaratish/o'qish | ✅ To'liq ishlaydi |
| Hashtag Generator | 🔧 Struktura tayyor, AI kalit kutilmoqda |
| Matn shifrlash/deshifrlash | ✅ To'liq ishlaydi (parol asosida, Fernet/AES) |
| Ob-havo | ✅ To'liq ishlaydi (Open-Meteo, API kalit shart emas) |

## Keyingi bosqichda qo'shish mumkin bo'lgan funksiyalar

Screenshotlaringizda ko'rilgan qo'shimcha g'oyalar: Profile Analyzer, Best
Posting Time, Logo Enhancer, PDF↔Word. Bularning har birini yuqoridagi
"Yangi funksiya qo'shish" andozasi bo'yicha alohida modul sifatida qo'shish
mumkin.
