from typing import Optional


from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional
from itertools import chain

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseFormSet, formset_factory
from django.forms.boundfield import BoundField
from django.db import transaction
from django.db.models import F, Q, Count

from UsuarioApp.models import Profile


from .models import (
    BranchProduct,
    FuelInventory,
    FuelPrice,
    Island,
    Machine,
    MachineFuelInventoryNumeral,
    Nozzle,
    Shift,
    ServiceSessionFirefighterPayment,
    ServiceSessionTransbankVoucher,
    ServiceSessionCreditSale,
    ServiceSessionFuelLoad,
    ServiceSessionProductLoad,
    ServiceSessionProductSale,
    ServiceSessionProductSaleItem,
    ServiceSessionWithdrawal,
    ServiceSession,
    Sucursal,
    SucursalStaff,
)

class SucursalForm(forms.ModelForm):
    administrators = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "profile-checkbox-grid"}
        ),
        label="Administradores",
    )
    accountants = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "profile-checkbox-grid"}
        ),
        label="Secretario(a)",
    )
    firefighters = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "profile-checkbox-grid"}
        ),
        label="Bomberos",
        help_text="Incluye perfiles con rol de bombero.",
    )

    STAFF_ROLE_FIELDS = {
        "administrators": ("ADMINISTRATOR",),
        "accountants": ("ACCOUNTANT",),
        "firefighters": ("ATTENDANT", "HEAD_ATTENDANT"),
    }

    class Meta:
        model = Sucursal
        fields = [
            "name",
            "address",
            "city",
            "region",
            "phone",
            "email",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "address": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "city": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "region": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "phone": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "email": forms.EmailInput(attrs={"class": "w-full border rounded p-2"}),
        }

    def __init__(self, *args, company: Optional["homeApp.models.Company"] = None, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)
        base_queryset = Profile.objects.select_related("position_FK", "user_FK")

        # Most staff assignments should be limited to the company's profiles, but
        # administrators must be selectable globally so any system administrator
        # can be assigned to the branch.
        company_queryset = base_queryset
        if company is not None:
            company_queryset = company_queryset.filter(company_rut=company.rut)
            company_queryset = company_queryset.exclude(
                position_FK__permission_code="OWNER"
            )
        for field_name, roles in self.STAFF_ROLE_FIELDS.items():
            # Administrators are pulled from the full set of profiles to ensure all
            # system administrators are available, while the rest stay limited to
            # the company scope.
            field_queryset = (
                base_queryset
                if field_name == "administrators"
                else company_queryset
            ).filter(position_FK__permission_code__in=roles)

            # If no profiles found for the expected roles (possible data
            # inconsistency during user creation), fall back to showing all
            # company profiles so administrators can still assign staff manually.
            if not field_queryset.exists():
                field_queryset = company_queryset

            if self.instance.pk:
                initial_ids = self.instance.staff.filter(role__in=roles).values_list(
                    "profile_id", flat=True
                )
                self.fields[field_name].initial = list(initial_ids)
            field = self.fields[field_name]
            field.queryset = field_queryset.order_by(
                "user_FK__first_name", "user_FK__last_name", "user_FK__username"
            )
            widget = self.fields[field_name].widget
            base_class = widget.attrs.get("class", "")
            extra_class = "profile-checkbox-grid"
            if extra_class not in base_class:
                widget.attrs["class"] = f"{base_class} {extra_class}".strip()
            widget.choices = self.fields[field_name].choices

    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        if self.company is not None:
            instance.company = self.company
        if commit:
            instance.save()
            self._save_staff_assignments(instance)
        else:
            self._pending_staff_assignment = True
        return instance

    def save_m2m(self):
        super().save_m2m()
        if getattr(self, "_pending_staff_assignment", False):
            self._save_staff_assignments(self.instance)
            self._pending_staff_assignment = False

    def _save_staff_assignments(self, instance: Sucursal) -> None:
        for field_name, roles in self.STAFF_ROLE_FIELDS.items():
            selected_profiles = self.cleaned_data.get(field_name)
            if selected_profiles is None:
                continue
            selected_ids = [profile.pk for profile in selected_profiles]
            instance.staff.filter(role__in=roles).exclude(
                profile_id__in=selected_ids
            ).delete()
            for profile in selected_profiles:
                role = None
                if getattr(profile, "position_FK", None):
                    role = profile.position_FK.permission_code
                SucursalStaff.objects.update_or_create(
                    sucursal=instance,
                    profile=profile,
                    defaults={"role": role},
                )


