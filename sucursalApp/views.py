from typing import Any, Dict, List

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, QuerySet
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy

from django.views import View

from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from django.views.generic.edit import FormMixin

from core.mixins import RoleRequiredMixin
from homeApp.models import Company
from .forms import (
    FuelInventoryForm,
    IslandForm,
    MachineForm,
    NozzleForm,
    ShiftForm,
    SucursalForm,
)
from .models import (
    FuelInventory,
    Island,
    Machine,
    Nozzle,
    Shift,
    Sucursal,
    SucursalStaff,
)


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
            context["islands"] = self.object.branch_islands.all()
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
            context["shifts"] = shift_queryset
            profile = getattr(self.request.user, "profile", None)
            can_manage_shifts = bool(
                self.request.user.is_superuser
                or (profile and profile.has_role("ADMINISTRATOR"))
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
            context["fuel_inventories"] = self.object.fuel_inventories.all()
            context["fuel_inventory_create_form"] = FuelInventoryForm(
                initial={"sucursal": self.object}, auto_id="new-inventory_%s"
            )
            context["fuel_inventory_create_url"] = reverse(
                "sucursal_fuel_inventory_create", args=[self.object.pk]
            )
            for island in context["islands"]:
                island.machine_create_form = MachineForm(
                    initial={"island": island}, auto_id=f"new-machine-{island.pk}_%s"
                )
                for machine in island.machines.all():
                    machine.nozzle_create_form = NozzleForm(
                        auto_id=f"new-nozzle-{machine.pk}_%s",
                        initial={"machine": machine},
                    )
        else:
            context.setdefault("islands", [])
            context.setdefault("shifts", [])
        context.setdefault("can_manage_shifts", False)
        return context


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
    allowed_roles = ["ADMINISTRATOR","OWNER"]

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

