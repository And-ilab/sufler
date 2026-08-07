#!/usr/bin/env bash
# Download CPU GGUF models (+ optional E5 prefetch) for Linux / Docker volumes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${ROOT}/../.." && pwd)"
MODELS_DIR="${MODELS_DIR:-${REPO}/models}"
LLM_DIR="${MODELS_DIR}/llm"
HF_CACHE="${MODELS_DIR}/hf-cache"
PREFETCH_E5="${PREFETCH_E5:-0}"

mkdir -p "${LLM_DIR}" "${HF_CACHE}"

download() {
  local url="$1"
  local out="$2"
  if [[ -f "${out}" ]]; then
    echo "OK (exists): ${out}"
    return 0
  fi
  echo "Downloading → ${out}"
  curl -fL --retry 3 --retry-delay 2 -o "${out}.partial" "${url}"
  mv "${out}.partial" "${out}"
}

download \
  "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf" \
  "${LLM_DIR}/qwen2.5-1.5b-instruct-q4_k_m.gguf"

download \
  "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf" \
  "${LLM_DIR}/qwen2.5-3b-instruct-q4_k_m.gguf"

if [[ "${PREFETCH_E5}" == "1" ]]; then
  echo "Prefetching intfloat/multilingual-e5-large into ${HF_CACHE}"
  docker run --rm \
    -e HF_HOME=/cache \
    -e TRANSFORMERS_CACHE=/cache \
    -v "${HF_CACHE}:/cache" \
    python:3.12-slim-bookworm \
    bash -lc '
      pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.6.0 \
        && pip install -q sentence-transformers==3.4.1 \
        && python -c "from sentence_transformers import SentenceTransformer as S; m=S(\"intfloat/multilingual-e5-large\"); print(\"dim\", len(m.encode([\"query: test\"], normalize_embeddings=True)[0]))"
    '
fi

echo "Done. Mount ${MODELS_DIR} into llm/embedding containers."
echo "  GGUF: ${LLM_DIR}"
echo "  HF:   ${HF_CACHE}"
