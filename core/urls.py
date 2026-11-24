from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, register_converter

from sucursalApp.views import (
    ServiceSessionCreateView,
    ServiceSessionDetailView,
    ServiceSessionRecordDeleteView,
)

from utils.hashids import HashidConverter

register_converter(HashidConverter, "hashid")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("homeApp.urls")),
    path("", include("UsuarioApp.urls")),
    path(
        "servicios/inicio/",
        ServiceSessionCreateView.as_view(),
        name="service_session_start",
    ),
    path(
        "servicios/<hashid:pk>/",
        ServiceSessionDetailView.as_view(),
        name="service_session_detail",
    ),
    path(
        "servicios/<hashid:pk>/eliminar/",
        ServiceSessionRecordDeleteView.as_view(),
        name="service_session_record_delete",
    ),
    path("sucursales/", include("sucursalApp.urls")),
    path("", include("iotApp.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
