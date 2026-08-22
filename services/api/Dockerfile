FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --gid 10001 laggente && useradd --uid 10001 --gid 10001 --no-create-home laggente
WORKDIR /app

COPY services/api/pyproject.toml services/api/uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev --no-install-project

COPY services/api/alembic.ini ./
COPY services/api/alembic ./alembic
COPY services/api/app ./app
RUN mkdir -p /data/uploads && chown -R laggente:laggente /app /data/uploads

USER laggente
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
