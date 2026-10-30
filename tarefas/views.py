from datetime import timedelta

from django.shortcuts import render
from django.utils import timezone

from . import consultas
from .models import Categoria, Status

CATEGORIAS_FILTRAVEIS = {c.value for c in consultas.CATEGORIAS_DE_TAREFA}


def saudacao(hora):
    """Bom dia até 11h59, boa tarde até 17h59, boa noite depois."""
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


def hoje(request):
    agora = timezone.localtime()
    dia = agora.date()

    # Filtro vem da URL (?categoria=trabalho); valores desconhecidos são ignorados.
    categoria = request.GET.get("categoria")
    if categoria not in CATEGORIAS_FILTRAVEIS:
        categoria = None

    secoes = consultas.secoes_hoje(dia, categoria)
    contadores = consultas.contadores(dia)
    linha = consultas.linha_do_tempo(consultas.reunioes_do_dia(dia), agora)

    # Resumo do topo: sempre sem filtro (é o panorama do dia).
    pendentes_hoje = consultas.tarefas_visiveis().filter(prazo=dia).exclude(status=Status.CONCLUIDA).count()

    return render(request, "tarefas/hoje.html", {
        "hoje": dia,
        "amanha": dia + timedelta(days=1),
        "saudacao": saudacao(agora.hour),
        "categoria": categoria,
        "categoria_rotulo": Categoria(categoria).label if categoria else "",
        "secoes": secoes,
        "contadores": contadores,
        "total_atrasadas": sum(c["atrasadas"] for c in contadores),
        "pendentes_hoje": pendentes_hoje,
        "linha": linha,
    })