class BranchStaffForm(forms.Form):
    administrators = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "profile-checkbox-grid"}
        ),
        label="Administradores",
    )
    accountants = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "profile-checkbox-grid"}
        ),
        label="Secretario(a)",
    )
    firefighters = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "profile-checkbox-grid"}
        ),
        label="Bomberos",
        help_text="Incluye perfiles con rol de bombero.",
    )

    STAFF_ROLE_FIELDS = SucursalForm.STAFF_ROLE_FIELDS

    def __init__(
        self,
        *args,
        company: Optional["homeApp.models.Company"] = None,
        instance: Optional[Sucursal] = None,
        allow_admin_assignment: bool = True,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.company = company or getattr(instance, "company", None)
        self.allow_admin_assignment = allow_admin_assignment

        base_queryset = Profile.objects.select_related("position_FK", "user_FK")
        company_queryset = base_queryset
        if self.company is not None:
            company_queryset = company_queryset.filter(company_rut=self.company.rut)

        for field_name, roles in self.STAFF_ROLE_FIELDS.items():
            if field_name == "administrators" and not self.allow_admin_assignment:
                self.fields.pop(field_name, None)
                continue

            field_queryset = (
                base_queryset
                if field_name == "administrators"
                else company_queryset
            ).filter(position_FK__permission_code__in=roles)
            # Fallback: if no users match the role filter, show all company profiles

            field = self.fields[field_name]
            field.queryset = field_queryset.order_by("user_FK__username")

            if self.instance and self.instance.pk:
                initial_ids = self.instance.staff.filter(
                    role__in=roles
                ).values_list("profile_id", flat=True)
                field.initial = list(initial_ids)

            widget = field.widget
            base_class = widget.attrs.get("class", "")
            extra_class = "profile-checkbox-grid"
            if extra_class not in base_class:
                widget.attrs["class"] = f"{base_class} {extra_class}".strip()

    def _save_staff_assignments(self) -> None:
        if not self.instance:
            raise ValueError("Branch instance is required to save staff assignments")

        for field_name, roles in self.STAFF_ROLE_FIELDS.items():
            if field_name not in self.fields:
                continue

            selected_profiles = self.cleaned_data.get(field_name)
            if selected_profiles is None:
                continue

            selected_ids = [profile.pk for profile in selected_profiles]
            self.instance.staff.filter(role__in=roles).exclude(
                profile_id__in=selected_ids
            ).delete()

            for profile in selected_profiles:
                role = None
                if getattr(profile, "position_FK", None):
                    role = profile.position_FK.permission_code
                SucursalStaff.objects.update_or_create(
                    sucursal=self.instance,
                    profile=profile,
                    defaults={"role": role},
                )

    def save(self) -> Sucursal:
        if not self.is_valid():
            raise ValueError("Cannot save an invalid form")

        if not self.instance:
            raise ValueError("Branch instance is required to save staff assignments")

        self._save_staff_assignments()
        return self.instance


class BranchUserLinkForm(forms.Form):
    available_users = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
            }
        ),
        label="Usuarios sin sucursal",
        help_text="Usuarios de la compañía sin asignación a sucursal.",
    )
    assigned_users = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
            }
        ),
        label="Usuarios asignados a la sucursal",
    )

    def __init__(
        self,
        *args,
        branch: Sucursal,
        company: Optional["homeApp.models.Company"] = None,
        **kwargs,
    ):
        self.branch = branch
        self.company = company or getattr(branch, "company", None)
        super().__init__(*args, **kwargs)

        base_queryset = (
            Profile.objects.select_related("user_FK", "position_FK")
            .filter(user_FK__is_active=True)
            .exclude(position_FK__permission_code="OWNER")
        )
        if self.company is not None:
            base_queryset = base_queryset.filter(company_rut=self.company.rut)

        available_queryset = (
            base_queryset.annotate(branch_count=Count("sucursal_staff", distinct=True))
            .filter(branch_count=0, current_branch__isnull=True)
            .order_by("user_FK__first_name", "user_FK__last_name", "user_FK__username")
        )

        assigned_queryset = (
            base_queryset.filter(sucursal_staff__sucursal=self.branch)
            .distinct()
            .order_by("user_FK__first_name", "user_FK__last_name", "user_FK__username")
        )

        self.fields["available_users"].queryset = available_queryset
        self.fields["assigned_users"].queryset = assigned_queryset
        self.fields["assigned_users"].initial = list(
            assigned_queryset.values_list("pk", flat=True)
        )

    def save(self) -> None:
        if not self.is_valid():
            raise ValueError("Cannot save an invalid form")

        selected_profiles = list(
            chain(
                self.cleaned_data.get("available_users") or [],
                self.cleaned_data.get("assigned_users") or [],
            )
        )
        final_ids = {profile.pk for profile in selected_profiles}

        current_staff_qs = self.branch.staff.exclude(
            profile__position_FK__permission_code="OWNER"
        )
        current_ids = set(current_staff_qs.values_list("profile_id", flat=True))
        removed_ids = current_ids - final_ids

        current_staff_qs.filter(profile_id__in=removed_ids).delete()
        Profile.objects.filter(
            pk__in=removed_ids, current_branch=self.branch
        ).update(current_branch=None)

        for profile in selected_profiles:
            role = None
            if getattr(profile, "position_FK", None):
                role = profile.position_FK.permission_code
            SucursalStaff.objects.update_or_create(
                sucursal=self.branch,
                profile=profile,
                defaults={"role": role},
            )
            if profile.current_branch_id != self.branch.pk:
                Profile.objects.filter(pk=profile.pk).update(current_branch=self.branch)

class IslandForm(forms.ModelForm):
    class Meta:
        model = Island
        fields = ["sucursal", "number", "description"]
        widgets = {
            "sucursal": forms.HiddenInput(),
            "number": forms.NumberInput(attrs={"class": "w-full border rounded p-2"}),
            "description": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
        }


class MachineForm(forms.ModelForm):
    def __init__(self, *args, island: Optional[Island] = None, **kwargs):
        instance_island = getattr(kwargs.get("instance"), "island", None)
        initial_island = kwargs.get("initial", {}).get("island")
        self._form_island = island or instance_island or initial_island

        self.inventory_numeral_fields: list[tuple[FuelInventory, list[BoundField]]] = []
        self.inventory_numeral_counts: dict[int, int] = {}
        super().__init__(*args, **kwargs)

        fuel_field = self.fields.get("fuel_inventories")
        if fuel_field:
            queryset = FuelInventory.objects.all()
            if self._form_island:
                queryset = queryset.filter(sucursal=self._form_island.sucursal)
            fuel_field.queryset = queryset.order_by("code")
            fuel_field.required = False

            for inventory in fuel_field.queryset:
                existing_numerals: list[MachineFuelInventoryNumeral] = []
                if self.instance and self.instance.pk:
                    existing_numerals = self.instance.get_numerals_for_inventory(
                        inventory
                    )

                default_count = max(len(existing_numerals), 1)
                count_key = f"numeral_count_{inventory.pk}"
                if self.is_bound:
                    try:
                        bound_count = int(self.data.get(count_key, default_count))
                    except (TypeError, ValueError):
                        bound_count = default_count
                    numeral_count = max(bound_count, 1)
                else:
                    numeral_count = default_count

                self.inventory_numeral_counts[inventory.pk] = numeral_count

                inventory_fields: list[BoundField] = []
                for slot in range(1, numeral_count + 1):
                    field_name = f"numeral_{inventory.pk}_{slot}"

                    initial_numeral = Decimal("0")
                    if slot - 1 < len(existing_numerals):
                        initial_numeral = existing_numerals[slot - 1].numeral

                    self.fields[field_name] = forms.DecimalField(
                        label=(
                            f"Numeral {inventory.code} ({inventory.fuel_type})"
                            f" #{slot}"
                        ),
                        required=False,
                        max_digits=12,
                        decimal_places=2,
                        min_value=Decimal("0"),
                        initial=initial_numeral,
                        help_text=(
                            "Se guarda solo si la máquina está asociada a este estanque."
                        ),
                        widget=forms.NumberInput(
                            attrs={
                                "class": "w-full border rounded p-2",
                                "step": "0.01",
                            }
                        ),
                    )
                    inventory_fields.append(self[field_name])

                self.inventory_numeral_fields.append((inventory, inventory_fields))


    def clean_fuel_inventories(self):
        fuel_inventories = self.cleaned_data.get("fuel_inventories")
        island = self.cleaned_data.get("island") or self._form_island

        if not island:
            return fuel_inventories
        invalid_inventories = fuel_inventories.exclude(sucursal_id=island.sucursal_id)
        if invalid_inventories.exists():
            raise ValidationError(
                "Todos los estanques seleccionados deben pertenecer a la sucursal de la máquina."
            )
        return fuel_inventories

    def save(self, commit=True):
        machine: Machine = super().save(commit=False)
        fuel_inventories = self.cleaned_data.get("fuel_inventories")
        primary_inventory = None
        if fuel_inventories:
            primary_inventory = fuel_inventories.order_by("pk").first()
        machine.fuel_inventory = primary_inventory
        if commit:
            machine.save()
            if fuel_inventories is not None:
                machine.fuel_inventories.set(fuel_inventories)
            self._save_numerals(machine, fuel_inventories)
        else:
            self._pending_fuel_inventories = fuel_inventories
            self._pending_numeral_save = True
        return machine

    def save_m2m(self):
        super().save_m2m()
        fuel_inventories = getattr(self, "_pending_fuel_inventories", None)
        if fuel_inventories is not None:
            self.instance.fuel_inventories.set(fuel_inventories)
        if getattr(self, "_pending_numeral_save", False):
            self._save_numerals(self.instance, fuel_inventories)
            self._pending_numeral_save = False

    def _save_numerals(
        self, machine: Machine, fuel_inventories: Iterable[FuelInventory] | None
    ) -> None:
        selected_inventories = list(fuel_inventories or [])
        if machine.fuel_inventory and machine.fuel_inventory not in selected_inventories:
            selected_inventories.insert(0, machine.fuel_inventory)

        for inventory, fields in self.inventory_numeral_fields:
            if inventory not in selected_inventories:
                continue

            numeral_count = self.inventory_numeral_counts.get(
                inventory.pk, len(fields)
            )

            for idx, field in enumerate(fields, start=1):
                numeral_value = self.cleaned_data.get(field.name)
                if numeral_value is None:
                    numeral_value = Decimal("0")
                MachineFuelInventoryNumeral.objects.update_or_create(
                    machine=machine,
                    fuel_inventory=inventory,
                    slot=idx,
                    defaults={"numeral": numeral_value},
                )

            MachineFuelInventoryNumeral.objects.filter(
                machine=machine, fuel_inventory=inventory
            ).exclude(slot__lte=numeral_count).delete()

        MachineFuelInventoryNumeral.objects.filter(machine=machine).exclude(
            fuel_inventory__in=selected_inventories
        ).delete()
    class Meta:
        model = Machine
        fields = [
            "island",
            "number",
            "fuel_inventories",
            "description",
        ]
        widgets = {
            "island": forms.HiddenInput(),
            "number": forms.NumberInput(attrs={"class": "w-full border rounded p-2"}),
            "fuel_inventories": forms.CheckboxSelectMultiple(
                attrs={"class": "space-y-2"}
            ),
            "description": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
        }


