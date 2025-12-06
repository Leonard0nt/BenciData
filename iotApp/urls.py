# iotApp/urls.py
from django.urls import path
from .views import recibir_datos_proxy

urlpatterns = [
    path("api/iot/proxy/", recibir_datos_proxy, name="recibir_datos_proxy"),
]
