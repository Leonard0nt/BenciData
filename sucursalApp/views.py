import json
from typing import Any, Dict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, QuerySet
from django.http import JsonResponse
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
                        "start_date": assignment.start_date.isoformat()
                        if assignment.start_date
                        else None,
                        "end_date": assignment.end_date.isoformat()
                        if assignment.end_date
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
            .order_by("-is_active", "-start_date")
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
                    "start_date": assignment.start_date.isoformat()
                    if assignment.start_date
                    else None,
                    "end_date": assignment.end_date.isoformat()
                    if assignment.end_date
                    else None,
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
                    "start_date": assignment.start_date.isoformat()
                    if assignment.start_date
                    else None,
                    "end_date": assignment.end_date.isoformat()
                    if assignment.end_date
                    else None,
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
                    "start_date": assignment.start_date.isoformat()
                    if assignment.start_date
                    else None,
                    "end_date": assignment.end_date.isoformat()
                    if assignment.end_date
                    else None,
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