from .forms import (
    UserCreateForm,
    ProfileCreateForm,
    UserUpdateForm,
    ProfileUpdateForm,
    CustomPasswordChangeForm,    
)

from homeApp.forms import CompanyForm
from django.views.generic import ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import redirect, render
from django.db.models import Q
from collections import defaultdict
from typing import Any

from django.utils import timezone
from django.utils.text import slugify
from django.templatetags.static import static
from allauth.account.models import EmailAddress
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from core.mixins import PermitsPositionMixin, RoleRequiredMixin
from .models import Profile
from sucursalApp.models import Shift, ShiftAssignment, Sucursal, SucursalStaff
from homeApp.models import Company

# Create your views here.




class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = "pages/usuarios/usuarios_lista.html"
    context_object_name = "users"
    paginate_by = 9

    access_scope: dict[str, Any] | None = None

    def _get_access_scope(self) -> dict[str, Any]:
        if self.access_scope is not None:
            return self.access_scope

        profile = getattr(self.request.user, "profile", None)
        is_owner = bool(profile and profile.is_owner())
        is_admin = bool(profile and profile.is_admin())

        company_rut: str | None = None
        branches_qs = Sucursal.objects.none()
        branch_ids: list[int] = []

        if profile:
            if is_owner:
                company = getattr(profile, "company", None)
                if company:
                    company_rut = company.rut
                    branches_qs = company.branches.all()
                elif profile.company_rut:
                    company_rut = Company.normalize_rut(profile.company_rut)
                    branches_qs = Sucursal.objects.filter(
                        company__rut=company_rut
                    )
                branch_ids = list(branches_qs.values_list("id", flat=True))
            elif is_admin:
                branch_ids = list(
                    SucursalStaff.objects.filter(profile=profile)
                    .values_list("sucursal_id", flat=True)
                )
                if profile.current_branch_id:
                    branch_ids.append(profile.current_branch_id)
                if branch_ids:
                    branch_ids = list(dict.fromkeys(branch_ids))
                    branches_qs = Sucursal.objects.filter(id__in=branch_ids)

        self.access_scope = {
            "profile": profile,
            "is_owner": is_owner,
            "is_admin": is_admin,
            "company_rut": company_rut,
            "branch_ids": branch_ids,
            "branches": list(branches_qs.order_by("name")),
        }
        return self.access_scope

    def get_queryset(self):
        access = self._get_access_scope()

        queryset = super().get_queryset().select_related("profile").order_by("-id")
        search_query = self.request.GET.get("search")

        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
            )

        profile = access.get("profile")
        if not profile:
            return queryset.none()

        if access["is_owner"]:
            company_rut = access.get("company_rut")
            if company_rut:
                queryset = queryset.filter(profile__company_rut=company_rut)
            else:
                queryset = queryset.none()
        elif access["is_admin"]:
            branch_ids: list[int] = access.get("branch_ids", [])
            if branch_ids:
                queryset = queryset.filter(
                    Q(profile__current_branch_id__in=branch_ids)
                    | Q(profile__sucursal_staff__sucursal_id__in=branch_ids)
                ).distinct()
            else:
                queryset = queryset.filter(id=self.request.user.id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        access = self._get_access_scope()
        branch_ids = set(access.get("branch_ids", []))
        accessible_branches: list[Sucursal] = access.get("branches", [])

        branch_lookup = {branch.id: branch for branch in accessible_branches}

        base_queryset = getattr(self, "object_list", self.get_queryset())
        filtered_users = list(
            base_queryset.select_related(
                "profile__position_FK", "profile__current_branch"
            )
        )

        user_ids = [user.id for user in filtered_users]
        verified_user_ids = set(
            EmailAddress.objects.filter(
                user_id__in=user_ids, verified=True
            ).values_list("user_id", flat=True)
        )

        cutoff_date = timezone.now() - timezone.timedelta(days=7)

        user_data_map: dict[int, dict[str, Any]] = {}
        assignments_by_user: dict[int, list[ShiftAssignment]] = defaultdict(list)
        shift_summary_cache: dict[int, list[dict[str, str]]] = {}

        assignments_qs = ShiftAssignment.objects.active().select_related(
            "shift__sucursal",
            "profile__user_FK",
            "profile__position_FK",
        ).prefetch_related("shift__schedules")

        if user_ids:
            assignments_qs = assignments_qs.filter(profile__user_FK_id__in=user_ids)

        company_rut = access.get("company_rut")
        if access["is_owner"] and company_rut:
            assignments_qs = assignments_qs.filter(
                shift__sucursal__company__rut=company_rut
            )
        elif access["is_admin"] and branch_ids:
            assignments_qs = assignments_qs.filter(shift__sucursal_id__in=branch_ids)

        for assignment in assignments_qs:
            assignments_by_user[assignment.profile.user_FK_id].append(assignment)
            if assignment.shift_id not in shift_summary_cache:
                shift_summary_cache[assignment.shift_id] = assignment.shift.get_schedule_summary()

        branch_groups_map: dict[Any, dict[str, Any]] = {}
        branchless_required = False

        for user in filtered_users:
            try:
                user_profile = user.profile
            except Profile.DoesNotExist:
                user_profile = None

            avatar_url = static("img/profile.webp")
            if user_profile is not None and getattr(user_profile, "image", None):
                image_field = user_profile.image
                if getattr(image_field, "url", None):
                    avatar_url = image_field.url

            assignments = assignments_by_user.get(user.id, [])
            branch_assignment_map: dict[Any, list[dict[str, Any]]] = defaultdict(list)
            branch_names: list[str] = []
            branch_name_set: set[str] = set()
            user_branch_ids: set[Any] = set()
            for assignment in assignments:
                shift = assignment.shift
                branch = shift.sucursal
                branch_id = branch.id if branch else None
                if branch_id is not None and branch_ids and branch_id not in branch_ids:
                    continue

                label = f"{shift.name} · {branch.name}" if branch else shift.name
                branch_name = branch.name if branch else None
                if branch_name and branch_name not in branch_name_set:
                    branch_names.append(branch_name)
                    branch_name_set.add(branch_name)

                schedule_summary = shift_summary_cache.get(shift.id, [])
                branch_assignment_map[branch_id].append(
                    {
                        "id": assignment.id,
                        "shift_id": shift.id,
                        "shift_name": shift.name,
                        "branch_id": branch_id,
                        "branch_name": branch_name,
                        "label": label,
                        "schedule": schedule_summary,
                    }
                )
                user_branch_ids.add(branch_id)

            current_branch = getattr(user_profile, "current_branch", None)
            if current_branch and (
                not branch_ids or current_branch.id in branch_ids
            ):
                if current_branch.name not in branch_name_set:
                    branch_names.append(current_branch.name)
                    branch_name_set.add(current_branch.name)
                user_branch_ids.add(current_branch.id)

            if user_profile is not None:
                for staff_membership in user_profile.sucursal_staff.select_related(
                    "sucursal"
                ):
                    branch = staff_membership.sucursal
                    if not branch:
                        continue
                    if branch_ids and branch.id not in branch_ids:
                        continue
                    user_branch_ids.add(branch.id)
                    if branch.name not in branch_name_set:
                        branch_names.append(branch.name)
                        branch_name_set.add(branch.name)

            if not user_branch_ids:
                branchless_required = True
                user_branch_ids.add(None)

            common_entry = {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
                "email": user.email,
                "profile_id": getattr(user_profile, "id", None),
                "role": (
                    user_profile.position_FK.user_position
                    if user_profile and user_profile.position_FK
                    else "Sin cargo"
                ),
                "branch": branch_names[0] if branch_names else None,
                "branches": branch_names,
                "branch_id": getattr(user_profile, "current_branch_id", None),
                "is_active": user.is_active,
                "is_verified": user.id in verified_user_ids,
                "profile_image": avatar_url,
                "last_login": user.last_login,
                "last_activity": getattr(user_profile, "last_activity", None),
                "date_joined": user.date_joined,
            }

            user_data_map[user.id] = {
                "common": common_entry,
                "branch_assignments": branch_assignment_map,
                "branch_ids": user_branch_ids,
            }

            for branch_id in user_branch_ids:
                branch_groups_map.setdefault(branch_id, {"users": []})
                branch_groups_map[branch_id]["users"].append(user.id)

        if branchless_required:
            branch_lookup[None] = None

        day_order = [
            "Lunes",
            "Martes",
            "Miércoles",
            "Jueves",
            "Viernes",
            "Sábado",
            "Domingo",
        ]
        day_sort_index = {day: index for index, day in enumerate(day_order)}

        def summarize_schedule(schedule: list[dict[str, str]]) -> str:
            if not schedule:
                return "Sin horario configurado"

            unique_ranges = {(item["start"], item["end"]) for item in schedule}
            if len(unique_ranges) == 1:
                start_time, end_time = unique_ranges.pop()
                unique_days = {item["day"] for item in schedule}
                weekday_map = set(day_order[:5])
                if unique_days == weekday_map:
                    day_label = "Lunes a Viernes"
                elif len(unique_days) == 7:
                    day_label = "Todos los días"
                else:
                    ordered_days = sorted(
                        unique_days, key=lambda day: day_sort_index.get(day, 99)
                    )
                    day_label = ", ".join(ordered_days)
                return f"{day_label} · {start_time} - {end_time}"

            return " · ".join(
                f"{item['day']} {item['start']} - {item['end']}" for item in schedule
            )

        shift_palette = [
            {
                "bg_class": "bg-sky-50",
                "ring_class": "ring-1 ring-inset ring-sky-100",
                "title_class": "text-sky-700",
                "text_class": "text-sky-700",
                "suffix_class": "text-sky-600",
                "description_class": "text-sky-600",
                "items_value_class": "text-sky-700",
                "items_border_class": "border-sky-100",
                "accent_class": "bg-sky-500",
                "detail_class": "text-sky-600",
            },
            {
                "bg_class": "bg-amber-50",
                "ring_class": "ring-1 ring-inset ring-amber-100",
                "title_class": "text-amber-700",
                "text_class": "text-amber-700",
                "suffix_class": "text-amber-600",
                "description_class": "text-amber-600",
                "items_value_class": "text-amber-700",
                "items_border_class": "border-amber-100",
                "accent_class": "bg-amber-500",
                "detail_class": "text-amber-600",
            },
            {
                "bg_class": "bg-emerald-50",
                "ring_class": "ring-1 ring-inset ring-emerald-100",
                "title_class": "text-emerald-700",
                "text_class": "text-emerald-700",
                "suffix_class": "text-emerald-600",
                "description_class": "text-emerald-600",
                "items_value_class": "text-emerald-700",
                "items_border_class": "border-emerald-100",
                "accent_class": "bg-emerald-500",
                "detail_class": "text-emerald-600",
            },
            {
                "bg_class": "bg-purple-50",
                "ring_class": "ring-1 ring-inset ring-purple-100",
                "title_class": "text-purple-700",
                "text_class": "text-purple-700",
                "suffix_class": "text-purple-600",
                "description_class": "text-purple-600",
                "items_value_class": "text-purple-700",
                "items_border_class": "border-purple-100",
                "accent_class": "bg-purple-500",
                "detail_class": "text-purple-600",
            },
        ]

        unassigned_palette = {
            "bg_class": "bg-gray-50",
            "ring_class": "ring-1 ring-inset ring-gray-200",
            "title_class": "text-gray-700",
            "text_class": "text-gray-700",
            "suffix_class": "text-gray-600",
            "description_class": "text-gray-600",
            "items_value_class": "text-gray-700",
            "items_border_class": "border-gray-200",
            "accent_class": "bg-gray-400",
            "detail_class": "text-gray-600",
        }

        branch_shift_catalog: dict[Any, dict[str, Any]] = {}
        accessible_branch_ids = [branch.id for branch in accessible_branches if branch]

        for branch in accessible_branches:
            if not branch:
                continue
            create_url = reverse(
                "shift_assignment_create",
                kwargs={"branch_pk": branch.id},
            )
            branch_shift_catalog[branch.id] = {
                "branch_id": branch.id,
                "branch_name": branch.name,
                "create_url": create_url,
                "shifts": [],
            }

        if accessible_branch_ids:
            shift_queryset = (
                Shift.objects.filter(sucursal_id__in=accessible_branch_ids)
                .select_related("sucursal")
                .prefetch_related("schedules")
                .order_by("sucursal__name", "name")
            )
        else:
            shift_queryset = Shift.objects.none()

        for shift in shift_queryset:
            branch_id = shift.sucursal_id
            branch_name = shift.sucursal.name if shift.sucursal else None
            branch_entry = branch_shift_catalog.setdefault(
                branch_id,
                {
                    "branch_id": branch_id,
                    "branch_name": branch_name,
                    "create_url": (
                        reverse(
                            "shift_assignment_create",
                            kwargs={"branch_pk": branch_id},
                        )
                        if branch_id
                        else None
                    ),
                    "shifts": [],
                },
            )
            schedule_summary = shift.get_schedule_summary()
            branch_entry["shifts"].append(
                {
                    "id": shift.id,
                    "name": shift.name,
                    "branch_name": branch_entry["branch_name"],
                    "schedule_display": summarize_schedule(schedule_summary),
                    "create_url": branch_entry["create_url"],
                }
            )

        for branch_entry in branch_shift_catalog.values():
            branch_entry["shifts"].sort(key=lambda item: item["name"].lower())

        branch_groups: list[dict[str, Any]] = []

        def build_branch_group(branch_id: Any, user_ids_for_branch: list[int]) -> dict[str, Any]:
            branch_obj = branch_lookup.get(branch_id)
            if branch_obj is None and branch_id is not None:
                branch_obj = Sucursal.objects.filter(id=branch_id).first()
                if branch_obj:
                    branch_lookup[branch_id] = branch_obj
            branch_name = branch_obj.name if branch_obj else "Sin sucursal"
            branch_slug = slugify(branch_name) or "sin-sucursal"
            tab_group_id = f"user-management-tabs-{branch_slug}"
            tab_prefix = f"tab-{branch_slug}"

            branch_user_rows: list[dict[str, Any]] = []
            branch_shift_tabs: dict[Any, dict[str, Any]] = {}
            branch_unassigned: list[dict[str, Any]] = []

            for user_id in user_ids_for_branch:
                user_info = user_data_map.get(user_id)
                if not user_info:
                    continue

                common = user_info["common"]
                assignments = user_info["branch_assignments"].get(branch_id, [])
                shift_label = (
                    assignments[0]["label"] if assignments else "Sin turno asignado"
                )

                row_entry = {
                    **common,
                    "branch": branch_name,
                    "assignments": assignments,
                    "shift_label": shift_label,
                    "profile_id": common["profile_id"],
                    "branch_id": branch_id,
                }

                branch_user_rows.append(row_entry)

                if assignments:
                    for assignment in assignments:
                        tab_slug = slugify(
                            f"{assignment['shift_id']}-{assignment['label']}"
                        ) or f"shift-{assignment['shift_id']}"
                        tab_id = f"{tab_prefix}-{tab_slug}"
                        tab_entry = branch_shift_tabs.setdefault(
                            assignment["shift_id"],
                            {
                                "id": tab_id,
                                "label": assignment["label"],
                                "sucursal_id": assignment["branch_id"],
                                "schedule": assignment.get("schedule", []),
                                "users": [],
                            },
                        )

                        tab_entry["users"].append(
                            {
                                "id": common["id"],
                                "username": common["username"],
                                "full_name": common["full_name"],
                                "email": common["email"],
                                "role": common["role"],
                                "branch": branch_name,
                                "is_active": common["is_active"],
                                "is_verified": common["is_verified"],
                                "shift_label": assignment["label"],
                                "profile_image": common["profile_image"],
                                "last_login": common["last_login"],
                                "last_activity": common["last_activity"],
                            }
                        )
                else:
                    branch_unassigned.append(row_entry)

            for tab_entry in branch_shift_tabs.values():
                tab_entry["users"].sort(key=lambda item: item["full_name"].lower())
                total_users = len(tab_entry["users"])
                active_count = sum(1 for item in tab_entry["users"] if item["is_active"])
                tab_entry["count"] = total_users
                tab_entry["active_count"] = active_count
                tab_entry["inactive_count"] = total_users - active_count

            shift_tabs = sorted(
                branch_shift_tabs.values(), key=lambda item: item["label"].lower()
            )

            if branch_unassigned:
                branch_unassigned.sort(key=lambda item: item["full_name"].lower())
                assignment_options = branch_shift_catalog.get(branch_id)
                if assignment_options is None:
                    assignment_options = {
                        "branch_id": getattr(branch_obj, "id", branch_id),
                        "branch_name": branch_name,
                        "create_url": (
                            reverse(
                                "shift_assignment_create",
                                kwargs={"branch_pk": branch_id},
                            )
                            if branch_id
                            else None
                        ),
                        "shifts": [],
                    }
                else:
                    assignment_options.setdefault("branch_id", getattr(branch_obj, "id", branch_id))
                    assignment_options.setdefault("branch_name", branch_name)
                    assignment_options.setdefault("shifts", [])
                shift_tabs.append(
                    {
                        "id": f"{tab_prefix}-sin-asignacion",
                        "label": "Sin turno asignado",
                        "count": len(branch_unassigned),
                        "active_count": sum(
                            1 for item in branch_unassigned if item["is_active"]
                        ),
                        "inactive_count": sum(
                            1 for item in branch_unassigned if not item["is_active"]
                        ),
                        "users": branch_unassigned,
                        "is_unassigned": True,
                        "assignment_options": assignment_options,
                    }
                )
            summary_cards: list[dict[str, Any]] = []

            total_branch_users = len(branch_user_rows)
            active_branch_users = sum(
                1 for item in branch_user_rows if item["is_active"]
            )
            inactive_branch_users = total_branch_users - active_branch_users
            recent_branch_users = sum(
                1
                for item in branch_user_rows
                if item["date_joined"] and item["date_joined"] >= cutoff_date
            )

            summary_cards.append(
                {
                    "title": "Usuarios registrados",
                    "value": total_branch_users,
                    "description": (
                        f"{recent_branch_users} nuevos en los últimos 7 días · "
                        f"{total_branch_users} en la vista"
                    ),
                    "bg_class": "bg-indigo-50",
                    "ring_class": "ring-1 ring-inset ring-indigo-100",
                    "title_class": "text-indigo-700",
                    "text_class": "text-indigo-700",
                    "description_class": "text-indigo-600",
                    "suffix_class": "text-indigo-600",
                    "accent_class": "bg-indigo-500",
                    "detail_class": "text-indigo-600",
                }
            )
            summary_cards.append(
                {
                    "title": "Usuarios activos",
                    "value": active_branch_users,
                    "description": (
                        f"{active_branch_users} activos visibles · "
                        f"{inactive_branch_users} inactivos"
                    ),
                    "bg_class": "bg-emerald-50",
                    "ring_class": "ring-1 ring-inset ring-emerald-100",
                    "title_class": "text-emerald-700",
                    "text_class": "text-emerald-700",
                    "description_class": "text-emerald-600",
                    "suffix_class": "text-emerald-600",
                    "accent_class": "bg-emerald-500",
                    "detail_class": "text-emerald-600",
                }
            )

            for index, shift in enumerate(shift_tabs):
                schedule_summary = shift.get("schedule", [])
                if schedule_summary:
                    description = summarize_schedule(schedule_summary)
                elif "sin-asignacion" in shift["id"]:
                    description = "Usuarios sin turno asignado"
                else:
                    description = "Sin horario configurado"

                card_entry = {
                    "title": shift["label"],
                    "value": shift.get("active_count", 0),
                    "suffix": f"de {shift.get('count', 0)} usuarios",
                    "description": description,
                    "items": [
                        {
                            "label": "Cobertura",
                            "value": shift.get("active_count", 0),
                            "total": shift.get("count", 0),
                        },
                        {
                            "label": "Inactivos",
                            "value": shift.get("inactive_count", 0),
                            "total": None,
                        },
                    ],
                }

                if "sin-asignacion" in shift["id"]:
                    card_entry.update(unassigned_palette)
                else:
                    palette = (
                        shift_palette[index % len(shift_palette)]
                        if shift_palette
                        else {}
                    )
                    card_entry.update(palette)

                summary_cards.append(card_entry)

            tab_navigation = [
                {
                    "id": f"{tab_prefix}-usuarios-todos",
                    "label": "Todos",
                    "count": total_branch_users,
                    "is_active": True,
                }
            ]
            tab_navigation.extend(
                {
                    "id": shift["id"],
                    "label": shift["label"],
                    "count": shift.get("count", 0),
                    "is_active": False,
                }
                for shift in shift_tabs
            )

            return {
                "branch": {
                    "id": getattr(branch_obj, "id", None),
                    "name": branch_name,
                },
                "tab_group_id": tab_group_id,
                "tab_navigation": tab_navigation,
                "shift_tabs": shift_tabs,
                "summary_cards": summary_cards,
                "user_rows": branch_user_rows,
            }

        ordered_branch_ids: list[Any] = [branch.id for branch in accessible_branches]
        if branchless_required:
            ordered_branch_ids.append(None)

        for branch_id in branch_groups_map.keys():
            if branch_id not in ordered_branch_ids:
                ordered_branch_ids.append(branch_id)

        for branch_id in ordered_branch_ids:
            user_ids_for_branch = branch_groups_map.get(branch_id, {}).get("users", [])
            if not user_ids_for_branch and branch_id is not None:
                continue
            group = build_branch_group(branch_id, user_ids_for_branch)
            branch_groups.append(group)

        if not branch_groups and branch_groups_map.get(None):
            branch_groups.append(
                build_branch_group(None, branch_groups_map.get(None, {}).get("users", []))
            )

        context["placeholder"] = "Buscar por usuario, nombre o apellido "
        context["search_query"] = self.request.GET.get("search", "")
        context["branch_groups"] = branch_groups
        return context

class UserShiftManagementView(LoginRequiredMixin, View):
    template_name = "pages/usuarios/gestion_turnos.html"

    def get(self, request, *args, **kwargs):
        profiles = (
            Profile.objects.select_related(
                "user_FK", "position_FK", "current_branch"
            )
            .prefetch_related(
                "shift_assignments__shift__sucursal",
                "shift_assignments__shift__schedules",
            )
            .order_by(
                "user_FK__first_name",
                "user_FK__last_name",
                "user_FK__username",
            )
        )

        request_profile = getattr(request.user, "profile", None)
        company_rut: str | None = None
        allowed_branch_ids: set[int] = set()
        allowed_branches_qs = Sucursal.objects.none()

        if request_profile is None:
            profiles = profiles.none()
        else:
            if request_profile.is_owner():
                company = getattr(request_profile, "company", None)
                if company is not None:
                    company_rut = company.rut
                    allowed_branches_qs = company.branches.all()
                elif request_profile.company_rut:
                    company_rut = Company.normalize_rut(request_profile.company_rut)
                    allowed_branches_qs = Sucursal.objects.filter(
                        company__rut=company_rut
                    )
                allowed_branch_ids = set(
                    allowed_branches_qs.values_list("id", flat=True)
                )
                if company_rut:
                    profiles = profiles.filter(company_rut=company_rut)
                else:
                    profiles = profiles.none()
            elif request_profile.is_admin():
                allowed_branch_ids = set(
                    SucursalStaff.objects.filter(profile=request_profile)
                    .values_list("sucursal_id", flat=True)
                )
                if request_profile.current_branch_id:
                    allowed_branch_ids.add(request_profile.current_branch_id)
                if allowed_branch_ids:
                    allowed_branches_qs = Sucursal.objects.filter(
                        id__in=allowed_branch_ids
                    )
                    profiles = profiles.filter(
                        Q(current_branch_id__in=allowed_branch_ids)
                        | Q(
                            shift_assignments__shift__sucursal_id__in=allowed_branch_ids
                        )
                        | Q(sucursal_staff__sucursal_id__in=allowed_branch_ids)
                    )
                else:
                    profiles = profiles.filter(pk=request_profile.pk)
            else:
                if request_profile.current_branch_id:
                    allowed_branch_ids = {request_profile.current_branch_id}
                    allowed_branches_qs = Sucursal.objects.filter(
                        id__in=allowed_branch_ids
                    )
                profiles = profiles.filter(pk=request_profile.pk)

        profiles = profiles.distinct()

        allowed_branches = list(allowed_branches_qs.order_by("name"))
        allowed_branch_ids = set(
            branch.id for branch in allowed_branches if branch is not None
        )

        employees: list[dict[str, Any]] = []
        assigned_employees = 0
        total_assignments = 0

        def summarize_schedule(schedule: list[dict[str, str]]) -> str:
            if not schedule:
                return ""
            return ", ".join(
                f"{item['day']} {item['start']}-{item['end']}" for item in schedule
            )

        for profile in profiles:
            user = profile.user_FK
            assignments: list[dict[str, Any]] = []

            for assignment in profile.shift_assignments.all():
                shift = assignment.shift
                if allowed_branch_ids and shift.sucursal_id not in allowed_branch_ids:
                    continue
                schedule_summary = shift.get_schedule_summary()
                assignments.append(
                    {
                        "id": assignment.id,
                        "shift_id": shift.id,
                        "shift_name": shift.name,
                        "branch_id": shift.sucursal_id,
                        "branch_name": shift.sucursal.name,
                        "schedule": schedule_summary,
                        "schedule_display": summarize_schedule(schedule_summary),
                        "is_active": assignment.is_current(),
                        "delete_url": reverse(
                            "shift_assignment_delete", kwargs={"pk": assignment.pk}
                        ),
                    }
                )

            assignments.sort(key=lambda item: item["shift_name"].lower())

            if assignments:
                assigned_employees += 1
                total_assignments += len(assignments)

            current_branch_name = None
            if profile.current_branch and (
                not allowed_branch_ids
                or profile.current_branch_id in allowed_branch_ids
            ):
                current_branch_name = profile.current_branch.name

            employees.append(
                {
                    "id": user.id,
                    "profile_id": profile.id,
                    "full_name": user.get_full_name() or user.username,
                    "username": user.username,
                    "email": user.email,
                    "role": (
                        profile.position_FK.user_position
                        if profile.position_FK
                        else "Sin cargo"
                    ),
                    "branch": current_branch_name,
                    "is_active": user.is_active,
                    "assignments": assignments,
                }
            )

        shift_queryset = (
            Shift.objects.select_related("sucursal")
            .prefetch_related("schedules")
            .order_by("sucursal__name", "name")
        )

        if allowed_branch_ids:
            shift_queryset = shift_queryset.filter(sucursal_id__in=allowed_branch_ids)
        elif company_rut:
            shift_queryset = shift_queryset.filter(sucursal__company__rut=company_rut)
        else:
            shift_queryset = shift_queryset.none()

        branch_map: dict[int, dict[str, Any]] = {}
        for branch in allowed_branches:
            create_url = reverse(
                "shift_assignment_create",
                kwargs={"branch_pk": branch.id},
            )
            branch_map[branch.id] = {
                "id": branch.id,
                "name": branch.name,
                "create_url": create_url,
                "shifts": [],
            }

        shift_choices: list[dict[str, Any]] = []

        for shift in shift_queryset:
            schedule_summary = shift.get_schedule_summary()
            create_url = reverse(
                "shift_assignment_create",
                kwargs={"branch_pk": shift.sucursal_id},
            )
            branch_entry = branch_map.get(shift.sucursal_id)
            if branch_entry is None:
                continue
            shift_entry = {
                "id": shift.id,
                "name": shift.name,
                "description": shift.description,
                "branch_id": shift.sucursal_id,
                "branch_name": shift.sucursal.name,
                "schedule": schedule_summary,
                "schedule_display": summarize_schedule(schedule_summary),
                "create_url": create_url,
            }
            branch_entry["shifts"].append(shift_entry)
            shift_choices.append(shift_entry)

        branches = sorted(branch_map.values(), key=lambda item: item["name"].lower())
        total_employees = len(employees)
        unassigned_employees = total_employees - assigned_employees

        context = {
            "employees": employees,
            "shift_choices": shift_choices,
            "branches": branches,
            "summary": {
                "total_employees": total_employees,
                "assigned_employees": assigned_employees,
                "unassigned_employees": unassigned_employees,
                "total_assignments": total_assignments,
            },
        }

        return render(request, self.template_name, context)


class UserCreateView(LoginRequiredMixin, PermitsPositionMixin, View):
    template_name = "pages/usuarios/registro_usuario.html"

    def get(self, request, *args, **kwargs):
        user_form = UserCreateForm()
        profile_form = ProfileCreateForm(user=request.user)

        context = {"user_form": user_form, "profile_form": profile_form}

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        user_form = UserCreateForm(request.POST)
        profile_form = ProfileCreateForm(request.POST, request.FILES, user=request.user)

        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile = profile_form.save(commit=False)
            profile.user_FK = user
            owner_profile = getattr(request.user, "profile", None)
            if owner_profile is not None:
                company = getattr(owner_profile, "company", None)
                if company is not None:
                    profile.company_rut = company.rut
                else:
                    messages.warning(
                        request,
                        "No se encontró una empresa asociada al usuario actual.",
                    )
            else:
                messages.warning(
                    request,
                    "No se encontró un perfil asociado al usuario actual.",
                )
            profile.save()
            messages.success(request, "Usuario creado con Éxito.")
            return redirect("Register")

        context = {"user_form": user_form, "profile_form": profile_form}

        return render(request, self.template_name, context)


class ProfileFormProcessingMixin:
    """Mixin to handle the shared logic for updating user/profile forms."""

    success_redirect_name = "Profile"
    success_message = "Perfil actualizado con éxito."
    error_message = None
    save_error_message = "Error al guardar la imagen"

    def get_success_url(self):
        return self.success_redirect_name

    def process_forms(self, request, user_form, profile_form, extra_context=None):
        if user_form.is_valid() and profile_form.is_valid():
            try:
                user_form.save()
                profile_form.save()
                messages.success(request, self.success_message)
            except Exception as e:
                print(e)
                print("*" * 30)
                messages.error(request, self.save_error_message)

            return redirect(self.get_success_url())

        if self.error_message:
            messages.error(request, self.error_message)

        context = {"user_form": user_form, "profile_form": profile_form}

        if extra_context:
            context.update(extra_context)

        return render(request, self.template_name, context)


class ProfileUpdateView(LoginRequiredMixin, ProfileFormProcessingMixin, View):
    template_name = "pages/perfil/perfil.html"

    def get(self, request, *args, **kwargs):
        user = request.user
        profile = user.profile
        user_form = UserUpdateForm(instance=user)
        profile_form = ProfileUpdateForm(instance=profile, user=request.user)

        context = {"user_form": user_form, "profile_form": profile_form}

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        user = request.user
        profile = user.profile
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=profile,
            user=request.user,
        )

        return self.process_forms(request, user_form, profile_form)


