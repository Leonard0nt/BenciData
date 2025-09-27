from .forms import (
    UserCreateForm,
    ProfileCreateForm,
    UserUpdateForm,
    ProfileUpdateForm,
    CustomPasswordChangeForm,    
)

from homeApp.forms import CompanyForm
from django.views.generic import ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import redirect, render
from django.db.models import Q
from typing import Any

from django.utils import timezone
from django.templatetags.static import static
from allauth.account.models import EmailAddress
from django.contrib import messages
from django.urls import reverse_lazy
from core.mixins import PermitsPositionMixin, RoleRequiredMixin
from .models import Profile
from sucursalApp.models import Sucursal, SucursalStaff
from homeApp.models import Company

# Create your views here.





class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = "pages/usuarios/usuarios_lista.html"
    context_object_name = "users"
    paginate_by = 9

    access_scope: dict[str, Any] | None = None

    def _get_access_scope(self) -> dict[str, Any]:
        if self.access_scope is not None:
            return self.access_scope

        profile = getattr(self.request.user, "profile", None)
        is_owner = bool(profile and profile.is_owner())
        is_admin = bool(profile and profile.is_admin())

        company_rut: str | None = None
        branches_qs = Sucursal.objects.none()
        branch_ids: list[int] = []

        if profile:
            if is_owner:
                company = getattr(profile, "company", None)
                if company:
                    company_rut = company.rut
                    branches_qs = company.branches.all()
                elif profile.company_rut:
                    company_rut = Company.normalize_rut(profile.company_rut)
                    branches_qs = Sucursal.objects.filter(
                        company__rut=company_rut
                    )
                branch_ids = list(branches_qs.values_list("id", flat=True))
            elif is_admin:
                branch_ids = list(
                    SucursalStaff.objects.filter(profile=profile)
                    .values_list("sucursal_id", flat=True)
                )
                if profile.current_branch_id:
                    branch_ids.append(profile.current_branch_id)
                if branch_ids:
                    branch_ids = list(dict.fromkeys(branch_ids))
                    branches_qs = Sucursal.objects.filter(id__in=branch_ids)

        self.access_scope = {
            "profile": profile,
            "is_owner": is_owner,
            "is_admin": is_admin,
            "company_rut": company_rut,
            "branch_ids": branch_ids,
            "branches": list(branches_qs.order_by("name")),
        }
        return self.access_scope

    def get_queryset(self):
        access = self._get_access_scope()

        queryset = super().get_queryset().select_related("profile").order_by("-id")
        search_query = self.request.GET.get("search")

        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
            )

        profile = access.get("profile")
        if not profile:
            return queryset.none()

        if access["is_owner"]:
            company_rut = access.get("company_rut")
            if company_rut:
                queryset = queryset.filter(profile__company_rut=company_rut)
            else:
                queryset = queryset.none()
        elif access["is_admin"]:
            branch_ids: list[int] = access.get("branch_ids", [])
            if branch_ids:
                queryset = queryset.filter(
                    Q(profile__current_branch_id__in=branch_ids)
                    | Q(profile__sucursal_staff__sucursal_id__in=branch_ids)
                ).distinct()
            else:
                queryset = queryset.filter(id=self.request.user.id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        access = self._get_access_scope()
        accessible_branches: list[Sucursal] = access.get("branches", [])
        branch_lookup = {branch.id: branch for branch in accessible_branches if branch}

        base_queryset = getattr(self, "object_list", self.get_queryset())
        filtered_users = list(
            base_queryset.select_related(
                "profile__position_FK",
                "profile__current_branch",
            ).prefetch_related("profile__sucursal_staff__sucursal")
        )

        user_ids = [user.id for user in filtered_users]
        verified_user_ids = set(
            EmailAddress.objects.filter(
                user_id__in=user_ids, verified=True
            ).values_list("user_id", flat=True)
        )

        cutoff_date = timezone.now() - timezone.timedelta(days=7)

        branch_groups_map: dict[int | None, list[dict[str, Any]]] = {}
        missing_branch_ids: set[int] = set()

        for user in filtered_users:
            try:
                user_profile = user.profile
            except Profile.DoesNotExist:
                user_profile = None

            avatar_url = static("img/profile.webp")
            if user_profile and getattr(user_profile, "image", None):
                image_field = user_profile.image
                if getattr(image_field, "url", None):
                    avatar_url = image_field.url

            branch_ids_for_user: set[int | None] = set()

            if user_profile is not None:
                if user_profile.current_branch_id:
                    branch_ids_for_user.add(user_profile.current_branch_id)
                staff_memberships = getattr(user_profile, "sucursal_staff", None)
                if staff_memberships is not None:
                    for membership in staff_memberships.all():
                        if membership.sucursal_id:
                            branch_ids_for_user.add(membership.sucursal_id)
                            if membership.sucursal_id not in branch_lookup:
                                missing_branch_ids.add(membership.sucursal_id)

            if not branch_ids_for_user:
                branch_ids_for_user.add(None)

            row_entry = {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
                "email": user.email,
                "profile_id": getattr(user_profile, "id", None),
                "role": (
                    user_profile.position_FK.user_position
                    if user_profile and user_profile.position_FK
                    else "Sin cargo"
                ),
                "is_active": user.is_active,
                "is_verified": user.id in verified_user_ids,
                "profile_image": avatar_url,
                "last_login": user.last_login,
                "last_activity": getattr(user_profile, "last_activity", None),
                "date_joined": user.date_joined,
            }

            for branch_id in branch_ids_for_user:
                branch_groups_map.setdefault(branch_id, []).append(row_entry)

        if missing_branch_ids:
            for branch in Sucursal.objects.filter(id__in=missing_branch_ids):
                branch_lookup.setdefault(branch.id, branch)

        branch_groups: list[dict[str, Any]] = []
        for branch_id, rows in branch_groups_map.items():
            branch_obj = branch_lookup.get(branch_id)
            branch_name = branch_obj.name if branch_obj else "Sin sucursal"
            row_entries = sorted(
                (
                    {**row, "branch": branch_name}
                    for row in rows
                ),
                key=lambda item: item["full_name"].lower(),
            )
            total_users = len(row_entries)
            active_users = sum(1 for item in row_entries if item["is_active"])
            inactive_users = total_users - active_users
            recent_users = sum(
                1
                for item in row_entries
                if item.get("date_joined") and item["date_joined"] >= cutoff_date
            )

            branch_groups.append(
                {
                    "branch": {
                        "id": getattr(branch_obj, "id", None),
                        "name": branch_name,
                    },
                    "users": row_entries,
                    "summary": {
                        "total_users": total_users,
                        "active_users": active_users,
                        "inactive_users": inactive_users,
                        "recent_users": recent_users,
                    },
                }
            )

        branch_groups.sort(key=lambda group: group["branch"]["name"].lower())

        context["placeholder"] = "Buscar por usuario, nombre o apellido "
        context["search_query"] = self.request.GET.get("search", "")
        context["branch_groups"] = branch_groups
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


class ProfileFormProcessingMixin:
    """Mixin to handle the shared logic for updating user/profile forms."""

    success_redirect_name = "Profile"
    success_message = "Perfil actualizado con éxito."
    error_message = None
    save_error_message = "Error al guardar la imagen"

    def get_success_url(self):
        return self.success_redirect_name

    def process_forms(self, request, user_form, profile_form, extra_context=None):
        if user_form.is_valid() and profile_form.is_valid():
            try:
                user_form.save()
                profile_form.save()
                messages.success(request, self.success_message)
            except Exception as e:
                print(e)
                print("*" * 30)
                messages.error(request, self.save_error_message)

            return redirect(self.get_success_url())

        if self.error_message:
            messages.error(request, self.error_message)

        context = {"user_form": user_form, "profile_form": profile_form}

        if extra_context:
            context.update(extra_context)

        return render(request, self.template_name, context)


class ProfileUpdateView(LoginRequiredMixin, ProfileFormProcessingMixin, View):
    template_name = "pages/perfil/perfil.html"

    def get(self, request, *args, **kwargs):
        user = request.user
        profile = user.profile
        user_form = UserUpdateForm(instance=user)
        profile_form = ProfileUpdateForm(instance=profile, user=request.user)

        context = {"user_form": user_form, "profile_form": profile_form}

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        user = request.user
        profile = user.profile
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=profile,
            user=request.user,
        )

        return self.process_forms(request, user_form, profile_form)


class ConfigurationView(LoginRequiredMixin, ProfileFormProcessingMixin, View):
    template_name = "pages/perfil/configuracion.html"
    success_redirect_name = "configuracion"
    error_message = "Corrige los errores para continuar."

    def get(self, request, *args, **kwargs):
        user = request.user
        profile = user.profile
        user_form = UserUpdateForm(instance=user)
        profile_form = ProfileUpdateForm(instance=profile, user=user)
        
        password_form = CustomPasswordChangeForm(user=user)
        password_form.helper = FormHelper()
        password_form.helper.form_tag = False

        context = {
            "user_form": user_form,
            "profile_form": profile_form,
            "password_form": password_form,
        }

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        user = request.user
        profile = user.profile
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = ProfileUpdateForm(
            request.POST, request.FILES, instance=profile, user=request.user
        )
        password_form = CustomPasswordChangeForm(user=user)
        password_form.helper = FormHelper()
        password_form.helper.form_tag = False

        extra_context = {"password_form": password_form}

        return self.process_forms(
            request,
            user_form,
            profile_form,
            extra_context=extra_context,
        )

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