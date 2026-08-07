# Local / server CPU inference (LLM + embeddings)

Для интеллектуального чата с RAG по `assistant_*` на **CPU** (Windows host или Linux Docker).

## Модели

| Роль | Модель |
|------|--------|
| LLM | `Qwen2.5-1.5B/3B-Instruct` Q4_K_M (GGUF) via llama.cpp |
| Embedding | `intfloat/multilingual-e5-large` (1024-d) |

По умолчанию на сервере стартует **1.5B** (меньше RAM). В чате можно переключить на 3B.

---

## Linux server (рекомендуется) — в пайплайне Compose

### 1. Скачать веса

```bash
chmod +x infra/local-inference/*.sh
./infra/local-inference/download-models.sh
# опционально прогреть E5 в volume:
# PREFETCH_E5=1 ./infra/local-inference/download-models.sh
```

### 2a. Dev compose (`infra/`)

```bash
cd infra
./local-inference/up-cpu.sh
./local-inference/verify-cpu.sh
```

Поднимает `llm` (:8070 manager + :8080 OpenAI) и `embedding` (:8090), прописывает в `.env`:

```text
MODEL_GATEWAY_MODE=openai
OPENAI_BASE_URL=http://llm:8080/v1
LOCAL_LLM_MANAGER_URL=http://llm:8070
EMBEDDING_MODE=http
EMBEDDING_BASE_URL=http://embedding:8090
```

### 2b. TEST prod-like (`infra/test/`)

```bash
cd infra/test
./deploy.sh models-pull
./deploy.sh up --cpu-inference
./deploy.sh cpu-verify
```

Сервисы `llm` / `embedding` в profile `cpu-inference` (internal network, без публикации наружу).

---

## Windows (host processes, без Docker для LLM)

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\local-inference\download-models.ps1
powershell -ExecutionPolicy Bypass -File .\infra\local-inference\start-llm.ps1
powershell -ExecutionPolicy Bypass -File .\infra\local-inference\start-embedding.ps1
```

В `infra/.env` для Docker backend:

```text
MODEL_GATEWAY_MODE=openai
OPENAI_BASE_URL=http://host.docker.internal:8080/v1
LOCAL_LLM_MANAGER_URL=http://host.docker.internal:8070
EMBEDDING_MODE=http
EMBEDDING_BASE_URL=http://host.docker.internal:8090
```

---

## Переключатель моделей

В чате ассистента — селект **Модель**.  
`PUT` → Django → `LOCAL_LLM_MANAGER_URL` → рестарт llama.cpp с другим GGUF.  
OpenAI alias остаётся `qwen2.5-1.5b-instruct` (совместимость с ModelGateway).

## RAM (ориентир)

| Компонент | RAM |
|-----------|-----|
| Qwen 1.5B Q4 | ~2–3 GB |
| Qwen 3B Q4 | ~3–4 GB |
| e5-large | ~2–3 GB |
| Итого комфортно | **≥12 GB** свободной RAM на хосте |

## Файлы

| Файл | Назначение |
|------|------------|
| `Dockerfile.llm` | llama.cpp + manager |
| `backend/services/embedding/Dockerfile` | E5 HTTP |
| `docker-compose.cpu.yml` | overlay profile `cpu-inference` |
| `download-models.sh` | GGUF на диск |
| `up-cpu.sh` / `verify-cpu.sh` | поднять / проверить |
