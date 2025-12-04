from pathlib import Path
import os
import environ
import datetime as dt

# 1) Define BASE_DIR primero
BASE_DIR = Path(__file__).resolve().parent.parent

# 2) Inicializa environ y dile EXACTAMENTE dónde está el .env
env = environ.Env()

env_file = BASE_DIR / ".env"
environ.Env.read_env(env_file)  # <- ahora sabe la ruta correcta

env = environ.Env()
environ.Env.read_env()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# -------------------------
# SECURITY / ENVIRONMENT
# -------------------------
SECRET_KEY = env("SECRET_KEY", default="dev-secret-key-change-me")

DEBUG = env.bool("DEBUG", default=False)

raw_allowed_hosts = env("ALLOWED_HOSTS", default="*")
ALLOWED_HOSTS = (
    [host.strip() for host in raw_allowed_hosts.split(",") if host.strip()]
    if raw_allowed_hosts
    else []
)




METABASE_SITE_URL = os.getenv("METABASE_SITE_URL", "http://10.64.89.194:3000")
METABASE_SECRET_KEY = os.getenv("METABASE_SECRET_KEY", "e2b7ad66de03e18a54fc6414e5c8a7616708f3a77748e24c0cdce579fff696fc")


# Application definition

DEFAULT_DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

LOCAL_APPS = [
    "homeApp",
    "UsuarioApp",
    "sucursalApp",
]

THIRD_APPS = [
    "tailwind",
    "theme",
    "allauth",
    "allauth.account",
    "widget_tweaks",
    "allauth.mfa",
    "crispy_forms",
    "crispy_tailwind",
    "preventconcurrentlogins",
    "axes",
]

INSTALLED_APPS = DEFAULT_DJANGO_APPS + LOCAL_APPS + THIRD_APPS

TAILWIND_APP_NAME = "theme"

INTERNAL_IPS = env.list("INTERNAL_IPS", default=[])

NPM_BIN_PATH = os.environ.get("NPM_BIN_PATH")

CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "preventconcurrentlogins.middleware.PreventConcurrentLoginsMiddleware",
    "axes.middleware.AxesMiddleware",
    "homeApp.middleware.UpdateLastActivityMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [TEMPLATES_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.service_session_navigation",
            ],
        },
    },
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

WSGI_APPLICATION = "core.wsgi.application"

MFA_ADAPTER = "allauth.mfa.adapter.DefaultMFAAdapter"

MFA_FORMS = {
    "authenticate": "allauth.mfa.forms.AuthenticateForm",
    "reauthenticate": "allauth.mfa.forms.AuthenticateForm",
    "activate_totp": "allauth.mfa.forms.ActivateTOTPForm",
    "deactivate_totp": "allauth.mfa.forms.DeactivateTOTPForm",
}

SITE_ID = 1

# -------------------------
# DATABASE
# -------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env("DB_NAME", default="bencidata"),
        'USER': env("DB_USER", default="bencidata"),
        'PASSWORD': env("DB_PASSWORD", default="bencidata"),
        'HOST': env("DB_HOST", default="localhost"),
        'PORT': env("DB_PORT", default="5432"),
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -------------------------
# INTERNATIONALIZATION
# -------------------------

LANGUAGE_CODE = "es-us"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# -------------------------
# STATIC & MEDIA
# -------------------------

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------
# EMAIL (con defaults)
# -------------------------

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)

EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")

# -------------------------
# ALLAUTH
# -------------------------

ACCOUNT_FORMS = {"login": "UsuarioApp.forms.CustomLoginForm"}
ACCOUNT_ALLOW_REGISTRATION = True

ACCOUNT_AUTHENTICATED_LOGIN_REDIRECTS = False
LOGIN_REDIRECT_URL = "Home"

ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True

ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3

ACCOUNT_LOGOUT_ON_GET = True

SESSION_COOKIE_AGE = 60 * 60 * 24 * 365

LOGIN_URL = "account_login"

# -------------------------
# MFA + AXES
# -------------------------

MFA_RECOVERY_CODE_COUNT = 10
MFA_TOTP_PERIOD = 30
MFA_TOTP_DIGITS = 6

delta = dt.timedelta(minutes=5)

AXES_FAILURE_LIMIT = 3
AXES_COOLOFF_TIME = delta
AXES_RESET_ON_SUCCESS = True
AXES_ENABLE_ACCESS_FAILURE_LOG = True
AXES_LOCK_OUT_AT_FAILURE = True

# -------------------------
# LOGGING
# -------------------------

if not DEBUG:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    }
