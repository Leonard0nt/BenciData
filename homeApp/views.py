from decimal import Decimal, ROUND_HALF_UP

from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from UsuarioApp.models import Profile
from homeApp.models import Company
from sucursalApp.models import Sucursal, SucursalStaff


# Create your views here.


class HomeView(LoginRequiredMixin, ListView):
    model = User
    template_name = "pages/index.html"

    def get_queryset(self):
        last_connected_users = User.objects.filter(
            Q(last_login__isnull=False)
        ).order_by("-last_login")[:5]
        return last_connected_users

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agrega los usuarios activos al contexto
        recent_activity_cutoff = timezone.now() - timezone.timedelta(minutes=2)
        active_users = Profile.objects.filter(
            last_activity__gte=recent_activity_cutoff
        ).values_list("user_FK_id", flat=True)
        context["active_users"] = active_users

        company = None
        try:
            profile = self.request.user.profile
        except Profile.DoesNotExist:
            profile = None

        if profile:
            try:
                company = profile.company
            except Company.DoesNotExist:
                company = None

            if not company and profile.company_rut:
                normalized_rut = Company.normalize_rut(profile.company_rut)
                company = Company.objects.filter(rut=normalized_rut).first()

fuel_dashboard: list[dict] = []
        branches: list[Sucursal] | None = None

        if company:
            branches = list(
                company.branches.prefetch_related("fuel_inventories").order_by("name")
            )
        elif profile:
            branch_ids = list(
                SucursalStaff.objects.filter(profile=profile).values_list(
                    "sucursal_id", flat=True
                )
            )
            if profile.current_branch_id:
                branch_ids.append(profile.current_branch_id)

            if branch_ids:
                branch_ids = list(dict.fromkeys(branch_ids))
                branches_qs = Sucursal.objects.filter(id__in=branch_ids).prefetch_related(
                    "fuel_inventories"
                )
                branches = list(branches_qs.order_by("name"))
                if not company and branches:
                    company = branches[0].company

        if branches:
            for branch in branches:
                inventories = []
                for inventory in branch.fuel_inventories.all():
                    percentage = Decimal("0")
                    if inventory.capacity:
                        percentage = (
                            inventory.liters
                            / inventory.capacity
                            * Decimal("100")
                        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                        percentage = min(percentage, Decimal("100"))

                    inventories.append(
                        {
                            "fuel_type": inventory.fuel_type,
                            "liters": inventory.liters,
                            "capacity": inventory.capacity,
                            "percentage": percentage,
                        }
                    )

                fuel_dashboard.append(
                    {
                        "branch_name": branch.name,
                        "city": branch.city,
                        "inventories": inventories,
                    }
                )

        context["company"] = company
        context["fuel_dashboard"] = fuel_dashboard

        return context


