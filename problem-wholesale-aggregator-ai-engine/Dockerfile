# Build the virtual environment using uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation for faster execution
ENV UV_COMPILE_BYTECODE=1


# Copy dependency definition files first for Docker caching
COPY pyproject.toml uv.lock ./

# Install dependencies (exclude installing the project itself and dev deps)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Final runner stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy the prepared virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Ensure our virtual env's bin is in PATH so installed commands can be run directly
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Copy project source code
COPY src/ /app/src/
COPY alembic.ini /app/
COPY migrations/ /app/migrations/

# Expose port 8000 (standard port for the FastAPI app)
EXPOSE 8000

# Default command (gets overridden for the Celery worker in compose)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]