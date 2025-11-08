from __future__ import annotations

from django.urls import reverse

from sucursalApp.models import ServiceSession


def service_session_navigation(request):
    """Expose navigation helpers for the service session entry point."""

    default_link = reverse("service_session_start")

    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return {
            "service_session_link": default_link,
            "has_active_service_session": False,
        }

    profile = getattr(user, "profile", None)
    branch_id = getattr(profile, "current_branch_id", None)

    if not branch_id:
        return {
            "service_session_link": default_link,
            "has_active_service_session": False,
        }

    latest_session_id = (
        ServiceSession.objects.filter(shift__sucursal_id=branch_id)
        .order_by("-started_at")
        .values_list("pk", flat=True)
        .first()
    )

    if latest_session_id is None:
        return {
            "service_session_link": default_link,
            "has_active_service_session": False,
        }

    return {
        "service_session_link": reverse(
            "service_session_detail", args=[latest_session_id]
        ),
        "has_active_service_session": True,
    }