class NozzleForm(forms.ModelForm):
    def __init__(self, *args, machine: Optional[Machine] = None, **kwargs):
        self._form_machine = machine or kwargs.get("initial", {}).get("machine")
        super().__init__(*args, **kwargs)
        fuel_field = self.fields.get("fuel_numeral")
        if fuel_field:
            numeral_queryset = MachineFuelInventoryNumeral.objects.none()
            if self._form_machine:
                numeral_queryset = MachineFuelInventoryNumeral.objects.filter(
                    machine=self._form_machine, numeral__gt=0
                )
            fuel_field.queryset = numeral_queryset.select_related("fuel_inventory").order_by(
                "fuel_inventory__code", "slot", "pk"
            )
            fuel_field.empty_label = "Selecciona un numeral"
            fuel_field.required = fuel_field.queryset.exists()

    def clean_fuel_numeral(self):
        fuel_numeral = self.cleaned_data.get("fuel_numeral")
        machine = self.cleaned_data.get("machine") or self._form_machine
        if fuel_numeral and machine and fuel_numeral.machine_id != machine.pk:
            raise ValidationError(
                "El numeral seleccionado debe pertenecer a la máquina."
            )
        return fuel_numeral

    def save(self, commit=True):
        nozzle: Nozzle = super().save(commit=False)
        fuel_numeral = self.cleaned_data.get("fuel_numeral")
        if fuel_numeral:
            nozzle.fuel_type = fuel_numeral.fuel_inventory.fuel_type
        if commit:
            nozzle.save()
        return nozzle

    class Meta:
        model = Nozzle
        fields = [
            "machine",
            "number",
            "code",
            "fuel_numeral",
            "description",
        ]
        widgets = {
            "machine": forms.HiddenInput(),
            "number": forms.NumberInput(attrs={"class": "w-full border rounded p-2"}),
            "code": forms.TextInput(
                attrs={
                    "class": "w-full border rounded p-2",
                    "placeholder": "Código enviado por la pistola",
                }
            ),
            "fuel_numeral": forms.Select(
                attrs={"class": "w-full border rounded p-2"}
            ),
            "description": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
        }


class ShiftForm(forms.ModelForm):
    def __init__(self, *args, sucursal: Optional[Sucursal] = None, **kwargs):
        self.sucursal = sucursal
        super().__init__(*args, **kwargs)
        branch = self.sucursal or self.initial.get("sucursal") or self.instance.sucursal
        queryset = Profile.objects.select_related("user_FK", "position_FK")
        if branch:
            queryset = queryset.filter(sucursal_staff__sucursal=branch).distinct()
        manager_queryset = queryset.filter(
            Q(position_FK__permission_code__in=["ATTENDANT", "HEAD_ATTENDANT"])
        )
        current_manager = getattr(self.instance, "manager_id", None)
        if current_manager:
            manager_queryset = (manager_queryset | queryset.filter(pk=current_manager)).distinct()
        self.fields["manager"].queryset = manager_queryset.order_by(
            "user_FK__first_name", "user_FK__last_name", "user_FK__username"
        )
        attendants_field = self.fields.get("attendants")
        if attendants_field is not None:
            attendants_queryset = queryset.filter(
                position_FK__permission_code__in=["ATTENDANT", "HEAD_ATTENDANT"]
            )
            attendants_field.required = False
            attendants_field.queryset = attendants_queryset.order_by(
                "user_FK__first_name", "user_FK__last_name", "user_FK__username"
            )
            base_class = attendants_field.widget.attrs.get("class", "")
            required_class = "profile-checkbox-grid"
            if required_class not in base_class:
                attendants_field.widget.attrs["class"] = (
                    f"{base_class} {required_class}".strip()
                )
            attendants_field.widget.choices = attendants_field.choices
            base_class = attendants_field.widget.attrs.get("class", "")
            extra_classes = "grid gap-2"
            if extra_classes not in base_class:
                attendants_field.widget.attrs["class"] = (
                    f"{base_class} {extra_classes}".strip()
                )
            attendants_field.widget.choices = attendants_field.choices

    class Meta:
        model = Shift
        fields = [
            "sucursal",
            "code",
            "description",
            "start_time",
            "end_time",
            "manager",
            "attendants",
        ]
        widgets = {
            "sucursal": forms.HiddenInput(),
            "code": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full border rounded p-2",
                    "rows": 3,
                    "placeholder": "Ej. Turno matutino para recepción y control de inventario",
                }
            ),
            "start_time": forms.TimeInput(
                attrs={"class": "w-full border rounded p-2", "type": "time"}
            ),
            "end_time": forms.TimeInput(
                attrs={"class": "w-full border rounded p-2", "type": "time"}
            ),
            "manager": forms.Select(attrs={"class": "w-full border rounded p-2"}
            ),
            "attendants": forms.CheckboxSelectMultiple(
                attrs={"class": "profile-checkbox-grid"}
            )
        }
    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_time")
        end = cleaned_data.get("end_time")
        if start and end and start >= end:
            self.add_error(
                "end_time",
                "La hora de término debe ser posterior a la hora de inicio.",
            )
        return cleaned_data


