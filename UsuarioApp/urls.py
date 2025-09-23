from django.urls import path
from UsuarioApp import views

urlpatterns = [
    path("usuarios/", views.UserListView.as_view(), name="User"),
    path(
        "usuarios/turnos/",
        views.UserShiftManagementView.as_view(),
        name="user_shift_management",
    ),
    path("registro/", views.UserCreateView.as_view(), name="Register"),
    path("perfil/", views.ProfileUpdateView.as_view(), name="Profile"),
    path("configuracion/", views.ConfigurationView.as_view(), name="configuracion"),
    path("empresa/", views.CompanyUpdateView.as_view(), name="company_edit"),
]