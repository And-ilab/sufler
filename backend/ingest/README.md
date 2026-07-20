# SUZ → RAG ingest

`ingest` receives the Model B webhook defined in
`docs/integration/suz-bitrix-rag/tz-bitrix-rag-sufler.md`.

## Endpoint

```text
POST /api/v1/knowledge/events
Content-Type: application/json
X-Sufler-Event-Id: <event_id>
X-Sufler-Signature: HMAC-SHA256(raw_body, shared_secret)
```

Set `SUZ_WEBHOOK_HMAC_SECRET` in `infra/.env`. An empty secret disables HMAC
only for local mock development.

Responses follow INT-07:

- `202 {"status":"accepted","outcome":"queued", ...}` when the event is queued;
- `400 {"error":"validation","fields":[...]}` for invalid input;
- `401 {"error":"auth"}` for an invalid HMAC;
- `503 {"error":"temporary"}` when the Redis broker is unavailable.

Repeated `event_id` values are accepted by the broker but resolved
idempotently by the worker.

## INT-01..05 pipeline

1. Validate the full SUZ payload and checksum.
2. Enqueue the Celery chain `ingest.reindex_kb -> qu.qu_retrain`.
3. Normalize whitespace in `body_plain`.
4. Split text using frozen `kb_cc_production` settings from ModelRegistry
   (currently 512 tokens with 100-token overlap).
5. Produce deterministic 1024-dimensional dev embeddings.
6. Upsert chunks into the PostgreSQL `cc_production` table. Its `embedding`
   column is `pgvector` and has a cosine HNSW index.
7. Run `qu_retrain` only after `reindex_kb` commits successfully.

The event mapping is:

- **INT-01:** publish and index a current KC article;
- **INT-02:** record a draft without changing production;
- **INT-03:** soft-delete an unpublished article;
- **INT-04:** hard-delete all article vectors;
- **INT-05:** replace the previous article version without duplicate chunks.

`event_id` prevents repeated delivery from running twice. The unique
`article_id + version_id + chunk_index` constraint and article replacement
make re-ingest idempotent. A new event with an unchanged article checksum
updates metadata/version without recalculating embeddings.

The deterministic embedder is a development adapter, not a production model.
Replace it with the approved on-prem embedding runtime before production
sign-off; the vector schema already matches the 1024 dimensions of the
current `multilingual-e5-large` dev profile.

## Verification

From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py migrate
.\backend\.venv\Scripts\python.exe -m pytest tests\test_ingest_webhook.py -v
```

With Docker:

```powershell
cd infra
docker compose up --build -d
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py check
docker compose exec postgres psql -U sufler -d sufler -c "\d cc_production"
```
