"""
Login no Google (OAuth) e token de acesso.

- credentials.json: identifica o app Kairos no Google (baixado do Google Cloud).
- token.json: a autorização do dono, gerada no primeiro login e renovada sozinha.
Os dois ficam em %LOCALAPPDATA%\\Kairos\\, nunca no repositório.
"""

from django.conf import settings

# Somente leitura. Etapa 5 acrescenta os escopos do Classroom.
ESCOPOS = ["https://www.googleapis.com/auth/calendar.events.readonly"]


class SemConexaoGoogle(Exception):
    """Ainda não conectou a conta (ou a autorização foi revogada)."""


def obter_credenciais(interativo=False):
    """
    Devolve credenciais válidas. Com `interativo=True` (comando --conectar),
    abre o navegador para o login quando necessário; sem isso, nunca abre
    janela por conta própria e avisa que falta conectar.
    """
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credenciais = None
    if settings.GOOGLE_TOKEN.exists():
        credenciais = Credentials.from_authorized_user_file(str(settings.GOOGLE_TOKEN), ESCOPOS)

    if credenciais and credenciais.valid:
        return credenciais

    if credenciais and credenciais.expired and credenciais.refresh_token:
        try:
            credenciais.refresh(Request())  # renova sem pedir login de novo
            salvar_token(credenciais)
            return credenciais
        except RefreshError:
            credenciais = None  # autorização revogada: precisa conectar de novo

    if not interativo:
        raise SemConexaoGoogle("Conta Google não conectada. Rode: python manage.py sincronizar --conectar")
    if not settings.GOOGLE_CREDENCIAIS.exists():
        raise SemConexaoGoogle(f"Arquivo não encontrado: {settings.GOOGLE_CREDENCIAIS}")

    fluxo = InstalledAppFlow.from_client_secrets_file(str(settings.GOOGLE_CREDENCIAIS), ESCOPOS)
    credenciais = fluxo.run_local_server(port=0, prompt="consent")  # abre o navegador
    salvar_token(credenciais)
    return credenciais


def salvar_token(credenciais):
    settings.GOOGLE_TOKEN.write_text(credenciais.to_json(), encoding="utf-8")


def servico_agenda(credenciais):
    from googleapiclient.discovery import build

    return build("calendar", "v3", credentials=credenciais, cache_discovery=False)
