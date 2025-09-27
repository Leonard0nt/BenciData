from django.urls import path

from . import views

urlpatterns = [
    path("", views.SucursalListView.as_view(), name="sucursal_list"),
    path("nueva/", views.SucursalCreateView.as_view(), name="sucursal_create"),
    path("<int:pk>/editar/", views.SucursalUpdateView.as_view(), name="sucursal_update"),
    path(
        "<int:branch_pk>/islas/nueva/",
        views.IslandCreateView.as_view(),
        name="sucursal_island_create",
    ),
    path(
        "<int:branch_pk>/islas/<int:pk>/editar/",
        views.IslandUpdateView.as_view(),
        name="sucursal_island_update",
    ),
    path(
        "<int:branch_pk>/islas/<int:pk>/eliminar/",
        views.IslandDeleteView.as_view(),
        name="sucursal_island_delete",
    ),
    path(
        "<int:branch_pk>/islas/<int:island_pk>/maquinas/nueva/",
        views.MachineCreateView.as_view(),
        name="sucursal_machine_create",
    ),
    path(
        "maquinas/<int:pk>/editar/",
        views.MachineUpdateView.as_view(),
        name="sucursal_machine_update",
    ),
    path(
        "maquinas/<int:pk>/eliminar/",
        views.MachineDeleteView.as_view(),
        name="sucursal_machine_delete",
    ),
    path(
        "maquinas/<int:machine_pk>/pistolas/nueva/",
        views.NozzleCreateView.as_view(),
        name="sucursal_nozzle_create",
    ),
    path(
        "pistolas/<int:pk>/editar/",
        views.NozzleUpdateView.as_view(),
        name="sucursal_nozzle_update",
    ),
    path(
        "pistolas/<int:pk>/eliminar/",
        views.NozzleDeleteView.as_view(),
        name="sucursal_nozzle_delete",
    ),
]