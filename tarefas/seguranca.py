"""Qual aparelho está acessando, para o bloqueio por senha errada (django-axes)."""


def ip_do_aparelho(request):
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
