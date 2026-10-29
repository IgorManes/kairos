"""
Configurações do Kairos.

Tudo que muda entre máquinas ou é sensível vem do arquivo .env
(veja .env.example). O resto fica fixo aqui.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Pasta do código (onde está o manage.py).
BASE_DIR = Path(__file__).resolve().parent.parent

# Lê o .env e joga os valores nas variáveis de ambiente.
load_dotenv(BASE_DIR / ".env")


def env_bool(nome, padrao=False):
    """Lê uma variável do .env como verdadeiro/falso."""
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in ("1", "true", "sim", "yes", "on")


# --- Segurança -------------------------------------------------------------

# Sem chave, o app não sobe (fail fast). Uma chave padrão no código seria
# pública no GitHub e permitiria forjar sessões de login.
try:
    SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
except KeyError:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY não definida. Copie .env.example para .env "
        "e gere uma chave (veja o README)."
    ) from None

# Padrão False: se esquecer de configurar, fica no modo seguro.
DEBUG = env_bool("DJANGO_DEBUG", padrao=False)

# Endereço onde o app escuta. Hoje 127.0.0.1; no futuro, o IP do Tailscale.
KAIROS_HOST = os.environ.get("KAIROS_HOST", "127.0.0.1")
KAIROS_PORT = int(os.environ.get("KAIROS_PORT", "8765"))

ALLOWED_HOSTS = list(dict.fromkeys([KAIROS_HOST, "127.0.0.1", "localhost"]))


# --- Pasta de dados (fora do código) ---------------------------------------

# Banco, token do Google e backups ficam em %LOCALAPPDATA%\Kairos\,
# longe do repositório, para nunca irem parar num commit.
_padrao_dados = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Kairos"
DATA_DIR = Path(os.environ.get("KAIROS_DATA_DIR") or _padrao_dados)
DATA_DIR.mkdir(parents=True, exist_ok=True)


# --- Aplicações ------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tarefas",
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
        "DIRS": [],
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


# --- Banco de dados --------------------------------------------------------

# PC de casa: kairos.sqlite3 (dados reais). Notebook: dev.sqlite3 (testes).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / os.environ.get("KAIROS_DB_NAME", "kairos.sqlite3"),
    }
}


# --- Senhas ----------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Idioma e fuso ---------------------------------------------------------

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True  # guarda em UTC no banco, mostra no fuso de São Paulo


# --- Arquivos estáticos ----------------------------------------------------

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
