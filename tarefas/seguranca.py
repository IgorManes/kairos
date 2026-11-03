"""Qual aparelho está acessando, para o bloqueio por senha errada (django-axes)."""

import ipaddress

from .gestor import IP_INTERNET, no_site_gestor


def ip_do_aparelho(request):
    if no_site_gestor(request):
        return _ip_pelo_funnel(request)
    return _ip_pelo_serve(request)


def _ip_pelo_funnel(request):
    """IP de quem acessa o mini-site do gestor pela internet.

    Testado em 2026-11-03: o Funnel SUBSTITUI o X-Forwarded-For pelo IP real (um cabeçalho
    falso mandado pelo visitante é descartado). Então cada IP tem o seu bloqueio e um
    atacante não trava o gestor. Sem o cabeçalho, ou com algo que não é IP, todas as
    tentativas contam juntas como "internet" (mais seguro). Nunca devolve 127.0.0.1:
    erros aqui não trancam a janela do PC.
    """
    candidato = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip()
    try:
        ip = ipaddress.ip_address(candidato)
    except ValueError:
        return IP_INTERNET
    return IP_INTERNET if ip.is_loopback else str(ip)


def _ip_pelo_serve(request):
    """IP real do aparelho, mesmo quando o acesso vem pelo Tailscale Serve.

    O Serve repassa tudo de 127.0.0.1 e acrescenta o IP de quem conectou no FIM do
    X-Forwarded-For. Se alguém mandar um cabeçalho falso, ele fica no começo da lista;
    por isso vale só o último item. Confiável porque o app só escuta em 127.0.0.1:
    só o Serve e o próprio PC conseguem chegar até aqui.
    A janela do PC não manda o cabeçalho e fica com o REMOTE_ADDR (127.0.0.1).
    """
    encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if encaminhado.strip():
        return encaminhado.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR")
