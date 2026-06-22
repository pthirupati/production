#!/usr/bin/env bash
# Start the full FixitLab platform (preserves all database/user data in named volumes)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# CLUSTER_ROLE selects the per-role compose file for the four-droplet topology.
# When unset/empty, behavior is the single-host default (docker-compose.prod.yml).
CLUSTER_ROLE="${CLUSTER_ROLE:-}"
case "$CLUSTER_ROLE" in
  edge) COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.edge.yml}" ;;
  app)  COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.app.yml}" ;;
  data) COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.data.yml}" ;;
  labs) COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}" ;;  # labs = remote docker engine only; no compose stack
  *)    COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}" ;;
esac
ENV_FILE="${ENV_FILE:-.env.production}"

_env_true() {
  case "${1:-}" in
    1|true|TRUE|True|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

# Helper: in a cluster role, only run a post-start step on the node that owns it.
# Returns 0 (run) when single-host (no CLUSTER_ROLE) OR when role matches.
_role_runs() {
  [ -z "$CLUSTER_ROLE" ] && return 0
  case " $* " in *" $CLUSTER_ROLE "*) return 0 ;; *) return 1 ;; esac
}

# Sync production env from Vault, GitHub secrets, or local deploy/production.env
chmod +x "$ROOT/scripts/sync-production-env.sh" "$ROOT/scripts/ensure-ssl-certs.sh" "$ROOT/scripts/startup.sh" \
  "$ROOT/scripts/vault/"*.sh "$ROOT/scripts/vault/env-kv-helper.py" 2>/dev/null || true

# Networks must exist before Vault (app containers resolve vault on fixitlab_net)
docker network inspect fixitlab_labs >/dev/null 2>&1 || docker network create fixitlab_labs
docker network inspect fixitlab_net >/dev/null 2>&1 || docker network create fixitlab_net

# Vault must be up before render-env (when enabled via env or local approle file).
# In the cluster, Vault runs only on the edge node (D1); app/data nodes reach it
# remotely via VAULT_ADDR=http://<edge>:8200 and do not start a local container.
if _role_runs edge && { _env_true "${VAULT_ENABLED:-}" || [ -f "$ROOT/deploy/vault-approle.env" ]; }; then
  bash "$ROOT/scripts/vault/start.sh" 2>/dev/null || true
  VAULT_CFG_HASH="$(md5sum "$ROOT/infra/vault/config.hcl" 2>/dev/null | awk '{print $1}' || md5 -q "$ROOT/infra/vault/config.hcl" 2>/dev/null || true)"
  VAULT_CFG_MARKER="/tmp/fixitlab-vault-config-hash"
  if [ -n "$VAULT_CFG_HASH" ] && [ -f "$VAULT_CFG_MARKER" ] && [ "$(cat "$VAULT_CFG_MARKER")" != "$VAULT_CFG_HASH" ]; then
    echo "Vault config changed — recreating container"
    # shellcheck source=lib.sh
    source "$ROOT/scripts/vault/lib.sh"
    vault_compose up -d --force-recreate vault 2>/dev/null || true
    bash "$ROOT/scripts/vault/unseal.sh" 2>/dev/null || true
    bash "$ROOT/scripts/vault/ensure-network.sh" 2>/dev/null || true
  fi
  [ -n "$VAULT_CFG_HASH" ] && echo "$VAULT_CFG_HASH" > "$VAULT_CFG_MARKER"
fi

bash "$ROOT/scripts/sync-production-env.sh" "$ROOT/.env.production"
ENV_FILE=".env.production"

echo "=== FixitLab Platform START ==="
echo "Compose: $COMPOSE_FILE | Env: $ENV_FILE"

# Resolve the host's docker group id so the backend (which bind-mounts
# /var/run/docker.sock for admin monitoring) can READ the socket via `group_add`
# even if the image ever runs as a non-root user. Compose interpolates
# ${DOCKER_GID} from .env.production; we persist the *real* host gid here (Debian
# default 999) so it is correct on every node. Harmless when the backend is root.
DOCKER_GID="$(getent group docker 2>/dev/null | cut -d: -f3 || true)"
if [ -z "${DOCKER_GID:-}" ]; then
  DOCKER_GID="$(stat -c '%g' /var/run/docker.sock 2>/dev/null || true)"
