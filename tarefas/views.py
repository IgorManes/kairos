from django.shortcuts import render


def hoje(request):
    """Tela inicial. Provisória: a versão completa vem na etapa 3."""
    return render(request, "tarefas/hoje.html")
