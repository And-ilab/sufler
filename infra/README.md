# Infrastructure

Локальный инфраструктурный контур Sufler запускается через Docker Compose:

- PostgreSQL 16 с расширением pgvector;
- Redis;
- MinIO;
- Django backend;
- Celery worker.

## Подготовка

Нужен Docker Desktop с поддержкой `docker compose`.

```powershell
cd infra
Copy-Item .env.example .env
```

Перед запуском замените значения паролей и `DJANGO_SECRET_KEY` в `.env`.
Файл `.env` игнорируется Git; `.env.example` содержит только шаблон.

## Запуск

```powershell
docker compose config
docker compose up --build -d
docker compose ps
```

Backend запускает миграции перед web-сервером и стартует только после
успешного healthcheck PostgreSQL. Redis и MinIO также должны перейти в
состояние `healthy`; Celery worker ожидает готовый backend.

Логи:

```powershell
docker compose logs -f backend
docker compose logs -f celery-worker
```

Остановка:

```powershell
docker compose down
```

Для удаления локальных данных PostgreSQL, Redis и MinIO:

```powershell
docker compose down -v
```

## Порты

- `8000` (`BACKEND_PORT_HOST`) — Django: <http://localhost:8000/>
- `5432` (`POSTGRES_PORT_HOST`) — PostgreSQL/pgvector
- `6379` (`REDIS_PORT_HOST`) — Redis
- `9000` (`MINIO_API_PORT_HOST`) — MinIO S3 API
- `9001` (`MINIO_CONSOLE_PORT_HOST`) — MinIO Console:
  <http://localhost:9001/>

Celery worker не публикует порт наружу. Все host-порты можно изменить в
`infra/.env`; внутренние имена сервисов и порты остаются фиксированными.

## Healthchecks

- PostgreSQL — `pg_isready`;
- Redis — `redis-cli ping`;
- MinIO — `/minio/health/live`;
- backend — HTTP `GET /client-info/`;
- Celery worker — `celery inspect ping`.

Расширение `vector` создаётся при первой инициализации PostgreSQL скриптом
`postgres/init.sql`. Данные сервисов хранятся в именованных Docker volumes.
