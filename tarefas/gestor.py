"""
Acesso web do gestor: um mini-site separado, só leitura, exposto na internet pelo Funnel.

Como os dois mundos ficam separados:
- O servidor do mini-site (outra porta local) marca cada pedido no próprio WSGI (`MARCA_SITE`).
  Cabeçalhos HTTP viram chaves "HTTP_..." no WSGI: ninguém de fora consegue forjar essa marca.
- No mini-site só existem as rotas de `config/urls_gestor.py`, e a sessão do dono é ignorada
  (cookies valem por endereço, não por porta: o navegador do dono mandaria a sessão dele).
- O gestor entra com um cookie assinado próprio; no Kairos completo ele é ignorado.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core import signing
from django.utils.crypto import constant_time_compare

MARCA_SITE = "kairos.site_gestor"
GRUPO = "gestor"
USUARIO = "gestor"
COOKIE = "kairos_gestor"
SAL = "kairos.gestor.login"
DURACAO = 30 * 24 * 3600  # 30 dias, como a sessão do dono
IP_INTERNET = "192.0.2.1"  # endereço reservado (documentação): "alguém na internet"


def app_do_gestor(aplicacao):
    """Envolve o app Django: todo pedido que chega por aqui é do mini-site."""

    def wsgi(environ, start_response):
        environ[MARCA_SITE] = True
        return aplicacao(environ, start_response)

    return wsgi


def no_site_gestor(request):
    return request.META.get(MARCA_SITE) is True


def e_gestor(usuario):
    return usuario.is_authenticated and usuario.groups.filter(name=GRUPO).exists()


def usuario_gestor():
    return get_user_model().objects.filter(groups__name=GRUPO).first()


def definir_senha(senha):
    """Cria o usuário gestor na primeira vez (ou troca a senha). Trocar derruba o acesso atual."""
    usuario = usuario_gestor()
    if usuario is None:
        usuario = get_user_model().objects.create_user(USUARIO)
        usuario.groups.add(Group.objects.get_or_create(name=GRUPO)[0])
    usuario.set_password(senha)
    usuario.is_active = True
    usuario.save()
    return usuario


# ===== Login por cookie assinado =====


def cookie_de_login(usuario):
    # A "impressão" da senha vai junto: trocar a senha invalida cookies antigos.
    return signing.dumps({"id": usuario.pk, "h": usuario.get_session_auth_hash()}, salt=SAL)


def gestor_do_cookie(request):
    valor = request.COOKIES.get(COOKIE)
    if not valor:
        return None
    try:
        dados = signing.loads(valor, salt=SAL, max_age=DURACAO)
    except signing.BadSignature:  # inclui o cookie vencido
        return None
    usuario = get_user_model().objects.filter(pk=dados.get("id"), is_active=True, groups__name=GRUPO).first()
    if usuario and constant_time_compare(str(dados.get("h", "")), usuario.get_session_auth_hash()):
        return usuario
    return None


class SiteGestorMiddleware:
    """Fica logo depois do AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if no_site_gestor(request):
            request.urlconf = "config.urls_gestor"  # só login, painel e sair
            request.user = AnonymousUser()  # a sessão do dono não vale aqui
            request.gestor = gestor_do_cookie(request)
        elif e_gestor(request.user):
            request.user = AnonymousUser()  # o gestor não usa o Kairos completo
        return self.get_response(request)
