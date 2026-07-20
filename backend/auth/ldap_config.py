"""Optional django-auth-ldap production configuration.

Imported only when ``AUTH_MODE=ldap``. The optional ``django-auth-ldap`` and
``python-ldap`` packages are intentionally not required by the Windows dev
setup.
"""

from __future__ import annotations

import json
import os
from typing import Any

from django.core.exceptions import ImproperlyConfigured


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ImproperlyConfigured(
            f"{name} is required when AUTH_MODE=ldap"
        )
    return value


def build_ldap_settings() -> dict[str, Any]:
    try:
        import ldap
        from django_auth_ldap.config import (
            LDAPSearch,
            NestedActiveDirectoryGroupType,
        )
    except ImportError as exc:
        raise ImproperlyConfigured(
            "AUTH_MODE=ldap requires django-auth-ldap and python-ldap"
        ) from exc

    server_uri = _required("AUTH_LDAP_SERVER_URI")
    user_base = _required("AUTH_LDAP_USER_SEARCH_BASE")
    group_base = _required("AUTH_LDAP_GROUP_SEARCH_BASE")
    bind_dn = _required("AUTH_LDAP_BIND_DN")
    bind_password = _required("AUTH_LDAP_BIND_PASSWORD")
    user_filter = os.getenv(
        "AUTH_LDAP_USER_FILTER",
        "(sAMAccountName=%(user)s)",
    )
    role_group_map_raw = os.getenv("AUTH_LDAP_ROLE_GROUP_MAP_JSON", "{}")
    try:
        role_group_map = json.loads(role_group_map_raw)
    except json.JSONDecodeError as exc:
        raise ImproperlyConfigured(
            "AUTH_LDAP_ROLE_GROUP_MAP_JSON is invalid JSON"
        ) from exc
    if not isinstance(role_group_map, dict):
        raise ImproperlyConfigured(
            "AUTH_LDAP_ROLE_GROUP_MAP_JSON must be an object"
        )

    return {
        "AUTH_LDAP_SERVER_URI": server_uri,
        "AUTH_LDAP_BIND_DN": bind_dn,
        "AUTH_LDAP_BIND_PASSWORD": bind_password,
        "AUTH_LDAP_USER_SEARCH": LDAPSearch(
            user_base,
            ldap.SCOPE_SUBTREE,
            user_filter,
        ),
        "AUTH_LDAP_GROUP_SEARCH": LDAPSearch(
            group_base,
            ldap.SCOPE_SUBTREE,
            "(objectClass=group)",
        ),
        "AUTH_LDAP_GROUP_TYPE": NestedActiveDirectoryGroupType(),
        "AUTH_LDAP_USER_ATTR_MAP": {
            "first_name": "givenName",
            "last_name": "sn",
            "email": "mail",
        },
        "AUTH_LDAP_ALWAYS_UPDATE_USER": True,
        "AUTH_LDAP_MIRROR_GROUPS": True,
        "AUTH_LDAP_CACHE_TIMEOUT": int(
            os.getenv("AUTH_LDAP_CACHE_TIMEOUT", "300")
        ),
        "AUTH_LDAP_CONNECTION_OPTIONS": {
            ldap.OPT_REFERRALS: 0,
            ldap.OPT_X_TLS_REQUIRE_CERT: ldap.OPT_X_TLS_DEMAND,
        },
        "AUTH_LDAP_ROLE_GROUP_MAP": role_group_map,
    }
