# Structured audit / KUMA foundation

`backend/audit/` emits one UTF-8 JSON object per security event. The envelope
contains `EventID`, RFC3339 UTC `Timestamp`, device/source fields, subject,
request correlation, result and safe metadata. Request or document bodies,
passwords, prompts and raw customer data are not written.

VI.3 category codes:

- `authentication`;
- `authorization`;
- `administration`;
- `data_security`;
- `integrations`.

## Sinks

Default development mode writes JSONL to
`backend/var/audit/audit.jsonl`. Docker stores the same file in the persistent
`audit_data` volume.

To additionally send each JSON event to a mock or KUMA-compatible HTTP
collector:

```env
AUDIT_ENABLED=true
AUDIT_SINKS=file,http
AUDIT_HTTP_COLLECTOR_URL=http://collector:8790/v1/events
AUDIT_HTTP_TIMEOUT_SECONDS=5
```

The collector must return any HTTP 2xx response. HTTP delivery failure does not
break the business request: the original event remains in the file sink and a
`hub.integrations.siem_delivery_failure` event is appended locally.

Production rotation and retention of the JSONL file must be configured by the
host/container platform for the contractual period. This package does not
delete or truncate audit files.

## Hooks

- Django login success/failure/logout signals;
- `AuditMiddleware` for HTTP 401/403;
- ModelRegistry KB/LLM parameter updates;
- `emit()` and `emit_kb_change()` for future VI.3 actions.
