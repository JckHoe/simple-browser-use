FROM ghcr.io/astral-sh/uv:bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/python \
    UV_PYTHON_PREFERENCE=only-managed

# Install build dependencies and clean up in the same layer
RUN apt-get update -y && \
    apt-get install --no-install-recommends -y clang git && \
    rm -rf /var/lib/apt/lists/*

# Install Python before the project for caching
RUN uv python install 3.13

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY app /app/app
COPY main.py /app/main.py
COPY uv.lock /app/uv.lock
COPY pyproject.toml /app/pyproject.toml
COPY .python-version /app/.python-version

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y \
    chromium \
    xvfb \
    x11-utils \
    fonts-ipafont-gothic \
    fonts-wqy-zenhei \
    fonts-thai-tlwg \
    fonts-kacst \
    fonts-freefont-ttf \
    libxss1 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libcups2 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /python /python
COPY --from=builder /app /app

RUN chmod -R 755 /python /app

ENV ANONYMIZED_TELEMETRY=false \
    PATH="/app/.venv/bin:$PATH"

ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN playwright install chromium
RUN playwright install-deps

ENV PYTHONUNBUFFERED=1

CMD xvfb-run --auto-servernum --server-args='-screen 0 1920x1080x24' python main.py
