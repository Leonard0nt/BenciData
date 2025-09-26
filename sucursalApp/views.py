import json
from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, QuerySet
from django.forms import HiddenInput
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.urls import reverse_lazy

from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView
from django.views.generic.edit import FormMixin

from core.mixins import RoleRequiredMixin
from homeApp.models import Company

from .forms import ShiftAssignmentForm, ShiftForm, SucursalForm
from .models import (
    Island,
    Machine,
    Shift,
    ShiftAssignment,
    Sucursal,
    SucursalStaff,
)


class OwnerCompanyMixin(LoginRequiredMixin, RoleRequiredMixin):
    allowed_roles = ["OWNER"]

    def get_company(self) -> Company | None:
        profile = getattr(self.request.user, "profile", None)
        if not profile:
            return None
        try:
            return profile.company
        except Company.DoesNotExist:
            return None

class SucursalListView(OwnerCompanyMixin, FormMixin, ListView):
    model = Sucursal
    template_name = "pages/sucursales/sucursal_list.html"
    context_object_name = "sucursales"
    form_class = SucursalForm
    success_url = reverse_lazy("sucursal_list")

    def get_queryset(self) -> QuerySet[Sucursal]:
        company = self.get_company()
        if company is None:
            return Sucursal.objects.none()
        return (
            Sucursal.objects.filter(company=company)
            .select_related("company")
            .prefetch_related(
                Prefetch(
                    "branch_islands",
                    queryset=Island.objects.prefetch_related(
                        Prefetch(
                            "machines",
                            queryset=Machine.objects.prefetch_related("nozzles"),
                        )
                    ),
                ),
                Prefetch(
                    "staff",
                    queryset=SucursalStaff.objects.select_related(
                        "profile__user_FK", "profile__position_FK"
                    ),
                ),
            )
        )


class SucursalCreateView(OwnerCompanyMixin, CreateView):
    form_class = SucursalForm
    template_name = "pages/sucursales/sucursal_form.html"
    success_url = reverse_lazy("sucursal_list")

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.get_company()
        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.setdefault("islands", [])
        return context

class SucursalUpdateView(OwnerCompanyMixin, UpdateView):
    model = Sucursal
    form_class = SucursalForm
    template_name = "pages/sucursales/sucursal_form.html"
    success_url = reverse_lazy("sucursal_list")

    def get_queryset(self) -> QuerySet[Sucursal]:
        company = self.get_company()
        if company is None:
            return Sucursal.objects.none()
        return (
            Sucursal.objects.filter(company=company)
            .select_related("company")
            .prefetch_related(
                Prefetch(
                    "branch_islands",
                    queryset=Island.objects.prefetch_related(
                        Prefetch(
                            "machines",
                            queryset=Machine.objects.prefetch_related("nozzles"),
                        )
                    ),
                ),
                Prefetch(
                    "staff",
                    queryset=SucursalStaff.objects.select_related(
                        "profile__user_FK", "profile__position_FK"
                    ),
                ),
            )
        )

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.get_company()
        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        if self.object:
            context["islands"] = (
                self.object.branch_islands.order_by("number")
                .prefetch_related(
                    Prefetch(
                        "machines",
                        queryset=Machine.objects.order_by("number").prefetch_related(
                            "nozzles"
                        ),
                    )
                )
            )
        else:
            context.setdefault("islands", [])
        return context


class BranchAccessMixin(OwnerCompanyMixin):
    branch_url_kwarg = "branch_pk"

    def get_branch_queryset(self):
        company = self.get_company()
        if company is None:
            return Sucursal.objects.none()
        return Sucursal.objects.filter(company=company)

    def get_sucursal(self) -> Sucursal:
        queryset = self.get_branch_queryset()
        return get_object_or_404(queryset, pk=self.kwargs.get(self.branch_url_kwarg))

