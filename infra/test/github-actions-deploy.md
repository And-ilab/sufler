# GitHub Actions → bank TEST VM deploy

Automated path: [`.github/workflows/deploy-test.yml`](../../.github/workflows/deploy-test.yml)

**Ops companion (step-by-step deploy, rollback, verify, FAQ):** [`docs/runbooks/deploy-test.md`](../../docs/runbooks/deploy-test.md)

Triggers:

| Event | Behavior |
| --- | --- |
| `workflow_dispatch` | Manual run from Actions UI (supports **dry_run**) |
| Push tag `v*` or `test-*` | Build → push registry → SSH `pull-up` on TEST VM |

Local Compose stays separate: [`docker-compose.prod-like.yml`](./docker-compose.prod-like.yml) + [`deploy.sh`](./deploy.sh).

## Pipeline (non–dry-run)

1. Build `backend` (`backend/Dockerfile`) and `frontend` (`frontend/Dockerfile.prod`)
2. Tag + push to registry (default **GHCR**: `ghcr.io/<owner>/<repo>/backend:<tag>`)
3. SSH to TEST VM → `infra/test/deploy.sh pull-up` with `BACKEND_IMAGE` / `FRONTEND_IMAGE`

App secrets (Postgres, LDAP, SUZ HMAC, …) stay in **`infra/test/.env` on the VM** — not in GitHub Actions.

## Required GitHub configuration

### Repository secrets

| Secret | Required | Purpose |
| --- | --- | --- |
| `TEST_SSH_HOST` | yes (for SSH deploy) | TEST VM hostname or IP (BelVPN / jump reachability from runner) |
| `TEST_SSH_USER` | yes | SSH user with Docker rights on the VM |
| `TEST_SSH_KEY` | yes | Private key (PEM). Public key in `~/.ssh/authorized_keys` on VM |
| `TEST_SSH_PORT` | no | SSH port (workflow default `22` if unset) |
| `TEST_DEPLOY_PATH` | yes | Absolute path to repo checkout on VM (e.g. `/opt/sufler`) |
| `REGISTRY_USERNAME` | for private registry / GHCR | Registry login user (GHCR: GitHub username or `token`) |
| `REGISTRY_PASSWORD` | for private registry / GHCR | Registry password or PAT with `write:packages` / `read:packages` |

When using **GHCR** with `GITHUB_TOKEN` on the Actions side, push can use the job token. The **TEST VM** still needs `REGISTRY_USERNAME` + `REGISTRY_PASSWORD` (PAT with `read:packages`) so `docker pull` works for private packages — set the same secrets for remote login in `deploy.sh pull-up`.

### Repository variables (optional)

| Variable | Default / notes |
| --- | --- |
| `REGISTRY_HOST` | `ghcr.io` |
| `IMAGE_PREFIX` | `ghcr.io/<owner>/<repo>` (workflow derives if unset) |

## Dry-run (no push, no SSH)

Actions → **Deploy TEST** → Run workflow → set **dry_run = true**.

Dry-run will:

- build both images locally on the runner
- print the **secret names** checklist (never values)
- **skip** registry login/push and SSH

Use this to verify the workflow file and build steps before wiring bank SSH.

## One-time VM prep

```bash
# On TEST VM (after BelVPN / ДИТ access)
sudo mkdir -p /opt/sufler && sudo chown "$USER" /opt/sufler
cd /opt/sufler
git clone <repo-url> .   # or sync release tree
cd infra/test
cp .env.example .env
# fill vault secrets — never commit
chmod +x deploy.sh
./deploy.sh config
```

Ensure the Actions SSH key can reach the host and the user can run `docker` / `docker compose`.

## Manual dispatch inputs

| Input | Meaning |
| --- | --- |
| `dry_run` | `true` = build + secrets checklist only |
| `image_tag` | Override tag (default: dispatch → `manual-<sha>`; tag push → tag name) |

## Security notes

- Do **not** store `infra/test/.env` contents in GitHub secrets (use VM vault / local `.env`).
- Do **not** commit `TEST_SSH_KEY` or registry PATs.
- Prefer a deploy-only SSH user with least privilege (Docker group, no root login if policy allows).
- Air-gapped bank runners: point `REGISTRY_HOST` / `IMAGE_PREFIX` at the internal registry and mirror base images offline.
