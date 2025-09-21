from .forms import (
    UserCreateForm,
    ProfileCreateForm,
    UserUpdateForm,
    ProfileUpdateForm,
    CustomPasswordChangeForm,
    CompanyForm,
)
from django.views.generic import ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import redirect, render
from django.db.models import Q
from allauth.account.models import EmailAddress
from django.contrib import messages
from django.urls import reverse_lazy
from core.mixins import PermitsPositionMixin, RoleRequiredMixin

from .models import Company, Profile

# Create your views here.


class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = "pages/usuarios/usuarios_lista.html"
    context_object_name = "users"
    paginate_by = 9

    def get_queryset(self):
        queryset = super().get_queryset().order_by("-id")
        search_query = self.request.GET.get("search")

        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        verification_users = []
        for user in context["users"]:
            verification = EmailAddress.objects.filter(
                user=user, verified=True
            ).exists()
            verification_users.append((user, verification))

        context["verification_users"] = verification_users
        context["placeholder"] = "Buscar por usuario, nombre o apellido "
        # Para mantener el texto en el campo de búsqueda
        context["search_query"] = self.request.GET.get("search", "")
        return context


class UserCreateView(LoginRequiredMixin, PermitsPositionMixin, View):
    template_name = "pages/usuarios/registro_usuario.html"

    def get(self, request, *args, **kwargs):
        user_form = UserCreateForm()
        profile_form = ProfileCreateForm(user=request.user)

        context = {"user_form": user_form, "profile_form": profile_form}

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        user_form = UserCreateForm(request.POST)
        profile_form = ProfileCreateForm(request.POST, request.FILES, user=request.user)

        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile = profile_form.save(commit=False)
            profile.user_FK = user
            owner_profile = getattr(request.user, "profile", None)
            if owner_profile is not None:
                company = getattr(owner_profile, "company", None)
                if company is not None:
                    profile.company_rut = company.rut
                else:
                    messages.warning(
                        request,
                        "No se encontró una empresa asociada al usuario actual.",
                    )
            else:
                messages.warning(
                    request,
                    "No se encontró un perfil asociado al usuario actual.",
                )
            profile.save()
            messages.success(request, "Usuario creado con Éxito.")
            return redirect("Register")

        context = {"user_form": user_form, "profile_form": profile_form}

        return render(request, self.template_name, context)


class ProfileUpdateView(LoginRequiredMixin, View):
    template_name = "pages/perfil/perfil.html"

    def get(self, request, *args, **kwargs):
        user = request.user
        profile = user.profile
        user_form = UserUpdateForm(instance=user)
        profile_form = ProfileUpdateForm(instance=profile)

        context = {"user_form": user_form, "profile_form": profile_form}

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        user = request.user
        profile = user.profile
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            try:
                user_form.save()
                profile_form.save()
                messages.success(request, "Perfil actualizado con éxito.")
            except Exception as e:
                print(e)
                print("*" * 30)
                messages.error(request, "Error al guardar la imagen")

            return redirect("Profile")

        context = {"user_form": user_form, "profile_form": profile_form}

        return render(request, self.template_name, context)


class ConfigurationView(LoginRequiredMixin, View):
    template_name = "pages/perfil/configuracion.html"

    def get(self, request, *args, **kwargs):
        user = request.user
        profile = user.profile
        user_form = UserUpdateForm(instance=user)
        profile_form = ProfileUpdateForm(instance=profile)
        
        password_form = CustomPasswordChangeForm(user=user)
        password_form.helper = FormHelper()
        password_form.helper.form_tag = False

        context = {
            "user_form": user_form,
            "profile_form": profile_form,
            "password_form": password_form,
        }

        return render(request, self.template_name, context)


class CompanyUpdateView(LoginRequiredMixin, RoleRequiredMixin, View):
    template_name = "pages/empresa/empresa_form.html"
    form_class = CompanyForm
    success_url = reverse_lazy("company_edit")
    allowed_roles = ["OWNER"]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        profile = getattr(request.user, "profile", None)

        if not profile or not profile.is_owner():
            return redirect(self.redirect_url)

        self.company_obj, _ = Company.objects.get_or_create(profile=profile)
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, data=None):
        return self.form_class(data=data, instance=getattr(self, "company_obj", None))

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        return render(request, self.template_name, {"form": form})

    def post(self, request, *args, **kwargs):
        old_rut = Company.normalize_rut(getattr(self.company_obj, "rut", None))
        form = self.get_form(request.POST)
        if form.is_valid():
            form.save()
            self.company_obj.refresh_from_db()
            new_rut = self.company_obj.rut
            if old_rut:
                Profile.objects.filter(company_rut=old_rut).update(
                    company_rut=new_rut
                )
            messages.success(request, "Información de la empresa actualizada con éxito.")
            return redirect(self.success_url)

        messages.error(request, "Corrige los errores para continuar.")
        return render(request, self.template_name, {"form": form})