fi
DOCKER_GID="${DOCKER_GID:-999}"
if grep -q '^DOCKER_GID=' "$ENV_FILE" 2>/dev/null; then
  sed -i "s/^DOCKER_GID=.*/DOCKER_GID=${DOCKER_GID}/" "$ENV_FILE"
else
  echo "DOCKER_GID=${DOCKER_GID}" >> "$ENV_FILE"
fi
export DOCKER_GID
echo "Resolved host docker gid: DOCKER_GID=${DOCKER_GID} (backend added to docker group for socket read)"

# Image source — DEFAULT (PULL_IMAGES unset/false) is the current behavior: build
# every service from its local ./backend|./frontend|./gateway context with
# `up -d --build`. When the Docker Hub pipeline is enabled the gated deploy sets
# PULL_IMAGES=1 (and IMAGE_TAG=<git-sha>), so instead we PULL the pinned images
# (compose `image:` now resolves to <ns>/fixitlab-*:<sha>) and bring the stack up
# WITHOUT --build, getting the exact CI-built, versioned image on every node.
# Services without a registry image (postgres, redis, rabbitmq, pgbouncer, vault,
# certbot) are unaffected; `pull` only fetches what each role's compose declares.
if _env_true "${PULL_IMAGES:-}"; then
  echo "PULL_IMAGES set — pulling pinned images (IMAGE_TAG=${IMAGE_TAG:-latest}, ns=${FIXITLAB_IMAGE_NS:-fixitlab}) instead of building"
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --no-build
else
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
fi

# Sync the Postgres role password to the current env. The fixitlab_db_data volume
# persists across deploys and keeps the password it was FIRST initialized with, so
# a rotated POSTGRES_PASSWORD won't match until we ALTER it — otherwise the backend
# fails with "password authentication failed". Local socket connections use trust
# auth, so no current password is needed. Generated passwords are [A-Za-z0-9._-~]
# (see ci-generate-secrets.py _SAFE_PUNCT), so inlining is injection-safe.
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx fixitlab_db; then
  _PGUSER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r"')"
  _PGPASS="$(grep -E '^POSTGRES_PASSWORD=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r"')"
  _PGUSER="${_PGUSER:-fixitlab}"
  if [ -n "$_PGPASS" ]; then
    for _i in $(seq 1 30); do docker exec fixitlab_db pg_isready -U "$_PGUSER" >/dev/null 2>&1 && break; sleep 2; done
    if docker exec fixitlab_db psql -v ON_ERROR_STOP=1 -U "$_PGUSER" -d postgres \
         -c "ALTER USER \"$_PGUSER\" WITH PASSWORD '$_PGPASS';" >/dev/null 2>&1; then
      echo "Synced Postgres role password to current env (rotation-safe)"
    else
      echo "WARN: could not sync Postgres role password — relying on init value"
    fi
  fi
fi

# Ensure Vault is on the same network as backend (fixes legacy standalone vault compose)
if _role_runs edge && { _env_true "${VAULT_ENABLED:-}" || [ -f "$ROOT/deploy/vault-approle.env" ]; }; then
  bash "$ROOT/scripts/vault/ensure-network.sh" 2>/dev/null || true
fi

# Pin all app services to fixitlab_net (migrate off legacy fixitlab_fixitlab_net).
# Single-host only — in the cluster, vault and app services live on different nodes.
if [ -z "$CLUSTER_ROLE" ] && docker network inspect fixitlab_fixitlab_net >/dev/null 2>&1; then
  BACKEND_ON_LEGACY="$(docker inspect fixitlab-backend-1 --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null \
    | grep -q fixitlab_fixitlab_net && echo yes || echo no)"
  if [ "$BACKEND_ON_LEGACY" = "yes" ]; then
    echo "Migrating app containers to fixitlab_net..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --force-recreate \
      vault backend celery_worker celery_provisioning celery_maintenance celery_beat gateway frontend-prod
    bash "$ROOT/scripts/vault/unseal.sh" 2>/dev/null || true
    bash "$ROOT/scripts/vault/ensure-network.sh" 2>/dev/null || true
  fi
fi

