from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from sucursalApp.views import ServiceSessionCreateView, ServiceSessionDetailView

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
        "servicios/<int:pk>/",
        ServiceSessionDetailView.as_view(),
        name="service_session_detail",
    ),
    path("sucursales/", include("sucursalApp.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
