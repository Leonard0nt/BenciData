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
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False