class BranchShiftManagementView(BranchAccessMixin, View):
    template_name = "pages/sucursales/sucursal_turnos.html"

    def get(self, request, *args, **kwargs):
        branch = self.get_sucursal()
        context = self.get_context_data(branch)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        branch = self.get_sucursal()
        action = request.POST.get("action")

        if action == "create_shift":
            prefix = request.POST.get("form_prefix") or "new-shift"
            shift_form = self.get_shift_form(branch, data=request.POST, prefix=prefix)
            assignment_form = self.get_assignment_form(branch, prefix="new-assignment")
            if shift_form.is_valid():
                shift_form.save()
                messages.success(request, "Turno creado con éxito.")
                return redirect(self.get_success_url(branch))
            context = self.get_context_data(
                branch,
                shift_form=shift_form,
                assignment_form=assignment_form,
            )
            return render(request, self.template_name, context)

        if action == "update_shift":
            shift = get_object_or_404(branch.shifts.all(), pk=request.POST.get("shift_id"))
            prefix = request.POST.get("form_prefix") or f"shift-{shift.pk}"
            shift_form = self.get_shift_form(
                branch,
                data=request.POST,
                instance=shift,
                prefix=prefix,
            )
            if shift_form.is_valid():
                shift_form.save()
                messages.success(request, "Turno actualizado correctamente.")
                return redirect(self.get_success_url(branch))
            assignment_form = self.get_assignment_form(branch, prefix="new-assignment")
            context = self.get_context_data(
                branch,
                assignment_form=assignment_form,
                shift_overrides={shift.pk: shift_form},
            )
            return render(request, self.template_name, context)

        if action == "delete_shift":
            shift = get_object_or_404(branch.shifts.all(), pk=request.POST.get("shift_id"))
            shift.delete()
            messages.success(request, "Turno eliminado correctamente.")
            return redirect(self.get_success_url(branch))

        if action == "create_assignment":
            prefix = request.POST.get("form_prefix") or "new-assignment"
            assignment_form = self.get_assignment_form(
                branch,
                data=request.POST,
                prefix=prefix,
            )
            shift_form = self.get_shift_form(branch, prefix="new-shift")
            if assignment_form.is_valid():
                assignment_form.save()
                messages.success(request, "Asignación creada con éxito.")
                return redirect(self.get_success_url(branch))
            context = self.get_context_data(
                branch,
                shift_form=shift_form,
                assignment_form=assignment_form,
            )
            return render(request, self.template_name, context)

        if action == "update_assignment":
            assignment = get_object_or_404(
                branch.shift_assignments.select_related("shift"),
                pk=request.POST.get("assignment_id"),
            )
            prefix = request.POST.get("form_prefix") or f"assignment-{assignment.pk}"
            assignment_form = self.get_assignment_form(
                branch,
                data=request.POST,
                instance=assignment,
                prefix=prefix,
            )
            if assignment_form.is_valid():
                assignment_form.save()
                messages.success(request, "Asignación actualizada correctamente.")
                return redirect(self.get_success_url(branch))
            shift_form = self.get_shift_form(branch, prefix="new-shift")
            context = self.get_context_data(
                branch,
                shift_form=shift_form,
                assignment_form=self.get_assignment_form(
                    branch, prefix="new-assignment"
                ),
                assignment_overrides={assignment.pk: assignment_form},
            )
            return render(request, self.template_name, context)

        if action == "delete_assignment":
            assignment = get_object_or_404(
                branch.shift_assignments.select_related("shift"),
                pk=request.POST.get("assignment_id"),
            )
            assignment.delete()
            messages.success(request, "Asignación eliminada correctamente.")
            return redirect(self.get_success_url(branch))

        messages.error(request, "Acción no válida para la gestión de turnos.")
        return redirect(self.get_success_url(branch))

    def get_shift_form(
        self,
        branch: Sucursal,
        *,
        data: Dict[str, Any] | None = None,
        instance: Shift | None = None,
        prefix: str | None = None,
    ) -> ShiftForm:
        company = self.get_company()
        args = (data,) if data is not None else ()
        kwargs: Dict[str, Any] = {"company": company, "instance": instance}
        if prefix is not None:
            kwargs["prefix"] = prefix
        form = ShiftForm(*args, **kwargs)
        form.fields["sucursal"].initial = branch
        form.fields["sucursal"].widget = HiddenInput()
        return form

    def get_assignment_form(
        self,
        branch: Sucursal,
        *,
        data: Dict[str, Any] | None = None,
        instance: ShiftAssignment | None = None,
        prefix: str | None = None,
    ) -> ShiftAssignmentForm:
        company = self.get_company()
        args = (data,) if data is not None else ()
        kwargs: Dict[str, Any] = {
            "company": company,
            "sucursal": branch,
            "instance": instance,
        }
        if prefix is not None:
            kwargs["prefix"] = prefix
        form = ShiftAssignmentForm(*args, **kwargs)
        form.fields["sucursal"].initial = branch
        form.fields["sucursal"].widget = HiddenInput()
        return form

    def build_shift_rows(
        self,
        branch: Sucursal,
        *,
        shift_overrides: Dict[int, ShiftForm] | None = None,
        assignment_overrides: Dict[int, ShiftAssignmentForm] | None = None,
    ) -> tuple[list[dict[str, Any]], Dict[str, int]]:
        shift_overrides = shift_overrides or {}
        assignment_overrides = assignment_overrides or {}

        shifts = (
            branch.shifts.all()
            .prefetch_related(
                "schedules",
                Prefetch(
                    "assignments",
                    queryset=ShiftAssignment.objects.select_related(
                        "profile__user_FK",
                        "profile__position_FK",
                    ),
                ),
            )
            .order_by("name")
        )

        rows: list[dict[str, Any]] = []
        summary = {"total_assignments": 0, "active_assignments": 0, "inactive_assignments": 0}

        for shift in shifts:
            schedule_summary = shift.get_schedule_summary()
            shift_form = shift_overrides.get(shift.pk)
            if shift_form is None:
                shift_form = self.get_shift_form(
                    branch,
                    instance=shift,
                    prefix=f"shift-{shift.pk}",
                )

            assignments_data: list[dict[str, Any]] = []
            active_count = 0

            for assignment in shift.assignments.all():
                profile_user = getattr(assignment.profile, "user_FK", None)
                full_name = None
                email = None
                if profile_user is not None:
                    full_name = profile_user.get_full_name() or profile_user.username
                    email = profile_user.email
                else:
                    full_name = str(assignment.profile)

                assignment_form = assignment_overrides.get(assignment.pk)
                if assignment_form is None:
                    assignment_form = self.get_assignment_form(
                        branch,
                        instance=assignment,
                        prefix=f"assignment-{assignment.pk}",
                    )

                is_active = assignment.is_current()
                if is_active:
                    active_count += 1

                assignments_data.append(
                    {
                        "object": assignment,
                        "form": assignment_form,
                        "profile_name": full_name,
                        "email": email,
                        "role": getattr(
                            getattr(assignment.profile, "position_FK", None),
                            "user_position",
                            "",
                        ),
                        "is_active": is_active,
                        "form_prefix": assignment_form.prefix,
                    }
                )

            summary["total_assignments"] += len(assignments_data)
            summary["active_assignments"] += active_count

            rows.append(
                {
                    "shift": shift,
                    "form": shift_form,
                    "schedule": schedule_summary,
                    "assignments": assignments_data,
                    "active_assignments": active_count,
                    "total_assignments": len(assignments_data),
                }
            )

        summary["inactive_assignments"] = (
            summary["total_assignments"] - summary["active_assignments"]
        )

        return rows, summary

    def get_context_data(
        self,
        branch: Sucursal,
        *,
        shift_form: ShiftForm | None = None,
        assignment_form: ShiftAssignmentForm | None = None,
        shift_overrides: Dict[int, ShiftForm] | None = None,
        assignment_overrides: Dict[int, ShiftAssignmentForm] | None = None,
    ) -> Dict[str, Any]:
        if shift_form is None:
            shift_form = self.get_shift_form(branch, prefix="new-shift")
        if assignment_form is None:
            assignment_form = self.get_assignment_form(branch, prefix="new-assignment")

        shift_rows, summary = self.build_shift_rows(
            branch,
            shift_overrides=shift_overrides,
            assignment_overrides=assignment_overrides,
        )

        profile_field = assignment_form.fields.get("profile")
        available_profiles = profile_field.queryset.count() if profile_field else 0

        context = {
            "branch": branch,
            "shift_form": shift_form,
            "assignment_form": assignment_form,
            "shift_rows": shift_rows,
            "summary": {
                "total_shifts": len(shift_rows),
                "total_assignments": summary["total_assignments"],
                "active_assignments": summary["active_assignments"],
                "inactive_assignments": summary["inactive_assignments"],
                "available_profiles": available_profiles,
            },
        }
        return context

    def get_success_url(self, branch: Sucursal) -> str:
        return reverse(
            "branch_shift_management",
            kwargs={self.branch_url_kwarg: branch.pk},
        )



