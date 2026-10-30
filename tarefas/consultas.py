"""
Consultas usadas pelas telas. Cada regra ("o que é atrasada", "o que entra
nos próximos 7 dias") fica num lugar só, para as telas e os testes usarem igual.
"""

from datetime import timedelta
from itertools import groupby

from django.db.models import Case, Count, F, Func, IntegerField, Q, TextField, Value, When
from django.db.models.functions import Concat
from django.utils import timezone

from .models import Categoria, Prioridade, Status, Tarefa
from .texto import sem_acento

ENCERRADAS = [Status.CONCLUIDA, Status.CANCELADA]
CATEGORIAS_DE_TAREFA = [Categoria.TRABALHO, Categoria.FACULDADE, Categoria.PESSOAL]

# A prioridade é guardada como texto; em ordem alfabética "urgente" iria para o
# fim. O CASE WHEN converte cada texto num peso numérico na hora da consulta.
PESO_PRIORIDADE = Case(
    When(prioridade=Prioridade.URGENTE, then=Value(3)),
    When(prioridade=Prioridade.ALTA, then=Value(2)),
    When(prioridade=Prioridade.MEDIA, then=Value(1)),
    default=Value(0),
    output_field=IntegerField(),
)
# Concluída = 1, resto = 0 → ordenando crescente, concluídas vão para o fim.
CONCLUIDA_POR_ULTIMO = Case(
    When(status=Status.CONCLUIDA, then=Value(1)),
    default=Value(0),
    output_field=IntegerField(),
)


def tarefas_visiveis(categoria=None):
    """Tarefas das listas (sem reuniões nem canceladas), já com os vínculos carregados."""
    qs = (
        Tarefa.objects.select_related("solicitante", "projeto", "disciplina")
        .exclude(categoria=Categoria.REUNIAO)
        .exclude(status=Status.CANCELADA)
        .annotate(peso=PESO_PRIORIDADE, feita=CONCLUIDA_POR_ULTIMO)
    )
    if categoria:
        qs = qs.filter(categoria=categoria)
    return qs


def secoes_hoje(hoje, categoria=None):
    """Atrasadas, para hoje e próximos 7 dias (agrupados por data)."""
    base = tarefas_visiveis(categoria)
    hora = F("prazo_hora").asc(nulls_last=True)

    atrasadas = base.filter(prazo__lt=hoje).exclude(status=Status.CONCLUIDA).order_by("prazo", "-peso", hora)
    de_hoje = base.filter(prazo=hoje).order_by("feita", "-peso", hora, "criado_em")
    semana = base.filter(prazo__gt=hoje, prazo__lte=hoje + timedelta(days=7)).order_by(
        "prazo", "feita", "-peso", hora, "criado_em"
    )
    proximos = [(dia, list(itens)) for dia, itens in groupby(semana, key=lambda t: t.prazo)]
    return {"atrasadas": list(atrasadas), "hoje": list(de_hoje), "proximos": proximos}


def listar_tarefas(filtros):
    """
    Tela Tarefas. `filtros` vem do FiltroTarefasForm (só valores válidos).
    Cada filtro presente acrescenta uma condição; o banco executa tudo de uma vez.
    """
    qs = Tarefa.objects.select_related("solicitante", "projeto", "disciplina").annotate(
        peso=PESO_PRIORIDADE, feita=CONCLUIDA_POR_ULTIMO
    )

    status = filtros.get("status", "")
    if status == "":  # padrão: só as abertas
        qs = qs.exclude(status__in=ENCERRADAS)
        # Reunião que já terminou não é "aberta" (sem mudar o status, que é do dono);
        # continua aparecendo em "Todas".
        agora = timezone.now()
        qs = qs.exclude(Q(categoria=Categoria.REUNIAO) & (Q(fim__lt=agora) | Q(fim__isnull=True, inicio__lt=agora)))
    elif status != "todas":
        qs = qs.filter(status=status)

    for campo in ("categoria", "prioridade", "solicitante", "projeto", "disciplina"):
        if campo in filtros:
            qs = qs.filter(**{campo: filtros[campo]})

    if busca := sem_acento(filtros.get("q", "").strip()):
        # Compara sem acento e sem maiúsculas: "relatorio" acha "Relatório".
        # (O SQLite sozinho só ignora maiúsculas em letras sem acento.)
        texto = Concat("titulo", Value(" "), "observacoes", Value(" "), "descricao_externa", output_field=TextField())
        qs = qs.annotate(texto_busca=Func(texto, function="sem_acento", output_field=TextField())).filter(
            texto_busca__contains=busca
        )

    prazo = F("prazo").asc(nulls_last=True)
    ordem = filtros.get("ordem", "prazo")
    if ordem == "prioridade":
        return qs.order_by("feita", "-peso", prazo, "-criado_em")
    if ordem == "recentes":
        return qs.order_by("-criado_em")
    return qs.order_by("feita", prazo, "-peso", "-criado_em")


COLUNAS_QUADRO = [Status.A_FAZER, Status.EM_ANDAMENTO, Status.AGUARDANDO, Status.CONCLUIDA]
DIAS_CONCLUIDAS_NO_QUADRO = 7


