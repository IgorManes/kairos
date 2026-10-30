"""Sincronizar agora, relógio do sync automático e tela de Configurações."""

import threading

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from .google.credenciais import obter_credenciais
from .google.servico import sincronizar_tudo, ultimo_sync
from .models import EstadoSync


def situacao_sync():
    """O que a barra lateral e as Configurações mostram sobre o sync."""
    conectado = settings.GOOGLE_TOKEN.exists()
    ultimo = ultimo_sync()
    com_erro = EstadoSync.objects.exclude(ultimo_erro="").order_by("-ultimo_erro_em").first()
    erro_recente = com_erro and (not ultimo or com_erro.ultimo_erro_em >= ultimo)

    if not conectado:
        estado, texto = "desconectado", "Google desconectado"
    elif erro_recente:
        estado, texto = "erro", "Erro no último sync"
    elif not ultimo:
        estado, texto = "nunca", "Ainda não sincronizado"
    else:
        segundos = (timezone.now() - ultimo).total_seconds()
        estado = "ok"
        texto = "Sincronizado agora" if segundos < 60 else f"Sincronizado há {int(segundos // 60)} min"
        if segundos >= 3600:
            texto = f"Sincronizado há {int(segundos // 3600)} h"
    return {"estado": estado, "texto": texto, "ultimo": ultimo, "conectado": conectado}


def contexto_sync(request):
    """Context processor: toda tela logada recebe a situação do sync."""
    if not request.user.is_authenticated:
        return {}
    return {"sync": situacao_sync()}


@require_POST
def sincronizar(request):
    """Chamado pelo relógio da página (auto/foco) e pelo botão "Sincronizar agora"."""
    motivo = request.POST.get("motivo", "auto")
    if motivo not in ("auto", "foco", "botao"):
        motivo = "auto"
    r = sincronizar_tudo(motivo=motivo)

    html = render_to_string("partials/sync_status.html", {"sync": situacao_sync()}, request)
    if motivo == "botao":
        mensagens = {
            "ok": "Sincronizado" + (" — com novidades" if r.mudou else ", nada novo"),
            "ocupado": "Já está sincronizando",
            "desconectado": "Conecte a conta Google nas Configurações",
            "erro": "Erro ao sincronizar (veja nas Configurações)",
        }
        html += render_to_string("tarefas/_resposta_acao.html", {"toast": {"mensagem": mensagens.get(r.situacao, "")}})
    resposta = HttpResponse(html)
    if r.mudou or motivo == "botao":
        resposta["HX-Trigger"] = "dadosMudaram"  # as telas abertas se atualizam
    return resposta


def configuracoes(request):
    estados = {e.fonte: e for e in EstadoSync.objects.all()}
    agendas = [
        {"nome": a["nome"] or "Agenda principal", "regra": a["regra"], "estado": estados.get(f"agenda:{a['id']}")}
        for a in settings.GOOGLE_AGENDAS
    ]
    return render(request, "tarefas/configuracoes.html", {
        "agendas": agendas,
        "tem_credenciais": settings.GOOGLE_CREDENCIAIS.exists(),
        "conectando": _conectando.is_set(),
    })


# ===== Conectar / desconectar a conta Google =====

_conectando = threading.Event()


def _login_em_segundo_plano():
    try:
        obter_credenciais(interativo=True)  # abre o navegador deste PC e espera a autorização
        sincronizar_tudo(motivo="botao")
    except Exception:
        pass  # a tela mostra "desconectado" e o usuário tenta de novo
    finally:
        _conectando.clear()


@require_POST
def conectar_google(request):
    if not settings.GOOGLE_CREDENCIAIS.exists():
        mensagem = "Falta o credentials.json na pasta de dados"
    elif _conectando.is_set():
        mensagem = "Já abrimos o navegador; termine a autorização lá"
    else:
        _conectando.set()
        threading.Thread(target=_login_em_segundo_plano, daemon=True).start()
        mensagem = "Abrimos o navegador: autorize o Kairos e volte aqui"
    resposta = render(request, "tarefas/_resposta_acao.html", {"toast": {"mensagem": mensagem}})
    resposta["HX-Trigger"] = "dadosMudaram"
    return resposta


@require_POST
def desconectar_google(request):
    """Revoga a autorização no Google e apaga o token local. As reuniões importadas continuam."""
    if settings.GOOGLE_TOKEN.exists():
        try:
            import requests
            from google.oauth2.credentials import Credentials

            credenciais = Credentials.from_authorized_user_file(str(settings.GOOGLE_TOKEN))
            requests.post("https://oauth2.googleapis.com/revoke", params={"token": credenciais.token},
                          headers={"content-type": "application/x-www-form-urlencoded"}, timeout=10)
        except Exception:
            pass  # mesmo sem internet, apagar o token local já desconecta este PC
        settings.GOOGLE_TOKEN.unlink(missing_ok=True)
    EstadoSync.objects.update(sync_token="")  # ao reconectar, começa com sync completo
    resposta = HttpResponse(render_to_string(
        "tarefas/_resposta_acao.html", {"toast": {"mensagem": "Conta Google desconectada"}}))
    resposta["HX-Refresh"] = "true"
    return resposta
