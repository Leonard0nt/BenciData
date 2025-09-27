import os

import requests
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm,  PasswordChangeForm
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from allauth.account.forms import LoginForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div

from homeApp.models import Company
from .models import Profile, Position
from sucursalApp.models import Sucursal
from .choices import GENDER_CHOICES


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].widget.attrs.pop("autofocus", None)

class CustomLoginForm(LoginForm):
    login = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"autofocus": "autofocus"})
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password"].label = "Contraseña"

class UserUpdateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

        self.helper.layout = Layout(
            "username",
            "email",
            Div(
                Div("first_name", css_class="flex-1"),
                Div("last_name",  css_class="flex-1"),
                css_class="flex gap-4",
            ),
        )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
        ]


class UserCreateForm(UserCreationForm, UserUpdateForm):
    password1 = forms.PasswordInput()
    password2 = forms.PasswordInput()

    class Meta:
        model = User
        fields = UserUpdateForm.Meta.fields + ["password1", "password2"]

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        validate_password(password1)
        return password1

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords do not match")

        return cleaned_data


class ProfileUpdateForm(forms.ModelForm):
    image = forms.ImageField(
        label="Imagen",
        widget=forms.FileInput(attrs={"class": "hidden", "id": "id_image"}),
        required=False,
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        label="Teléfono",
        widget=forms.TextInput(
            attrs={
                "class": "bg-white focus:outline-none border border-gray-300 rounded-lg py-2 px-4 block w-full leading-normal text-gray-700 mb-3"
            }
        ),
    )
    gender = forms.ChoiceField(
        choices=GENDER_CHOICES,
        required=False,
        label="Sexo",
        widget=forms.Select(
            attrs={
                "class": "bg-white focus:outline-none border border-gray-300 rounded-lg py-2 px-4 block w-full leading-normal text-gray-700 mb-3"
            }
        ),
    )
    date_of_birth = forms.DateField(
        required=False,
        label="Fecha de nacimiento",
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "date",
                "class": "bg-white focus:outline-none border border-gray-300 rounded-lg py-2 px-4 block w-full leading-normal text-gray-700 mb-3",
            }
        ),
        input_formats=["%Y-%m-%d"],
    )
    salario = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label="Salario",
        widget=forms.NumberInput(
            attrs={
                "class": "bg-white focus:outline-none border border-gray-300 rounded-lg py-2 px-4 block w-full leading-normal text-gray-700 mb-3"
            }
        ),
    )
    is_partime = forms.TypedChoiceField(
        choices=[(True, "Tiempo completo"), (False, "Medio tiempo")],
        coerce=lambda x: x == "True",
        required=False,
        label="Tipo de jornada",
        widget=forms.Select(
            attrs={
                "class": "bg-white focus:outline-none border border-gray-300 rounded-lg py-2 px-4 block w-full leading-normal text-gray-700 mb-3"
            }
        ),
    )
    current_branch = forms.ModelChoiceField(
        label="Sucursal",
        queryset=Sucursal.objects.none(),
        required=False,
        widget=forms.Select(
            attrs={
                "class": "bg-white focus:outline-none border border-gray-300 rounded-lg py-2 px-4 block w-full leading-normal text-gray-700 mb-3"
            }
        ),
    )
    examen_medico = forms.FileField(
        label="Examen médico",
        required=False,
    )
    contrato = forms.FileField(
        label="Contrato",
        required=False,
    )

    def __init__(self, *args, user=None, **kwargs):
        self.request_user = user
        super().__init__(*args, **kwargs)

        self.fields["current_branch"].queryset = self._get_branch_queryset(user)

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if not phone:
            return phone

        api_key = os.getenv("PHONE_API_KEY")

        if not api_key:
            return phone

        params = {"access_key": api_key, "number": phone}
        try:
            resp = requests.get("http://apilayer.net/api/validate", params=params, timeout=5)
            data = resp.json()
            if not data.get("valid"):
                raise forms.ValidationError("Número telefónico inválido.")
        except Exception:
            raise forms.ValidationError("Error al validar el número.")
        return phone

    class Meta:
        model = Profile
        fields = [
            "image",
            "phone",
            "gender",
            "date_of_birth",
            "salario",
            "current_branch",
            "is_partime",
            "examen_medico",
            "contrato",
        ]

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError(
                "El tamaño del archivo de imagen no debe exceder los 5 MB."
            )
        return image

    def clean_examen_medico(self):
        examen = self.cleaned_data.get("examen_medico")
        if examen and examen.size > 5 * 1024 * 1024:
            raise forms.ValidationError(
                "El tamaño del archivo no debe exceder los 5 MB."
            )
        allowed_types = ["application/pdf"]
        if examen and getattr(examen, "content_type", None) not in allowed_types:
            raise forms.ValidationError("Solo se permiten archivos PDF.")
        return examen

    def clean_contrato(self):
        contrato = self.cleaned_data.get("contrato")
        if contrato and contrato.size > 5 * 1024 * 1024:
            raise forms.ValidationError(
                "El tamaño del archivo no debe exceder los 5 MB."
            )
        allowed_types = ["application/pdf"]
        if contrato and getattr(contrato, "content_type", None) not in allowed_types:
            raise forms.ValidationError("Solo se permiten archivos PDF.")
        return contrato

    def _get_branch_queryset(self, user):
        if not user:
            return Sucursal.objects.none()

        profile = getattr(user, "profile", None)
        if profile is None:
            return Sucursal.objects.none()

        company = None
        try:
            company = profile.company
        except Company.DoesNotExist:
            company = None

        queryset = Sucursal.objects.none()
        if company is not None:
            queryset = Sucursal.objects.filter(company=company)
        elif getattr(profile, "company_rut", None):
            queryset = Sucursal.objects.filter(company__rut=profile.company_rut)

        if self.instance and self.instance.current_branch_id:
            queryset = queryset | Sucursal.objects.filter(pk=self.instance.current_branch_id)

        return queryset


class ProfileCreateForm(ProfileUpdateForm):
    position_FK = forms.ModelChoiceField(
        label="Cargo",
        queryset=Position.objects.none(),
        widget=forms.Select(
            attrs={
                "class": "bg-white focus:outline-none border border-gray-300 rounded-lg py-2 px-4 block w-full appearance-none leading-normal text-gray-700 mb-3"
            }
        ),
    )

    class Meta(ProfileUpdateForm.Meta):
        fields = ProfileUpdateForm.Meta.fields + ["position_FK"]  # incluye documentos

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)

        queryset = Position.objects.none()
        profile = getattr(user, "profile", None)
        if profile is not None:
            if profile.is_owner():
                queryset = Position.objects.exclude(
                    permission_code__in=["OWNER", "HEAD_ATTENDANT"]
                )
            elif profile.is_admin():
                queryset = Position.objects.exclude(
                    permission_code__in=["OWNER", "ADMINISTRATOR", "HEAD_ATTENDANT"]
                )

        self.fields["position_FK"].queryset = queryset