class ShiftAccessMixin(OwnerCompanyMixin):
    def get_shift_queryset(self):
        company = self.get_company()
        if company is None:
            return Shift.objects.none()
        return Shift.objects.filter(sucursal__company=company)

    def get_shift(self) -> Shift:
        queryset = self.get_shift_queryset()
        return get_object_or_404(queryset, pk=self.kwargs.get("pk"))


class JSONPayloadMixin:
    def get_request_data(self) -> Dict[str, Any]:
        content_type = self.request.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                body = self.request.body.decode("utf-8") or "{}"
                return json.loads(body)
            except json.JSONDecodeError:
                return {}
        if self.request.method in {"POST", "PUT", "PATCH"}:
            return self.request.POST.copy()
        return {}


class ShiftListView(BranchAccessMixin, JSONPayloadMixin, View):
    def get(self, request, *args, **kwargs):
        sucursal = self.get_sucursal()
        shifts = (
            sucursal.shifts.all()
            .prefetch_related(
                "schedules",
                Prefetch(
                    "assignments",
                    queryset=ShiftAssignment.objects.select_related(
                        "profile__user_FK"
                    ),
                ),
            )
            .order_by("name")
        )

        data = []
        for shift in shifts:
            schedules = shift.get_schedule_summary()
            assignments = []
            for assignment in shift.assignments.all():
                profile_user = getattr(assignment.profile, "user_FK", None)
                assignments.append(
                    {
                        "id": assignment.id,
                        "profile": str(assignment.profile),
                        "user": profile_user.get_full_name()
                        if profile_user
                        else None,
                        "is_active": assignment.is_current(),
                    }
                )
            data.append(
                {
                    "id": shift.id,
                    "name": shift.name,
                    "description": shift.description,
                    "sucursal": shift.sucursal_id,
                    "schedules": schedules,
                    "assignments": assignments,
                }
            )

        return JsonResponse({"results": data})


