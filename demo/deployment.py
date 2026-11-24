import os

from demo.settings import *  # noqa: F403 - reutiliza la configuración de la demo.

DEBUG = False
DEMO_HTTPS = os.environ.get("BENCIDATA_DEMO_HTTPS", "0") == "1"
SESSION_COOKIE_SECURE = DEMO_HTTPS
CSRF_COOKIE_SECURE = DEMO_HTTPS
CSRF_TRUSTED_ORIGINS = os.environ.get("BENCIDATA_DEMO_CSRF_ORIGINS", "").split()

if DEMO_HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
