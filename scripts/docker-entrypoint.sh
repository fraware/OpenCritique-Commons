#!/bin/sh
# Compose / container entrypoint: migrate fail-closed, then exec the service command.
set -eu

if [ -z "${OPENCRITIQUE_DATABASE_URL:-}" ]; then
  echo "OPENCRITIQUE_DATABASE_URL is required before starting the registry" >&2
  exit 1
fi

echo "Applying database migrations (alembic upgrade head)..."
python -c "
from opencritique_registry.migrate import upgrade_head
import os
upgrade_head(os.environ['OPENCRITIQUE_DATABASE_URL'])
print('migrations at head')
"

exec "$@"