class ShiftCreateView(BranchAccessMixin, JSONPayloadMixin, View):
    def post(self, request, *args, **kwargs):
        sucursal = self.get_sucursal()
        data = self.get_request_data()
        if hasattr(data, "mutable") and not data.mutable:
            data = data.copy()
        if "sucursal" not in data:
            data["sucursal"] = str(sucursal.pk)

        form = ShiftForm(data, company=self.get_company())
        if form.is_valid():
            shift = form.save()
            return JsonResponse(
                {
                    "id": shift.id,
                    "name": shift.name,
                    "description": shift.description,
                    "schedules": shift.get_schedule_summary(),
                },
                status=201,
            )
        return JsonResponse({"errors": form.errors}, status=400)


class ShiftUpdateView(ShiftAccessMixin, JSONPayloadMixin, View):
    def put(self, request, *args, **kwargs):
        shift = self.get_shift()
        data = self.get_request_data()
        form = ShiftForm(data, instance=shift, company=self.get_company())
        if form.is_valid():
            shift = form.save()
            return JsonResponse(
                {
                    "id": shift.id,
                    "name": shift.name,
                    "description": shift.description,
                    "schedules": shift.get_schedule_summary(),
                }
            )
        return JsonResponse({"errors": form.errors}, status=400)

    def post(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)


class ShiftDeleteView(ShiftAccessMixin, View):
    def delete(self, request, *args, **kwargs):
        shift = self.get_shift()
        shift.delete()
        return JsonResponse({}, status=204)

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


class ShiftAssignmentListView(BranchAccessMixin, View):
    def get(self, request, *args, **kwargs):
        sucursal = self.get_sucursal()
        assignments = (
            sucursal.shift_assignments.select_related(
                "shift", "profile__user_FK", "profile__position_FK"
            )
            .order_by("-is_active", "-created_at")
        )
        data = []
        for assignment in assignments:
            profile_user = getattr(assignment.profile, "user_FK", None)
            data.append(
                {
                    "id": assignment.id,
                    "shift": assignment.shift_id,
                    "shift_name": assignment.shift.name,
                    "profile": assignment.profile_id,
                    "profile_name": profile_user.get_full_name()
                    if profile_user
                    else str(assignment.profile),
                    "is_active": assignment.is_current(),
                }
            )
        return JsonResponse({"results": data})


class ShiftAssignmentCreateView(BranchAccessMixin, JSONPayloadMixin, View):
    def post(self, request, *args, **kwargs):
        sucursal = self.get_sucursal()
        data = self.get_request_data()
        if hasattr(data, "mutable") and not data.mutable:
            data = data.copy()
        data.setdefault("sucursal", str(sucursal.pk))
        form = ShiftAssignmentForm(
            data,
            company=self.get_company(),
            sucursal=sucursal,
        )
        if form.is_valid():
            assignment = form.save()
            return JsonResponse(
                {
                    "id": assignment.id,
                    "shift": assignment.shift_id,
                    "profile": assignment.profile_id,
                    "is_active": assignment.is_current(),
                },
                status=201,
            )
        return JsonResponse({"errors": form.errors}, status=400)


class ShiftAssignmentUpdateView(ShiftAccessMixin, JSONPayloadMixin, View):
    assignment_model = ShiftAssignment

    def get_assignment(self) -> ShiftAssignment:
        queryset = self.assignment_model.objects.filter(
            shift__in=self.get_shift_queryset()
        )
        return get_object_or_404(queryset, pk=self.kwargs.get("pk"))

    def put(self, request, *args, **kwargs):
        assignment = self.get_assignment()
        data = self.get_request_data()
        form = ShiftAssignmentForm(
            data,
            instance=assignment,
            company=self.get_company(),
            sucursal=assignment.sucursal,
        )
        if form.is_valid():
            assignment = form.save()
            return JsonResponse(
                {
                    "id": assignment.id,
                    "shift": assignment.shift_id,
                    "profile": assignment.profile_id,
                    "is_active": assignment.is_current(),
                }
            )
        return JsonResponse({"errors": form.errors}, status=400)

    def post(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)


class ShiftAssignmentDeleteView(ShiftAssignmentUpdateView):
    def delete(self, request, *args, **kwargs):
        assignment = self.get_assignment()
        assignment.delete()
        return JsonResponse({}, status=204)

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)