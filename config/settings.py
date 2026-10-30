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
    "axes",
    "django_tailwind_cli",
    "template_partials",
    "tarefas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Toda tela exige login, exceto as marcadas como públicas (ex.: login).
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # O axes precisa ser o último.
    "axes.middleware.AxesMiddleware",
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
                "tarefas.views_google.contexto_sync",  # situação do sync do Google
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


# --- Login e sessão --------------------------------------------------------

# O axes confere primeiro se o IP está bloqueado; depois, a senha normal.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "hoje"
LOGOUT_REDIRECT_URL = "login"

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 dias, para não pedir login toda hora

# Proteção contra força bruta: 5 erros bloqueiam o IP por 1 hora.
# Bloqueia por IP (não por usuário) para ninguém conseguir te trancar fora.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # horas
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ["ip_address"]


# --- Idioma e fuso ---------------------------------------------------------

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True  # guarda em UTC no banco, mostra no fuso de São Paulo


# --- Arquivos estáticos ----------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Tailwind via executável standalone (sem Node). Versão fixa para as duas
# máquinas gerarem o mesmo CSS. O fonte fica fora de static/ (o pacote exige);
# o CSS gerado vai para static/css/tailwind.css e não é commitado.
TAILWIND_CLI_VERSION = "4.3.3"
TAILWIND_CLI_SRC_CSS = "assets/css/kairos.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"

# --- Google (etapa 4) -------------------------------------------------------

# credentials.json (baixado do Google Cloud) e token.json (gerado no login)
# ficam na pasta de dados, nunca no repositório.
GOOGLE_CREDENCIAIS = DATA_DIR / "credentials.json"
GOOGLE_TOKEN = DATA_DIR / "token.json"


def ler_agendas_extras(texto):
    """'Invoga=a@b.com, Outra=c@d.com' → [("Invoga", "a@b.com"), ("Outra", "c@d.com")]."""
    agendas = []
    for item in (texto or "").split(","):
        nome, _, email = item.partition("=")
        if nome.strip() and email.strip():
            agendas.append((nome.strip(), email.strip()))
    return agendas


# Agendas sincronizadas: a principal (regra "aceitei ou organizei") e as de
# empresa do .env (regra "tudo, menos recusados"). O ID da agenda de uma conta
# é o próprio e-mail.
GOOGLE_AGENDAS = [{"id": "primary", "nome": "", "email": None, "regra": "aceitos"}] + [
    {"id": email, "nome": nome, "email": email, "regra": "nao_recusados"}
    for nome, email in ler_agendas_extras(os.environ.get("GOOGLE_AGENDAS_EXTRAS"))
]

# Página mostrada quando o axes bloqueia o login.
AXES_LOCKOUT_TEMPLATE = "registration/bloqueado.html"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
