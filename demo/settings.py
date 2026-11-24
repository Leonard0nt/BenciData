from core.settings import *  # noqa: F403 - conserva la configuración base.
from core.settings import MIDDLEWARE as CORE_MIDDLEWARE

SESSION_COOKIE_SECURE = False
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

MIDDLEWARE = [
    middleware for middleware in CORE_MIDDLEWARE
    if middleware != "preventconcurrentlogins.middleware.PreventConcurrentLoginsMiddleware"
]
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware") + 1,
    "demo.access.DemoAccessMiddleware",
)
