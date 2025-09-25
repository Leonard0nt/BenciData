from django.urls import path

from . import views

urlpatterns = [
    path("", views.SucursalListView.as_view(), name="sucursal_list"),
    path("nueva/", views.SucursalCreateView.as_view(), name="sucursal_create"),
    path("<int:pk>/editar/", views.SucursalUpdateView.as_view(), name="sucursal_update"),
    path(
        "<int:branch_pk>/turnos/gestion/",
        views.BranchShiftManagementView.as_view(),
        name="branch_shift_management",
    ),
    path(
        "<int:branch_pk>/turnos/",
        views.ShiftListView.as_view(),
        name="shift_list",
    ),
    path(
        "<int:branch_pk>/turnos/nuevo/",
        views.ShiftCreateView.as_view(),
        name="shift_create",
    ),
    path(
        "turnos/<int:pk>/editar/",
        views.ShiftUpdateView.as_view(),
        name="shift_update",
    ),
    path(
        "turnos/<int:pk>/eliminar/",
        views.ShiftDeleteView.as_view(),
        name="shift_delete",
    ),
    path(
        "<int:branch_pk>/turnos/asignaciones/",
        views.ShiftAssignmentListView.as_view(),
        name="shift_assignment_list",
    ),
    path(
        "<int:branch_pk>/turnos/asignaciones/nueva/",
        views.ShiftAssignmentCreateView.as_view(),
        name="shift_assignment_create",
    ),
    path(
        "turnos/asignaciones/<int:pk>/editar/",
        views.ShiftAssignmentUpdateView.as_view(),
        name="shift_assignment_update",
    ),
    path(
        "turnos/asignaciones/<int:pk>/eliminar/",
        views.ShiftAssignmentDeleteView.as_view(),
        name="shift_assignment_delete",
    ),
]