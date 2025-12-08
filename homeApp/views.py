from decimal import Decimal, ROUND_HALF_UP
from functools import reduce
from operator import or_

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

    def _resolve_scope(self):
        profile = getattr(self.request.user, "profile", None)
        company = None
        branches: list[Sucursal] = []

        if profile and (
            profile.is_owner() or profile.is_admin() or profile.is_accountant()
        ):
            company = Company.objects.filter(profile=profile).first()
            if not company and profile.company_rut:
                normalized_rut = Company.normalize_rut(profile.company_rut)
                company = Company.objects.filter(rut=normalized_rut).first()

        if profile and profile.current_branch and not (
            profile.is_owner() or profile.is_admin()
        ):
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

        return profile, company, branches

    def _get_scoped_profiles(self, company: Company | None, branches: list[Sucursal]):
        branch_ids = [branch.pk for branch in branches if branch and branch.pk]
        if company:
            branch_ids.extend(
                company.branches.values_list("pk", flat=True)
            )
        branch_ids = list(dict.fromkeys(branch_ids))

        filters: list[Q] = []
        if company:
            filters.append(Q(company_rut=company.rut))
            if company.profile_id:
                filters.append(Q(pk=company.profile_id))

        if branch_ids:
            filters.append(Q(current_branch_id__in=branch_ids))
            filters.append(Q(sucursal_staff__sucursal_id__in=branch_ids))

        if not filters:
            return Profile.objects.none()

        combined_filter = filters[0]
        if len(filters) > 1:
            combined_filter = reduce(or_, filters)

        return Profile.objects.filter(combined_filter).distinct()

    def get_queryset(self):
        _, company, branches = self._resolve_scope()
        scoped_profiles = self._get_scoped_profiles(company, branches)
        scoped_user_ids = list(scoped_profiles.values_list("user_FK_id", flat=True))
        if not scoped_user_ids:
            return User.objects.none()

        return (
            User.objects.filter(id__in=scoped_user_ids, last_login__isnull=False)
            .order_by("-last_login")[:5]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, company, branches = self._resolve_scope()
        scoped_profiles = self._get_scoped_profiles(company, branches)

        # Agrega los usuarios activos al contexto, limitados al alcance del usuario
        recent_activity_cutoff = timezone.now() - timezone.timedelta(minutes=2)
        active_users = scoped_profiles.filter(
            last_activity__gte=recent_activity_cutoff
        ).values_list("user_FK_id", flat=True)
        context["active_users"] = active_users

        is_company_admin = bool(
            profile and (profile.is_owner() or profile.is_admin())
        )

        fuel_dashboard: list[dict] = []

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
                    session_profit=ExpressionWrapper(
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
                records = queryset.annotate(period=trunc_fn("ended_at")).values(
                    "period",
                    "initial_budget",
                    "credit_total",
                    "voucher_total",
                    "withdrawal_total",
                    "product_sales_value",
                    "fuel_load_payment_total",
                    "firefighter_payments_total",
                    "product_load_payment_total",
                )

                grouped_totals: dict = {}
                for record in records:
                    period = record["period"]
                    if not period:
                        continue

                    totals = grouped_totals.setdefault(
                        period,
                        {
                            "total_initial_budget": decimal_zero,
                            "total_credit": decimal_zero,
                            "total_voucher": decimal_zero,
                            "total_withdrawal": decimal_zero,
                            "total_product_sales": decimal_zero,
                            "total_fuel_payment": decimal_zero,
                            "total_firefighter_payment": decimal_zero,
                            "total_product_load_payment": decimal_zero,
                        },
                    )

                    totals["total_initial_budget"] += record["initial_budget"] or decimal_zero
                    totals["total_credit"] += record["credit_total"] or decimal_zero
                    totals["total_voucher"] += record["voucher_total"] or decimal_zero
                    totals["total_withdrawal"] += record["withdrawal_total"] or decimal_zero
                    totals["total_product_sales"] += record["product_sales_value"] or decimal_zero
                    totals["total_fuel_payment"] += record[
                        "fuel_load_payment_total"
                    ] or decimal_zero
                    totals["total_firefighter_payment"] += record[
                        "firefighter_payments_total"
                    ] or decimal_zero
                    totals["total_product_load_payment"] += record[
                        "product_load_payment_total"
                    ] or decimal_zero

                grouped = []
                for period, totals in grouped_totals.items():
                    total_profit = (
                        totals["total_initial_budget"]
                        + totals["total_credit"]
                        + totals["total_voucher"]
                        + totals["total_withdrawal"]
                        + totals["total_product_sales"]
                        - totals["total_fuel_payment"]
                        - totals["total_firefighter_payment"]
                        - totals["total_product_load_payment"]
                    )

                    grouped.append(
                        {
                            "label": period.strftime(date_format),
                            "value": float(total_profit or decimal_zero),
                        }
                    )

                return sorted(grouped, key=lambda item: item["label"])

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


