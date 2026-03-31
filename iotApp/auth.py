# iotApp/auth.py
import hmac
from django.conf import settings
from django.http import JsonResponse
from functools import wraps

def iot_token_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        token = request.headers.get("X-IoT-Token", "")
        expected = getattr(settings, "IOT_SECRET_TOKEN", "")
        if not expected or not hmac.compare_digest(token, expected):
            return JsonResponse({"error": "Unauthorized"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper