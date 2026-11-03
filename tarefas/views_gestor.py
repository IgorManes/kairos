"""Mini-site do gestor (login, painel, sair) e as ações dele nas Configurações do dono."""

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.signals import user_login_failed
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from . import consultas, gestor
from .models import Projeto
from .views import responder_acao

# ===== Mini-site (internet) =====


@login_not_required  # o login do gestor é o cookie próprio (gestor.py), não a sessão
@require_http_methods(["GET", "POST"])
def entrar(request):
    if request.gestor:
        return redirect("gestor_painel")
    erro = ""
    if request.method == "POST":
        nome = request.POST.get("username", "").strip()
        senha = request.POST.get("password", "")
        conta = gestor.usuario_gestor()
        if conta is not None and nome == conta.username:
            usuario = authenticate(request, username=nome, password=senha)  # o axes conta erros e bloqueia
        else:
            # Outro usuário (ex.: o dono): a senha nem é conferida aqui, mas a tentativa conta no bloqueio.
            usuario = None
            user_login_failed.send(sender=__name__, credentials={"username": nome}, request=request)
        if usuario is not None and gestor.e_gestor(usuario):
            resposta = redirect("gestor_painel")
            resposta.set_cookie(
                gestor.COOKIE,
                gestor.cookie_de_login(usuario),
                max_age=gestor.DURACAO,
                httponly=True,  # o JavaScript da página não lê o cookie
                secure=request.is_secure(),
                samesite="Lax",
            )
            return resposta
        erro = "Usuário ou senha incorretos."
    return render(request, "gestor/entrar.html", {"erro": erro, "usuario": request.POST.get("username", "")})


@login_not_required
def painel(request):
    if not request.gestor:
        return redirect("gestor_entrar")
    contexto = consultas.carga_gestor(ver=request.GET.get("ver"))
    contexto["dono"] = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
    return render(request, "gestor/painel.html", contexto)


@login_not_required
@require_POST
def sair(request):
    resposta = redirect("gestor_entrar")
    resposta.delete_cookie(gestor.COOKIE, samesite="Lax")
    return resposta


# ===== Configurações do dono (Kairos completo) =====


@require_POST
def definir_senha(request):
    senha = request.POST.get("senha", "")
    if senha != request.POST.get("confirmacao", ""):
        return responder_acao(request, "As senhas não conferem")
    try:
        validate_password(senha, user=gestor.usuario_gestor())
    except ValidationError as erro:
        return responder_acao(request, " ".join(erro.messages))
    gestor.definir_senha(senha)
    return responder_acao(request, "Senha do gestor salva (quem estava logado precisa entrar de novo)")


@require_POST
def alternar_acesso(request):
    conta = gestor.usuario_gestor()
    if conta is None:
        return responder_acao(request, "Defina a senha do gestor primeiro")
    conta.is_active = request.POST.get("valor") == "on"
    conta.save(update_fields=["is_active"])
    return responder_acao(request, f"Acesso do gestor: {'ligado' if conta.is_active else 'desligado'}")


@require_POST
def alternar_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    projeto.visivel_gestor = request.POST.get("valor") == "on"
    projeto.save(update_fields=["visivel_gestor"])
    estado = "visível ao gestor" if projeto.visivel_gestor else "oculto do gestor"
    return responder_acao(request, f"{projeto.nome}: {estado}")