class ServiceSessionForm(forms.ModelForm):
    """Formulario para iniciar un servicio asociado a un turno."""

    attendants = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "profile-checkbox-grid"}
        ),
        label="Bomberos asignados",
        help_text="Selecciona los bomberos que trabajarán en este turno.",
    )

    class Meta:
        model = ServiceSession
        fields = ["shift", "coins_amount", "cash_amount", "attendants"]
        widgets = {
            "shift": forms.Select(attrs={"class": "w-full border rounded p-2"}),
            "coins_amount": forms.NumberInput(
                attrs={"class": "w-full border rounded p-2", "min": "0", "step": "0.01"}
            ),
            "cash_amount": forms.NumberInput(
                attrs={"class": "w-full border rounded p-2", "min": "0", "step": "0.01"}
            ),
        }
        help_texts = {
            "coins_amount": "Ingresa el monto disponible en monedas al inicio del turno.",
            "cash_amount": "Ingresa el monto disponible en billetes al inicio del turno.",
        }

    def __init__(
        self,
        *args,
        shift: Shift | None = None,
        branch_ids: list[int] | None = None,
        available_shifts=None,
        **kwargs,
    ):
        self.selected_shift: Shift | None = shift
        self.branch_ids = branch_ids or []
        super().__init__(*args, **kwargs)
        if available_shifts is not None:
            self.fields["shift"].queryset = available_shifts
        else:
            self.fields["shift"].queryset = Shift.objects.filter(
                sucursal_id__in=self.branch_ids
            ).select_related("sucursal")

        # Determinar el turno seleccionado en función de los datos enviados.
        shift_from_data = self.data.get(self.add_prefix("shift"))
        if shift_from_data:
            try:
                self.selected_shift = self.fields["shift"].queryset.get(pk=shift_from_data)
            except (Shift.DoesNotExist, ValueError, TypeError):
                self.selected_shift = None

        if self.selected_shift:
            self.fields["shift"].initial = self.selected_shift.pk

        self.fields["coins_amount"].min_value = 0
        self.fields["cash_amount"].min_value = 0

        self._configure_attendants_field()

    def _configure_attendants_field(self) -> None:
        base_queryset = Profile.objects.select_related("user_FK", "position_FK").filter(
            position_FK__permission_code__in=("ATTENDANT", "HEAD_ATTENDANT"),
            user_FK__is_active=True
        )

        if self.selected_shift and self.selected_shift.manager_id:
            base_queryset = base_queryset.exclude(pk=self.selected_shift.manager_id)

        if self.branch_ids:
            base_queryset = base_queryset.filter(
                Q(sucursal_staff__sucursal_id__in=self.branch_ids)
                | Q(current_branch_id__in=self.branch_ids)
            )

        base_queryset = base_queryset.distinct()

        current_attendants_qs = Profile.objects.none()
        if self.selected_shift:
            current_attendants_qs = self.selected_shift.attendants.select_related(
                "user_FK", "position_FK"
            )

        available_for_replacement_qs = (
            base_queryset.annotate(shift_count=Count("assigned_shifts", distinct=True))
            .filter(shift_count=0)
            .distinct()
        )

        current_ids = list(current_attendants_qs.values_list("pk", flat=True))
        available_ids = list(available_for_replacement_qs.values_list("pk", flat=True))
        combined_ids = current_ids + [pk for pk in available_ids if pk not in current_ids]
        attendants_field = self.fields["attendants"]

        if combined_ids:
            attendants_field.queryset = base_queryset.filter(pk__in=combined_ids).order_by(
                "user_FK__first_name",
                "user_FK__last_name",
                "user_FK__username",
            )
        else:
            attendants_field.queryset = base_queryset.none()

        if current_ids:
            attendants_field.initial = current_ids

        widget = attendants_field.widget
        base_class = widget.attrs.get("class", "")
        required_class = "profile-checkbox-grid"
        if required_class not in base_class:
            widget.attrs["class"] = f"{base_class} {required_class}".strip()
        widget.choices = attendants_field.choices

        self.current_attendants = list(current_attendants_qs)
        self.available_replacements = list(
            base_queryset.filter(pk__in=available_ids).order_by(
                "user_FK__first_name",
                "user_FK__last_name",
                "user_FK__username",
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        shift = cleaned_data.get("shift")

        if shift and ServiceSession.objects.filter(
            shift__sucursal=shift.sucursal, ended_at__isnull=True
        ).exists():
            self.add_error(
                "shift",
                "Ya existe un servicio en curso para esta sucursal. Cierra la caja del servicio activo antes de iniciar uno nuevo.",
            )

        return cleaned_data

    def clean_attendants(self):
        attendants = self.cleaned_data.get("attendants")
        if not attendants:
            raise forms.ValidationError(
                "Debes seleccionar al menos un bombero para iniciar el turno."
            )

        manager_id = getattr(self.selected_shift, "manager_id", None)
        if manager_id:
            for attendant in attendants:
                if attendant.pk == manager_id:
                    raise forms.ValidationError(
                        "El bombero encargado ya está asignado al turno y no puede agregarse nuevamente."
                    )
        return attendants

    def save(self, commit: bool = True):
        instance: ServiceSession = super().save(commit=False)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class FuelInventoryForm(forms.ModelForm):
    class Meta:
        model = FuelInventory
        fields = ["sucursal", "code", "fuel_type", "capacity", "liters"]
        widgets = {
            "sucursal": forms.HiddenInput(),
            "code": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "fuel_type": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "capacity": forms.NumberInput(
                attrs={"class": "w-full border rounded p-2", "step": "0.01"}
            ),
            "liters": forms.NumberInput(
                attrs={"class": "w-full border rounded p-2", "step": "0.01"}
            ),
        }


class FuelPriceForm(forms.ModelForm):
    def __init__(
        self,
        *args,
        branch: Sucursal,
        available_fuel_types: Iterable[str],
        **kwargs,
    ):
        self.branch = branch
        self.available_fuel_types = set(available_fuel_types)
        super().__init__(*args, **kwargs)
        self.fields["sucursal"].initial = branch
        self.fields["sucursal"].widget = forms.HiddenInput()
        self.fields["fuel_type"].widget = forms.HiddenInput()
        if "fuel_type" in self.initial and not self.fields["fuel_type"].initial:
            self.fields["fuel_type"].initial = self.initial.get("fuel_type")

    def clean_fuel_type(self):
        fuel_type = self.cleaned_data.get("fuel_type")
        if fuel_type not in self.available_fuel_types:
            raise forms.ValidationError(
                "El tipo de combustible seleccionado no es válido para la sucursal."
            )
        return fuel_type

    class Meta:
        model = FuelPrice
        fields = ["sucursal", "fuel_type", "price"]
        widgets = {
            "price": forms.NumberInput(
                attrs={
                    "class": "w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "Ej: 1200.50",
                }
            )
        }


class BranchProductForm(forms.ModelForm):
    class Meta:
        model = BranchProduct
        fields = [
            "sucursal",
            "product_type",
            "quantity",
            "arrival_date",
            "batch_number",
            "value",
        ]
        widgets = {
            "sucursal": forms.HiddenInput(),
            "product_type": forms.TextInput(
                attrs={"class": "w-full border rounded p-2"}
            ),
            "quantity": forms.NumberInput(
                attrs={"class": "w-full border rounded p-2", "min": "0"}
            ),
            "arrival_date": forms.DateInput(
                attrs={"class": "w-full border rounded p-2", "type": "date"}
            ),
            "batch_number": forms.TextInput(
                attrs={"class": "w-full border rounded p-2"}
            ),
            "value": forms.NumberInput(
                attrs={"class": "w-full border rounded p-2", "step": "0.01"}
            ),
        }


class ServiceSessionFuelLoadForm(forms.ModelForm):
    class Meta:
        model = ServiceSessionFuelLoad
        fields = [
            "inventory",
            "liters_added",
            "payment_amount",
            "invoice_number",
            "responsible",
            "driver_name",
            "license_plate",
            "date",
        ]
        widgets = {
            "inventory": forms.Select(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                }
            ),
            "liters_added": forms.NumberInput(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "payment_amount": forms.NumberInput(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "invoice_number": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                }
            ),
            "responsible": forms.HiddenInput(),
            "driver_name": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                }
            ),
            "license_plate": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                }
            ),
            "date": forms.HiddenInput(),
        }

    def __init__(self, *args, service_session: ServiceSession, **kwargs):
        self.service_session = service_session
        super().__init__(*args, **kwargs)
        branch = service_session.shift.sucursal
        self.fields["inventory"].queryset = branch.fuel_inventories.all()
        manager = service_session.shift.manager
        if manager:
            self.initial.setdefault("responsible", manager.pk)
        self.initial.setdefault("date", service_session.started_at.date())

    def clean_inventory(self):
        inventory = self.cleaned_data.get("inventory")
        if not inventory:
            return inventory
        branch = self.service_session.shift.sucursal
        if inventory.sucursal_id != branch.pk:
            raise forms.ValidationError(
                "El inventario seleccionado no pertenece a la sucursal del servicio."
            )
        return inventory

    def clean_responsible(self):
        responsible = self.cleaned_data.get("responsible")
        manager = self.service_session.shift.manager
        if manager is None:
            raise forms.ValidationError(
                "El servicio no tiene un encargado asignado."
            )
        if responsible != manager:
            raise forms.ValidationError(
                "El responsable debe coincidir con el encargado del turno."
            )
        return responsible

    def clean_liters_added(self):
        liters = self.cleaned_data.get("liters_added")
        if liters is not None and liters <= 0:
            raise forms.ValidationError("Debes ingresar una cantidad de litros mayor a 0.")
        return liters

    def clean_payment_amount(self):
        amount = self.cleaned_data.get("payment_amount")
        if amount is not None and amount < 0:
            raise forms.ValidationError("El valor pagado no puede ser negativo.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        inventory = cleaned_data.get("inventory")
        liters = cleaned_data.get("liters_added")
        if inventory and liters is not None:
            projected_total = inventory.liters + liters
            if projected_total > inventory.capacity:
                raise forms.ValidationError(
                    "La carga supera la capacidad máxima del tanque seleccionado."
                )
        return cleaned_data

    def clean_date(self):
        date = self.cleaned_data.get("date")
        expected_date = self.service_session.started_at.date()
        if date and date != expected_date:
            raise forms.ValidationError(
                "La fecha debe coincidir con la fecha del servicio."
            )
        return expected_date

    def save(self, commit: bool = True):
        instance: ServiceSessionFuelLoad = super().save(commit=False)
        instance.service_session = self.service_session
        instance.responsible = self.service_session.shift.manager
        instance.date = self.service_session.started_at.date()

        if commit:
            with transaction.atomic():
                instance.save()
                FuelInventory.objects.filter(pk=instance.inventory.pk).update(
                    liters=F("liters") + instance.liters_added
                )
                instance.inventory.refresh_from_db(fields=["liters"])
        return instance


class ServiceSessionProductLoadForm(forms.ModelForm):
    class Meta:
        model = ServiceSessionProductLoad
        fields = [
            "product",
            "quantity_added",
            "payment_amount",
        ]
        widgets = {
            "product": forms.Select(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                }
            ),
            "quantity_added": forms.NumberInput(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                    "min": "1",
                }
            ),
            "payment_amount": forms.NumberInput(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                    "step": "0.01",
                    "min": "0",
                }
            ),
        }

    def __init__(self, *args, service_session: ServiceSession, **kwargs):
        self.service_session = service_session
        super().__init__(*args, **kwargs)
        branch = service_session.shift.sucursal
        self.fields["product"].queryset = branch.products.all()

    def clean(self):
        cleaned_data = super().clean()
        if self.service_session.shift.manager is None:
            raise forms.ValidationError(
                "El servicio no tiene un encargado asignado."
            )
        return cleaned_data

    def clean_product(self):
        product = self.cleaned_data.get("product")
        if not product:
            return product
        branch = self.service_session.shift.sucursal
        if product.sucursal_id != branch.pk:
            raise forms.ValidationError(
                "El producto seleccionado no pertenece a la sucursal del servicio."
            )
        return product

    def clean_quantity_added(self):
        quantity = self.cleaned_data.get("quantity_added")
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError(
                "Debes ingresar una cantidad mayor a 0."
            )
        return quantity

    def clean_payment_amount(self):
        amount = self.cleaned_data.get("payment_amount")
        if amount is not None and amount < 0:
            raise forms.ValidationError("El valor pagado no puede ser negativo.")
        return amount

    def save(self, commit: bool = True):
        instance: ServiceSessionProductLoad = super().save(commit=False)
        instance.service_session = self.service_session
        manager = self.service_session.shift.manager
        instance.responsible = manager
        instance.date = self.service_session.started_at.date()

        if commit:
            with transaction.atomic():
                instance.save()
                BranchProduct.objects.filter(pk=instance.product.pk).update(
                    quantity=F("quantity") + instance.quantity_added
                )
                instance.product.refresh_from_db(fields=["quantity"])
        return instance


