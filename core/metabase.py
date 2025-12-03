# homeApp/metabase_utils.py
import time
import jwt
from django.conf import settings


def metabase_iframe(question_id: int, params=None) -> str:
    """
    Genera la URL de iframe firmada para una pregunta de Metabase.
    """
    payload = {
        "resource": {"question": question_id},
        "params": params or {},
        "exp": round(time.time()) + (60 * 10),  # 10 minutos
    }

    token = jwt.encode(
        payload,
        settings.METABASE_SECRET_KEY,
        algorithm="HS256",
    )

    iframe_url = (
        f"{settings.METABASE_SITE_URL}/embed/question/{token}"
        "#bordered=true&titled=true"
    )
    return iframe_url
