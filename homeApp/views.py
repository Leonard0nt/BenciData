from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from UsuarioApp.models import Profile
from homeApp.models import Company
from core.metabase import metabase_iframe

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
        current_branch_id = None 
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

        context["company"] = company
        if current_branch_id is not None:
            # 👇 "branch_id" es el nombre del parámetro que vas a usar en Metabase
            params["branch_id"] = current_branch_id

        context["metabase_iframe_url"] = metabase_iframe(
            question_id=41
        )
        return context
