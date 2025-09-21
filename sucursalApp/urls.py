from django.urls import path

from . import views

urlpatterns = [
    path("", views.SucursalListView.as_view(), name="sucursal_list"),
    path("nueva/", views.SucursalCreateView.as_view(), name="sucursal_create"),
    path("<int:pk>/editar/", views.SucursalUpdateView.as_view(), name="sucursal_update"),
]