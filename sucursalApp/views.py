from typing import Any, Dict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, QuerySet
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from core.mixins import RoleRequiredMixin
from homeApp.models import Company

from .forms import SucursalForm
from .models import Sucursal


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


class SucursalListView(OwnerCompanyMixin, ListView):
    model = Sucursal
    template_name = "pages/sucursales/sucursal_list.html"
    context_object_name = "sucursales"

    def get_queryset(self) -> QuerySet[Sucursal]:
        company = self.get_company()
        if company is None:
            return Sucursal.objects.none()
        return (
            Sucursal.objects.filter(company=company)
            .select_related("company")
            .prefetch_related(Prefetch("users"))
        )


class SucursalCreateView(OwnerCompanyMixin, CreateView):
    form_class = SucursalForm
    template_name = "pages/sucursales/sucursal_form.html"
    success_url = reverse_lazy("sucursal_list")

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.get_company()
        return kwargs


class SucursalUpdateView(OwnerCompanyMixin, UpdateView):
    model = Sucursal
    form_class = SucursalForm
    template_name = "pages/sucursales/sucursal_form.html"
    success_url = reverse_lazy("sucursal_list")

    def get_queryset(self) -> QuerySet[Sucursal]:
        company = self.get_company()
        if company is None:
            return Sucursal.objects.none()
        return Sucursal.objects.filter(company=company).select_related("company").prefetch_related(
            Prefetch("users")
        )

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.get_company()
        return kwargs