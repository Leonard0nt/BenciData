from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List

from django.contrib.auth.models import User
from django.utils import timezone

from sucursalApp.models import ShiftAssignment


AssignmentList = List[ShiftAssignment]


def get_shift_assignments_for_users(users: Iterable[User]) -> dict[int, AssignmentList]:
    """Return a mapping of user id to upcoming shift assignments."""

    user_ids = [user.id for user in users]
    if not user_ids:
        return {}

    assignments = (
        ShiftAssignment.objects.filter(profile__user_FK__in=user_ids)
        .select_related(
            "shift__sucursal",
            "shift__schedule",
            "profile__user_FK",
            "profile__position_FK",
        )
        .order_by("shift__start")
    )

    mapping: dict[int, AssignmentList] = defaultdict(list)
    now = timezone.now()

    for assignment in assignments:
        if assignment.shift.end < now:
            continue
        user_id = assignment.profile.user_FK_id
        mapping[user_id].append(assignment)

    return mapping


def serialize_assignment(assignment: ShiftAssignment) -> dict:
    """Serialize an assignment for JSON consumption."""

    shift = assignment.shift
    profile = assignment.profile
    user = getattr(profile, "user_FK", None)
    return {
        "id": assignment.pk,
        "role": assignment.assigned_role,
        "start": shift.start.isoformat(),
        "end": shift.end.isoformat(),
        "shift_name": shift.name,
        "branch_id": shift.sucursal_id,
        "branch_name": shift.sucursal.name,
        "schedule": shift.schedule.get_day_of_week_display()
        if shift.schedule
        else None,
        "user": user.get_full_name() if user else str(profile),
    }