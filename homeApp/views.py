from decimal import Decimal, ROUND_HALF_UP

from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db.models import Q
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncYear
from django.utils import timezone
from UsuarioApp.models import Profile
from homeApp.models import Company
from sucursalApp.models import Sucursal, SucursalStaff, ServiceSession


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

        if profile and (
            profile.is_owner() or profile.is_admin() or profile.is_accountant()
        ):
            try:
                company = profile.company
            except Company.DoesNotExist:
                company = None

            if not company and profile.company_rut:
                normalized_rut = Company.normalize_rut(profile.company_rut)
                company = Company.objects.filter(rut=normalized_rut).first()

        fuel_dashboard: list[dict] = []
        branches: list[Sucursal] | None = None

        is_company_admin = bool(
            profile and (profile.is_owner() or profile.is_admin())
        )

        if profile and profile.current_branch and not is_company_admin:
            branches = [profile.current_branch]
            company = company or profile.current_branch.company
        elif company:
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

        profit_dashboard: list[dict] = []
        if branches:
            decimal_zero = Decimal("0")
            zero_value = Value(
                decimal_zero,
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )

            annotated_sessions = (
                ServiceSession.objects.filter(
                    shift__sucursal__in=branches, ended_at__isnull=False
                )
                .annotate(
                    credit_total=Coalesce(Sum("credit_sales__amount"), zero_value),
                    withdrawal_total=Coalesce(Sum("withdrawals__amount"), zero_value),
                    voucher_total=Coalesce(
                        Sum("transbank_vouchers__total_amount"), zero_value
                    ),
                    fuel_load_payment_total=Coalesce(
                        Sum("fuel_loads__payment_amount"), zero_value
                    ),
                    product_load_payment_total=Coalesce(
                        Sum("product_loads__payment_amount"), zero_value
                    ),
                    firefighter_payments_total=Coalesce(
                        Sum("firefighter_payments__amount"), zero_value
                    ),
                    product_sales_value=Coalesce(
                        Sum(
                            F("product_sales__items__quantity")
                            * F("product_sales__items__product__value"),
                            output_field=DecimalField(
                                max_digits=14,
                                decimal_places=2,
                            ),
                        ),
                        zero_value,
                    ),
                )
                .annotate(
                    turn_profit=ExpressionWrapper(
                        F("initial_budget")
                        + F("credit_total")
                        + F("voucher_total")
                        + F("withdrawal_total")
                        + F("product_sales_value"),
                        output_field=DecimalField(
                            max_digits=14, decimal_places=2
                        ),
                    ),
                    net_turn_profit=ExpressionWrapper(
                        F("turn_profit")
                        - F("fuel_load_payment_total")
                        - F("firefighter_payments_total")
                        - F("product_load_payment_total"),
                        output_field=DecimalField(
                            max_digits=14, decimal_places=2
                        ),
                    ),
                )
            )

            def build_series(queryset, trunc_fn, date_format: str):
                grouped = (
                    queryset.annotate(period=trunc_fn("ended_at"))
                    .values("period")
                    .annotate(total_profit=Sum("net_turn_profit"))
                    .order_by("period")
                )
                return [
                    {
                        "label": record["period"].strftime(date_format),
                        "value": float(record["total_profit"] or decimal_zero),
                    }
                    for record in grouped
                    if record["period"]
                ]

            for branch in branches:
                branch_sessions = annotated_sessions.filter(shift__sucursal=branch)
                if not branch_sessions.exists():
                    continue

                profit_dashboard.append(
                    {
                        "branch_name": branch.name,
                        "city": branch.city,
                        "series": {
                            "day": build_series(
                                branch_sessions, TruncDay, "%d %b"
                            ),
                            "month": build_series(
                                branch_sessions, TruncMonth, "%b %Y"
                            ),
                            "year": build_series(branch_sessions, TruncYear, "%Y"),
                        },
                    }
                )

        context["company"] = company
        context["fuel_dashboard"] = fuel_dashboard
        context["profit_dashboard"] = profit_dashboard

        return context


