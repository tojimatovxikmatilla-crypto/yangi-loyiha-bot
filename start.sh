#!/bin/sh
set -e

echo "=== telegram-bot-api fayli tekshiruvi ==="
ls -la /usr/local/bin/telegram-bot-api || echo "FAYL TOPILMADI"
file /usr/local/bin/telegram-bot-api || echo "file buyrugi yoq"
ldd /usr/local/bin/telegram-bot-api || echo "ldd ishlamadi (bu ozi muhim malumot)"

mkdir -p /var/lib/telegram-bot-api

/usr/local/bin/telegram-bot-api \
  --api-id="${TELEGRAM_API_ID}" \
  --api-hash="${TELEGRAM_API_HASH}" \
  --local \
  --http-port=8081 \
  --dir=/var/lib/telegram-bot-api \
  --log=/dev/stdout &

sleep 3

exec python main.py