#!/bin/sh
set -e

mkdir -p /var/lib/telegram-bot-api

telegram-bot-api \
  --api-id="${TELEGRAM_API_ID}" \
  --api-hash="${TELEGRAM_API_HASH}" \
  --local \
  --http-port=8081 \
  --dir=/var/lib/telegram-bot-api \
  --log=/dev/stdout &

sleep 3

exec python main.py
