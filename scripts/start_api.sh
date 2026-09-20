#!/usr/bin/env bash
set -euo pipefail

alembic upgrade head

exec uvicorn accountant.api.app:app \
  --host "${ACCOUNTANT_HOST:-0.0.0.0}" \
  --port "${ACCOUNTANT_PORT:-8010}" \
  --proxy-headers
