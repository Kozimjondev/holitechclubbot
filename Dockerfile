FROM python:3.12

ENV PYTHONUNBUFFERED=1

RUN pip install uv

WORKDIR /app

COPY requirements.lock pyproject.toml ./
COPY README.md ./

RUN uv pip install --no-cache --system -r requirements.lock

COPY . .

WORKDIR /app/src

EXPOSE 8000