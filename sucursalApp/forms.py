from typing import Optional

from django import forms

from UsuarioApp.models import Profile

from .models import (
    FuelInventory,
    Island,
    Machine,
    Nozzle,
    Shift,
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
        self.fields["manager"].queryset = queryset.order_by(
            "user_FK__first_name", "user_FK__last_name", "user_FK__username"
        )
        attendants_field = self.fields.get("attendants")
        if attendants_field is not None:
            attendants_queryset = queryset.filter(
                position_FK__permission_code__in=["ATTENDANT", "HEAD_ATTENDANT"]
            )
            attendants_field.queryset = attendants_queryset.order_by(
                "user_FK__first_name", "user_FK__last_name", "user_FK__username"
            )
    class Meta:
        model = Shift
        fields = [
            "sucursal",
            "code",
            "description",
            "start_time",
            "end_time",
            "manager",
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
            "manager": forms.Select(attrs={"class": "w-full border rounded p-2"}),
        }
            "attendants": forms.SelectMultiple(
                attrs={"class": "w-full border rounded p-2"}
            ),
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