class ConfigurationView(LoginRequiredMixin, ProfileFormProcessingMixin, View):
    template_name = "pages/perfil/configuracion.html"
    success_redirect_name = "configuracion"
    error_message = "Corrige los errores para continuar."

    def get(self, request, *args, **kwargs):
        user = request.user
        profile = user.profile
        user_form = UserUpdateForm(instance=user)
        profile_form = ProfileUpdateForm(instance=profile, user=user)
        
        password_form = CustomPasswordChangeForm(user=user)
        password_form.helper = FormHelper()
        password_form.helper.form_tag = False

        context = {
            "user_form": user_form,
            "profile_form": profile_form,
            "password_form": password_form,
        }

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        user = request.user
        profile = user.profile
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = ProfileUpdateForm(
            request.POST, request.FILES, instance=profile, user=request.user
        )
        password_form = CustomPasswordChangeForm(user=user)
        password_form.helper = FormHelper()
        password_form.helper.form_tag = False

        extra_context = {"password_form": password_form}

        return self.process_forms(
            request,
            user_form,
            profile_form,
            extra_context=extra_context,
        )

class CompanyUpdateView(LoginRequiredMixin, RoleRequiredMixin, View):
    template_name = "pages/empresa/empresa_form.html"
    form_class = CompanyForm
    success_url = reverse_lazy("company_edit")
    allowed_roles = ["OWNER"]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        profile = getattr(request.user, "profile", None)

        if not profile or not profile.is_owner():
            return redirect(self.redirect_url)

        self.company_obj, _ = Company.objects.get_or_create(profile=profile)
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, data=None):
        return self.form_class(data=data, instance=getattr(self, "company_obj", None))

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        return render(request, self.template_name, {"form": form})

    def post(self, request, *args, **kwargs):
        old_rut = Company.normalize_rut(getattr(self.company_obj, "rut", None))
        form = self.get_form(request.POST)
        if form.is_valid():
            form.save()
            self.company_obj.refresh_from_db()
            new_rut = self.company_obj.rut
            if old_rut:
                Profile.objects.filter(company_rut=old_rut).update(
                    company_rut=new_rut
                )
            messages.success(request, "Información de la empresa actualizada con éxito.")
            return redirect(self.success_url)

        messages.error(request, "Corrige los errores para continuar.")
        return render(request, self.template_name, {"form": form})
