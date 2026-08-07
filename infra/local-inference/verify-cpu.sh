#!/usr/bin/env bash
# Smoke-check CPU inference services (llm + embedding).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA="$(cd "${ROOT}/.." && pwd)"
ENV_FILE="${INFRA}/.env"
PROJECT="${COMPOSE_PROJECT_NAME:-sufler}"

cd "${INFRA}"
[[ -f "${ENV_FILE}" ]] || { echo "ERROR: missing ${ENV_FILE}" >&2; exit 1; }

compose() {
  COMPOSE_PROFILES=cpu-inference docker compose \
    -p "${PROJECT}" \
    --env-file "${ENV_FILE}" \
    -f docker-compose.yml \
    -f local-inference/docker-compose.cpu.yml \
    "$@"
}

die() { echo "ERROR: $*" >&2; exit 1; }

echo "=== llm manager /health ==="
compose exec -T llm \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8070/health', timeout=5).read().decode())" \
  || die "llm manager health failed"

echo "=== llama OpenAI /v1/models ==="
compose exec -T llm \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/v1/models', timeout=5).read().decode()[:400])" \
  || die "llama /v1/models failed"

echo "=== embedding /health ==="
compose exec -T embedding \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=5).read().decode())" \
  || die "embedding health failed"

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
