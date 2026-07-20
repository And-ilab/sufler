"""Small session-auth context API consumed by the portal launcher."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from auth.roles import role_codes_for_user, tabs_for_user


@require_GET
def auth_context(request: HttpRequest) -> JsonResponse:
    authenticated = bool(
        getattr(request.user, "is_authenticated", False)
    )
    return JsonResponse(
        {
            "authenticated": authenticated,
            "username": (
                request.user.get_username() if authenticated else None
            ),
            "roles": sorted(role_codes_for_user(request.user)),
            "tabs": list(tabs_for_user(request.user)),
        }
    )
