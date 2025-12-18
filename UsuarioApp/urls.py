from django.urls import path
from UsuarioApp import views

urlpatterns = [
    path("usuarios/", views.UserListView.as_view(), name="User"),
    path(
        "usuarios/<hashid:pk>/editar/",
        views.UserUpdateView.as_view(),
        name="UserEdit",
    ),
    path(
        "usuarios/<hashid:pk>/eliminar/",
        views.UserDeleteView.as_view(),
        name="UserDelete",
    ),
    path(
        "usuarios/<hashid:pk>/desactivar/",
        views.UserDeactivateView.as_view(),
        name="UserDeactivate",
    ),
    path(
        "usuarios/<hashid:pk>/reactivar/",
        views.UserReactivateView.as_view(),
        name="UserReactivate",
    ),
    path("registro/", views.UserCreateView.as_view(), name="Register"),
    path("perfil/", views.ProfileUpdateView.as_view(), name="Profile"),
    path("configuracion/", views.ConfigurationView.as_view(), name="configuracion"),
    path("empresa/", views.CompanyUpdateView.as_view(), name="company_edit"),
]
