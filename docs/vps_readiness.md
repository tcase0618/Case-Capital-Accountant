# Accountant VPS Readiness Runbook

This terminal is research-only. It does not execute trades. The Trading Terminal owns execution.

## Current Deployment Target

Use Docker Compose on a VPS with these services:

- `postgres`: primary PostgreSQL database.
- `api`: FastAPI backend and bundled frontend.
- `scheduler`: unattended SEC import, stale report refresh, score refresh, and bottleneck cache refresh.
- `backup`: daily `pg_dump` backups with retention.

Recommended first VPS size:

- 4 vCPU minimum.
- 8 GB RAM minimum, 16 GB preferred.
- 160 GB SSD minimum.
- Ubuntu 24.04 LTS.

## Storage Sizing

Run this before choosing or resizing a VPS:

```bash
python scripts/storage_audit.py --vps-disk-gb 50
```

Local measurement on 2026-09-20 showed:

- Repo workspace footprint: about 106 GB.
- PostgreSQL database size: about 56 GB.
- Largest table: `raw_facts`, about 49 GB.
- Derived/reporting data without `raw_facts`: about 7.5 GB.
- Legacy SQLite file: `data/accountant.db`, about 46 GB, and should not be copied to the VPS.

A 50 GB VPS is not safe for the full warehouse. PostgreSQL alone is larger than the disk once OS, Docker images, WAL, backups, and free-space headroom are included.

Safe options:

- Preferred: use a 160 GB VPS or attach a 100 GB+ data volume mounted for Postgres.
- Acceptable interim: deploy a lean/read-only dashboard copy with only derived tables and keep the raw warehouse local or on external storage.
- Not acceptable: delete `raw_facts` in-place and assume canonical facts remain valid. `canonical_facts` currently references `raw_facts`, so raw-fact pruning requires a planned schema/data-mode change.
- Do not copy `.run`, `data/accountant.db`, local `artifacts`, or local backups to the VPS.

For a 50 GB VPS, backups must be pulled off-host or stored in external object storage. Keeping full database backups on the same 50 GB disk defeats the deployment.

## First-Time VPS Setup

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Log out and back in after adding the Docker group.

Clone and configure:

```bash
git clone <repo-url> Case-Capital-Accountant
cd Case-Capital-Accountant
cp .env.production.example .env.production
nano .env.production
```

Required edits:

- Set a long random `POSTGRES_PASSWORD`.
- Set a valid `SEC_USER_AGENT` with contact information.
- Leave `MARKET_DATA_MODE=research_only`.
- Leave `IBKR_READ_ONLY=true` if IBKR is ever enabled.
- Do not add execution keys to this project.

Start:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## Readiness Gates

Run:

```bash
docker compose -f docker-compose.prod.yml exec api python scripts/vps_readiness_check.py --base-url http://127.0.0.1:8010
```

Required pass criteria:

- `/health` returns `ok`.
- `/api/reports/status` returns `running=true`.
- `last_error` is null.
- `/api/source-integrity` returns `STRONG` or `WATCH`.
- SEC freshness is within the configured limit.
- Report coverage is at least 99%.
- Bottleneck coverage is at least 99%.

## Backup

Backups run through the `backup` service and are stored in the `accountant_backups` Docker volume.

Manual backup:

```bash
docker compose -f docker-compose.prod.yml exec backup bash scripts/backup_postgres.sh
```

Restore drill:

```bash
docker compose -f docker-compose.prod.yml stop api scheduler
docker compose -f docker-compose.prod.yml exec postgres dropdb -U accountant accountant
docker compose -f docker-compose.prod.yml exec postgres createdb -U accountant accountant
docker compose -f docker-compose.prod.yml exec postgres pg_restore -U accountant -d accountant /backups/<backup-file>.dump
docker compose -f docker-compose.prod.yml up -d api scheduler
```

## Known Local Audit Findings From 2026-09-20

- Local Docker is not installed, so the container build was not run on the laptop.
- GitHub CI validates the production Docker Compose file and production Docker image build.
- Backend tests pass locally.
- Frontend production build passes locally.
- Alembic is at revision `009 (head)`.
- Local source integrity returned `STRONG` after the latest SEC freshness check.
- A stale local portable Postgres `postmaster.pid` caused DB startup instability; VPS should use Docker Postgres, not the Windows portable database.
- Local repo has many uncommitted changes. Do not deploy until Git is cleaned up and pushed.

## Do Not Deploy If

- `docker compose config` fails.
- `scripts/vps_readiness_check.py` fails.
- `last_error` is non-null in `/api/reports/status`.
- Source integrity is `FAILED`.
- `.env.production` contains secrets that are committed to Git.
- Backups have not been tested.
- The repo still depends on the Windows portable Postgres scripts.
