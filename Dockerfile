FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg ca-certificates gnupg aria2 unzip \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

ENV DENO_INSTALL="/usr/local"
RUN curl -fsSL https://deno.land/install.sh | sh -s -- -y \
    && /usr/local/bin/deno --version

ENV PATH="/usr/local/bin:${PATH}"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]