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
            "has_active_service_assigned": False,
        }

    profile = getattr(user, "profile", None)
    branch_id = getattr(profile, "current_branch_id", None)

    if not branch_id:
        return {
            "service_session_link": default_link,
            "has_active_service_session": False,
            "has_active_service_assigned": False,
        }

    latest_session_id = (
        ServiceSession.objects.filter(
            shift__sucursal_id=branch_id, ended_at__isnull=True
        )
        .order_by("-started_at")
        .values_list("pk", flat=True)
        .first()
    )

    if latest_session_id is None:
        return {
            "service_session_link": default_link,
            "has_active_service_session": False,
            "has_active_service_assigned": False,
        }

    # Check if the current user is assigned to that active service
    has_assigned = False
    try:
        session = ServiceSession.objects.filter(pk=latest_session_id).prefetch_related("attendants", "shift__manager").first()
        profile = getattr(request.user, "profile", None)
        if profile and session:
            # assigned as attendant
            if session.attendants.filter(pk=getattr(profile, "pk", None)).exists():
                has_assigned = True
            # or is the manager of the shift
            elif getattr(session.shift, "manager_id", None) == getattr(profile, "pk", None):
                has_assigned = True
    except Exception:
        has_assigned = False

    return {
        "service_session_link": reverse(
            "service_session_detail", args=[latest_session_id]
        ),
        "has_active_service_session": True,
        "has_active_service_assigned": has_assigned,
    }