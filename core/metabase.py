# core/metabase.py
import os
import time
import jwt  # PyJWT
from django.conf import settings

METABASE_SITE_URL = os.environ.get("METABASE_SITE_URL")
METABASE_SECRET_KEY = os.environ.get("METABASE_SECRET_KEY")


def metabase_iframe(question_id: int, params: dict | None = None,
                    width: str = "100%", height: int = 500) -> str:
    """
    Devuelve el HTML del iframe para un question embed de Metabase.
    """
    if not METABASE_SITE_URL or not METABASE_SECRET_KEY:
        return ""  # o levantar excepción si prefieres

    payload = {
        "resource": {"question": question_id},
        "params": params or {},
        # token válido por 10 minutos
        "exp": int(time.time()) + 60 * 10,
    }

    token = jwt.encode(payload, METABASE_SECRET_KEY, algorithm="HS256")
    # PyJWT a veces devuelve bytes en versiones antiguas
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    iframe_url = f"{METABASE_SITE_URL}/embed/question/{token}#bordered=true&titled=true"

    # HTML listo para incrustar
    return f'<iframe src="{iframe_url}" frameborder="0" width="{width}" height="{height}" allowtransparency></iframe>'
