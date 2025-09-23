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
from collections import defaultdict
from typing import Any

from django.utils import timezone
from django.utils.text import slugify
from django.templatetags.static import static
from allauth.account.models import EmailAddress
from django.contrib import messages
from django.urls import reverse_lazy
from core.mixins import PermitsPositionMixin, RoleRequiredMixin
from UsuarioApp.services import get_shift_assignments_for_users

from .models import Profile
from sucursalApp.models import ShiftAssignment
from homeApp.models import Company

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

        base_queryset = getattr(self, "object_list", self.get_queryset())
        filtered_users = list(
            base_queryset.select_related(
                "profile__position_FK", "profile__current_branch"
            )
        )

        total_filtered = len(filtered_users)
        active_filtered = sum(1 for user in filtered_users if user.is_active)
        inactive_filtered = total_filtered - active_filtered

        user_ids = [user.id for user in filtered_users]
        verified_user_ids = set(
            EmailAddress.objects.filter(
                user_id__in=user_ids, verified=True
            ).values_list("user_id", flat=True)
        )

        cutoff_date = timezone.now() - timezone.timedelta(days=7)
        recent_new_users = sum(
            1 for user in filtered_users if user.date_joined >= cutoff_date
        )

        user_data_map = {}
        assignments_by_user: dict[int, list[ShiftAssignment]] = defaultdict(list)
        shift_summary_cache: dict[int, list[dict[str, str]]] = {}

        assignments_qs = (
            ShiftAssignment.objects.active()
            .select_related(
                "shift__sucursal",
                "profile__user_FK",
                "profile__position_FK",
            )
            .prefetch_related("shift__schedules")
            .filter(profile__user_FK_id__in=user_ids)
        )
        for assignment in assignments_qs:
            assignments_by_user[assignment.profile.user_FK_id].append(assignment)
            if assignment.shift_id not in shift_summary_cache:
                shift_summary_cache[assignment.shift_id] = assignment.shift.get_schedule_summary()

        shift_tabs_map: dict[int, dict[str, Any]] = {}
        unassigned_users: list[dict[str, Any]] = []
        unassigned_label = "Sin turno asignado"

        for user in filtered_users:
            try:
                profile = user.profile
            except Profile.DoesNotExist:
                profile = None

            avatar_url = static("img/profile.webp")
            if profile is not None and getattr(profile, "image", None):
                image_field = profile.image
                if getattr(image_field, "url", None):
                    avatar_url = image_field.url

            assignments = assignments_by_user.get(user.id, [])
            assignment_entries = []
            branch_names = []

            for assignment in assignments:
                shift = assignment.shift
                branch = shift.sucursal
                label = f"{shift.name} · {branch.name}" if branch else shift.name
                branch_name = branch.name if branch else None
                if branch_name and branch_name not in branch_names:
                    branch_names.append(branch_name)

                schedule_summary = shift_summary_cache.get(shift.id, [])
                assignment_entries.append(
                    {
                        "id": assignment.id,
                        "shift_id": shift.id,
                        "shift_name": shift.name,
                        "branch_id": branch.id if branch else None,
                        "branch_name": branch_name,
                        "label": label,
                        "schedule": schedule_summary,
                    }
                )

                slug_source = f"{shift.id}-{label}"
                tab_slug = slugify(slug_source) or f"shift-{shift.id}"
                tab_id = f"tab-turno-{tab_slug}"
                tab_entry = shift_tabs_map.setdefault(
                    shift.id,
                    {
                        "id": tab_id,
                        "label": label,
                        "sucursal_id": branch.id if branch else None,
                        "schedule": schedule_summary,
                        "users": [],
                    },
                )

                tab_user_entry = dict()
                tab_user_entry.update(
                    {
                        "id": user.id,
                        "username": user.username,
                        "full_name": user.get_full_name() or user.username,
                        "email": user.email,
                        "role": (
                            profile.position_FK.user_position
                            if profile and profile.position_FK
                            else "Sin cargo"
                        ),
                        "branch": branch_name,
                        "is_active": user.is_active,
                        "is_verified": user.id in verified_user_ids,
                        "shift_label": label,
                        "profile_image": avatar_url,
                        "last_login": user.last_login,
                        "last_activity": getattr(profile, "last_activity", None),
                    }
                )
                tab_entry["users"].append(tab_user_entry)

            if profile and not branch_names and getattr(profile, "current_branch", None):
                branch_names.append(profile.current_branch.name)

            user_entry = {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
                "email": user.email,
                "role": (
                    profile.position_FK.user_position
                    if profile and profile.position_FK
                    else "Sin cargo"
                ),
                "branch": branch_names[0] if branch_names else None,
                "branches": branch_names,
                "is_active": user.is_active,
                "is_verified": user.id in verified_user_ids,
                "shift_label": assignment_entries[0]["label"]
                if assignment_entries
                else unassigned_label,
                "profile_image": avatar_url,
                "last_login": user.last_login,
                "last_activity": getattr(profile, "last_activity", None),
                "assignments": assignment_entries,
            }

            user_data_map[user.id] = user_entry

            if not assignment_entries:
                unassigned_users.append(user_entry)

        for tab_entry in shift_tabs_map.values():
            tab_entry["users"].sort(key=lambda item: item["full_name"].lower())
            total_users = len(tab_entry["users"])
            active_count = sum(1 for item in tab_entry["users"] if item["is_active"])
            tab_entry["count"] = total_users
            tab_entry["active_count"] = active_count
            tab_entry["inactive_count"] = total_users - active_count

        shift_tabs = sorted(shift_tabs_map.values(), key=lambda item: item["label"].lower())

        if unassigned_users:
            unassigned_users.sort(key=lambda item: item["full_name"].lower())
            unassigned_tab = {
                "id": "tab-turno-sin-asignacion",
                "label": unassigned_label,
                "count": len(unassigned_users),
                "active_count": sum(1 for item in unassigned_users if item["is_active"]),
                "inactive_count": sum(
                    1 for item in unassigned_users if not item["is_active"]
                ),
                "users": unassigned_users,
            }
            shift_tabs.append(unassigned_tab)

        active_shifts = sum(1 for shift in shift_tabs if shift["active_count"] > 0)

        global_total_users = User.objects.count()
        global_active_users = User.objects.filter(is_active=True).count()

        summary_cards = [
            {
                "title": "Usuarios registrados",
                "value": global_total_users,
                "description": (
                    f"{recent_new_users} nuevos en los últimos 7 días · "
                    f"{total_filtered} en la vista"
                ),
            },
            {
                "title": "Usuarios activos",
                "value": global_active_users,
                "description": (
                    f"{active_filtered} activos visibles · "
                    f"{inactive_filtered} inactivos"
                ),
            },
            {
                "title": "Turnos activos",
                "value": active_shifts,
                "description": "Usuarios activos por turno (filtros actuales)",
                "items": [
                    {
                        "label": shift["label"],
                        "value": shift["active_count"],
                        "total": shift["count"],
                    }
                    for shift in shift_tabs
                ],
            },
        ]

        tab_navigation = [
            {
                "id": "tab-usuarios-todos",
                "label": "Todos",
                "count": total_filtered,
                "is_active": True,
            }
        ]
        tab_navigation.extend(
            {
                "id": shift["id"],
                "label": shift["label"],
                "count": shift["count"],
                "is_active": False,
            }
            for shift in shift_tabs
        )

        page_users = list(context["users"])
        context["user_rows"] = [
            user_data_map[user.id]
            for user in page_users
            if user.id in user_data_map
        ]

        verification_users = [
            (user, user_data_map[user.id]["is_verified"])
            for user in page_users
            if user.id in user_data_map
        ]

        context["verification_users"] = verification_users
        context["summary_cards"] = summary_cards
        context["shift_tabs"] = shift_tabs
        context["tab_navigation"] = tab_navigation
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
