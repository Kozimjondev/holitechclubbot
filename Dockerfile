# Use slim variant to reduce image size
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock README.md ./

# Create virtual environment and sync dependencies
RUN uv sync --frozen --no-dev && \
    rm -rf /root/.cache /tmp/* && \
    find /app/.venv -name "*.pyc" -delete && \
    find /app/.venv -name "__pycache__" -type d -exec rm -rf {} +

# Copy application code
COPY . .

WORKDIR /app/src

# Activate virtual environment
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000