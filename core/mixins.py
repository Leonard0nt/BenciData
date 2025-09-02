from django.shortcuts import redirect
from django.urls import reverse_lazy


class RoleRequiredMixin:
    """Generic mixin to require specific profile roles for a view."""

    redirect_url = reverse_lazy("Home")
    allowed_roles = None  # list or tuple of allowed permission codes

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        profile = getattr(user, "profile", None)

        if user.is_superuser or (profile and profile.has_role(self.allowed_roles)):
            return super().dispatch(request, *args, **kwargs)
        return redirect(self.redirect_url)


class PermitsPositionMixin(RoleRequiredMixin):
    """Backward compatible mixin allowing any non-restricted role."""

    pass


class AdminRequiredMixin(RoleRequiredMixin):
    """Allow access only to users with the ADMIN role."""

    allowed_roles = ["ADMIN"]


class ManagerRequiredMixin(RoleRequiredMixin):
    """Allow access to MANAGER and ADMIN roles."""

    allowed_roles = ["MANAGER", "ADMIN"]