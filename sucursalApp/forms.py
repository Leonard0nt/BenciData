from typing import Optional

from django import forms

from UsuarioApp.models import Profile

from .models import (
    Island,
    Machine,
    Nozzle,
    Shift,
    ShiftAssignment,
    ShiftSchedule,
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
            "initial_numeral",
            "final_numeral",
            "fuel_type",
            "description",
        ]
        widgets = {
            "machine": forms.HiddenInput(),
            "number": forms.NumberInput(attrs={"class": "w-full border rounded p-2"}),
            "initial_numeral": forms.NumberInput(attrs={"class": "w-full border rounded p-2"}),
            "final_numeral": forms.NumberInput(attrs={"class": "w-full border rounded p-2"}),
            "fuel_type": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "description": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
        }


class ShiftForm(forms.ModelForm):
    days_of_week = forms.MultipleChoiceField(
        required=False,
        choices=[(str(day), label) for day, label in ShiftSchedule.DAYS_OF_WEEK],
        widget=forms.CheckboxSelectMultiple,
        label="Días de la semana",
        help_text="Seleccione los días en los que aplica el turno.",
    )
    start_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"class": "w-full border rounded p-2", "type": "time"}),
        label="Hora de inicio",
    )
    end_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"class": "w-full border rounded p-2", "type": "time"}),
        label="Hora de término",
    )

    class Meta:
        model = Shift
        fields = ["sucursal", "name", "description"]
        widgets = {
            "sucursal": forms.Select(attrs={"class": "w-full border rounded p-2"}),
            "name": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "description": forms.Textarea(
                attrs={"class": "w-full border rounded p-2", "rows": 3}
            ),
        }

    def __init__(self, *args, company: Optional["homeApp.models.Company"] = None, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)
        queryset = Sucursal.objects.all()
        if company is not None:
            queryset = queryset.filter(company=company)
        self.fields["sucursal"].queryset = queryset.order_by("name")

        if self.instance.pk:
            schedules = list(self.instance.schedules.all())
            self.fields["days_of_week"].initial = [
                str(schedule.day_of_week) for schedule in schedules
            ]
            if schedules:
                self.fields["start_time"].initial = schedules[0].start_time
                self.fields["end_time"].initial = schedules[0].end_time

    def clean(self):
        cleaned_data = super().clean()
        days = cleaned_data.get("days_of_week") or []
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        if days and (start_time is None or end_time is None):
            raise forms.ValidationError(
                "Debe definir la hora de inicio y término para los días seleccionados."
            )
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(
                "La hora de término debe ser posterior a la hora de inicio."
            )
        return cleaned_data

    def save(self, commit: bool = True):
        instance = super().save(commit)
        if commit:
            self._save_schedules(instance)
        else:
            self._pending_schedule_save = True
        return instance

    def save_m2m(self):
        super().save_m2m()
        if getattr(self, "_pending_schedule_save", False):
            self._save_schedules(self.instance)
            self._pending_schedule_save = False

    def _save_schedules(self, instance: Shift) -> None:
        days = self.cleaned_data.get("days_of_week") or []
        start_time = self.cleaned_data.get("start_time")
        end_time = self.cleaned_data.get("end_time")

        selected_days = {int(day) for day in days}
        instance.schedules.exclude(day_of_week__in=selected_days).delete()

        for day in selected_days:
            ShiftSchedule.objects.update_or_create(
                shift=instance,
                day_of_week=day,
                defaults={"start_time": start_time, "end_time": end_time},
            )


class ShiftAssignmentForm(forms.ModelForm):
    class Meta:
        model = ShiftAssignment
        fields = [
            "sucursal",
            "shift",
            "profile",
            "start_date",
            "end_date",
            "is_active",
        ]
        widgets = {
            "sucursal": forms.Select(attrs={"class": "w-full border rounded p-2"}),
            "shift": forms.Select(attrs={"class": "w-full border rounded p-2"}),
            "profile": forms.Select(attrs={"class": "w-full border rounded p-2"}),
            "start_date": forms.DateInput(
                attrs={"class": "w-full border rounded p-2", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "w-full border rounded p-2", "type": "date"}
            ),
        }

    def __init__(
        self,
        *args,
        company: Optional["homeApp.models.Company"] = None,
        sucursal: Optional[Sucursal] = None,
        **kwargs,
    ):
        self.company = company
        self.sucursal = sucursal
        super().__init__(*args, **kwargs)

        sucursal_queryset = Sucursal.objects.all()
        if company is not None:
            sucursal_queryset = sucursal_queryset.filter(company=company)
        self.fields["sucursal"].queryset = sucursal_queryset.order_by("name")

        if sucursal is not None:
            self.fields["sucursal"].initial = sucursal
            self.fields["sucursal"].queryset = sucursal_queryset.filter(pk=sucursal.pk)

        shift_queryset = Shift.objects.select_related("sucursal")
        if sucursal is not None:
            shift_queryset = shift_queryset.filter(sucursal=sucursal)
        elif company is not None:
            shift_queryset = shift_queryset.filter(sucursal__company=company)
        self.fields["shift"].queryset = shift_queryset.order_by("name")

        profile_queryset = Profile.objects.select_related("user_FK", "position_FK")
        if sucursal is not None:
            profile_queryset = profile_queryset.filter(
                sucursal_staff__sucursal=sucursal
            ).distinct()
        elif company is not None:
            profile_queryset = profile_queryset.filter(company_rut=company.rut)
        self.fields["profile"].queryset = profile_queryset.order_by("user_FK__username")

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError(
                "La fecha de término no puede ser anterior a la fecha de inicio."
            )
        shift = cleaned_data.get("shift")
        sucursal = cleaned_data.get("sucursal")
        if shift and sucursal and shift.sucursal_id != sucursal.id:
            raise forms.ValidationError(
                "El turno seleccionado pertenece a otra sucursal."
            )
        return cleaned_data