#!/usr/bin/env bash
# Bring up Sufler + CPU inference (llm + embedding) on Linux.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA="$(cd "${ROOT}/.." && pwd)"
ENV_FILE="${INFRA}/.env"

cd "${INFRA}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: missing ${ENV_FILE}" >&2
  exit 1
fi

# Ensure GGUFs exist (idempotent).
bash "${ROOT}/download-models.sh"

# Point backend at in-compose services (Docker DNS).
set_env() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" "${ENV_FILE}"; then
    # portable-ish in-place replace
    tmp="${ENV_FILE}.tmp.$$"
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

set_env MODEL_GATEWAY_MODE openai
set_env OPENAI_BASE_URL http://llm:8080/v1
set_env OPENAI_API_KEY local
set_env OPENAI_TIMEOUT_SECONDS "${OPENAI_TIMEOUT_SECONDS:-300}"
set_env LOCAL_LLM_MANAGER_URL http://llm:8070
set_env EMBEDDING_MODE http
set_env EMBEDDING_BASE_URL http://embedding:8090
set_env EMBEDDING_MODEL intfloat/multilingual-e5-large
set_env EMBEDDING_DIMENSIONS 1024
set_env LLM_DEFAULT_MODEL_ID "${LLM_DEFAULT_MODEL_ID:-qwen2.5-1.5b-instruct}"
set_env COMPOSE_PROFILES cpu-inference

export COMPOSE_PROFILES=cpu-inference
docker compose \
  --env-file "${ENV_FILE}" \
  -f docker-compose.yml \
  -f local-inference/docker-compose.cpu.yml \
  up -d --build "$@"

echo
echo "CPU inference stack started."
echo "  LLM manager:  http://llm:8070  (host :${LLM_MANAGER_PORT_HOST:-8070})"
echo "  LLM OpenAI:   http://llm:8080/v1"
echo "  Embedding:    http://embedding:8090"
echo "Verify: ./local-inference/verify-cpu.sh"
