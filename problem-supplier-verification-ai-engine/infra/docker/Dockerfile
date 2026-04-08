# STAGE 1: Build & Setup
From python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml .
RUN uv sync --frozen --no-cache

# STAGE 2: Production Image
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . .

# Environment setup
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
