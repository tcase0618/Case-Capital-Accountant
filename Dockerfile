FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md AGENTS.md ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

RUN uv sync --no-dev --no-editable

COPY data/raw/.gitkeep data/raw/.gitkeep
COPY data/duckdb/.gitkeep data/duckdb/.gitkeep
COPY data/parquet/.gitkeep data/parquet/.gitkeep

EXPOSE 8000

CMD ["uvicorn", "accountant.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