class ServiceSessionProductSaleItemForm(forms.ModelForm):
    class Meta:
        model = ServiceSessionProductSaleItem
        fields = [
            "product",
            "quantity",
        ]
        widgets = {
            "product": forms.Select(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                }
            ),
            "quantity": forms.NumberInput(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                    "min": "1",
                }
            ),
        }

    def __init__(self, *args, service_session: ServiceSession, **kwargs):
        self.service_session = service_session
        super().__init__(*args, **kwargs)
        branch = service_session.shift.sucursal
        self.fields["product"].queryset = branch.products.all()

    def clean(self):
        cleaned_data = super().clean()
        product: Optional[BranchProduct] = cleaned_data.get("product")
        quantity = cleaned_data.get("quantity")

        if not product and not quantity:
            return cleaned_data

        if not product:
            raise forms.ValidationError("Debes seleccionar un producto válido.")

        if quantity is None or quantity <= 0:
            raise forms.ValidationError("Debes ingresar una cantidad mayor a 0.")

        if quantity > product.quantity:
            raise forms.ValidationError(
                "La cantidad solicitada supera el stock disponible en la sucursal.",
            )

        if product.sucursal_id != self.service_session.shift.sucursal_id:
            raise forms.ValidationError(
                "El producto seleccionado no pertenece a la sucursal del servicio.",
            )

        return cleaned_data


