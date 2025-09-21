from typing import Optional

from django import forms

from UsuarioApp.models import Profile

from .models import Sucursal


class SucursalForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "w-full border rounded p-2"}),
        label="Usuarios asociados",
    )

    class Meta:
        model = Sucursal
        fields = [
            "name",
            "address",
            "city",
            "region",
            "phone",
            "email",
            "islands",
            "users",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "address": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "city": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "region": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "phone": forms.TextInput(attrs={"class": "w-full border rounded p-2"}),
            "email": forms.EmailInput(attrs={"class": "w-full border rounded p-2"}),
            "islands": forms.NumberInput(attrs={"class": "w-full border rounded p-2"}),
        }

    def __init__(self, *args, company: Optional["homeApp.models.Company"] = None, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)
        queryset = Profile.objects.all()
        if company is not None:
            queryset = queryset.filter(company_rut=company.rut)
        self.fields["users"].queryset = queryset.order_by("user_FK__username")

    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        if self.company is not None:
            instance.company = self.company
        if commit:
            instance.save()
            self.save_m2m()
        return instance