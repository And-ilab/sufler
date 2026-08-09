#!/usr/bin/env bash
# Bring up Sufler + Ollama + embedding on Linux (no custom LLM scripts).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA="$(cd "${ROOT}/.." && pwd)"
ENV_FILE="${INFRA}/.env"
DEFAULT_MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"

cd "${INFRA}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: missing ${ENV_FILE}" >&2
  exit 1
fi

set_env() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" "${ENV_FILE}"; then
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
set_env OPENAI_BASE_URL http://ollama:11434/v1
set_env OPENAI_API_KEY ollama
set_env OPENAI_MODEL "${DEFAULT_MODEL}"
set_env OLLAMA_BASE_URL http://ollama:11434
set_env OPENAI_TIMEOUT_SECONDS "${OPENAI_TIMEOUT_SECONDS:-600}"
set_env EMBEDDING_MODE http
set_env EMBEDDING_BASE_URL http://embedding:8090
set_env EMBEDDING_MODEL intfloat/multilingual-e5-large
set_env EMBEDDING_DIMENSIONS 1024
set_env EMBEDDING_TIMEOUT_SECONDS "${EMBEDDING_TIMEOUT_SECONDS:-180}"
set_env ASSISTANT_MAX_TOKENS "${ASSISTANT_MAX_TOKENS:-256}"
set_env COMPOSE_PROFILES cpu-inference

export COMPOSE_PROFILES=cpu-inference
# --remove-orphans drops legacy sufler-llm-1 (old llama.cpp on :8080)
docker compose \
  --env-file "${ENV_FILE}" \
  -f docker-compose.yml \
  -f local-inference/docker-compose.cpu.yml \
  up -d --remove-orphans "$@"

echo
echo "Stack started. Pull / switch models with plain Ollama CLI:"
echo "  docker compose --profile cpu-inference -f docker-compose.yml -f local-inference/docker-compose.cpu.yml exec ollama ollama pull ${DEFAULT_MODEL}"
echo "  docker compose --profile cpu-inference -f docker-compose.yml -f local-inference/docker-compose.cpu.yml exec ollama ollama list"
echo
echo "Active chat model = OPENAI_MODEL in .env (default ${DEFAULT_MODEL})."
echo "After changing OPENAI_MODEL: docker compose restart backend"
echo "Verify: ./local-inference/verify-cpu.sh"
