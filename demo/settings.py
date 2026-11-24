from core.settings import *  # noqa: F403 - conserva la configuración base.

SESSION_COOKIE_SECURE = False
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
