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

`up-cpu.sh` / `deploy.sh` **не затирают** уже заданный `OPENAI_MODEL` (default `qwen2.5:3b` только если ключа нет).

С хоста (если порт проброшен): `ollama pull …` / `http://127.0.0.1:11434`.

Переключателя моделей в UI чата больше нет.

## Чтобы модель не выгружалась из RAM

В compose для `ollama` задано `OLLAMA_KEEP_ALIVE=-1` (держать загруженной постоянно).
После изменения пересоздайте контейнер:

```bash
docker compose --profile cpu-inference \
  -f docker-compose.yml -f local-inference/docker-compose.cpu.yml \
  up -d --force-recreate ollama
```

Первый запрос после рестарта всё равно загрузит модель в память; дальше она не уходит по таймауту.
Чтобы заранее «прогреть»: `docker compose … exec ollama ollama run llama3.2:3b ""`  
(или любой короткий `curl` на `/v1/chat/completions`).

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

Сервис `llm` (порт **8080**, образ `sufler-llm`) **удалён** из compose.
При `up` / `deploy.sh` используется `--remove-orphans` — старый `sufler-llm-1` снимается сам.

`llm_manager.py`, `start-llm*.ps1`, `Dockerfile.llm` — не используются; LLM только `ollama/ollama` (:11434).
