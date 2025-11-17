from typing import Any, Dict, List
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import DecimalField, F, Prefetch, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from django.views import View

from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from django.views.generic.edit import FormMixin

from core.mixins import RoleRequiredMixin
from homeApp.models import Company
from .forms import (
    BranchProductForm,
    FuelInventoryForm,
    IslandForm,
    MachineForm,
    NozzleForm,
    ServiceSessionCreditSaleForm,
    ServiceSessionFuelLoadForm,
    ServiceSessionProductLoadForm,
    ServiceSessionProductSaleForm,
    ServiceSessionProductSaleItemFormSet,
    ServiceSessionWithdrawalForm,
    ShiftForm,
    ServiceSessionForm,
    SucursalForm,
)
from .models import (
    BranchProduct,
    FuelInventory,
    Island,
    Machine,
    Nozzle,
    ServiceSessionCreditSale,
    ServiceSessionFuelLoad,
    ServiceSessionProductLoad,
    ServiceSessionProductSale,
    ServiceSessionProductSaleItem,
    ServiceSessionWithdrawal,
    Shift,
    ServiceSession,
    Sucursal,
    SucursalStaff,
)


def redirect_to_modal(branch_id: int, modal_name: str) -> HttpResponseRedirect:
    """Build a redirect response to reopen a specific modal on the branch page."""

    base_url = reverse("sucursal_update", args=[branch_id])
    query = urlencode({"modal": modal_name})
    return HttpResponseRedirect(f"{base_url}?{query}")


def get_admin_branch_ids(profile) -> List[int]:
    """Return the branch IDs managed by the given administrator profile."""

    if not profile or not getattr(profile, "is_admin", None) or not profile.is_admin():
        return []

    branch_ids = set(
        SucursalStaff.objects.filter(
            profile=profile, role="ADMINISTRATOR"
        ).values_list("sucursal_id", flat=True)
    )

    current_branch_id = getattr(profile, "current_branch_id", None)
    if current_branch_id:
        branch_ids.add(current_branch_id)

    branch_ids.discard(None)
    return list(branch_ids)


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
    def get_managed_branch_ids(self) -> List[int]:
        if hasattr(self, "_managed_branch_ids"):
            return self._managed_branch_ids  # type: ignore[attr-defined]

        company = self.get_company()
        if company is not None:
            branch_ids = list(company.branches.values_list("pk", flat=True))
        else:
            profile = getattr(self.request.user, "profile", None)
            branch_ids = get_admin_branch_ids(profile)

        # Ensure unique values and ignore None entries
        branch_ids = list(dict.fromkeys(branch_ids))
        self._managed_branch_ids = branch_ids  # type: ignore[attr-defined]
        return branch_ids

    def get_managed_branches_queryset(self) -> QuerySet[Sucursal]:
        branch_ids = self.get_managed_branch_ids()
        if not branch_ids:
            return Sucursal.objects.none()
        return Sucursal.objects.filter(pk__in=branch_ids)
