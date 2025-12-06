from django.shortcuts import render

# Create your views here.
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.utils import timezone
import json

# Si creaste el modelo:
from .models import DispenseEvent


@csrf_exempt  # Arduino no manda CSRF, así que lo desactivamos SOLO aquí
def recibir_datos_proxy(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"], "Solo se permite POST")

    # 1) Parsear JSON del body
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("JSON inválido")

    # 2) Leer campos enviados por el Arduino
    uid = data.get("uid")              # Ej: "4 8C 8D B2 2B 64 81"
    litros = data.get("litros")        # Ej: 12.34
    pistola = data.get("pistola")      # Ej: 1
    timestamp = data.get("timestamp")  # Ej: millis, epoch, ISO, etc.

    # 3) Validar mínimos
    if not uid or litros is None:
        return HttpResponseBadRequest("Faltan campos 'uid' o 'litros'")

    # 4) Guardar en BD (si tienes el modelo)
    event = DispenseEvent.objects.create(
        uid=uid,
        litros=float(litros),
        pistola=pistola,
        timestamp_arduino=str(timestamp) if timestamp is not None else None,
    )

    # 5) Puedes loguear en consola también
    print("✅ Evento IoT recibido:", data)

    # 6) Respuesta al Arduino
    return JsonResponse(
        {
            "status": "ok",
            "event_id": event.id,
            "received_at": timezone.now().isoformat(),
        }
    )