def quadro(categoria=None):
    """
    Kanban: uma coluna por status. Concluídas só dos últimos 7 dias (senão a
    coluna cresce para sempre). Cada tarefa ganha `anterior`/`proximo`: os
    status das colunas vizinhas, para os botões ← →.
    """
    desde = timezone.now() - timedelta(days=DIAS_CONCLUIDAS_NO_QUADRO)
    qs = (
        tarefas_visiveis(categoria)
        .filter(Q(status__in=COLUNAS_QUADRO[:-1]) | Q(status=Status.CONCLUIDA, concluida_em__gte=desde))
        .order_by("-peso", F("prazo").asc(nulls_last=True), "-criado_em")
    )

    colunas = {status: [] for status in COLUNAS_QUADRO}
    for t in qs:
        i = COLUNAS_QUADRO.index(t.status)
        t.anterior = COLUNAS_QUADRO[i - 1] if i > 0 else None
        t.proximo = COLUNAS_QUADRO[i + 1] if i < len(COLUNAS_QUADRO) - 1 else None
        colunas[t.status].append(t)
    return [{"status": s, "rotulo": s.label, "tarefas": colunas[s]} for s in COLUNAS_QUADRO]


def contadores(hoje):
    """Por categoria: tarefas em aberto e quantas estão atrasadas."""
    linhas = (
        Tarefa.objects.filter(categoria__in=CATEGORIAS_DE_TAREFA)
        .exclude(status__in=ENCERRADAS)
        .values("categoria")
        .annotate(total=Count("id"), atrasadas=Count("id", filter=Q(prazo__lt=hoje)))
    )
    por_categoria = {linha["categoria"]: linha for linha in linhas}
    return [
        {
            "categoria": cat.value,
            "rotulo": cat.label,
            "total": por_categoria.get(cat.value, {}).get("total", 0),
            "atrasadas": por_categoria.get(cat.value, {}).get("atrasadas", 0),
        }
        for cat in CATEGORIAS_DE_TAREFA
    ]


def reunioes_do_dia(hoje):
    return list(
        Tarefa.objects.filter(categoria=Categoria.REUNIAO, inicio__date=hoje)
        .exclude(status=Status.CANCELADA)
        .order_by("inicio")
    )


def _horas(momento):
    local = timezone.localtime(momento)
    return local.hour + local.minute / 60


def _css(numero):
    # Números vão para o CSS; sempre com ponto (pt-BR usaria vírgula e quebraria o estilo).
    return f"{numero:.3f}"


def distribuir_em_colunas(eventos):
    """
    Reuniões que se sobrepõem ficam lado a lado (cada evento ganha `coluna` e `colunas`).
    1. Ordena por início.
    2. Agrupa em blocos: o bloco acaba quando a próxima começa depois de todas terminarem.
    3. Dentro do bloco, cada uma vai para a 1ª coluna livre (guloso, como "quantas salas preciso?").
    4. Todas do bloco dividem a largura pelo nº de colunas que o bloco usou.
    """
    eventos.sort(key=lambda e: (e["ini"], e["fim"]))
    bloco, fins_das_colunas, fim_do_bloco = [], [], None

    def fechar_bloco():
        for e in bloco:
            e["colunas"] = len(fins_das_colunas)

    for e in eventos:
        if fim_do_bloco is not None and e["ini"] >= fim_do_bloco:
            fechar_bloco()
            bloco, fins_das_colunas = [], []
        livre = next((i for i, fim in enumerate(fins_das_colunas) if fim <= e["ini"]), None)
        if livre is None:
            fins_das_colunas.append(e["fim"])
            livre = len(fins_das_colunas) - 1
        else:
            fins_das_colunas[livre] = e["fim"]
        e["coluna"] = livre
        bloco.append(e)
        fim_do_bloco = max(fim_do_bloco or e["fim"], e["fim"])
    fechar_bloco()


def linha_do_tempo(reunioes, agora):
    """
    Posições da linha do tempo, em "horas desde o topo". Vai das 8h às 18h,
    esticando se alguma reunião começar antes ou terminar depois.
    """
    eventos = []
    for r in reunioes:
        fim = r.fim or r.inicio + timedelta(minutes=30)
        eventos.append(
            {
                "tarefa": r,
                "ini": _horas(r.inicio),
                "fim": max(_horas(fim), _horas(r.inicio) + 0.25),
                "passada": fim <= agora,
            }
        )

    distribuir_em_colunas(eventos)

    h0 = min([8] + [int(e["ini"]) for e in eventos])
    h1 = max([18] + [int(e["fim"]) + (e["fim"] % 1 > 0) for e in eventos])
    for e in eventos:
        duracao = e["fim"] - e["ini"]
        e["topo"] = _css(e["ini"] - h0)
        e["altura"] = _css(max(duracao, 0.45))
        e["curta"] = duracao <= 0.5

    hora_agora = _horas(agora)
    return {
        "horas": [{"rotulo": f"{h:02d}:00", "topo": h - h0} for h in range(h0, h1 + 1)],
        "total": h1 - h0,
        "eventos": eventos,
        "agora": _css(hora_agora - h0) if h0 <= hora_agora <= h1 else None,
        "proxima": next((e["tarefa"] for e in eventos if e["ini"] > hora_agora), None),
        "restantes": sum(1 for e in eventos if not e["passada"]),
    }
