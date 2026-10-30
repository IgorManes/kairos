from django.shortcuts import render
from django.utils import timezone


def saudacao(hora):
    """Bom dia até 11h59, boa tarde até 17h59, boa noite depois."""
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


def hoje(request):
    """Tela inicial. Provisória: a versão completa vem na etapa 3."""
    agora = timezone.localtime()
    return render(request, "tarefas/hoje.html", {
        "hoje": agora.date(),
        "saudacao": saudacao(agora.hour),
    })
