import json
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import F
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from sucursalApp.models import MachineFuelInventoryNumeral, Nozzle, ServiceSession
from UsuarioApp.models import Profile

from .auth import iot_token_required
from .models import DispenseEvent


def find_nozzle(identifier):
    if identifier is None:
        return None

    nozzles = Nozzle.objects.select_related("machine__island")
    nozzle = nozzles.filter(code=identifier).first()
    if nozzle is not None:
        return nozzle

    # Los equipos antiguos pueden enviar el número en vez del código.
    try:
        number = int(identifier)
    except ValueError:
        return None
    return nozzles.filter(number=number).first()


@csrf_exempt
@iot_token_required
@require_POST
def recibir_datos_proxy(request):
    try:
        data = json.loads(request.body)
    except (UnicodeDecodeError, ValueError):
        return HttpResponseBadRequest("JSON inválido")
    if not isinstance(data, dict):
        return HttpResponseBadRequest("Se esperaba un objeto JSON")

    uid = data.get("uid")
    if not isinstance(uid, str) or not uid.strip() or len(uid) > 100:
        return HttpResponseBadRequest("El UID no es válido")

    try:
        liters = Decimal(str(data.get("litros")))
    except InvalidOperation:
        return HttpResponseBadRequest("El valor de 'litros' no es válido")
    if not liters.is_finite() or not 0 < liters < Decimal("1000000000"):
        return HttpResponseBadRequest("El valor de 'litros' está fuera de rango")

    identifier = data.get("pistola")
    timestamp = data.get("timestamp")
    nozzle_code = str(identifier) if identifier is not None else None
    device_timestamp = str(timestamp) if timestamp is not None else None
    if len(nozzle_code or "") > 50 or len(device_timestamp or "") > 100:
        return HttpResponseBadRequest("Identificador o marca de tiempo demasiado largos")

    operator = Profile.objects.filter(codigo_identificador=uid).first()
    if operator is None:
        return JsonResponse(
            {"status": "error", "message": "UID no asociado a ningún bombero"},
            status=400,
        )

    nozzle = find_nozzle(nozzle_code)
    session = None
    if nozzle is not None:
        session = (
            ServiceSession.objects.filter(
                shift__sucursal_id=nozzle.machine.island.sucursal_id,
                ended_at__isnull=True,
            )
            .order_by("-started_at", "-pk")
            .first()
        )

    numeral_id = nozzle.fuel_numeral_id if nozzle else None
    # El descuento y la lectura deben guardarse juntos.
    with transaction.atomic():
        if numeral_id is not None:
            MachineFuelInventoryNumeral.objects.filter(pk=numeral_id).update(
                numeral=F("numeral") - liters
            )
        event = DispenseEvent.objects.create(
            uid=uid,
            litros=float(liters),
            nozzle=nozzle,
            fuel_numeral_id=numeral_id,
            firefighter=operator,
            service_session=session,
            pistola=nozzle_code,
            timestamp_arduino=device_timestamp,
        )

    return JsonResponse(
        {
            "status": "ok",
            "event_id": event.pk,
            "received_at": event.created_at.isoformat(),
        }
    )
