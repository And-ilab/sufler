#!/usr/bin/env bash
# Smoke-check CPU inference services (llm + embedding).
#
# Dev (from infra/):
#   ./local-inference/verify-cpu.sh
#
# TEST prod-like (from infra/test/ via deploy.sh cpu-verify):
#   COMPOSE_PROJECT_NAME=sufler-test \
#   COMPOSE_FILE=docker-compose.prod-like.yml \
#   COMPOSE_DIR=.../infra/test \
#   ./verify-cpu.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA="$(cd "${ROOT}/.." && pwd)"
COMPOSE_DIR="${COMPOSE_DIR:-${INFRA}}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
ENV_FILE="${ENV_FILE:-${COMPOSE_DIR}/.env}"
PROJECT="${COMPOSE_PROJECT_NAME:-sufler}"
WAIT_SECONDS="${VERIFY_WAIT_SECONDS:-300}"
EXTRA_COMPOSE_FILE="${EXTRA_COMPOSE_FILE:-}"

cd "${COMPOSE_DIR}"
[[ -f "${ENV_FILE}" ]] || { echo "ERROR: missing ${ENV_FILE}" >&2; exit 1; }

compose() {
  local args=(
    -p "${PROJECT}"
    --env-file "${ENV_FILE}"
    -f "${COMPOSE_FILE}"
  )
  if [[ -n "${EXTRA_COMPOSE_FILE}" ]]; then
    args+=(-f "${EXTRA_COMPOSE_FILE}")
  elif [[ "${COMPOSE_FILE}" == "docker-compose.yml" && -f "${COMPOSE_DIR}/local-inference/docker-compose.cpu.yml" ]]; then
    args+=(-f local-inference/docker-compose.cpu.yml)
  elif [[ "${COMPOSE_FILE}" == docker-compose.yml && -f "${ROOT}/docker-compose.cpu.yml" && "${COMPOSE_DIR}" == "${INFRA}" ]]; then
    args+=(-f local-inference/docker-compose.cpu.yml)
  fi
  COMPOSE_PROFILES=cpu-inference docker compose "${args[@]}" "$@"
}

die() { echo "ERROR: $*" >&2; exit 1; }

wait_http() {
  local service="$1"
  local url="$2"
  local label="$3"
  local deadline=$((SECONDS + WAIT_SECONDS))
  echo "Waiting for ${label} (${url}, timeout ${WAIT_SECONDS}s)…"
  while (( SECONDS < deadline )); do
    if compose exec -T "${service}" \
      python -c "import urllib.request; urllib.request.urlopen('${url}', timeout=3).read()" \
      >/dev/null 2>&1; then
      echo "OK: ${label} is up"
      return 0
    fi
    compose ps "${service}" || true
    sleep 5
  done
  echo "---- ${service} logs (tail) ----" >&2
  compose logs --tail=80 "${service}" >&2 || true
  die "${label} not ready within ${WAIT_SECONDS}s"
}

wait_llama_ready() {
  local deadline=$((SECONDS + WAIT_SECONDS))
  echo "Waiting for manager ready=true and OpenAI /v1/models 200…"
  while (( SECONDS < deadline )); do
    local body
    body="$(compose exec -T llm \
      python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8070/health', timeout=5).read().decode())" \
      2>/dev/null || true)"
    local openai_ok=0
    if compose exec -T llm \
      python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8080/v1/models', timeout=5); assert r.status==200" \
      >/dev/null 2>&1; then
      openai_ok=1
    fi
    # Prefer explicit ready flag; also accept active_model_id + not switching.
    if [[ "${openai_ok}" -eq 1 ]] && {
      [[ "${body}" == *'"ready": true'* ]] || [[ "${body}" == *'"ready":true'* ]] ||
      { [[ "${body}" == *'"active_model_id": "'* ]] && [[ "${body}" != *'"active_model_id": null'* ]] && [[ "${body}" != *'"switching": true'* ]]; }
    }; then
      echo "${body}"
      return 0
    fi
    if [[ -n "${body}" ]]; then
      echo "  still starting (openai_ok=${openai_ok}): $(echo "${body}" | head -c 240)…"
    else
      echo "  manager health not ready yet…"
    fi
    sleep 5
  done
  echo "---- llm logs (tail) ----" >&2
  compose logs --tail=120 llm >&2 || true
  die "llama did not become ready within ${WAIT_SECONDS}s"
}

echo "=== container status ==="
compose ps llm embedding backend || true

echo "=== llm manager /health ==="
wait_http llm "http://127.0.0.1:8070/health" "llm manager"
wait_llama_ready

echo "=== llama OpenAI /v1/models ==="
compose exec -T llm \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/v1/models', timeout=5).read().decode()[:400])" \
  || die "llama /v1/models failed"

echo "=== embedding /health ==="
wait_http embedding "http://127.0.0.1:8090/health" "embedding"

echo "=== backend → llm / embedding DNS ==="
compose exec -T backend \
  python -c "
import os, urllib.request
mgr = os.environ.get('LOCAL_LLM_MANAGER_URL', 'http://llm:8070').rstrip('/')
emb = os.environ.get('EMBEDDING_BASE_URL', 'http://embedding:8090').rstrip('/')
print('manager', urllib.request.urlopen(mgr + '/health', timeout=5).status)
print('embedding', urllib.request.urlopen(emb + '/health', timeout=5).status)
oa = os.environ.get('OPENAI_BASE_URL', 'http://llm:8080/v1').rstrip('/')
print('openai', urllib.request.urlopen(oa + '/models', timeout=5).status)
" || die "backend cannot reach inference services"

echo "OK: CPU inference pipeline ready"
