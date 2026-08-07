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
#   ./deploy.sh up --cpu-inference  # also start CPU llm + embedding
#   ./deploy.sh models-pull  # download GGUF weights into ../../models
#   ./deploy.sh pull-up      # pull BACKEND_IMAGE/FRONTEND_IMAGE then up (CI)
#   ./deploy.sh db-verify    # migrate + pgvector indexes + backend connection
#   ./deploy.sh support-verify  # redis + celery worker + MinIO upload/download
#   ./deploy.sh inference-verify  # ASR + LLM gateway (profile=test) + suggest smoke
#   ./deploy.sh cpu-verify   # llm manager + embedding + backend DNS smoke
#   ./deploy.sh nginx-test   # nginx -t against nginx.conf + certs
#   ./deploy.sh backup-stub  # PostgreSQL backup stub (--dry-run by default)
#   ./deploy.sh down         # stop and remove containers
#   ./deploy.sh config       # validate compose only
#   ./deploy.sh logs         # follow logs
#   ./deploy.sh ps           # service status
set -euo pipefail

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

set_env_key() {
  local key="$1"
  local value="$2"
  local tmp="${ENV_FILE}.tmp.$$"
  if grep -qE "^${key}=" "${ENV_FILE}"; then
    awk -v k="${key}" -v v="${value}" '
      BEGIN { FS="="; OFS="=" }
      $1==k { print k, v; next }
      { print }
    ' "${ENV_FILE}" > "${tmp}"
    mv "${tmp}" "${ENV_FILE}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${ENV_FILE}"
  fi
}

enable_cpu_inference_env() {
  # Wire backend to in-compose CPU inference services.
  set_env_key MODEL_GATEWAY_MODE openai
  set_env_key OPENAI_BASE_URL http://llm:8080/v1
  set_env_key OPENAI_API_KEY local
  set_env_key OPENAI_TIMEOUT_SECONDS 300
  set_env_key LOCAL_LLM_MANAGER_URL http://llm:8070
  set_env_key EMBEDDING_MODE http
  set_env_key EMBEDDING_BASE_URL http://embedding:8090
  set_env_key EMBEDDING_MODEL intfloat/multilingual-e5-large
  set_env_key EMBEDDING_DIMENSIONS 1024
  set_env_key LLM_DEFAULT_MODEL_ID qwen2.5-1.5b-instruct
  set_env_key COMPOSE_PROFILES cpu-inference
  export COMPOSE_PROFILES=cpu-inference
  export MODEL_GATEWAY_MODE=openai
  export OPENAI_BASE_URL=http://llm:8080/v1
  export LOCAL_LLM_MANAGER_URL=http://llm:8070
  export EMBEDDING_MODE=http
  export EMBEDDING_BASE_URL=http://embedding:8090
}

compose() {
  # shellcheck disable=SC1090
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
  if [[ "${COMPOSE_PROFILES:-}" == *"cpu-inference"* ]]; then
    export COMPOSE_PROFILES
  fi
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
shift || true
cpu_inference=0
for arg in "$@"; do
  case "${arg}" in
    --cpu-inference|cpu-inference) cpu_inference=1 ;;
  esac
done

case "${cmd}" in
  models-pull)
    bash "${ROOT}/../local-inference/download-models.sh"
    ;;
  up)
    require_env
    require_tls_certs
    if [[ "${cpu_inference}" -eq 1 || "${CPU_INFERENCE:-0}" == "1" ]]; then
      bash "${ROOT}/../local-inference/download-models.sh"
      enable_cpu_inference_env
      echo "CPU inference profile enabled (llm + embedding)."
    fi
    compose config --quiet
    echo "Bringing up ${PROJECT} (prod-like)…"
    compose up --build -d
    echo
    echo "Stack started. HTTPS UI: https://localhost/  (HTTP :80 redirects to HTTPS)"
    echo "Health:  curl -k https://localhost/health/"
    echo "Logs:    ./deploy.sh logs"
    if [[ "${cpu_inference}" -eq 1 || "${CPU_INFERENCE:-0}" == "1" ]]; then
      echo "CPU verify: ./deploy.sh cpu-verify"
    fi
    ;;
  pull-up)
    require_env
    require_tls_certs
    write_image_env
    registry_login
    if [[ "${cpu_inference}" -eq 1 || "${CPU_INFERENCE:-0}" == "1" ]]; then
      bash "${ROOT}/../local-inference/download-models.sh"
      enable_cpu_inference_env
    fi
    compose config --quiet
    echo "Pulling images and starting ${PROJECT} (no local build)…"
    compose pull backend celery-worker frontend asr edge
    if [[ "${cpu_inference}" -eq 1 || "${CPU_INFERENCE:-0}" == "1" ]]; then
      compose pull llm embedding || true
    fi
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
    bash "${ROOT}/verify-support-services.sh" "${1:---all}"
    ;;
  inference-verify)
    require_env
    bash "${ROOT}/verify-inference-tier.sh" "${1:---all}"
    ;;
  cpu-verify)
    require_env
    set_env_key COMPOSE_PROFILES cpu-inference
    export COMPOSE_PROFILES=cpu-inference
    echo "=== llm /health ==="
    compose exec -T llm \
      python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8070/health', timeout=5).read().decode())" \
      || die "llm health failed"
    echo "=== embedding /health ==="
    compose exec -T embedding \
      python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=5).read().decode())" \
      || die "embedding health failed"
    echo "=== backend → inference ==="
    compose exec -T backend \
      python -c "
import os, urllib.request
print(urllib.request.urlopen(os.environ['LOCAL_LLM_MANAGER_URL'].rstrip('/') + '/health', timeout=5).status)
print(urllib.request.urlopen(os.environ['EMBEDDING_BASE_URL'].rstrip('/') + '/health', timeout=5).status)
print(urllib.request.urlopen(os.environ['OPENAI_BASE_URL'].rstrip('/') + '/models', timeout=5).status)
" || die "backend cannot reach CPU inference"
    echo "OK: CPU inference ready"
    ;;
  backup-stub)
    bash "${ROOT}/backup-postgres.sh" "${1:---dry-run}"
    ;;
  *)
    die "Unknown command: ${cmd} (use: up|pull-up|down|config|logs|ps|db-verify|support-verify|inference-verify|cpu-verify|models-pull|backup-stub|nginx-test)"
    ;;
esac
