"""
Login no Google (OAuth) e token de acesso.

- credentials.json: identifica o app Kairos no Google (baixado do Google Cloud).
- token.json: a autorização do dono, gerada no primeiro login e renovada sozinha.
Os dois ficam em %LOCALAPPDATA%\\Kairos\\, nunca no repositório.
"""

import os

from django.conf import settings

# Somente leitura.
ESCOPOS = [
    "https://www.googleapis.com/auth/calendar.events.readonly",   # eventos das agendas
    "https://www.googleapis.com/auth/classroom.courses.readonly",  # turmas
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",  # atividades e minhas entregas
]


# O Google tem nomes antigos e novos para a mesma permissão; o console e o token
# podem trazer qualquer um. Para cada escopo pedido, estes nomes também valem.
EQUIVALENTES = {
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly": {
        "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
    },
}


class SemConexaoGoogle(Exception):
    """Ainda não conectou a conta (ou a autorização foi revogada)."""


class PrecisaReconectar(SemConexaoGoogle):
    """O token é de antes de o Kairos pedir permissões novas (ex.: Classroom)."""


def escopos_faltando():
    """Permissões que o Kairos pede e o token salvo não tem (lista vazia = tudo certo)."""
    import json

    if not settings.GOOGLE_TOKEN.exists():
        return list(ESCOPOS)
    try:
        concedidos = set(json.loads(settings.GOOGLE_TOKEN.read_text(encoding="utf-8")).get("scopes") or [])
    except (ValueError, OSError):
        return list(ESCOPOS)
    return [e for e in ESCOPOS if not ({e} | EQUIVALENTES.get(e, set())) & concedidos]


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
    if settings.GOOGLE_TOKEN.exists() and escopos_faltando() and not interativo:
        raise PrecisaReconectar("O Kairos precisa de permissões novas: reconecte a conta Google nas Configurações.")
    if settings.GOOGLE_TOKEN.exists() and not escopos_faltando():
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

    # O Google deixa desmarcar permissões na tela de consentimento. Sem isto, a
    # biblioteca do OAuth dá erro quando recebe menos permissões do que pediu.
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    fluxo = InstalledAppFlow.from_client_secrets_file(str(settings.GOOGLE_CREDENCIAIS), ESCOPOS)
    credenciais = fluxo.run_local_server(port=0, prompt="consent")  # abre o navegador
    salvar_token(credenciais)
    faltando = escopos_faltando()
    if faltando:
        nomes = ", ".join(e.rsplit("/", 1)[1] for e in faltando)
        raise PrecisaReconectar(
            f"Faltou marcar permissões na tela do Google ({nomes}). Conecte de novo e marque todas as caixas."
        )
    return credenciais


def salvar_token(credenciais):
    """
    Grava o token com as permissões CONCEDIDAS (o padrão da biblioteca grava as
    pedidas; se o dono desmarcou alguma, o Kairos acharia que tem acesso e não tem).
    """
    import json

    dados = json.loads(credenciais.to_json())
    concedidas = getattr(credenciais, "granted_scopes", None)
    if concedidas:
        dados["scopes"] = sorted(concedidas)
    settings.GOOGLE_TOKEN.write_text(json.dumps(dados), encoding="utf-8")


def servico_agenda(credenciais):
    from googleapiclient.discovery import build

    return build("calendar", "v3", credentials=credenciais, cache_discovery=False)


def servico_classroom(credenciais):
    from googleapiclient.discovery import build

    return build("classroom", "v1", credentials=credenciais, cache_discovery=False)
