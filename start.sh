#!/bin/sh
set -e

echo "=== telegram-bot-api fayli tekshiruvi ==="
ls -la /usr/local/bin/telegram-bot-api || echo "FAYL TOPILMADI: /usr/local/bin/telegram-bot-api"
which telegram-bot-api || echo "PATH orqali topilmadi"

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