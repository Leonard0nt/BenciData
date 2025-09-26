from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List

from django.contrib.auth.models import User

from sucursalApp.models import ShiftAssignment


AssignmentList = List[ShiftAssignment]


def _should_include_assignment(assignment: ShiftAssignment) -> bool:
    """Return ``True`` when the assignment should be part of the schedule feed."""
    return assignment.is_active

def get_shift_assignments_for_users(users: Iterable[User]) -> dict[int, AssignmentList]:
    """Return a mapping of user id to active or upcoming shift assignments."""

    user_ids = [user.id for user in users]
    if not user_ids:
        return {}

    assignments = (
        ShiftAssignment.objects.filter(profile__user_FK__in=user_ids)
        .select_related(
            "shift__sucursal",
            "profile__user_FK",
            "profile__position_FK",
        )
        .prefetch_related("shift__schedules")
        .order_by(
            "profile__user_FK__first_name",
            "profile__user_FK__last_name",
            "shift__sucursal__name",
            "shift__name",
            "created_at",
        )
    )

    mapping: dict[int, AssignmentList] = defaultdict(list)
    today = timezone.localdate()

    for assignment in assignments:
        if not _should_include_assignment(assignment):
            continue
        user_id = assignment.profile.user_FK_id
        mapping[user_id].append(assignment)

    return mapping


def serialize_assignment(assignment: ShiftAssignment) -> dict:
    """Serialize an assignment using the new shift scheduling schema."""

    shift = assignment.shift
    profile = assignment.profile
    user = getattr(profile, "user_FK", None)
    schedule_summary = shift.get_schedule_summary()

    role = None
    if getattr(profile, "position_FK", None):
        role = profile.position_FK.user_position

    return {
        "id": assignment.pk,
        "role": role,
        "end_date": assignment.end_date.isoformat() if assignment.end_date else None,
        "is_active": assignment.is_current(),
        "shift_name": shift.name,
        "branch_id": shift.sucursal_id,
        "branch_name": shift.sucursal.name,
        "schedule": schedule_summary,
        "schedule_display": ", ".join(
            f"{item['day']} {item['start']}-{item['end']}" for item in schedule_summary
        )
        if schedule_summary
        else None,
        "user": user.get_full_name() if user else str(profile),
    }