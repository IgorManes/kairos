"""Notificações no celular: service worker, assinar, remover e testar."""

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from . import push
from .models import AssinaturaPush
from .views import responder_acao


@login_not_required  # o navegador busca o service worker sem passar pelo login
def service_worker(request):
    """Servido na raiz (/sw.js): um service worker só vale para as páginas abaixo do endereço dele."""
    resposta = HttpResponse(
        (settings.BASE_DIR / "static" / "js" / "sw.js").read_bytes(), content_type="text/javascript; charset=utf-8"
    )
    resposta["Cache-Control"] = "no-cache"  # versão nova do Kairos = service worker novo na hora
    return resposta


def nome_do_aparelho(user_agent):
    for trecho, nome in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows")):
        if trecho in user_agent:
            return nome
    return "Mac" if "Macintosh" in user_agent else "Aparelho"


def _chave_valida(texto, tamanho):
    try:
        return len(push.de_b64(texto)) == tamanho
    except ValueError:
        return False


@require_POST
def assinar(request):
    """O aparelho aceitou: guarda o endereço de entrega e as chaves dele."""
    endpoint = request.POST.get("endpoint", "")
    p256dh = request.POST.get("p256dh", "")
    auth = request.POST.get("auth", "")
    # Só https e chaves do tamanho certo (65 bytes = ponto da curva; 16 = segredo).
    if not endpoint.startswith("https://") or not _chave_valida(p256dh, 65) or not _chave_valida(auth, 16):
        return HttpResponseBadRequest("Assinatura inválida")
    AssinaturaPush.objects.update_or_create(
        endpoint=endpoint,
        defaults={"p256dh": p256dh, "auth": auth, "aparelho": nome_do_aparelho(request.headers.get("User-Agent", ""))},
    )
    return responder_acao(request, "Avisos ativados neste aparelho")


@require_POST
def remover(request, pk):
    assinatura = get_object_or_404(AssinaturaPush, pk=pk)
    assinatura.delete()
    return responder_acao(request, f"{assinatura} não recebe mais avisos")


@require_POST
def testar(request):
    aceitos = push.enviar_para_todos("Teste do Kairos", "Se você vê isto, os avisos chegam aqui.", "/configuracoes/")
    total = AssinaturaPush.objects.count()
    if not total:
        return responder_acao(request, "Nenhum aparelho recebe avisos")
    return responder_acao(request, f"Teste enviado: {aceitos} de {total} aparelho(s) aceitaram")
