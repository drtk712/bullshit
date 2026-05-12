FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_CACHE_DIR=/tmp/uv-cache

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

COPY app ./app

EXPOSE 80

CMD ["sh", "-c", "uv run python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-80}"]