class BaseServiceSessionProductSaleItemFormSet(forms.BaseModelFormSet):
    def __init__(self, *args, service_session: ServiceSession, **kwargs):
        self.service_session = service_session
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs.setdefault("service_session", self.service_session)
        return kwargs

    def _construct_form(self, i, **kwargs):
        kwargs.setdefault("service_session", self.service_session)
        return super()._construct_form(i, **kwargs)

    def clean(self):
        super().clean()
        has_data = False
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                has_data = True
                break
        if not has_data:
            raise forms.ValidationError(
                "Debes agregar al menos un producto para registrar la venta.",
            )


ServiceSessionProductSaleItemFormSet = forms.modelformset_factory(
    ServiceSessionProductSaleItem,
    form=ServiceSessionProductSaleItemForm,
    formset=BaseServiceSessionProductSaleItemFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
)


class ServiceSessionProductSaleForm(forms.ModelForm):
    class Meta:
        model = ServiceSessionProductSale
        fields: list[str] = []

    def __init__(
        self,
        *args,
        service_session: ServiceSession,
        responsible_profile: Optional[Profile] = None,
        **kwargs,
    ):
        self.service_session = service_session
        self.responsible_profile: Optional[Profile] = responsible_profile
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if self.responsible_profile is None:
            raise forms.ValidationError(
                "El servicio no tiene un encargado asignado."
            )
        return cleaned_data

    def save(self, commit: bool = True):
        instance: ServiceSessionProductSale = super().save(commit=False)
        instance.service_session = self.service_session
        instance.responsible = self.responsible_profile
        if commit:
            instance.save()
        return instance


class ServiceSessionCreditSaleForm(forms.ModelForm):
    class Meta:
        model = ServiceSessionCreditSale
        fields = [
            "invoice_number",
            "customer_name",
            "fuel_inventory",
            "amount",
        ]
        widgets = {
            "invoice_number": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                    "placeholder": "Ej: 000123",
                }
            ),
            "customer_name": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                    "placeholder": "Nombre del cliente",
                }
            ),
            "fuel_inventory": forms.Select(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                }
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                    "min": "1",
                    "step": "0.01",
                }
            ),
        }

    def __init__(
        self,
        *args,
        service_session: ServiceSession,
        responsible_profile: Optional[Profile] = None,
        **kwargs,
    ):
        self.service_session = service_session
        self.responsible_profile = responsible_profile
        super().__init__(*args, **kwargs)
        branch = service_session.shift.sucursal
        self.fields["fuel_inventory"].queryset = branch.fuel_inventories.all()
        self.fields["fuel_inventory"].empty_label = "Selecciona un estanque"

    def clean_fuel_inventory(self):
        fuel_inventory = self.cleaned_data.get("fuel_inventory")
        if not fuel_inventory:
            return fuel_inventory
        if fuel_inventory.sucursal_id != self.service_session.shift.sucursal_id:
            raise forms.ValidationError(
                "El estanque seleccionado no pertenece a la sucursal del servicio.",
            )
        return fuel_inventory

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError(
                "Debes ingresar un monto mayor a 0.",
            )
        return amount

    def clean(self):
        cleaned_data = super().clean()
        if self.responsible_profile is None:
            raise forms.ValidationError(
                "No hay un responsable disponible para registrar la venta a crédito.",
            )
        return cleaned_data

    def save(self, commit: bool = True):
        instance: ServiceSessionCreditSale = super().save(commit=False)
        instance.service_session = self.service_session
        instance.responsible = self.responsible_profile  # type: ignore[assignment]
        if commit:
            instance.save()
        return instance


