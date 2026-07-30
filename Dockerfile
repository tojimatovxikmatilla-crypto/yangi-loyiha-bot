FROM debian:bookworm AS botapi-build

RUN apt-get update && apt-get install -y --no-install-recommends \
    make git zlib1g-dev libssl-dev gperf cmake g++ ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --recursive https://github.com/tdlib/telegram-bot-api.git /src \
    && mkdir /src/build \
    && cd /src/build \
    && cmake -DCMAKE_BUILD_TYPE=Release .. \
    && cmake --build . --target install -j$(nproc)

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

COPY --from=botapi-build /usr/local/bin/telegram-bot-api /usr/local/bin/telegram-bot-api

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]