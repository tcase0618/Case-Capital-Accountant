#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${1:-/opt/case-capital/accountant}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

if ! id casecapital >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_ROOT" --shell /usr/sbin/nologin casecapital
fi

install -d -o casecapital -g casecapital \
  "$APP_ROOT/data" \
  "$APP_ROOT/data/raw" \
  "$APP_ROOT/data/duckdb" \
  "$APP_ROOT/data/parquet" \
  "$APP_ROOT/artifacts"

if [[ -d "$APP_ROOT/.venv" ]]; then
  chown -R casecapital:casecapital "$APP_ROOT/.venv"
fi

if [[ -f "$APP_ROOT/.env.production" ]]; then
  chown root:casecapital "$APP_ROOT/.env.production"
  chmod 0640 "$APP_ROOT/.env.production"
fi

echo "Prepared runtime user casecapital for $APP_ROOT"
