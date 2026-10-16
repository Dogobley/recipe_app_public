"""Environment-configured Django settings."""

import os
from hashlib import sha256
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCTION = os.environ.get("DJANGO_ENV", "development").lower() == "production"


def env_flag(name: str, default: bool = False) -> bool:
    """Read a conventional true/false environment variable."""
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


PLACEHOLDER_VALUES = {
    "replace-with-a-long-random-secret",
    "replace-with-a-local-database-password",
}


def required_environment(name: str, *, reject_placeholder: bool = False) -> str:
    """Return a required production setting with an actionable error."""
    value = os.environ.get(name, "")
    if not value:
        raise ImproperlyConfigured(
            f"{name} must be set when DJANGO_ENV=production."
        )
    if reject_placeholder and value in PLACEHOLDER_VALUES:
        raise ImproperlyConfigured(
            f"{name} must not use an example placeholder when DJANGO_ENV=production."
        )
    return value


# A local checkout needs no committed secret. Deployments must provide a secret.
SECRET_KEY = (
    required_environment("DJANGO_SECRET_KEY", reject_placeholder=True)
    if PRODUCTION
    else os.environ.get("DJANGO_SECRET_KEY", sha256(str(BASE_DIR).encode()).hexdigest())
)
DEBUG = env_flag("DJANGO_DEBUG", default=not PRODUCTION)
if PRODUCTION and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be false when DJANGO_ENV=production.")
ALLOWED_HOSTS = [
    host.strip()
    for host in (
        required_environment("DJANGO_ALLOWED_HOSTS")
        if PRODUCTION
        else os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
    ).split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in (
        required_environment("DJANGO_CSRF_TRUSTED_ORIGINS") if PRODUCTION else os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "")
    ).split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "calculator.apps.CalculatorConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_ENGINE = (
    required_environment("DJANGO_DB_ENGINE")
    if PRODUCTION
    else os.environ.get("DJANGO_DB_ENGINE", "django.db.backends.sqlite3")
)
if PRODUCTION and DATABASE_ENGINE != "django.db.backends.postgresql":
    raise ImproperlyConfigured("DJANGO_DB_ENGINE must be django.db.backends.postgresql in production.")

DATABASES = {
    "default": {
        "ENGINE": DATABASE_ENGINE,
        "NAME": os.environ.get(
            "DJANGO_DB_NAME",
            (
                required_environment("DJANGO_DB_NAME")
                if PRODUCTION
                else "" if DATABASE_ENGINE != "django.db.backends.sqlite3" else str(BASE_DIR / "db.sqlite3")
            ),
        ),
    }
}

if DATABASE_ENGINE != "django.db.backends.sqlite3":
    DATABASES["default"].update(
        {
            "USER": required_environment("DJANGO_DB_USER") if PRODUCTION else os.environ.get("DJANGO_DB_USER", ""),
            "PASSWORD": (
                required_environment("DJANGO_DB_PASSWORD", reject_placeholder=True)
                if PRODUCTION
                else os.environ.get("DJANGO_DB_PASSWORD", "")
            ),
            "HOST": required_environment("DJANGO_DB_HOST") if PRODUCTION else os.environ.get("DJANGO_DB_HOST", ""),
            "PORT": required_environment("DJANGO_DB_PORT") if PRODUCTION else os.environ.get("DJANGO_DB_PORT", ""),
        }
    )

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
