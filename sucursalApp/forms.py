from typing import Optional

from django import forms

from UsuarioApp.models import Profile
from django.db.models import Q, Count

from .models import (
    BranchProduct,
    FuelInventory,
    Island,
    Machine,
    Nozzle,
    Shift,
    ServiceSession,
    Sucursal,
    SucursalStaff,
)

class SucursalForm(forms.ModelForm):
    administrators = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "w-full border rounded p-2"}),
        label="Administradores",
    )
    accountants = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "w-full border rounded p-2"}),
        label="Contadores",
    )
    firefighters = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "w-full border rounded p-2"}),
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
        queryset = Profile.objects.select_related("position_FK", "user_FK")
        if company is not None:
            queryset = queryset.filter(company_rut=company.rut)
        for field_name, roles in self.STAFF_ROLE_FIELDS.items():
            field_queryset = queryset.filter(position_FK__permission_code__in=roles)
            self.fields[field_name].queryset = field_queryset.order_by("user_FK__username")
            if self.instance.pk:
                initial_ids = self.instance.staff.filter(role__in=roles).values_list(
                    "profile_id", flat=True
                )
                self.fields[field_name].initial = list(initial_ids)

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
    class Meta:
        model = Machine
        fields = [
            "island",
            "number",
            "initial_numeral",
            "final_numeral",
            "fuel_type",
            "description",
        ]
        widgets = {
            "island": forms.HiddenInput(),
            "number": forms.NumberInput(attrs={"class": "w-full border rounded p-2"}),
            "initial_numeral": forms.NumberInput(attrs={"class": "w-full border rounded p-2"}),
            "final_numeral": forms.NumberInput(attrs={"class": "w-full border rounded p-2"}),
            "fuel_type": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "description": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
        }


class NozzleForm(forms.ModelForm):
    class Meta:
        model = Nozzle
        fields = [
            "machine",
            "number",
            "fuel_type",
            "description",
        ]
        widgets = {
            "machine": forms.HiddenInput(),
            "number": forms.NumberInput(attrs={"class": "w-full border rounded p-2"}),
            "fuel_type": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
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
                attrs={"class": "attendant-checkboxes grid gap-2 sm:grid-cols-2"}
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
        widget=forms.SelectMultiple(
            attrs={
                "class": "w-full border rounded p-2 min-h-[10rem]",
                "size": "10",
            }
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
            position_FK__permission_code__in=("ATTENDANT", "HEAD_ATTENDANT")
        )

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

        if combined_ids:
            self.fields["attendants"].queryset = base_queryset.filter(pk__in=combined_ids).order_by(
                "user_FK__first_name",
                "user_FK__last_name",
                "user_FK__username",
            )
        else:
            self.fields["attendants"].queryset = base_queryset.none()

        if current_ids:
            self.fields["attendants"].initial = current_ids

        self.current_attendants = list(current_attendants_qs)
        self.available_replacements = list(
            base_queryset.filter(pk__in=available_ids).order_by(
                "user_FK__first_name",
                "user_FK__last_name",
                "user_FK__username",
            )
        )

    def clean_attendants(self):
        attendants = self.cleaned_data.get("attendants")
        if not attendants:
            raise forms.ValidationError(
                "Debes seleccionar al menos un bombero para iniciar el turno."
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