import os

import requests
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm,  PasswordChangeForm
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from allauth.account.forms import LoginForm
from django.utils.text import slugify
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div

from .models import Profile, Position
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

        layout_fields = []
        if "username" in self.fields:
            layout_fields.append("username")

        layout_fields.append("email")

        name_fields = []
        if "first_name" in self.fields:
            name_fields.append(Div("first_name", css_class="flex-1"))
        if "last_name" in self.fields:
            name_fields.append(Div("last_name", css_class="flex-1"))

        name_div = Div(*name_fields, css_class="flex gap-4") if name_fields else None

        layout_items = layout_fields
        if name_div is not None:
            layout_items.append(name_div)

        self.helper.layout = Layout(*layout_items)

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
        fields = [
            field
            for field in UserUpdateForm.Meta.fields
            if field != "username"
        ] + ["password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("username", None)

        field_class = "bg-white focus:outline-none border border-gray-300 rounded-lg py-2 px-4 block w-full leading-normal text-gray-700 mb-3"
        for name in ["first_name", "last_name", "email", "password1", "password2"]:
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("class", field_class)

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

    def save(self, commit=True):
        user = super().save(commit=False)

        first_name = (self.cleaned_data.get("first_name") or "").strip()
        last_name = (self.cleaned_data.get("last_name") or "").strip()
        email = (self.cleaned_data.get("email") or "").strip()

        base_username = " ".join(part for part in [first_name, last_name] if part)
        if not base_username and email:
            base_username = email.split("@")[0]

        base_username = slugify(base_username) or "usuario"

        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}-{counter}"
            counter += 1

        user.username = username

        if commit:
            user.save()
            self.save_m2m()

        return user


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
    codigo_identificador = forms.CharField(
        max_length=50,
        required=False,
        label="Código identificador",
        widget=forms.TextInput(
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

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if not phone:
            return phone

        api_key = os.getenv("PHONE_API_KEY")

        if not api_key:
            return phone

        params = {"access_key": api_key, "number": phone}
        try:
            resp = requests.get(
                "http://apilayer.net/api/validate", params=params, timeout=5
            )
            data = resp.json()
        except Exception:
            return phone

        if data.get("success") is False:
            return phone

        if data.get("valid") is False:
            return phone
        return phone

    class Meta:
        model = Profile
        fields = [
            "image",
            "phone",
            "gender",
            "date_of_birth",
            "codigo_identificador",
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