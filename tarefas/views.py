import json
from datetime import timedelta

from django.core import serializers, signing
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import consultas
from .forms import TarefaForm, pessoa_eu
from .models import Categoria, Origem, Pessoa, Status, Tarefa

CATEGORIAS_FILTRAVEIS = {c.value for c in consultas.CATEGORIAS_DE_TAREFA}
SAL_RESTAURAR = "kairos.restaurar-tarefa"
VALIDADE_DESFAZER = 10 * 60  # segundos

# Opções de status do menu ⋯ (ícone de cada uma)
STATUS_MENU = [
    (Status.EM_ANDAMENTO, "Em andamento", "play"),
    (Status.AGUARDANDO, "Aguardando", "hourglass"),
    (Status.A_FAZER, "A fazer", "circle"),
]


def saudacao(hora):
    """Bom dia até 11h59, boa tarde até 17h59, boa noite depois."""
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


def ler_categoria(valor):
    """Só aceita categorias conhecidas; qualquer outra coisa vira 'sem filtro'."""
    return valor if valor in CATEGORIAS_FILTRAVEIS else None


def contexto_hoje(categoria):
    """Tudo que a tela Hoje precisa. Usado pela página e pelas ações (HTMX)."""
    agora = timezone.localtime()
    dia = agora.date()
    contadores = consultas.contadores(dia)
    return {
        "hoje": dia,
        "amanha": dia + timedelta(days=1),
        "saudacao": saudacao(agora.hour),
        "categoria": categoria,
        "categoria_rotulo": Categoria(categoria).label if categoria else "",
        "secoes": consultas.secoes_hoje(dia, categoria),
        "contadores": contadores,
        "total_atrasadas": sum(c["atrasadas"] for c in contadores),
        # Resumo do topo: sempre sem filtro (é o panorama do dia).
        "pendentes_hoje": consultas.tarefas_visiveis().filter(prazo=dia).exclude(status=Status.CONCLUIDA).count(),
        "linha": consultas.linha_do_tempo(consultas.reunioes_do_dia(dia), agora),
        "status_menu": STATUS_MENU,
        "cat_rapida": Categoria.TRABALHO,
        "categorias_rapidas": [(c.value, c.label) for c in consultas.CATEGORIAS_DE_TAREFA],
    }


def hoje(request):
    return render(request, "tarefas/hoje.html", contexto_hoje(ler_categoria(request.GET.get("categoria"))))


# ===== Ações (chamadas pelo HTMX; respondem com o painel atualizado + toast) =====

def responder_acao(request, mensagem, desfazer=None, extra=None):
    """
    Devolve o painel do dia redesenhado e um toast. `desfazer` é (url, dados)
    para o botão "Desfazer" do toast. O filtro ativo chega como `filtro`.
    """
    if not request.headers.get("HX-Request"):
        return redirect("hoje")  # sem JS: volta para a página
    filtro = ler_categoria(request.POST.get("filtro"))
    contexto = contexto_hoje(filtro)
    contexto.update(extra or {})
    contexto["toast"] = {"mensagem": mensagem}
    if desfazer:
        url, dados = desfazer
        contexto["toast"]["desfazer_url"] = url
        contexto["toast"]["desfazer_vals"] = json.dumps({**dados, "filtro": filtro or ""})
    return render(request, "tarefas/_resposta_acao.html", contexto)


@require_POST
def mudar_status(request, pk):
    tarefa = get_object_or_404(Tarefa, pk=pk)
    novo = request.POST.get("status")
    if novo not in Status.values:
        return HttpResponseBadRequest("Status inválido.")

    anterior = tarefa.status
    tarefa.status = novo
    tarefa.save(update_fields=["status", "atualizado_em"])  # save() também grava concluida_em

    if novo == Status.CONCLUIDA:
        mensagem = "Tarefa concluída"
    elif novo == Status.CANCELADA:
        mensagem = "Tarefa cancelada" + (" (continua no Google)" if tarefa.origem != Origem.MANUAL else "")
    elif anterior == Status.CONCLUIDA:
        mensagem = "Tarefa reaberta"
    else:
        mensagem = f'Marcada como "{Status(novo).label}"'
    return responder_acao(request, mensagem, (reverse("mudar_status", args=[pk]), {"status": anterior}))


