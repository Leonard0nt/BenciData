from __future__ import annotations

from django.db.models import Q
from django.urls import reverse

from sucursalApp.models import ServiceSession, SucursalStaff

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

    # Fallback: if the administrator does not have a current branch set,
    # try to use the first branch where they are configured as ADMINISTRATOR.
    if branch_id is None and profile:
        branch_id = (
            SucursalStaff.objects.filter(profile=profile, role="ADMINISTRATOR")
            .values_list("sucursal_id", flat=True)
            .first()
        )

    # If the user has no branch selected, try to locate an active service where
    # they are explicitly assigned (as attendant) or are managing the shift. In
    # this case, they should still see the navigation entry pointing directly
    # to their active session.
    if branch_id is None and profile:
        assigned_session = (
            ServiceSession.objects.filter(ended_at__isnull=True)
            .filter(Q(attendants=profile) | Q(shift__manager=profile))
            .select_related("shift")
            .order_by("-started_at")
            .first()
        )

        if assigned_session:
            return {
                "service_session_link": reverse(
                    "service_session_detail", args=[assigned_session.pk]
                ),
                "has_active_service_session": True,
                "has_active_service_assigned": True,
            }

    if not branch_id:
        return {
            "service_session_link": default_link,
            "has_active_service_session": False,
            "has_active_service_assigned": False,
        }

    active_sessions = ServiceSession.objects.filter(
        shift__sucursal_id=branch_id, ended_at__isnull=True
    ).order_by("-started_at")

    latest_session_id = active_sessions.values_list("pk", flat=True).first()

    if latest_session_id is None:
        return {
            "service_session_link": default_link,
            "has_active_service_session": False,
            "has_active_service_assigned": False,
        }

    # Check if the current user is assigned to that active service
    has_assigned = False
    try:
        session = (
            active_sessions.select_related("shift__manager")
            .prefetch_related("attendants")
            .first()
        )
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