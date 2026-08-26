# syntax=docker/dockerfile:1.4

# ==============================================================================
# Stage 1: Build Dependencies & Wheels
# ==============================================================================
FROM python:3.11-slim AS builder

# Set build-time environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install compilation tools needed for C-extensions/Pillow/etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtualenv to hold isolated production dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy package requirements first for optimal Docker layer caching
COPY requirements.txt .

# Install dependencies into virtualenv (utilizing BuildKit cache for speed)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# ==============================================================================
# Stage 2: Minimal Production Runtime (Optimized for ZimaOS / Low-Spec Hosts)
# ==============================================================================
FROM python:3.11-slim AS runner

# Install only minimal runtime utilities:
# - dumb-init: Graceful shutdown (PID 1 signal forwarding for SIGTERM/SIGINT)
# - ca-certificates: Secure SSL connections to Telegram, Instagram, and Gemini APIs
# - fonts: TTF font rendering support for story/post image generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    dumb-init \
    ca-certificates \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Production environment optimizations:
# - PYTHONDONTWRITEBYTECODE: Reduces disk I/O on slow eMMC/flash storage
# - PYTHONUNBUFFERED: Instant log streaming to Docker/ZimaOS dashboards
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# 1. Create dedicated non-privileged user and group (UID/GID 10001)
# 2. Create persistent directories with correct permissions for ZimaOS mounts
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -M appuser && \
    mkdir -p /app/data/media /app/config && \
    chown -R appuser:appgroup /app

# Copy virtual environment from builder stage
COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv

# Copy source code and debug utility
COPY --chown=appuser:appgroup src/ /app/src/
COPY --chown=appuser:appgroup debug.py /app/debug.py

# Switch to non-root user (security hardening & proper host mount permissions)
USER appuser

# Lightweight Healthcheck (verifies Python runtime responsiveness)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Expose local media server port if used with ZimaOS / Cloudflare Tunnel
EXPOSE 3018

# Process manager entrypoint for clean signal handling & zombie reaping
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# Run Telegram bot service
CMD ["python", "-m", "src.main"]