# Always unseal Vault after containers start (Vault always starts sealed after restart).
# Edge node owns Vault in the cluster; other roles reach it remotely.
if _role_runs edge && { _env_true "${VAULT_ENABLED:-}" || [ -f "$ROOT/deploy/vault-approle.env" ]; }; then
  echo "Auto-unsealing Vault..."
  for _i in $(seq 1 12); do
    bash "$ROOT/scripts/vault/unseal.sh" 2>/dev/null && break || sleep 5
  done
fi

# Recreate app workers when env file changes so containers pick up new secrets.
# Only on a node that runs the backend/celery stack (single-host or cluster app).
if _role_runs app; then
  ENV_HASH="$(md5sum "$ENV_FILE" 2>/dev/null | awk '{print $1}' || md5 -q "$ENV_FILE" 2>/dev/null || true)"
  ENV_HASH_FILE="/tmp/fixitlab-env-hash"
  if [ -n "$ENV_HASH" ] && [ -f "$ENV_HASH_FILE" ] && [ "$(cat "$ENV_HASH_FILE")" != "$ENV_HASH" ]; then
    echo "Env changed — recreating backend/celery containers"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --force-recreate \
      backend celery_worker celery_provisioning celery_maintenance celery_beat
  fi
  [ -n "$ENV_HASH" ] && echo "$ENV_HASH" > "$ENV_HASH_FILE"

  echo "Waiting for backend..."
  for i in $(seq 1 60); do
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python -c \
      "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/health/'); assert r.status==200" 2>/dev/null; then
      break
    fi
    sleep 3
  done
fi

# SSL/Let's Encrypt is owned by the gateway, which runs on the edge node (or single-host).
export COMPOSE_FILE ENV_FILE
if _role_runs edge; then
  echo "Ensuring SSL certificates (Let's Encrypt)..."
fi
if _role_runs edge && bash "$ROOT/scripts/ensure-ssl-certs.sh"; then
  echo "SSL ready"
elif ! _role_runs edge; then
  : # not the edge node — gateway/SSL handled on D1
else
  echo "WARNING: SSL certificate not obtained — site available on HTTP only until DNS/port 80 is fixed"
fi

# Database-touching steps run on the node with the backend (single-host or cluster app).
if _role_runs app; then
  echo "Running migrations (safe — does not wipe data)..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python manage.py migrate --noinput

  echo "Syncing superuser credentials from env..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python /scripts/create_superuser.py || true

  echo "Seeding/updating scenarios..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python manage.py seed_scenarios --dir /scenarios --merge-only

  echo "Admin demo certificate / sample interview..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python manage.py seed_admin_demo || true

  echo "Seeding/updating projects..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python manage.py seed_projects || true

  echo "Seeding/updating certification tracks..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python manage.py seed_certifications || true

  echo "Seeding/updating interview question bank (free, rule-based)..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python manage.py seed_interview_data || true

  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python /scripts/migrate_jira_to_simulation.py || true
fi

should_build_scenarios() {
  case "${1:-true}" in
    1|true|TRUE|True|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

# Scenario lab images: built single-host here, but in the cluster they are built
# on the D4 Labs droplet's remote docker engine by scripts/ci-cluster-deploy.sh.
if [ -n "$CLUSTER_ROLE" ]; then
  echo "Cluster role '$CLUSTER_ROLE' — scenario image build/validation handled on D4 (skipping here)"
elif should_build_scenarios "${BUILD_SCENARIOS:-true}"; then
  echo "Building scenario lab images (BUILD_SCENARIOS=${BUILD_SCENARIOS:-true})..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend bash /scripts/build-scenario-images.sh 2>/dev/null || \
    bash "$ROOT/scripts/build-scenario-images.sh"
  echo "Validating scenario images..."
  bash "$ROOT/scripts/validate-scenario-images.sh"
else
  echo "Skipping scenario image build (BUILD_SCENARIOS=${BUILD_SCENARIOS})"
  bash "$ROOT/scripts/validate-scenario-images.sh" || {
    echo "ERROR: Scenario images missing. Re-run with BUILD_SCENARIOS=true"
    exit 1
  }
fi

echo ""
echo "✅ Platform is UP"
echo "   Users, subscriptions, and progress are stored in Docker volume: fixitlab_db_data"
# shellcheck source=env-helpers.sh
source "$ROOT/scripts/env-helpers.sh"
echo "   Site: $(env_val SITE_URL "$ENV_FILE")"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
