from django.shortcuts import render
from decimal import Decimal
import json
# Create your views here.
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Q
from django.http import HttpResponseBadRequest, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import render
import json
from django.views.decorators.csrf import csrf_exempt

from UsuarioApp.models import Profile
from sucursalApp.models import MachineFuelInventoryNumeral, Nozzle, ServiceSession
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
    try:
        litros_decimal = Decimal(str(litros))
    except Exception:
        return HttpResponseBadRequest("El valor de 'litros' no es válido")

    nozzle = None
    fuel_numeral = None
    firefighter = None
    service_session = None

    try:
        nozzle = (
            Nozzle.objects.select_related(
                "machine__island__sucursal", "fuel_numeral__fuel_inventory"
            )
            .filter(Q(code=str(pistola)) | Q(number=pistola))
            .first()
        )
        fuel_numeral = getattr(nozzle, "fuel_numeral", None)

        if nozzle and nozzle.machine and nozzle.machine.island:
            branch_id = nozzle.machine.island.sucursal_id
            service_session = (
                ServiceSession.objects.filter(
                    shift__sucursal_id=branch_id, ended_at__isnull=True
                )
                .order_by("-started_at")
                .first()
            )

        firefighter = Profile.objects.filter(
            codigo_identificador=uid
        ).select_related("user_FK").first()

        if fuel_numeral:
            with transaction.atomic():
                MachineFuelInventoryNumeral.objects.filter(pk=fuel_numeral.pk).update(
                    numeral=F("numeral") - litros_decimal
                )
                fuel_numeral.refresh_from_db(fields=["numeral"])
    except Exception as exc:  # pragma: no cover - defensive logging
        print("⚠️ Error procesando datos IoT:", exc)


    # 4) Guardar en BD (si tienes el modelo)
    event = DispenseEvent.objects.create(
        uid=uid,
        litros=float(litros_decimal),
        nozzle=nozzle,
        fuel_numeral=fuel_numeral,
        firefighter=firefighter,
        service_session=service_session,
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
