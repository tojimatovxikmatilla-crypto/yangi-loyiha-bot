FROM python:3.12-slim

# Node.js 20 va ffmpeg o'rnatish
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]