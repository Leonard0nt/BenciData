from pathlib import Path

from django.contrib.auth import get_user_model
from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect

DEMO_ACCOUNTS = {
    "OWNER": "bencidata-demo-owner",
    "ADMINISTRATOR": "administrador-demo",
    "ACCOUNTANT": "secretaria-demo",
    "HEAD_ATTENDANT": "operador-demo",
    "ATTENDANT": "bombero-demo",
}
PROFILE_PATH = Path(__file__).with_name("profile.txt")
DEMO_ROLE = (
    PROFILE_PATH.read_text().strip() if PROFILE_PATH.is_file() else "HEAD_ATTENDANT"
)
DEMO_USERNAME = DEMO_ACCOUNTS[DEMO_ROLE]


class DemoAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info.rstrip("/")
        if path in {"/accounts/login", "/accounts/logout"}:
            return redirect("Home")
        if path in {"/admin", "/accounts"} or path.startswith(("/admin/", "/accounts/")):
            return HttpResponseNotFound()
        if path.startswith(("/api/iot/", "/media/", "/static/")):
            return self.get_response(request)

        # Cada petición usa la cuenta ficticia de la rama y conserva sus permisos.
        user = get_user_model().objects.select_related("profile__position_FK").filter(
            username=DEMO_USERNAME,
            is_active=True,
            is_superuser=False,
            profile__blocked=False,
            profile__position_FK__permission_code=DEMO_ROLE,
        ).first()
        if user is None:
            return HttpResponse("La cuenta de demo requiere inicialización.", status=503)

        request.user = user
        request.demo_access = True
        return self.get_response(request)