class SucursalListView(OwnerCompanyMixin, FormMixin, ListView):
    model = Sucursal
    template_name = "pages/sucursales/sucursal_list.html"
    context_object_name = "sucursales"
    form_class = SucursalForm
    success_url = reverse_lazy("sucursal_list")
    allowed_roles = ["OWNER", "ADMINISTRATOR"]

    def dispatch(self, request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        if profile and profile.has_role("ADMINISTRATOR"):
            branch_ids = self.get_managed_branch_ids()
            if branch_ids:
                current_branch_id = getattr(profile, "current_branch_id", None)
                if current_branch_id in branch_ids:
                    branch_id = current_branch_id
                else:
                    branch_id = branch_ids[0]
                return redirect("sucursal_update", pk=branch_id)
        return super().dispatch(request, *args, **kwargs)
        
    def get_queryset(self) -> QuerySet[Sucursal]:
        branch_ids = self.get_managed_branch_ids()
        if not branch_ids:
            return Sucursal.objects.none()
        return (
            Sucursal.objects.filter(pk__in=branch_ids)
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
                    "fuel_inventories",
                    queryset=FuelInventory.objects.order_by("code"),
                ),
                Prefetch(
                    "products",
                    queryset=BranchProduct.objects.order_by("product_type", "arrival_date"),
                ),
                Prefetch(
                    "staff",
                    queryset=SucursalStaff.objects.select_related(
                        "profile__user_FK", "profile__position_FK"
                    ),
                ),
                Prefetch(
                    "shifts",
                    queryset=Shift.objects.select_related(
                        "manager__user_FK", "manager__position_FK"
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
        context.setdefault("fuel_inventories", [])
        return context

class SucursalUpdateView(OwnerCompanyMixin, UpdateView):
    model = Sucursal
    form_class = SucursalForm
    template_name = "pages/sucursales/sucursal_form.html"
    success_url = reverse_lazy("sucursal_list")
    allowed_roles = ["OWNER", "ADMINISTRATOR"]

    def get_queryset(self) -> QuerySet[Sucursal]:
        branch_ids = self.get_managed_branch_ids()
        if not branch_ids:
            return Sucursal.objects.none()
        return (
            Sucursal.objects.filter(pk__in=branch_ids)
            .select_related("company")
            .prefetch_related(
                Prefetch(
                    "branch_islands",
                    queryset=Island.objects.order_by("number").prefetch_related(
                        Prefetch(
                            "machines",
                            queryset=Machine.objects.order_by("number").prefetch_related(
                                "nozzles"
                            ),
                        )
                    ),
                ),
                Prefetch(
                    "fuel_inventories",
                    queryset=FuelInventory.objects.order_by("code"),
                ),
                Prefetch(
                    "products",
                    queryset=BranchProduct.objects.order_by("product_type", "arrival_date"),
                ),
                Prefetch(
                    "staff",
                    queryset=SucursalStaff.objects.select_related(
                        "profile__user_FK", "profile__position_FK"
                    ),
                ),
                Prefetch(
                    "shifts",
                    queryset=Shift.objects.order_by("start_time")
                    .select_related("manager__user_FK", "manager__position_FK")
                    .prefetch_related("attendants__user_FK", "attendants__position_FK"),
                ),
            )
        )

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        company = self.get_company()
        if company is None and getattr(self, "object", None):
            company = self.object.company
        kwargs["company"] = company
        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        if self.object:
            islands = list(self.object.branch_islands.all())
            context["islands"] = islands
            context["island_create_form"] = IslandForm(
                initial={"sucursal": self.object}, auto_id="new-island_%s"
            )
            context["island_create_url"] = reverse(
                "sucursal_island_create", args=[self.object.pk]
            )
            shift_queryset = (
                self.object.shifts.select_related(
                    "manager__user_FK", "manager__position_FK"
                )
                .prefetch_related("attendants__user_FK", "attendants__position_FK")
                .order_by("start_time")
            )
            shifts = list(shift_queryset)
            for shift in shifts:
                shift.update_form = ShiftForm(
                    instance=shift,
                    sucursal=self.object,
                    auto_id=f"edit-shift-{shift.pk}_%s",
                )
            context["shifts"] = shifts
            profile = getattr(self.request.user, "profile", None)
            can_manage_shifts = bool(
                self.request.user.is_superuser
                or (profile and profile.has_role("ADMINISTRATOR"))
                or (profile and profile.has_role("OWNER"))
            )
            context["can_manage_shifts"] = can_manage_shifts
            if can_manage_shifts:
                context["shift_create_form"] = ShiftForm(
                    initial={"sucursal": self.object},
                    sucursal=self.object,
                    auto_id="new-shift_%s",
                )
                context["shift_create_url"] = reverse(
                    "sucursal_shift_create", args=[self.object.pk]
                )
            fuel_inventories = list(self.object.fuel_inventories.all())
            for inventory in fuel_inventories:
                inventory.update_form = FuelInventoryForm(
                    instance=inventory, auto_id=f"edit-inventory-{inventory.pk}_%s"
                )
            context["fuel_inventories"] = fuel_inventories
            context["fuel_inventory_create_form"] = FuelInventoryForm(
                initial={"sucursal": self.object}, auto_id="new-inventory_%s"
            )
            context["fuel_inventory_create_url"] = reverse(
                "sucursal_fuel_inventory_create", args=[self.object.pk]
            )
            products = list(self.object.products.all())
            for product in products:
                product.update_form = BranchProductForm(
                    instance=product, auto_id=f"edit-product-{product.pk}_%s"
                )
            context["products"] = products
            context["product_create_form"] = BranchProductForm(
                initial={"sucursal": self.object}, auto_id="new-product_%s"
            )
            context["product_create_url"] = reverse(
                "sucursal_product_create", args=[self.object.pk]
            )
            branch_credit_sales = (
                ServiceSessionCreditSale.objects.filter(
                    service_session__shift__sucursal=self.object
                )
                .select_related(
                    "service_session__shift",
                    "responsible__user_FK",
                    "fuel_inventory",
                )
                .order_by("-created_at")
            )
            context["branch_credit_sales"] = branch_credit_sales
            context["branch_credit_sales_count"] = branch_credit_sales.count()
            context["branch_credit_sales_total"] = (
                branch_credit_sales.aggregate(
                    total=Coalesce(
                        Sum("amount"),
                        Value(0),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                )["total"]
                or 0
            )
            for island in islands:
                island.update_form = IslandForm(
                    instance=island, auto_id=f"edit-island-{island.pk}_%s"
                )
                island.machine_create_form = MachineForm(
                    initial={"island": island}, auto_id=f"new-machine-{island.pk}_%s"
                )
                machines = list(island.machines.all())
                for machine in machines:
                    machine.update_form = MachineForm(
                        instance=machine, auto_id=f"edit-machine-{machine.pk}_%s"
                    )
                    machine.nozzle_create_form = NozzleForm(
                        auto_id=f"new-nozzle-{machine.pk}_%s",
                        initial={"machine": machine},
                    )
                    nozzles = list(machine.nozzles.all())
                    for nozzle in nozzles:
                        nozzle.update_form = NozzleForm(
                            instance=nozzle, auto_id=f"edit-nozzle-{nozzle.pk}_%s"
                        )
                    machine.nozzles_list = nozzles
                island.machines_list = machines
        else:
            context.setdefault("islands", [])
            context.setdefault("shifts", [])
            context.setdefault("products", [])
            context.setdefault("branch_credit_sales", [])
            context.setdefault("branch_credit_sales_count", 0)
            context.setdefault("branch_credit_sales_total", 0)
        context.setdefault("can_manage_shifts", False)
        if not context.get("active_modal"):
            requested_modal = self.request.GET.get("modal")
            if requested_modal:
                context["active_modal"] = requested_modal
        context.setdefault("active_modal", None)
        return context

    def get_success_url(self) -> str:
        if self.object:
            return reverse("sucursal_update", args=[self.object.pk])
        return super().get_success_url()

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        scope = request.POST.get("form_scope")
        if scope == "shift-update":
            return self._handle_shift_update(request)
        if scope == "fuel-inventory-update":
            return self._handle_fuel_inventory_update(request)
        if scope == "product-update":
            return self._handle_product_update(request)
        if scope == "island-update":
            return self._handle_island_update(request)
        if scope == "machine-update":
            return self._handle_machine_update(request)
        if scope == "nozzle-update":
            return self._handle_nozzle_update(request)
        return super().post(request, *args, **kwargs)

    def _get_branch_form(self) -> SucursalForm:
        form_kwargs = self.get_form_kwargs()
        form_kwargs.update({"data": None, "files": None, "instance": self.object})
        return self.form_class(**form_kwargs)

    def _render_with_inline_form(self, *, modal_name: str) -> Any:
        context = self.get_context_data(form=self._get_branch_form())
        context["active_modal"] = modal_name
        return self.render_to_response(context)

    def _handle_shift_update(self, request) -> Any:
        shift_id = request.POST.get("object_id")
        shift = get_object_or_404(self.object.shifts.all(), pk=shift_id)
        form = ShiftForm(
            request.POST,
            instance=shift,
            sucursal=self.object,
            auto_id=f"edit-shift-{shift.pk}_%s",
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Turno actualizado correctamente.")
            return redirect("sucursal_update", pk=self.object.pk)
        response = self._render_with_inline_form(
            modal_name=f"shift-edit-{shift.pk}"
        )
        for shift_context in response.context_data.get("shifts", []):  # type: ignore[attr-defined]
            if shift_context.pk == shift.pk:
                shift_context.update_form = form
                break
        return response

    def _handle_fuel_inventory_update(self, request) -> Any:
        inventory_id = request.POST.get("object_id")
        inventory = get_object_or_404(
            self.object.fuel_inventories.all(), pk=inventory_id
        )
        form = FuelInventoryForm(
            request.POST,
            instance=inventory,
            auto_id=f"edit-inventory-{inventory.pk}_%s",
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Inventario actualizado correctamente.")
            return redirect("sucursal_update", pk=self.object.pk)
        response = self._render_with_inline_form(
            modal_name=f"fuel-inventory-edit-{inventory.pk}"
        )
        for inventory_context in response.context_data.get("fuel_inventories", []):  # type: ignore[attr-defined]
            if inventory_context.pk == inventory.pk:
                inventory_context.update_form = form
                break
        return response

    def _handle_product_update(self, request) -> Any:
        product_id = request.POST.get("object_id")
        product = get_object_or_404(self.object.products.all(), pk=product_id)
        form = BranchProductForm(
            request.POST,
            instance=product,
            auto_id=f"edit-product-{product.pk}_%s",
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Producto actualizado correctamente.")
            return redirect("sucursal_update", pk=self.object.pk)
        response = self._render_with_inline_form(
            modal_name=f"product-edit-{product.pk}"
        )
        for product_context in response.context_data.get("products", []):  # type: ignore[attr-defined]
            if product_context.pk == product.pk:
                product_context.update_form = form
                break
        return response

    def _handle_island_update(self, request) -> Any:
        island_id = request.POST.get("object_id")
        island = get_object_or_404(self.object.branch_islands.all(), pk=island_id)
        form = IslandForm(
            request.POST,
            instance=island,
            auto_id=f"edit-island-{island.pk}_%s",
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Isla actualizada correctamente.")
            return redirect("sucursal_update", pk=self.object.pk)
        response = self._render_with_inline_form(
            modal_name=f"island-edit-{island.pk}"
        )
        for island_context in response.context_data.get("islands", []):  # type: ignore[attr-defined]
            if island_context.pk == island.pk:
                island_context.update_form = form
                break
        return response

    def _handle_machine_update(self, request) -> Any:
        machine_id = request.POST.get("object_id")
        machine = get_object_or_404(
            Machine.objects.filter(island__sucursal=self.object), pk=machine_id
        )
        form = MachineForm(
            request.POST,
            instance=machine,
            auto_id=f"edit-machine-{machine.pk}_%s",
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Máquina actualizada correctamente.")
            return redirect("sucursal_update", pk=self.object.pk)
        response = self._render_with_inline_form(
            modal_name=f"machine-edit-{machine.pk}"
        )
        for island_context in response.context_data.get("islands", []):  # type: ignore[attr-defined]
            machines = getattr(island_context, "machines_list", [])
            for machine_context in machines:
                if machine_context.pk == machine.pk:
                    machine_context.update_form = form
                    break
        return response

    def _handle_nozzle_update(self, request) -> Any:
        nozzle_id = request.POST.get("object_id")
        nozzle = get_object_or_404(
            Nozzle.objects.filter(machine__island__sucursal=self.object), pk=nozzle_id
        )
        form = NozzleForm(
            request.POST,
            instance=nozzle,
            auto_id=f"edit-nozzle-{nozzle.pk}_%s",
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Pistola actualizada correctamente.")
            return redirect("sucursal_update", pk=self.object.pk)
        response = self._render_with_inline_form(
            modal_name=f"nozzle-edit-{nozzle.pk}"
        )
        for island_context in response.context_data.get("islands", []):  # type: ignore[attr-defined]
            machines = getattr(island_context, "machines_list", [])
            for machine_context in machines:
                nozzles = getattr(machine_context, "nozzles_list", [])
                for nozzle_context in nozzles:
                    if nozzle_context.pk == nozzle.pk:
                        nozzle_context.update_form = form
                        break
        return response

class SucursalDeleteView(OwnerCompanyMixin, DeleteView):
    model = Sucursal
    success_url = reverse_lazy("sucursal_list")

    def get_queryset(self) -> QuerySet[Sucursal]:
        company = self.get_company()
        if company is None:
            return Sucursal.objects.none()
        return Sucursal.objects.filter(company=company)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        sucursal_name = self.object.name
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f"Sucursal '{sucursal_name}' eliminada con éxito.")
        return response

class BranchAccessMixin(OwnerCompanyMixin):
    branch_url_kwarg = "branch_pk"
    allowed_roles = ["OWNER", "ADMINISTRATOR"]

    def get_branch_queryset(self):
        return self.get_managed_branches_queryset()

    def get_sucursal(self) -> Sucursal:
        queryset = self.get_branch_queryset()
        return get_object_or_404(queryset, pk=self.kwargs.get(self.branch_url_kwarg))
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return redirect(self.redirect_url)

class ShiftAccessMixin(OwnerCompanyMixin):
    model = Shift
    allowed_roles = ["OWNER", "ADMINISTRATOR"]
    def get_queryset(self) -> QuerySet[Shift]:
        branch_ids = self.get_managed_branch_ids()
        if not branch_ids:
            return Shift.objects.none()
        return (
            Shift.objects.filter(sucursal_id__in=branch_ids)
            .select_related("sucursal", "manager__user_FK", "manager__position_FK")
            .prefetch_related("attendants__user_FK", "attendants__position_FK")
        )

    def get_object(self) -> Shift:
        return get_object_or_404(self.get_queryset(), pk=self.kwargs.get("pk"))

    def get_success_url(self, obj: Shift | None = None) -> str:
        instance = obj or getattr(self, "object", None)
        if instance is None:
            instance = self.get_object()
        return reverse("sucursal_update", args=[instance.sucursal_id])


class ShiftCreateView(BranchAccessMixin, CreateView):
    form_class = ShiftForm
    template_name = "pages/sucursales/related_form.html"
    allowed_roles = ["ADMINISTRATOR","OWNER"]

    def get_initial(self) -> Dict[str, Any]:
        initial = super().get_initial()
        initial.setdefault("sucursal", self.get_sucursal())
        return initial

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs.setdefault("sucursal", self.get_sucursal())
        return kwargs

    def form_valid(self, form: ShiftForm) -> HttpResponseRedirect:
        form.instance.sucursal = self.get_sucursal()
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        sucursal = self.get_sucursal()
        context.update({"sucursal": sucursal, "title": "Agregar turno"})
        return context

    def get_success_url(self) -> str:
        return reverse("sucursal_update", args=[self.get_sucursal().pk])


class ShiftUpdateView(ShiftAccessMixin, UpdateView):
    form_class = ShiftForm
    template_name = "pages/sucursales/related_form.html"
    allowed_roles = ["ADMINISTRATOR", "OWNER"]

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return redirect_to_modal(
            self.object.sucursal_id, f"shift-edit-{self.object.pk}"
        )

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs.setdefault("sucursal", self.object.sucursal)
        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update({"sucursal": self.object.sucursal, "title": "Editar turno"})
        return context

    def get_success_url(self) -> str:
        return super().get_success_url(self.object)


class ShiftDeleteView(ShiftAccessMixin, View):
    allowed_roles = ["ADMINISTRATOR","OWNER"]
    def post(self, request, *args, **kwargs) -> HttpResponseRedirect:
        shift = self.get_object()
        success_url = self.get_success_url(shift)
        shift.delete()
        return HttpResponseRedirect(success_url)


class FuelInventoryAccessMixin(OwnerCompanyMixin):
    model = FuelInventory
    allowed_roles = ["OWNER", "ADMINISTRATOR"]
    def get_queryset(self) -> QuerySet[FuelInventory]:
        branch_ids = self.get_managed_branch_ids()
        if not branch_ids:
            return FuelInventory.objects.none()
        return FuelInventory.objects.filter(sucursal_id__in=branch_ids).select_related(
            "sucursal"
        )

    def get_object(self) -> FuelInventory:
        return get_object_or_404(self.get_queryset(), pk=self.kwargs.get("pk"))

    def get_success_url(self, obj: FuelInventory | None = None) -> str:
        instance = obj or getattr(self, "object", None)
        if instance is None:
            instance = self.get_object()
        return reverse("sucursal_update", args=[instance.sucursal_id])


class FuelInventoryCreateView(BranchAccessMixin, CreateView):
    form_class = FuelInventoryForm
    template_name = "pages/sucursales/related_form.html"

    def get_initial(self) -> Dict[str, Any]:
        initial = super().get_initial()
        initial.setdefault("sucursal", self.get_sucursal())
        return initial

    def form_valid(self, form: FuelInventoryForm) -> HttpResponseRedirect:
        form.instance.sucursal = self.get_sucursal()
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        sucursal = self.get_sucursal()
        context.update({"sucursal": sucursal, "title": "Agregar inventario"})
        return context

    def get_success_url(self) -> str:
        return reverse("sucursal_update", args=[self.get_sucursal().pk])


class FuelInventoryUpdateView(FuelInventoryAccessMixin, UpdateView):
    form_class = FuelInventoryForm
    template_name = "pages/sucursales/related_form.html"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return redirect_to_modal(
            self.object.sucursal_id, f"fuel-inventory-edit-{self.object.pk}"
        )

    def form_valid(self, form: FuelInventoryForm) -> HttpResponseRedirect:
        form.instance.sucursal = self.object.sucursal
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "sucursal": self.object.sucursal,
                "title": "Editar inventario",
            }
        )
        return context

    def get_success_url(self) -> str:
        return super().get_success_url(self.object)


class FuelInventoryDeleteView(FuelInventoryAccessMixin, View):
    def post(self, request, *args, **kwargs) -> HttpResponseRedirect:
        inventory = self.get_object()
        success_url = self.get_success_url(inventory)
        inventory.delete()
        return HttpResponseRedirect(success_url)


class BranchProductAccessMixin(OwnerCompanyMixin):
    model = BranchProduct
    allowed_roles = ["OWNER", "ADMINISTRATOR"]

    def get_queryset(self) -> QuerySet[BranchProduct]:
        branch_ids = self.get_managed_branch_ids()
        if not branch_ids:
            return BranchProduct.objects.none()
        return BranchProduct.objects.filter(sucursal_id__in=branch_ids).select_related(
            "sucursal"
        )

    def get_object(self) -> BranchProduct:
        return get_object_or_404(self.get_queryset(), pk=self.kwargs.get("pk"))

    def get_success_url(self, obj: BranchProduct | None = None) -> str:
        instance = obj or getattr(self, "object", None)
        if instance is None:
            instance = self.get_object()
        return reverse("sucursal_update", args=[instance.sucursal_id])


class BranchProductCreateView(BranchAccessMixin, CreateView):
    form_class = BranchProductForm
    template_name = "pages/sucursales/related_form.html"

    def get_initial(self) -> Dict[str, Any]:
        initial = super().get_initial()
        initial.setdefault("sucursal", self.get_sucursal())
        return initial

    def form_valid(self, form: BranchProductForm) -> HttpResponseRedirect:
        form.instance.sucursal = self.get_sucursal()
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update({"sucursal": self.get_sucursal(), "title": "Agregar producto"})
        return context

    def get_success_url(self) -> str:
        return reverse("sucursal_update", args=[self.get_sucursal().pk])


class BranchProductUpdateView(BranchProductAccessMixin, UpdateView):
    form_class = BranchProductForm
    template_name = "pages/sucursales/related_form.html"


    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return redirect_to_modal(
            self.object.sucursal_id, f"product-edit-{self.object.pk}"
        )

    def form_valid(self, form: BranchProductForm) -> HttpResponseRedirect:
        form.instance.sucursal = self.object.sucursal
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "sucursal": self.object.sucursal,
                "title": "Editar producto",
            }
        )
        return context

    def get_success_url(self) -> str:
        return super().get_success_url(self.object)


class BranchProductDeleteView(BranchProductAccessMixin, View):
    def post(self, request, *args, **kwargs) -> HttpResponseRedirect:
        product = self.get_object()
        success_url = self.get_success_url(product)
        product.delete()
        return HttpResponseRedirect(success_url)

class IslandAccessMixin(OwnerCompanyMixin):
    model = Island
    allowed_roles = ["OWNER", "ADMINISTRATOR"]
    def get_queryset(self) -> QuerySet[Island]:
        branch_ids = self.get_managed_branch_ids()
        if not branch_ids:
            return Island.objects.none()
        return Island.objects.filter(sucursal_id__in=branch_ids).select_related(
            "sucursal"
        )

    def get_object(self) -> Island:
        return get_object_or_404(self.get_queryset(), pk=self.kwargs.get("pk"))

    def get_success_url(self, obj: Island | None = None) -> str:
        instance = obj or getattr(self, "object", None)
        if instance is None:
            instance = self.get_object()
        return reverse("sucursal_update", args=[instance.sucursal_id])


class MachineAccessMixin(OwnerCompanyMixin):
    model = Machine
    allowed_roles = ["OWNER", "ADMINISTRATOR"]
    def get_queryset(self) -> QuerySet[Machine]:
        branch_ids = self.get_managed_branch_ids()
        if not branch_ids:
            return Machine.objects.none()
        return Machine.objects.filter(island__sucursal_id__in=branch_ids).select_related(
            "island__sucursal"
        )

    def get_object(self) -> Machine:
        return get_object_or_404(self.get_queryset(), pk=self.kwargs.get("pk"))

    def get_success_url(self, obj: Machine | None = None) -> str:
        instance = obj or getattr(self, "object", None)
        if instance is None:
            instance = self.get_object()
        return reverse("sucursal_update", args=[instance.island.sucursal_id])


class NozzleAccessMixin(OwnerCompanyMixin):
    model = Nozzle
    allowed_roles = ["OWNER", "ADMINISTRATOR"]
    def get_queryset(self) -> QuerySet[Nozzle]:
        branch_ids = self.get_managed_branch_ids()
        if not branch_ids:
            return Nozzle.objects.none()
        return Nozzle.objects.filter(
            machine__island__sucursal_id__in=branch_ids
        ).select_related("machine__island__sucursal")

    def get_object(self) -> Nozzle:
        return get_object_or_404(self.get_queryset(), pk=self.kwargs.get("pk"))

    def get_success_url(self, obj: Nozzle | None = None) -> str:
        instance = obj or getattr(self, "object", None)
        if instance is None:
            instance = self.get_object()
        return reverse("sucursal_update", args=[instance.machine.island.sucursal_id])


class IslandCreateView(BranchAccessMixin, CreateView):
    form_class = IslandForm
    template_name = "pages/sucursales/related_form.html"

    def get_initial(self) -> Dict[str, Any]:
        initial = super().get_initial()
        initial.setdefault("sucursal", self.get_sucursal())
        return initial

    def form_valid(self, form: IslandForm) -> HttpResponseRedirect:
        form.instance.sucursal = self.get_sucursal()
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        sucursal = self.get_sucursal()
        context.update(
            {
                "sucursal": sucursal,
                "title": "Agregar isla",
            }
        )
        return context

    def get_success_url(self) -> str:
        return reverse("sucursal_update", args=[self.get_sucursal().pk])


class IslandUpdateView(IslandAccessMixin, UpdateView):
    form_class = IslandForm
    template_name = "pages/sucursales/related_form.html"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return redirect_to_modal(
            self.object.sucursal_id, f"island-edit-{self.object.pk}"
        )

    def form_valid(self, form: IslandForm) -> HttpResponseRedirect:
        form.instance.sucursal = self.object.sucursal
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "sucursal": self.object.sucursal,
                "title": "Editar isla",
            }
        )
        return context

    def get_success_url(self) -> str:
        return super().get_success_url(self.object)


class IslandDeleteView(IslandAccessMixin, View):
    def post(self, request, *args, **kwargs) -> HttpResponseRedirect:
        island = self.get_object()
        success_url = self.get_success_url(island)
        island.delete()
        return HttpResponseRedirect(success_url)


class MachineCreateView(BranchAccessMixin, CreateView):
    form_class = MachineForm
    template_name = "pages/sucursales/related_form.html"
    island_url_kwarg = "island_pk"

    def get_island(self) -> Island:
        sucursal = self.get_sucursal()
        queryset = sucursal.branch_islands.all()
        return get_object_or_404(queryset, pk=self.kwargs.get(self.island_url_kwarg))

    def get_initial(self) -> Dict[str, Any]:
        initial = super().get_initial()
        initial.setdefault("island", self.get_island())
        return initial

    def form_valid(self, form: MachineForm) -> HttpResponseRedirect:
        form.instance.island = self.get_island()
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        island = self.get_island()
        context.update(
            {
                "sucursal": island.sucursal,
                "island": island,
                "title": "Agregar máquina",
            }
        )
        return context

    def get_success_url(self) -> str:
        return reverse("sucursal_update", args=[self.get_island().sucursal_id])


class MachineUpdateView(MachineAccessMixin, UpdateView):
    form_class = MachineForm
    template_name = "pages/sucursales/related_form.html"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return redirect_to_modal(
            self.object.island.sucursal_id, f"machine-edit-{self.object.pk}"
        )

    def form_valid(self, form: MachineForm) -> HttpResponseRedirect:
        form.instance.island = self.object.island
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "sucursal": self.object.island.sucursal,
                "island": self.object.island,
                "title": "Editar máquina",
            }
        )
        return context

    def get_success_url(self) -> str:
        return super().get_success_url(self.object)


class MachineDeleteView(MachineAccessMixin, View):
    def post(self, request, *args, **kwargs) -> HttpResponseRedirect:
        machine = self.get_object()
        success_url = self.get_success_url(machine)
        machine.delete()
        return HttpResponseRedirect(success_url)


class NozzleCreateView(OwnerCompanyMixin, CreateView):
    form_class = NozzleForm
    template_name = "pages/sucursales/related_form.html"
    machine_url_kwarg = "machine_pk"
    allowed_roles = ["OWNER", "ADMINISTRATOR"]

    def get_machine_queryset(self) -> QuerySet[Machine]:
        branch_ids = self.get_managed_branch_ids()
        if not branch_ids:
            return Machine.objects.none()
        return Machine.objects.filter(island__sucursal_id__in=branch_ids).select_related(
            "island__sucursal"
        )

    def get_machine(self) -> Machine:
        queryset = self.get_machine_queryset()
        return get_object_or_404(queryset, pk=self.kwargs.get(self.machine_url_kwarg))

    def get_initial(self) -> Dict[str, Any]:
        initial = super().get_initial()
        initial.setdefault("machine", self.get_machine())
        return initial

    def form_valid(self, form: NozzleForm) -> HttpResponseRedirect:
        form.instance.machine = self.get_machine()
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        machine = self.get_machine()
        context.update(
            {
                "sucursal": machine.island.sucursal,
                "island": machine.island,
                "machine": machine,
                "title": "Agregar pistola",
            }
        )
        return context

    def get_success_url(self) -> str:
        return reverse("sucursal_update", args=[self.get_machine().island.sucursal_id])


class NozzleUpdateView(NozzleAccessMixin, UpdateView):
    form_class = NozzleForm
    template_name = "pages/sucursales/related_form.html"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return redirect_to_modal(
            self.object.machine.island.sucursal_id,
            f"nozzle-edit-{self.object.pk}",
        )

    def form_valid(self, form: NozzleForm) -> HttpResponseRedirect:
        form.instance.machine = self.object.machine
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "sucursal": self.object.machine.island.sucursal,
                "island": self.object.machine.island,
                "machine": self.object.machine,
                "title": "Editar pistola",
            }
        )
        return context

    def get_success_url(self) -> str:
        return super().get_success_url(self.object)


class NozzleDeleteView(NozzleAccessMixin, View):
    def post(self, request, *args, **kwargs) -> HttpResponseRedirect:
        nozzle = self.get_object()
        success_url = self.get_success_url(nozzle)
        nozzle.delete()
        return HttpResponseRedirect(success_url)

class ServiceSessionCreateView(OwnerCompanyMixin, CreateView):
    model = ServiceSession
    form_class = ServiceSessionForm
    template_name = "pages/service_sessions/service_session_start.html"
    allowed_roles = ["OWNER", "ADMINISTRATOR"]

    def get_success_url(self):
        return reverse("service_session_detail", args=[self.object.pk])


    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        branch_ids = self.get_managed_branch_ids()
        available_shifts = (
            Shift.objects.filter(sucursal_id__in=branch_ids)
            .select_related("sucursal")
            .order_by("sucursal__name", "code")
        )

        detailed_shifts = available_shifts.select_related(
            "manager__user_FK",
            "manager__position_FK",
        ).prefetch_related("attendants__user_FK", "attendants__position_FK")

        shift_id = (
            self.request.POST.get("shift")
            if self.request.method == "POST"
            else self.request.GET.get("shift")
        )

        selected_shift = None
        if shift_id:
            selected_shift = detailed_shifts.filter(pk=shift_id).first()
        elif self.request.method == "GET":
            selected_shift = detailed_shifts.first()

        self.available_shifts = available_shifts
        self.selected_shift = selected_shift

        kwargs.update(
            {
                "shift": selected_shift,
                "available_shifts": available_shifts,
                "branch_ids": branch_ids,
            }
        )
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Servicio iniciado correctamente. Gestiona la caja e inventario del turno desde esta pantalla.",
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get("form")
        context.update(
            {
                "selected_shift": getattr(self, "selected_shift", None),
                "current_attendants": getattr(form, "current_attendants", []),
                "available_replacements": getattr(form, "available_replacements", []),
                "current_datetime": timezone.localtime(),
                "has_shifts": self.available_shifts.exists(),
            }
        )
        return context


