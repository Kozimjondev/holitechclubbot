# Use slim variant to reduce image size
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# Install uv in a single layer
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency files first for better layer caching
COPY requirements.lock pyproject.toml README.md ./

# Install dependencies with additional space-saving flags
RUN uv pip install --no-cache --system --no-deps -r requirements.lock \
    && rm -rf /root/.cache /tmp/* \
    && find /usr/local -name "*.pyc" -delete \
    && find /usr/local -name "__pycache__" -type d -exec rm -rf {} +

# Copy application code
COPY . .

WORKDIR /app/src

EXPOSE 8000