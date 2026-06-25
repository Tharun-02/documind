# DocuMind - Dockerfile
# Multi-stage build using pip (simpler than Poetry inside Docker)
# Builder: installs deps → Runtime: lean final image

# ──────────────────────────────────────────────
# Stage 1: Builder — install all dependencies
# ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps needed to compile some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment in /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# ── CACHE TRICK ──────────────────────────────
# Copy requirements first — Docker caches this layer.
# If only your code changes (not requirements.txt),
# Docker skips reinstalling packages → fast rebuilds.
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ──────────────────────────────────────────────
# Stage 2: Runtime — lean final image
# ──────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Only runtime system deps (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from builder
# /opt/venv contains uvicorn, fastapi, and everything else
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads

EXPOSE 8000

# Health check — used by Docker and Railway
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# uvicorn is at /opt/venv/bin/uvicorn — PATH above makes this work
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
