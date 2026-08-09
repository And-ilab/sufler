# Local CPU inference — Ollama + embeddings

Простой стек: **официальный контейнер Ollama** для LLM и отдельный сервис embedding.
Без кастомного llama-manager и без скриптов переключения моделей.

## Быстрый старт (dev compose)

```bash
cd infra
./local-inference/up-cpu.sh
# скачать модель (пример — лёгкая для CPU):
docker compose --profile cpu-inference \
  -f docker-compose.yml -f local-inference/docker-compose.cpu.yml \
  exec ollama ollama pull qwen2.5:3b

./local-inference/verify-cpu.sh
```

В `infra/.env` скрипт пропишет:

```text
MODEL_GATEWAY_MODE=openai
OPENAI_BASE_URL=http://ollama:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://ollama:11434
EMBEDDING_MODE=http
EMBEDDING_BASE_URL=http://embedding:8090
```

Порты на хосте: Ollama `:11434`, embedding `:8090`.

## Смена / проба моделей

Только стандартный CLI Ollama:

```bash
# список
docker compose --profile cpu-inference \
  -f docker-compose.yml -f local-inference/docker-compose.cpu.yml \
  exec ollama ollama list

# скачать другую
docker compose --profile cpu-inference \
  -f docker-compose.yml -f local-inference/docker-compose.cpu.yml \
  exec ollama ollama pull llama3.2:3b

# активировать в чате — имя в .env и рестарт backend
# OPENAI_MODEL=llama3.2:3b
docker compose restart backend
```

С хоста (если порт проброшен): `ollama pull …` / `http://127.0.0.1:11434`.

Переключателя моделей в UI чата больше нет.

## TEST prod-like

```bash
cd infra/test
# в .env:
# MODEL_GATEWAY_MODE=openai
# OPENAI_BASE_URL=http://ollama:11434/v1
# OPENAI_MODEL=qwen2.5:3b
# OLLAMA_BASE_URL=http://ollama:11434
./deploy.sh up --cpu-inference
docker compose --profile cpu-inference exec ollama ollama pull qwen2.5:3b
```

## Embedding

Сервис `embedding` (E5-large) без изменений. Веса кэшируются в `infra/models` / volume.

Опционально прогреть кэш:

```bash
# PREFETCH_E5=1 ./local-inference/download-models.sh
```

## Устаревшее

`llm_manager.py`, `start-llm*.ps1`, `Dockerfile.llm` и GGUF-каталог — **legacy**.
Новый путь — только образ `ollama/ollama`.
