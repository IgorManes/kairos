"""
Telas de cadastro: Pessoas e Projetos. As duas funcionam igual, então as
funções recebem o modelo e o formulário como parâmetro.
"""

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .consultas import ENCERRADAS
from .forms import PessoaForm, ProjetoForm
from .models import Pessoa, Projeto, Status
from .views import responder_acao

# Configuração de cada cadastro
CADASTROS = {
    "pessoa": {
        "modelo": Pessoa, "form": PessoaForm, "nome": "pessoa", "titulo": "Pessoas",
        "filtro_tarefas": "solicitante", "rota": "pessoas",
    },
    "projeto": {
        "modelo": Projeto, "form": ProjetoForm, "nome": "projeto", "titulo": "Projetos",
        "filtro_tarefas": "projeto", "rota": "projetos",
    },
}


def com_contagens(modelo):
    """Cada item com o total de tarefas, quantas estão abertas e quantas foram concluídas."""
    return modelo.objects.annotate(
        total=Count("tarefas"),
        abertas=Count("tarefas", filter=~Q(tarefas__status__in=ENCERRADAS)),
        concluidas=Count("tarefas", filter=Q(tarefas__status=Status.CONCLUIDA)),
    ).order_by("nome")


def lista(request, tipo):
    cfg = CADASTROS[tipo]
    itens = list(com_contagens(cfg["modelo"]))
    return render(request, "tarefas/cadastros.html", {
        "cfg": cfg,
        "ativos": [i for i in itens if i.ativo],
        "inativos": [i for i in itens if not i.ativo],
    })


def formulario(request, tipo, pk=None):
    """Painel lateral de criar/editar (mesmo padrão do painel de tarefa)."""
    cfg = CADASTROS[tipo]
    item = get_object_or_404(cfg["modelo"], pk=pk) if pk else cfg["modelo"]()
    form = cfg["form"](request.POST or None, instance=item)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            mensagem = "Alterações salvas" if pk else f"{cfg['nome'].capitalize()} criad{'a' if tipo == 'pessoa' else 'o'}"
            return responder_acao(request, mensagem, gatilhos=["fecharPainel"])
        resposta = render(request, "tarefas/_painel_cadastro.html", {"form": form, "item": item, "cfg": cfg})
        resposta["HX-Retarget"] = "#drawer-conteudo"
        resposta["HX-Reswap"] = "innerHTML"
        return resposta

    return render(request, "tarefas/_painel_cadastro.html", {"form": form, "item": item, "cfg": cfg})


@require_POST
def alternar_ativo(request, tipo, pk):
    """Ativa/desativa com um clique; o Desfazer chama esta mesma ação de novo."""
    cfg = CADASTROS[tipo]
    item = get_object_or_404(cfg["modelo"], pk=pk)
    item.ativo = not item.ativo
    item.save(update_fields=["ativo"])
    estado = "reativad" if item.ativo else "desativad"
    sufixo = "a" if tipo == "pessoa" else "o"
    return responder_acao(
        request, f"{item.nome} {estado}{sufixo}",
        (reverse("alternar_ativo", args=[tipo, pk]), {}),
    )


# Atalhos usados nas URLs
def pessoas(request):
    return lista(request, "pessoa")


def projetos(request):
    return lista(request, "projeto")


def mais(request):
    """Celular: a barra inferior só tem 4 itens; o resto fica aqui."""
    return render(request, "tarefas/mais.html")
