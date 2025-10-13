from django.urls import path
from UsuarioApp import views

urlpatterns = [
    path("usuarios/", views.UserListView.as_view(), name="User"),
    path(
        "usuarios/<int:pk>/editar/",
        views.UserUpdateView.as_view(),
        name="UserEdit",
    ),
    path(
        "usuarios/<int:pk>/eliminar/",
        views.UserDeleteView.as_view(),
        name="UserDelete",
    ),
    path("registro/", views.UserCreateView.as_view(), name="Register"),
    path("perfil/", views.ProfileUpdateView.as_view(), name="Profile"),
    path("configuracion/", views.ConfigurationView.as_view(), name="configuracion"),
    path("empresa/", views.CompanyUpdateView.as_view(), name="company_edit"),
]