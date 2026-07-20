# Backend Sufler

Канонический Django backend проекта Sufler: приложение чата, модели и
административная часть, Celery и конфигурация AI-моделей. Локальный
инфраструктурный контур находится в `infra/`.

## Prerequisites

Для рекомендуемого запуска через Docker:

- Git;
- Docker Desktop с WSL 2 на Windows;
- Docker Compose v2 (`docker compose`);
- свободные host-порты `8000`, `5432`, `6379`, `9000`, `9001`;
- рекомендуется не менее 8 GB RAM.

Проверка:

```powershell
docker --version
docker compose version
docker info
```

Для запуска Django без контейнера дополнительно нужен Python 3.12. PostgreSQL,
Redis и MinIO локально устанавливать не требуется: их можно оставить в Docker.

## Основные каталоги

```text
backend/
├── manage.py
├── requirements.txt
├── Dockerfile
├── sufler/                  # settings, urls, ASGI/WSGI, Celery
├── chat/                    # Django app
├── config/                  # YAML-конфигурация, включая ModelRegistry
├── core/                    # общая backend-инфраструктура
├── services/asr/            # dev ASR-сервис
├── templates/
├── static/
└── staticfiles/

infra/
├── docker-compose.yml
├── .env.example
└── postgres/init.sql

tests/
└── acceptance/
```

## Быстрый запуск всего стека через Docker

Из корня репозитория:

```powershell
cd infra
Copy-Item .env.example .env
```

Замените в `.env` значения `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD` и
`MINIO_ROOT_PASSWORD`. Файл `.env` не должен попадать в Git.

```powershell
docker compose config
docker compose up --build -d
docker compose ps
```

Запускаются PostgreSQL/pgvector, Redis, MinIO, backend и Celery worker. Backend
ждёт healthy PostgreSQL и автоматически выполняет миграции перед `runserver`.

Основные URL:

- приложение: <http://localhost:8000/>
- текущий health URL backend: <http://localhost:8000/client-info/>
- Django admin: <http://localhost:8000/admin/>
- MinIO Console: <http://localhost:9001/>

`/client-info/` используется Docker healthcheck и должен отвечать HTTP 200.
Отдельный диагностический `/health/` в backend пока не реализован.

Логи и остановка:

```powershell
docker compose logs -f backend
docker compose logs -f celery-worker
docker compose down
```

`docker compose down` сохраняет данные. Команда `docker compose down -v`
удаляет volumes PostgreSQL, Redis и MinIO и должна использоваться только для
полного сброса локального dev-окружения.

## Django management-команды в Docker

Миграции:

```powershell
cd infra
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py showmigrations
```

Суперпользователь:

```powershell
docker compose exec backend python manage.py createsuperuser
```

Проверка Django:

```powershell
docker compose exec backend python manage.py check
```

## Локальный запуск Django без backend-контейнера

Из корня репозитория:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Без `POSTGRES_HOST` backend использует локальную SQLite-базу
`backend/db.sqlite3`. Сервер доступен на <http://127.0.0.1:8000/>.

## Celery

В Docker worker запускается автоматически. Проверка:

```powershell
cd infra
docker compose ps celery-worker
docker compose exec celery-worker celery -A sufler inspect ping --timeout=10
```

Ожидаемый ответ содержит `pong`.

Для локального worker на Windows сначала запустите Redis через Docker:

```powershell
cd infra
docker compose up -d redis
cd ..\backend
$env:CELERY_BROKER_URL = "redis://localhost:6379/0"
$env:CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
.\.venv\Scripts\celery.exe -A sufler worker --loglevel=info --pool=solo
```

## Тесты и lint

Из корня репозитория:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install pytest ruff
.\backend\.venv\Scripts\python.exe -m ruff check backend tests dashboard/app recognizer
.\backend\.venv\Scripts\python.exe -m pytest tests -v
```

Эти же проверки выполняет GitHub Actions.

## ASR

ASR запускается отдельно от Docker Compose. Зависимости и модель:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r services\asr\requirements.txt
$env:VOSK_MODEL_PATH = "C:\models\vosk-model-ru-0.22"
.\.venv\Scripts\python.exe -m services.asr.main
```

WebSocket ASR: `ws://localhost:8765`.

## Troubleshooting

### Docker Desktop Linux Engine не запущен

Ошибка содержит `dockerDesktopLinuxEngine` или `pipe ... not found`.

1. Запустите Docker Desktop.
2. Убедитесь, что включён WSL 2 engine.
3. Выполните `docker info` и повторите `docker compose up -d`.

### Порт уже занят

Ошибка содержит `Ports are not available` или `bind: Only one usage`.
Измените только host-порт в `infra/.env`, например:

```env
POSTGRES_PORT_HOST=5433
BACKEND_PORT_HOST=8001
```

Внутренние порты контейнеров менять не нужно.

### PostgreSQL не запускается

```powershell
cd infra
docker compose ps -a postgres
docker compose logs --tail=100 postgres
docker compose up -d postgres
```

Проверьте непустой `POSTGRES_PASSWORD` и доступность host-порта.

### pgvector отсутствует

```powershell
docker compose exec postgres psql -U sufler -d sufler -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker compose exec postgres psql -U sufler -d sufler -c "SELECT extversion FROM pg_extension WHERE extname='vector';"
```

`infra/postgres/init.sql` создаёт расширение автоматически только при первой
инициализации нового PostgreSQL volume.

### Redis недоступен

```powershell
docker compose ps redis
docker compose exec redis redis-cli ping
docker compose logs --tail=100 redis
```

Ожидаемый ответ Redis — `PONG`.

### Backend или Celery не запускаются

```powershell
docker compose ps -a
docker compose logs --tail=100 backend
docker compose logs --tail=100 celery-worker
docker compose up --build -d backend celery-worker
```

Backend стартует только после healthy PostgreSQL, Redis и MinIO. Повторяющиеся
`GET /client-info/` со статусом 200 в логах — нормальная работа healthcheck.

## Legacy compatibility

Старые точки входа `dashboard/app/manage.py` и `recognizer/main.py`, а также
импорты `app.settings`, `app.urls`, `app.wsgi` и `app.asgi` сохранены через
совместимые wrapper/shim-модули.
