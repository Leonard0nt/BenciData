from django import forms

from homeApp.models import Company


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["rut", "business_name", "tax_address"]
        labels = {
            "rut": "RUT",
            "business_name": "Razón social",
            "tax_address": "Dirección tributaria",
        }
        widgets = {
            "rut": forms.TextInput(
                attrs={
                    "class": "bg-white focus:outline-none border border-gray-300 rounded-lg py-2 px-4 block w-full leading-normal text-gray-700 mb-3",
                    "placeholder": "12.345.678-9",
                }
            ),
            "business_name": forms.TextInput(
                attrs={
                    "class": "bg-white focus:outline-none border border-gray-300 rounded-lg py-2 px-4 block w-full leading-normal text-gray-700 mb-3",
                    "placeholder": "Nombre de la empresa",
                }
            ),
            "tax_address": forms.TextInput(
                attrs={
                    "class": "bg-white focus:outline-none border border-gray-300 rounded-lg py-2 px-4 block w-full leading-normal text-gray-700 mb-3",
                    "placeholder": "Dirección tributaria",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
    def save(self, commit=True):
        company = super().save(commit=False)

        if self.user and hasattr(self.user, "profile"):
            profile = self.user.profile

            # asociar empresa al dueño (si no existe)
            if not company.profile_id:
                company.profile = profile

            # asignar rut al dueño
            profile.company_rut = company.rut
            profile.save(update_fields=["company_rut"])

        if commit:
            company.save()

        return company