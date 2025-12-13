from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from functools import reduce
from operator import or_

from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db.models import Q
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    OuterRef,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import (
    Coalesce,
    TruncDay,
    TruncWeek,
    TruncYear,
)
from django.utils import timezone
from UsuarioApp.models import Profile
from homeApp.models import Company
from sucursalApp.models import (
    ServiceSession,
    ServiceSessionCreditSale,
    ServiceSessionFirefighterPayment,
    ServiceSessionFuelLoad,
    ServiceSessionFuelSale,
    ServiceSessionProductLoad,
    ServiceSessionProductSaleItem,
    ServiceSessionTransbankVoucher,
    ServiceSessionWithdrawal,
    Sucursal,
    SucursalStaff,
)


# Create your views here.


class HomeView(LoginRequiredMixin, ListView):
    model = User
    template_name = "pages/index.html"

    def _resolve_scope(self):
        profile = getattr(self.request.user, "profile", None)
        company = None
        branches: list[Sucursal] = []
        has_company_scope = False

        if profile and profile.is_owner():
            has_company_scope = True
            company = Company.objects.filter(profile=profile).first()
            if not company and profile.company_rut:
                normalized_rut = Company.normalize_rut(profile.company_rut)
                company = Company.objects.filter(rut=normalized_rut).first()

        if profile and profile.current_branch and not has_company_scope:
            branches = [profile.current_branch]
            company = company or profile.current_branch.company
        elif has_company_scope and company:
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

        return profile, company, branches, has_company_scope

    def _get_scoped_profiles(
        self,
        company: Company | None,
        branches: list[Sucursal],
        has_company_scope: bool,
    ):
        branch_ids = [branch.pk for branch in branches if branch and branch.pk]
        if has_company_scope and company:
            branch_ids.extend(
                company.branches.values_list("pk", flat=True)
            )
        branch_ids = list(dict.fromkeys(branch_ids))

        filters: list[Q] = []
        if has_company_scope and company:
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
        _, company, branches, has_company_scope  = self._resolve_scope()
        scoped_profiles = self._get_scoped_profiles(company, branches, has_company_scope )
        scoped_user_ids = list(scoped_profiles.values_list("user_FK_id", flat=True))
        if not scoped_user_ids:
            return User.objects.none()

        return (
            User.objects.filter(id__in=scoped_user_ids, last_login__isnull=False)
            .order_by("-last_login")[:5]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, company, branches, has_company_scope = self._resolve_scope()
        scoped_profiles = self._get_scoped_profiles(
            company, branches, has_company_scope
        )

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

            def sum_subquery(model, value_field: str, filter_field: str = "service_session"):
                return Coalesce(
                    Subquery(
                        model.objects.filter(**{f"{filter_field}": OuterRef("pk")})
                        .values(filter_field)
                        .annotate(total=Sum(value_field))
                        .values("total"),
                        output_field=DecimalField(
                            max_digits=14,
                            decimal_places=2,
                        ),
                    ),
                    zero_value,
                )

            annotated_sessions = ServiceSession.objects.filter(
                shift__sucursal__in=branches, ended_at__isnull=False
            ).annotate(
                credit_total=sum_subquery(
                    ServiceSessionCreditSale, "amount", "service_session"
                ),
                withdrawal_total=sum_subquery(
                    ServiceSessionWithdrawal, "amount", "service_session"
                ),
                voucher_total=sum_subquery(
                    ServiceSessionTransbankVoucher, "total_amount", "service_session"
                ),
                fuel_load_payment_total=sum_subquery(
                    ServiceSessionFuelLoad, "payment_amount", "service_session"
                ),
                product_load_payment_total=sum_subquery(
                    ServiceSessionProductLoad, "payment_amount", "service_session"
                ),
                firefighter_payments_total=sum_subquery(
                    ServiceSessionFirefighterPayment, "amount", "service_session"
                ),
                product_sales_value=Coalesce(
                    Subquery(
                        ServiceSessionProductSaleItem.objects.filter(
                            sale__service_session=OuterRef("pk")
                        )
                        .values("sale__service_session")
                        .annotate(
                            total=Sum(
                                F("quantity") * F("product__value"),
                                output_field=DecimalField(
                                    max_digits=14,
                                    decimal_places=2,
                                ),
                            )
                        )
                        .values("total"),
                        output_field=DecimalField(
                            max_digits=14,
                            decimal_places=2,
                        ),
                    ),
                    zero_value,
                ),
            )

            def build_series(queryset, trunc_fn, date_format: str, start_date=None, end_date=None):
                filtered_queryset = queryset
                if start_date:
                    filtered_queryset = filtered_queryset.filter(
                        ended_at__date__gte=start_date
                    )

                if end_date:
                    filtered_queryset = filtered_queryset.filter(ended_at__date__lt=end_date)

                session_ids = list(filtered_queryset.values_list("id", flat=True))

                records = filtered_queryset.annotate(period=trunc_fn("ended_at")).values(
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
                period_labels: dict = {}
                fuel_totals: dict[str, dict] = defaultdict(lambda: defaultdict(lambda: decimal_zero))
                product_totals: dict[str, dict] = defaultdict(
                    lambda: defaultdict(lambda: decimal_zero)
                )

                for record in records:
                    period = record["period"]
                    if not period:
                        continue

                    period_labels.setdefault(period, period.strftime(date_format))
                    totals = grouped_totals.setdefault(
                        period,
                        {
                            "total_credit": decimal_zero,
                            "total_voucher": decimal_zero,
                            "total_withdrawal": decimal_zero,
                            "total_product_sales": decimal_zero,
                            "total_fuel_payment": decimal_zero,
                            "total_firefighter_payment": decimal_zero,
                            "total_product_load_payment": decimal_zero,
                        },
                    )
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

                fuel_records = (
                    ServiceSessionFuelSale.objects.filter(
                        service_session_id__in=session_ids
                    )
                    .annotate(period=trunc_fn("service_session__ended_at"))
                    .values("period", "fuel_type")
                    .annotate(total=Sum("liters_sold"))
                )

                for record in fuel_records:
                    period = record["period"]
                    fuel_type = record["fuel_type"] or "Combustible"
                    if not period:
                        continue

                    period_labels.setdefault(period, period.strftime(date_format))
                    fuel_totals[fuel_type][period] += record["total"] or decimal_zero

                product_records = (
                    ServiceSessionProductSaleItem.objects.filter(
                        sale__service_session_id__in=session_ids
                    )
                    .annotate(period=trunc_fn("sale__service_session__ended_at"))
                    .values("period", "product__product_type")
                    .annotate(
                        total=Sum(
                            F("quantity") * F("product__value"),
                            output_field=DecimalField(
                                max_digits=14,
                                decimal_places=2,
                            ),
                        )
                    )
                )

                for record in product_records:
                    period = record["period"]
                    product_type = record["product__product_type"] or "Producto"
                    if not period:
                        continue

                    period_labels.setdefault(period, period.strftime(date_format))
                    product_totals[product_type][period] += record["total"] or decimal_zero

                ordered_periods = [
                    item[0] for item in sorted(period_labels.items(), key=lambda item: item[0])
                ]
                labels = [period_labels[period] for period in ordered_periods]

                total_series = []
                for period in ordered_periods:
                    totals = grouped_totals.get(period)
                    if not totals:
                        continue

                    total_profit = (
                        + totals["total_credit"]
                        + totals["total_voucher"]
                        + totals["total_withdrawal"]
                        + totals["total_product_sales"]
                        - totals["total_fuel_payment"]
                        - totals["total_firefighter_payment"]
                        - totals["total_product_load_payment"]
                    )

                    total_series.append(
                        {
                            "label": period_labels[period],
                            "value": float(total_profit or decimal_zero),
                        }
                    )

                def build_grouped_series(grouped: dict[str, dict]):
                    grouped_series: dict[str, list[dict]] = {}
                    for entry, period_totals in grouped.items():
                        grouped_series[entry] = [
                            {
                                "label": period_labels[period],
                                "value": float(period_totals.get(period) or decimal_zero),
                            }
                            for period in ordered_periods
                            if period in period_totals
                        ]
                    return grouped_series

                return {
                    "labels": labels,
                    "total": total_series,
                    "fuels": build_grouped_series(fuel_totals),
                    "products": build_grouped_series(product_totals),
                }

            for branch in branches:
                branch_sessions = annotated_sessions.filter(shift__sucursal=branch)
                if not branch_sessions.exists():
                    continue
            for branch in branches:
                branch_sessions = annotated_sessions.filter(shift__sucursal=branch)
                if not branch_sessions.exists():
                    continue

                last_session = branch_sessions.order_by("-ended_at").values_list(
                    "ended_at", flat=True
                ).first()
                if not last_session:
                    continue

                last_session_date = timezone.localtime(last_session).date()

                start_of_week = last_session_date - timezone.timedelta(days=6)
                start_of_week_range = last_session_date - timezone.timedelta(weeks=11)
                start_of_year_range = date(last_session_date.year - 3, 1, 1)
                end_of_range = last_session_date + timezone.timedelta(days=1)

                profit_dashboard.append(
                    {
                        "branch_name": branch.name,
                        "city": branch.city,
                        "series": {
                            "day": build_series(
                                branch_sessions,
                                TruncDay,
                                "%d %b",
                                start_of_week,
                                end_of_range,
                            ),
                            "week": build_series(
                                branch_sessions,
                                TruncWeek,
                                "%d %b",
                                start_of_week_range,
                                end_of_range,
                            ),
                            "year": build_series(
                                branch_sessions,
                                TruncYear,
                                "%Y",
                                start_of_year_range,
                                end_of_range,
                            ),
                        },
                    }
                )

        context["company"] = company
        context["fuel_dashboard"] = fuel_dashboard
        context["profit_dashboard"] = profit_dashboard

        return context