class ServiceSessionDetailView(OwnerCompanyMixin, DetailView):
    model = ServiceSession
    template_name = "pages/service_sessions/service_session_detail.html"
    context_object_name = "service_session"
    allowed_roles = ["OWNER", "ADMINISTRATOR"]
    fuel_load_form_prefix = "fuel_load"
    product_load_form_prefix = "product_load"
    product_sale_form_prefix = "product_sale"
    credit_sale_form_prefix = "credit_sale"
    withdrawal_form_prefix = "withdrawal"

    def get_queryset(self):
        branch_ids = self.get_managed_branch_ids()
        queryset = (
            super()
            .get_queryset()
            .select_related(
                "shift__sucursal",
                "shift__manager__user_FK",
                "shift__manager__position_FK",
            )
            .prefetch_related(
                "attendants__user_FK",
                "attendants__position_FK",
                Prefetch(
                    "fuel_loads",
                    queryset=ServiceSessionFuelLoad.objects.select_related(
                        "inventory",
                        "responsible__user_FK",
                    ),
                ),

                Prefetch(
                    "product_loads",
                    queryset=ServiceSessionProductLoad.objects.select_related(
                        "product",
                        "responsible__user_FK",
                    ),
                ),
                Prefetch(
                    "product_sales",
                    queryset=ServiceSessionProductSale.objects.select_related(
                        "responsible__user_FK"
                    ).prefetch_related("items__product"),
                ),
                Prefetch(
                    "credit_sales",
                    queryset=ServiceSessionCreditSale.objects.select_related(
                        "responsible__user_FK",
                        "fuel_inventory",
                    ),
                ),
                Prefetch(
                    "withdrawals",
                    queryset=ServiceSessionWithdrawal.objects.select_related(
                        "responsible__user_FK"
                    ),
                ),
            )
        )
        if branch_ids:
            queryset = queryset.filter(shift__sucursal_id__in=branch_ids)
        else:
            queryset = queryset.none()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_profile = getattr(self.request.user, "profile", None)
        current_datetime = timezone.localtime()
        fuel_load_form = kwargs.get("fuel_load_form")
        if fuel_load_form is None:
            fuel_load_form = ServiceSessionFuelLoadForm(
                service_session=self.object,
                prefix=self.fuel_load_form_prefix,
            )




        product_load_form = kwargs.get("product_load_form")
        if product_load_form is None:
            product_load_form = ServiceSessionProductLoadForm(
                service_session=self.object,
                prefix=self.product_load_form_prefix,
            )

        product_sale_form = kwargs.get("product_sale_form")
        if product_sale_form is None:
            product_sale_form = ServiceSessionProductSaleForm(
                service_session=self.object,
                responsible_profile=current_profile,
                prefix=self.product_sale_form_prefix,
            )

        credit_sale_form = kwargs.get("credit_sale_form")
        if credit_sale_form is None:
            credit_sale_form = ServiceSessionCreditSaleForm(
                service_session=self.object,
                responsible_profile=current_profile,
                prefix=self.credit_sale_form_prefix,
            )

        product_sale_formset = kwargs.get("product_sale_formset")
        if product_sale_formset is None:
            product_sale_formset = ServiceSessionProductSaleItemFormSet(
                service_session=self.object,
                queryset=ServiceSessionProductSaleItem.objects.none(),
            )

        withdraw_form = kwargs.get("withdraw_form")
        if withdraw_form is None:
            withdraw_form = ServiceSessionWithdrawalForm(
                service_session=self.object,
                responsible_profile=current_profile,
                prefix=self.withdrawal_form_prefix,
            )

        branch = self.object.shift.sucursal
        product_loads = list(self.object.product_loads.all())
        product_additions = {
            entry["product_id"]: entry["total_added"]
            for entry in self.object.product_loads.values("product_id").annotate(
                total_added=Coalesce(Sum("quantity_added"), 0)
            )
        }
        product_sales_items = {
            entry["product_id"]: entry["total_sold"]
            for entry in ServiceSessionProductSaleItem.objects.filter(
                sale__service_session=self.object
            )
            .values("product_id")
            .annotate(total_sold=Coalesce(Sum("quantity"), 0))
        }
        branch_products = list(branch.products.all())
        for product in branch_products:
            product.session_added_quantity = product_additions.get(product.pk, 0)
            product.session_sold_quantity = product_sales_items.get(product.pk, 0)
        withdrawals = list(self.object.withdrawals.all())
        context.update(
            {
                "shift": self.object.shift,
                "attendants": self.object.attendants.all(),
                "branch": branch,
                "fuel_inventories": branch.fuel_inventories.all(),
                "fuel_loads": self.object.fuel_loads.all(),
                "branch_products": branch_products,
                "product_loads": product_loads,
                "fuel_load_form": fuel_load_form,
                "product_sales": list(self.object.product_sales.all()),
                "product_load_form": product_load_form,
                "fuel_responsible": self.object.shift.manager,
                "product_load_responsible": self.object.shift.manager,
                "product_sale_form": product_sale_form,
                "product_sale_formset": product_sale_formset,
                "credit_sale_form": credit_sale_form,
                "product_responsible": self.object.shift.manager,
                "product_sale_responsible": current_profile,
                "credit_sale_responsible": current_profile,
                "credit_sales": list(self.object.credit_sales.all()),
                "service_date": self.object.started_at.date(),
                "withdrawals": withdrawals,
                "withdraw_form": withdraw_form,
                "withdraw_responsible": current_profile,
                "current_datetime": current_datetime,
                "current_profile_name": (
                    (current_profile.user_FK.get_full_name() or current_profile.user_FK.username)
                    if current_profile and getattr(current_profile, "user_FK", None)
                    else "Sin encargado asignado"
                ),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form_type = request.POST.get("form_type", "fuel-load")

        if form_type == "product-load":
            form = ServiceSessionProductLoadForm(
                data=request.POST,
                service_session=self.object,
                prefix=self.product_load_form_prefix,
            )
            if form.is_valid():
                form.save()
                messages.success(
                    request,
                    "Ingreso de productos registrado correctamente.",
                )
                return redirect("service_session_detail", pk=self.object.pk)

            context = self.get_context_data(product_load_form=form)
            return self.render_to_response(context)
        if form_type == "product-sale":
            sale_form = ServiceSessionProductSaleForm(
                data=request.POST,
                service_session=self.object,
                responsible_profile=getattr(request.user, "profile", None),
                prefix=self.product_sale_form_prefix,
            )
            item_formset = ServiceSessionProductSaleItemFormSet(
                data=request.POST,
                service_session=self.object,
                queryset=ServiceSessionProductSaleItem.objects.none(),
            )
            if sale_form.is_valid() and item_formset.is_valid():
                with transaction.atomic():
                    sale = sale_form.save()
                    for form in item_formset:
                        if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                            continue
                        product = form.cleaned_data["product"]
                        quantity = form.cleaned_data["quantity"]
                        ServiceSessionProductSaleItem.objects.create(
                            sale=sale,
                            product=product,
                            quantity=quantity,
                        )
                        BranchProduct.objects.filter(pk=product.pk).update(
                            quantity=F("quantity") - quantity
                        )
                    messages.success(
                        request,
                        "Venta de productos registrada correctamente.",
                    )
                return redirect("service_session_detail", pk=self.object.pk)

            context = self.get_context_data(
                product_sale_form=sale_form,
                product_sale_formset=item_formset,
            )
            return self.render_to_response(context)

        if form_type == "credit-sale":
            credit_form = ServiceSessionCreditSaleForm(
                data=request.POST,
                service_session=self.object,
                responsible_profile=getattr(request.user, "profile", None),
                prefix=self.credit_sale_form_prefix,
            )
            if credit_form.is_valid():
                credit_form.save()
                messages.success(
                    request,
                    "Venta a crédito registrada correctamente.",
                )
                return redirect("service_session_detail", pk=self.object.pk)

            context = self.get_context_data(credit_sale_form=credit_form)
            return self.render_to_response(context)

        if form_type == "withdrawal":
            withdraw_form = ServiceSessionWithdrawalForm(
                data=request.POST,
                service_session=self.object,
                responsible_profile=getattr(request.user, "profile", None),
                prefix=self.withdrawal_form_prefix,
            )
            if withdraw_form.is_valid():
                withdraw_form.save()
                messages.success(
                    request,
                    "Tirada de caja registrada correctamente.",
                )
                return redirect("service_session_detail", pk=self.object.pk)

            context = self.get_context_data(withdraw_form=withdraw_form)
            return self.render_to_response(context)
        form = ServiceSessionFuelLoadForm(
            data=request.POST,
            service_session=self.object,
            prefix=self.fuel_load_form_prefix,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Carga de combustible registrada correctamente.")
            return redirect("service_session_detail", pk=self.object.pk)

        context = self.get_context_data(fuel_load_form=form)
        return self.render_to_response(context)