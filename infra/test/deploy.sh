#!/usr/bin/env bash
# Deploy Sufler prod-like stack on the bank TEST VM.
#
# Prerequisites: Docker Engine + Compose v2, .env next to this script.
# Secrets stay in .env (gitignored) — never commit them.
#
# Usage (from infra/test):
#   cp .env.example .env && $EDITOR .env
#   chmod +x deploy.sh
#   ./deploy.sh              # validate + up --build -d (local build)
#   ./deploy.sh pull-up      # pull BACKEND_IMAGE/FRONTEND_IMAGE then up (CI)
#   ./deploy.sh db-verify    # migrate + pgvector indexes + backend connection
#   ./deploy.sh support-verify  # redis + celery worker + MinIO upload/download
#   ./deploy.sh inference-verify  # ASR + LLM gateway (profile=test) + suggest smoke
#   ./deploy.sh nginx-test   # nginx -t against nginx.conf + certs
#   ./deploy.sh backup-stub  # PostgreSQL backup stub (--dry-run by default)
#   ./deploy.sh down         # stop and remove containers
#   ./deploy.sh config       # validate compose only
#   ./deploy.sh logs         # follow logs
#   ./deploy.sh ps           # service statusset -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${ROOT}/docker-compose.prod-like.yml"
ENV_FILE="${ROOT}/.env"
PROJECT="sufler-test"

cd "${ROOT}"

die() { echo "ERROR: $*" >&2; exit 1; }

require_env() {
  [[ -f "${ENV_FILE}" ]] || die "Missing ${ENV_FILE}. Copy .env.example → .env and fill secrets."
  # Fail fast if required keys are empty placeholders
  local required=(POSTGRES_PASSWORD MINIO_ROOT_USER MINIO_ROOT_PASSWORD DJANGO_SECRET_KEY)
  local key
  # shellcheck disable=SC1090
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
  for key in "${required[@]}"; do
    if [[ -z "${!key:-}" ]]; then
      die "${key} is empty in .env"
    fi
    if [[ "${!key}" == *"CHANGE_ME"* ]] || [[ "${!key}" == replace-with-* ]] || [[ "${!key}" == *"replace-me"* ]]; then
      die "${key} still has a placeholder value — set a real secret"
    fi
  done
}

require_tls_certs() {
  local crt="${ROOT}/certs/fullchain.pem"
  local key="${ROOT}/certs/privkey.pem"
  if [[ ! -f "${crt}" || ! -f "${key}" ]]; then
    die "Missing TLS certs. Run: ./gen-self-signed-cert.sh [CN]  (see README — HTTPS only)"
  fi
}

compose() {
  docker compose -p "${PROJECT}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

write_image_env() {
  # Persist CI image refs into .env without printing secrets.
  local backend_image="${BACKEND_IMAGE:-}"
  local frontend_image="${FRONTEND_IMAGE:-}"
  [[ -n "${backend_image}" ]] || die "BACKEND_IMAGE is required for pull-up"
  [[ -n "${frontend_image}" ]] || die "FRONTEND_IMAGE is required for pull-up"

  # Remove prior image lines, then append (idempotent).
  if grep -qE '^(BACKEND_IMAGE|FRONTEND_IMAGE)=' "${ENV_FILE}" 2>/dev/null; then
    grep -vE '^(BACKEND_IMAGE|FRONTEND_IMAGE)=' "${ENV_FILE}" > "${ENV_FILE}.tmp"
    mv "${ENV_FILE}.tmp" "${ENV_FILE}"
  fi
  {
    echo "BACKEND_IMAGE=${backend_image}"
    echo "FRONTEND_IMAGE=${frontend_image}"
  } >> "${ENV_FILE}"
  # Re-export for this process
  export BACKEND_IMAGE="${backend_image}"
  export FRONTEND_IMAGE="${frontend_image}"
}

registry_login() {
  if [[ -n "${REGISTRY_USERNAME:-}" && -n "${REGISTRY_PASSWORD:-}" ]]; then
    local host="${REGISTRY_HOST:-ghcr.io}"
    echo "${REGISTRY_PASSWORD}" | docker login "${host}" -u "${REGISTRY_USERNAME}" --password-stdin
  else
    echo "NOTE: REGISTRY_USERNAME/PASSWORD unset — assuming images are already pullable."
  fi
}

cmd="${1:-up}"

case "${cmd}" in
  up)
    require_env
    require_tls_certs
    compose config --quiet
    echo "Bringing up ${PROJECT} (prod-like)…"
    compose up --build -d
    echo
    echo "Stack started. HTTPS UI: https://localhost/  (HTTP :80 redirects to HTTPS)"
    echo "Health:  curl -k https://localhost/health/"
    echo "Logs:    ./deploy.sh logs"
    ;;
  pull-up)
    require_env
    require_tls_certs
    write_image_env
    registry_login
    compose config --quiet
    echo "Pulling images and starting ${PROJECT} (no local build)…"
    compose pull backend celery-worker frontend asr edge
    compose up -d --no-build
    echo
    echo "Stack started from registry images (edge TLS)."
    echo "BACKEND_IMAGE=${BACKEND_IMAGE}"
    echo "FRONTEND_IMAGE=${FRONTEND_IMAGE}"
    ;;
  config)
    require_env
    require_tls_certs
    compose config --quiet
    echo "OK: ${COMPOSE_FILE} validates"
    ;;
  nginx-test)
    require_tls_certs
    docker run --rm \
      -v "${ROOT}/nginx.conf:/etc/nginx/nginx.conf:ro" \
      -v "${ROOT}/certs:/etc/nginx/certs:ro" \
      nginx:1.27-alpine nginx -t
    ;;
  down)
    require_env
    compose down
    ;;
  logs)
    require_env
    compose logs -f --tail=200
    ;;
  ps)
    require_env
    compose ps
    ;;
  db-verify)
    require_env
    bash "${ROOT}/verify-data-tier.sh"
    ;;
  support-verify)
    require_env
    bash "${ROOT}/verify-support-services.sh" "${2:---all}"
    ;;
  inference-verify)
    require_env
    bash "${ROOT}/verify-inference-tier.sh" "${2:---all}"
    ;;
  backup-stub)
    bash "${ROOT}/backup-postgres.sh" "${2:---dry-run}"
    ;;
  *)
    die "Unknown command: ${cmd} (use: up|pull-up|down|config|logs|ps|db-verify|support-verify|inference-verify|backup-stub|nginx-test)"
    ;;
esac