@require_POST
def excluir(request, pk):
    tarefa = get_object_or_404(Tarefa, pk=pk)
    if tarefa.origem != Origem.MANUAL:
        # Apagar faria o sync trazer de volta; itens do Google são cancelados.
        return HttpResponseBadRequest("Itens do Google são cancelados, não excluídos.")

    # Antes de apagar, guarda uma cópia completa, assinada, para o "Desfazer".
    # Datas em ISO completo (o serializador "json" do Django corta em milissegundos).
    campos = json.dumps(serializers.serialize("python", [tarefa]), default=lambda valor: valor.isoformat())
    copia = signing.dumps(campos, salt=SAL_RESTAURAR, compress=True)
    tarefa.delete()
    return responder_acao(request, "Tarefa excluída", (reverse("restaurar"), {"copia": copia}))


@require_POST
def restaurar(request):
    try:
        dados = signing.loads(request.POST.get("copia", ""), salt=SAL_RESTAURAR, max_age=VALIDADE_DESFAZER)
    except signing.BadSignature:  # inclui "expirado"
        return HttpResponseBadRequest("Não foi possível desfazer (expirou ou é inválido).")

    for objeto in serializers.deserialize("python", json.loads(dados)):
        if Tarefa.objects.filter(pk=objeto.object.pk).exists():
            return HttpResponseBadRequest("Essa tarefa já existe.")
        objeto.save()  # grava exatamente como era (mesmo id e mesmas datas)
    return responder_acao(request, "Desfeito")


@require_POST
def criar_rapida(request):
    """Campo do topo: só título e categoria, prazo hoje."""
    titulo = request.POST.get("titulo", "").strip()[:200]
    categoria = ler_categoria(request.POST.get("cat_rapida"))
    if not titulo or not categoria:
        return HttpResponseBadRequest("Escreva um título para a tarefa.")

    tarefa = Tarefa(titulo=titulo, categoria=categoria, prazo=timezone.localdate())
    if categoria == Categoria.TRABALHO:
        # Demandas que eu mesmo crio: solicitante "Eu" (criado na primeira vez).
        tarefa.solicitante = pessoa_eu() or Pessoa.objects.create(nome="Eu", cor="#a3e635")
    tarefa.full_clean()
    tarefa.save()
    return responder_acao(
        request, "Tarefa criada para hoje", (reverse("excluir", args=[tarefa.pk]), {}),
        extra={"cat_rapida": categoria, "focar_rapida": True},
    )


def contexto_form(form, tarefa, filtro):
    return {"form": form, "tarefa": tarefa, "filtro": filtro,
            "google": bool(tarefa.pk and tarefa.origem != Origem.MANUAL)}


def tarefa_form(request, pk=None):
    """Painel lateral de criar/editar. GET mostra o formulário; POST salva."""
    if pk:
        tarefa = get_object_or_404(Tarefa, pk=pk)
    else:
        tarefa = Tarefa(categoria=Categoria.TRABALHO, prazo=timezone.localdate(), solicitante=pessoa_eu())
    filtro = ler_categoria(request.GET.get("filtro") or request.POST.get("filtro"))

    if request.method == "POST":
        form = TarefaForm(request.POST, instance=tarefa)
        if form.is_valid():
            form.save()
            resposta = responder_acao(request, "Alterações salvas" if pk else "Tarefa criada")
            resposta["HX-Trigger"] = "fecharPainel"  # o JS fecha o painel lateral
            return resposta
        # Com erros: redesenha o formulário dentro do painel, em vez de trocar o #painel.
        resposta = render(request, "tarefas/_painel_tarefa.html", contexto_form(form, tarefa, filtro))
        resposta["HX-Retarget"] = "#drawer-conteudo"
        resposta["HX-Reswap"] = "innerHTML"
        return resposta

    form = TarefaForm(instance=tarefa)
    return render(request, "tarefas/_painel_tarefa.html", contexto_form(form, tarefa, filtro))
