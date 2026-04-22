#!/usr/bin/env bash
#
# Container entrypoint that guarantees the schema is in place before we hand
# control to the real process (uvicorn / celery worker / celery beat).
#
# We run migrations on every container start because:
#   1. A fresh `docker compose up` needs a schema bootstrap — the initial
#      migration also seeds the tracked companies so the Celery pipeline has
#      something to iterate over.
#   2. `alembic upgrade head` is idempotent, so re-runs on existing volumes
#      are a cheap no-op.
#
# We only migrate when the caller is the primary API or the beat scheduler.
# Celery worker pods skip migrations (they race with the API on cold-start and
# the API will have already handled it anyway).

set -euo pipefail

cd /app

should_migrate=1
case "${1:-}" in
  celery)
    # `celery ... worker` → skip, `celery ... beat` → migrate so we still have
    # a safety-net if the API container is disabled in a given topology.
    for arg in "$@"; do
      if [[ "$arg" == "worker" ]]; then
        should_migrate=0
      fi
    done
    ;;
esac

if [[ "$should_migrate" == "1" ]]; then
  # Wait up to 60s for Postgres. docker-compose healthchecks usually make
  # this unnecessary, but keep it as belt-and-suspenders for bare `docker run`.
  python - <<'PY'
import os, sys, time
import psycopg2

url = os.environ.get("SYNC_DATABASE_URL")
if not url:
    sys.exit(0)

deadline = time.time() + 60
last = None
while time.time() < deadline:
    try:
        conn = psycopg2.connect(url)
        conn.close()
        break
    except Exception as exc:
        last = exc
        time.sleep(1.5)
else:
    print(f"[entrypoint] Postgres not reachable: {last}", file=sys.stderr)
    sys.exit(1)
PY

  echo "[entrypoint] Running alembic upgrade head..."
  alembic upgrade head
fi

exec "$@"