class ServiceSessionWithdrawalForm(forms.ModelForm):
    amount = forms.CharField(
        label="Monto de la tirada",
        widget=forms.TextInput(
            attrs={
                "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                "inputmode": "decimal",
                "placeholder": "Ej: 150000",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = ServiceSessionWithdrawal
        fields = ["amount"]
        widgets = {}

    def __init__(
        self,
        *args,
        service_session: ServiceSession,
        responsible_profile: Optional[Profile],
        **kwargs,
    ):
        self.service_session = service_session
        self.responsible_profile = responsible_profile
        super().__init__(*args, **kwargs)

    def _normalize_amount_input(self, raw_value: str) -> str:
        cleaned = str(raw_value)
        for char in ("$", " ", " ", " "):
            cleaned = cleaned.replace(char, "")
        cleaned = cleaned.strip()
        if not cleaned:
            return ""
        if "," in cleaned:
            cleaned = cleaned.replace(".", "")
            cleaned = cleaned.replace(",", ".")
            return cleaned
        dot_count = cleaned.count(".")
        if dot_count > 1:
            return cleaned.replace(".", "")
        if dot_count == 1:
            integer_part, decimal_part = cleaned.split(".")
            if len(decimal_part) == 3 and integer_part:
                return integer_part + decimal_part
        return cleaned

    def clean_amount(self):
        raw_value = self.data.get(self.add_prefix("amount"), "") or ""
        if isinstance(raw_value, (list, tuple)):
            raw_value = raw_value[0]
        normalized_value = self._normalize_amount_input(str(raw_value))
        if not normalized_value:
            raise forms.ValidationError("Debes ingresar un monto para la tirada.")
        try:
            amount = Decimal(normalized_value)
        except InvalidOperation:
            raise forms.ValidationError("Ingresa un monto válido usando solo números.")
        if amount <= 0:
            raise forms.ValidationError("El monto debe ser mayor a 0.")
        return amount.quantize(Decimal("0.01"))

    def clean(self):
        cleaned_data = super().clean()
        if self.responsible_profile is None:
            raise forms.ValidationError(
                "No se puede registrar la tirada porque no se encontró un encargado asignado."
            )
        return cleaned_data

    def save(self, commit: bool = True):
        instance: ServiceSessionWithdrawal = super().save(commit=False)
        instance.service_session = self.service_session
        instance.responsible = self.responsible_profile  # type: ignore[assignment]
        if commit:
            instance.save()
        return instance


class ServiceSessionTransbankVoucherForm(forms.ModelForm):
    total_amount = forms.CharField(
        label="Monto total",
        widget=forms.TextInput(
            attrs={
                "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                "inputmode": "decimal",
                "placeholder": "Ej: 200000",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = ServiceSessionTransbankVoucher
        fields = ["total_amount"]

    def __init__(
        self,
        *args,
        service_session: ServiceSession,
        responsible_profile: Optional[Profile],
        **kwargs,
    ):
        self.service_session = service_session
        self.responsible_profile = responsible_profile
        super().__init__(*args, **kwargs)

    def _normalize_amount_input(self, raw_value: str) -> str:
        cleaned = str(raw_value)
        for char in ("$", " ", " ", " "):
            cleaned = cleaned.replace(char, "")
        cleaned = cleaned.strip()
        if not cleaned:
            return ""
        if "," in cleaned:
            cleaned = cleaned.replace(".", "")
            cleaned = cleaned.replace(",", ".")
            return cleaned
        dot_count = cleaned.count(".")
        if dot_count > 1:
            return cleaned.replace(".", "")
        if dot_count == 1:
            integer_part, decimal_part = cleaned.split(".")
            if len(decimal_part) == 3 and integer_part:
                return integer_part + decimal_part
        return cleaned

    def clean_total_amount(self):
        raw_value = self.data.get(self.add_prefix("total_amount"), "") or ""
        if isinstance(raw_value, (list, tuple)):
            raw_value = raw_value[0]
        normalized_value = self._normalize_amount_input(str(raw_value))
        if not normalized_value:
            raise forms.ValidationError("Debes ingresar el monto total de los vouchers.")
        try:
            amount = Decimal(normalized_value)
        except InvalidOperation:
            raise forms.ValidationError("Ingresa un monto válido usando solo números.")
        if amount <= 0:
            raise forms.ValidationError("El monto debe ser mayor a 0.")
        return amount.quantize(Decimal("0.01"))

    def clean(self):
        cleaned_data = super().clean()
        if self.responsible_profile is None:
            raise forms.ValidationError(
                "No se puede registrar porque no se encontró un encargado asignado."
            )
        return cleaned_data

    def save(self, commit: bool = True):
        instance: ServiceSessionTransbankVoucher = super().save(commit=False)
        instance.service_session = self.service_session
        instance.responsible = self.responsible_profile  # type: ignore[assignment]
        if commit:
            instance.save()
        return instance


class ServiceSessionFirefighterPaymentForm(forms.Form):
    """Formulario para registrar pagos a bomberos part-time del servicio."""

    amount_widget_attrs = {
        "class": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
        "inputmode": "decimal",
        "placeholder": "Ej: 25000",
        "autocomplete": "off",
    }

    def __init__(
        self,
        *args,
        service_session: ServiceSession,
        firefighters: list[Profile],
        **kwargs,
    ):
        self.service_session = service_session
        self.firefighters = firefighters
        super().__init__(*args, **kwargs)

        for firefighter in firefighters:
            field_name = self._field_name(firefighter)
            self.fields[field_name] = forms.CharField(
                label="Monto a pagar",
                required=False,
                widget=forms.TextInput(attrs=self.amount_widget_attrs),
            )

    def _field_name(self, firefighter: Profile) -> str:
        return f"amount_{firefighter.pk}"

    def get_field_name(self, firefighter: Profile) -> str:
        return self._field_name(firefighter)

    def get_bound_field(self, firefighter: Profile):
        return self[self._field_name(firefighter)]

    def _normalize_amount_input(self, raw_value: str) -> str:
        cleaned = str(raw_value)
        for char in ("$", " ", " ", " "):
            cleaned = cleaned.replace(char, "")
        cleaned = cleaned.strip()
        if not cleaned:
            return ""
        if "," in cleaned:
            cleaned = cleaned.replace(".", "")
            cleaned = cleaned.replace(",", ".")
            return cleaned
        dot_count = cleaned.count(".")
        if dot_count > 1:
            return cleaned.replace(".", "")
        if dot_count == 1:
            integer_part, decimal_part = cleaned.split(".")
            if len(decimal_part) == 3 and integer_part:
                return integer_part + decimal_part
        return cleaned

    def clean(self):
        cleaned_data = super().clean()
        self.cleaned_payments: list[tuple[Profile, Decimal]] = []

        if not self.firefighters:
            raise forms.ValidationError(
                "No hay bomberos part-time disponibles para registrar pagos.",
            )

        for firefighter in self.firefighters:
            field_name = self._field_name(firefighter)
            raw_value = self.data.get(self.add_prefix(field_name), "") or ""
            normalized_value = self._normalize_amount_input(str(raw_value))

            if not normalized_value:
                continue

            try:
                amount = Decimal(normalized_value)
            except InvalidOperation:
                self.add_error(field_name, "Ingresa un monto válido usando solo números.")
                continue

            if amount <= 0:
                self.add_error(field_name, "El monto debe ser mayor a 0.")
                continue

            self.cleaned_payments.append(
                (firefighter, amount.quantize(Decimal("0.01")))
            )

        if not self.cleaned_payments and not self.errors:
            raise forms.ValidationError(
                "Debes ingresar al menos un pago para registrar.",
            )

        return cleaned_data

    def save(self):
        payments = []
        for firefighter, amount in self.cleaned_payments:
            payments.append(
                ServiceSessionFirefighterPayment.objects.create(
                    service_session=self.service_session,
                    firefighter=firefighter,
                    amount=amount,
                )
            )
        return payments



class MachineInventoryClosingForm(forms.Form):
    machine_id = forms.IntegerField(widget=forms.HiddenInput())
    fuel_inventory_id = forms.IntegerField(widget=forms.HiddenInput())
    slot = forms.IntegerField(widget=forms.HiddenInput())
    # Use a custom DecimalField that normalizes common user input formats
    # (thousands separators and comma as decimal separator) before parsing.
    class NormalizedDecimalField(forms.DecimalField):
        def to_python(self, value):
            if value in self.empty_values:
                return None
            # Keep original if already a Decimal or numeric type
            if not isinstance(value, str):
                return super().to_python(value)

            cleaned = value.strip()
            # remove currency symbols and non-breaking spaces
            for ch in ("$", " ", "\u202f"):
                cleaned = cleaned.replace(ch, "")
            if not cleaned:
                return None

            # If comma appears, assume it is the decimal separator and dots are thousands
            if "," in cleaned:
                cleaned = cleaned.replace(".", "")
                cleaned = cleaned.replace(",", ".")
            else:
                # If multiple dots, assume they are thousands separators and remove them
                if cleaned.count(".") > 1:
                    cleaned = cleaned.replace(".", "")

            return super().to_python(cleaned)

    numeral = NormalizedDecimalField(
        label="Numeral",
        max_digits=12,
        decimal_places=2,
    )

    def __init__(
        self,
        *args,
        machine: Machine | None = None,
        fuel_inventory: FuelInventory | None = None,
        current_numeral: Decimal | None = None,
        numeral_entry: MachineFuelInventoryNumeral | None = None,
        pistol_dispensed_total: Decimal | None = None,
        **kwargs,
    ):
        self.machine = machine
        self.fuel_inventory = fuel_inventory
        self.current_numeral = current_numeral or Decimal("0")
        self.numeral_entry = numeral_entry
        self.pistol_dispensed_total = pistol_dispensed_total or Decimal("0")
        super().__init__(*args, **kwargs)
        if machine:
            self.fields["machine_id"].initial = machine.pk
        if fuel_inventory:
            self.fields["fuel_inventory_id"].initial = fuel_inventory.pk
            nozzle_codes: list[str] = []
            if numeral_entry:
                nozzle_codes = [
                    str(code)
                    for code in numeral_entry.nozzles.order_by("number").values_list(
                        "number", flat=True
                    )
                ]

            slot_label = numeral_entry.slot if numeral_entry else 1
            label_suffix = (
                f"Pistola(s) {', '.join(nozzle_codes)}" if nozzle_codes else f"Numeral #{slot_label}"
            )
            self.fields["numeral"].label = (
                f"Máquina {machine.number} · Estanque {fuel_inventory.code}"
                f" · {label_suffix}"
            )
        if numeral_entry:
            self.fields["slot"].initial = numeral_entry.slot
        self.fields["numeral"].initial = self.current_numeral
        default_numeral = self.current_numeral or Decimal("0")
        pistol_numeral = default_numeral + self.pistol_dispensed_total
        self.fields["numeral"].widget.attrs.update(
            {
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-right",
                "inputmode": "decimal",
                "data-default-numeral": f"{default_numeral}",
                "data-pistol-dispensed": f"{self.pistol_dispensed_total}",
                "data-pistol-numeral": f"{pistol_numeral}",
                "x-bind:readonly": "closeSessionMode === 'pistola'",
                "x-on:input": "if (closeSessionMode === 'numeral') { $el.dataset.defaultNumeral = $el.value }",
                "x-effect": (
                    "if (closeSessionMode === 'pistola') { $el.value = $el.dataset.pistolNumeral || '' } "
                    "else { $el.value = $el.dataset.defaultNumeral || '' }"
                ),
            }
        )
        
    def clean_numeral(self):
        value = self.cleaned_data.get("numeral")
        if value is None:
            return value
        if value < 0:
            raise forms.ValidationError("El numeral debe ser mayor o igual a 0.")
        if value < self.current_numeral:
            raise forms.ValidationError(
                "El numeral no puede ser menor al valor registrado actualmente."
            )
        return value


class MachineInventoryClosingFormSet(BaseFormSet):
    def __init__(
        self,
        *args,
        machine_inventory_pairs: list[
            tuple[Machine, FuelInventory, MachineFuelInventoryNumeral]
        ]
        | None = None,
        pistol_dispense_totals: dict[int, Decimal] | None = None,
        **kwargs,
    ):
        self.machine_inventory_pairs = machine_inventory_pairs or []
        self.pistol_dispense_totals = pistol_dispense_totals or {}
        kwargs.setdefault("initial", [{} for _ in self.machine_inventory_pairs])
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        machine = None
        fuel_inventory = None
        current_numeral = None
        numeral_entry = None
        if self.machine_inventory_pairs and i < len(self.machine_inventory_pairs):
            machine, fuel_inventory, numeral_entry = self.machine_inventory_pairs[i]
            current_numeral = numeral_entry.numeral if numeral_entry else None
            pistol_total = self.pistol_dispense_totals.get(
                numeral_entry.pk if numeral_entry else None, Decimal("0")
            )
        kwargs.update(
            {
                "machine": machine,
                "fuel_inventory": fuel_inventory,
                "current_numeral": current_numeral,
                "numeral_entry": numeral_entry,
                "pistol_dispensed_total": pistol_total,
            }
        )
        return super()._construct_form(i, **kwargs)


ServiceSessionMachineInventoryClosingFormSet = formset_factory(
    MachineInventoryClosingForm, formset=MachineInventoryClosingFormSet, extra=0
)