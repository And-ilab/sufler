# Authentication and I.4 RBAC

`backend/auth/` is a plain Python package, not an installed Django app.
`django.contrib.auth` already uses the app label `auth`; registering a second
app with that label would break Django startup.

## Portal auth context

The frontend launcher reads the current Django session and I.4 role codes from
`GET /api/auth/me/`. Anonymous users receive `authenticated: false` and an empty
`roles` list, so the launcher and protected module routes remain hidden.

## Modes

`AUTH_MODE` selects the Django authentication backend:

- `mock_ldap` — development directory from `mock_ldap.py`;
- `ldap` — optional `django-auth-ldap` production configuration stub;
- `model` — standard Django `ModelBackend`.

Default: `mock_ldap` when `DJANGO_DEBUG=true`, otherwise `model`.

### Development mock LDAP

Set:

```powershell
$env:AUTH_MODE = "mock_ldap"
$env:AUTH_MOCK_LDAP_DEFAULT_PASSWORD = "local-dev-secret"
python manage.py runserver
```

The default directory creates `dev-role-01` through `dev-role-13`, one account
per contractual I.4 role. All use the configured dev-only password.
`dev-role-01` is marked `is_staff` and can authenticate through Django admin.

The backend provisions a normal Django user and mirrors only managed groups
whose names start with `Sufler_Role_`. It never stores the mock password in
the Django user table.

Custom dev records may be supplied through `AUTH_MOCK_LDAP_USERS_JSON`:

```json
{
  "operator.one": {
    "password": "dev-only",
    "first_name": "Operator",
    "last_name": "One",
    "email": "operator.one@example.invalid",
    "department": "Contact center",
    "groups": ["Sufler_Role_04_TelephonyOperator"]
  }
}
```

Mock authentication returns no user when `DEBUG=false`, unless the explicitly
unsafe `AUTH_MOCK_LDAP_ALLOW_INSECURE=true` override is set. That override is
for isolated tests only and is forbidden in production.

## Production LDAP stub

`AUTH_MODE=ldap` loads `auth.ldap_config.build_ldap_settings()` and configures
`django_auth_ldap.backend.LDAPBackend`. The optional `django-auth-ldap` and
`python-ldap` packages are not part of the Windows dev requirements.

Required environment:

```env
AUTH_MODE=ldap
AUTH_LDAP_SERVER_URI=ldaps://ad.bank.local:636
AUTH_LDAP_BIND_DN=CN=svc-sufler,OU=Service,DC=bank,DC=local
AUTH_LDAP_BIND_PASSWORD=secret-from-vault
AUTH_LDAP_USER_SEARCH_BASE=OU=Users,DC=bank,DC=local
AUTH_LDAP_GROUP_SEARCH_BASE=OU=Groups,DC=bank,DC=local
AUTH_LDAP_USER_FILTER=(sAMAccountName=%(user)s)
AUTH_LDAP_ROLE_GROUP_MAP_JSON={"software_administrator":"BANK_SUFLER_ADMIN"}
```

The JSON map is `role_code → approved AD group name`. Production values,
LDAPS CA trust, bind account rotation and all 13 group names remain P7-03
inputs from the Customer. Secrets must come from a secret store, not Git.

## RBAC request context

`auth.middleware.RBACMiddleware` runs after Django
`AuthenticationMiddleware` and adds:

- `request.rbac_roles`;
- `request.rbac_permissions`;
- `request.rbac_tabs`.

The same values are available in templates through
`auth.context_processors.rbac`. Tabs not present in `rbac_tabs` must not be
rendered. Backend authorization remains mandatory even when a tab is hidden.

Legacy routes remain unprotected until they are explicitly migrated.
New routes must use decorators or be added to `RBAC_PATH_PERMISSIONS`.
`/client-info/` stays public for the Docker healthcheck.

## Decorators

Admin panel:

```python
from auth.decorators import admin_permission_required

@admin_permission_required
def settings_panel(request):
    ...
```

Panel tab:

```python
from auth.decorators import panel_tab_required

@panel_tab_required("ocr")
def ocr_panel(request):
    ...
```

JSON API:

```python
from auth.decorators import api_permission_required
from auth.roles import PERM_OCR_USE

@api_permission_required(PERM_OCR_USE)
def upload_document(request):
    ...
```

Denied JSON APIs return `401 authentication_required` or
`403 permission_denied` with required permissions. HTML views return plain
401/403 responses. Django superusers and contractual role 1 have all Sufler
RBAC permissions.

## Contractual roles

`roles.py` contains exactly the 13 verbatim I.4 names and stable internal role
codes. Mock group names are development placeholders only; they are not a
proposal for the Customer's AD naming.

Tests:

```powershell
.\.venv\Scripts\python.exe -m pytest ..\tests\test_rbac.py -q
```

The tests verify all 13 names, mock credentials, custom AD group mapping,
admin/tab/API allow-deny behavior and middleware path enforcement.
