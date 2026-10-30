"""
Relatórios semanais: "foto congelada" de cada semana (segunda a domingo).

- gerar_foto(): copia os dados da semana (com os nomes como eram naquele dia).
- garantir_relatorios(): gera as fotos das semanas encerradas que faltam.
- recortes_de() / aplicar_recorte(): filtros na hora de exportar (Geral, categoria,
  solicitante, projeto, disciplina), sem precisar de uma foto por filtro.
"""

from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from .models import Categoria, Prioridade, RelatorioSemanal, Status, Tarefa

VERSAO = 1
ENCERRADAS = (Status.CONCLUIDA, Status.CANCELADA)


# ===== Semanas =====

def semana_de(data):
    """A segunda-feira da semana de `data` (weekday(): segunda = 0 ... domingo = 6)."""
    return data - timedelta(days=data.weekday())


def limites(inicio):
    """Início (segunda 00:00) e fim exclusivo (próxima segunda 00:00) no fuso local."""
    comeco = timezone.make_aware(datetime.combine(inicio, time.min))
    return comeco, comeco + timedelta(days=7)


# ===== Foto =====

def _iso(valor):
    return valor.isoformat() if valor else None


def _linha(t, comeco, fim, agora):
    """Uma tarefa como texto e números (nada de chave estrangeira: a foto não pode mudar)."""
    aberta = t.status not in ENCERRADAS
    return {
        "id": t.pk,
        "titulo": t.titulo,
        "categoria": t.categoria,
        "categoria_rotulo": Categoria(t.categoria).label,
        "status": t.status,
        "status_rotulo": Status(t.status).label,
        "prioridade": t.prioridade,
        "prioridade_rotulo": Prioridade(t.prioridade).label,
        "prazo": _iso(t.prazo),
        "prazo_hora": t.prazo_hora.strftime("%H:%M") if t.prazo_hora else None,
        "criado_em": _iso(t.criado_em),
        "concluida_em": _iso(t.concluida_em),
        "solicitante": t.solicitante.nome if t.solicitante else "",
        "projeto": t.projeto.nome if t.projeto else "",
        "disciplina": t.disciplina.nome if t.disciplina else "",
        "origem": t.origem,
        "observacoes": t.observacoes,
        "concluida_na_semana": bool(t.concluida_em and comeco <= t.concluida_em < fim),
        "criada_na_semana": comeco <= t.criado_em < fim,
        "aberta": aberta,
        # Atrasada: aberta e com prazo antes do que vier primeiro, a próxima segunda (semana
        # encerrada) ou hoje (semana em andamento: o prazo de amanhã ainda não venceu).
        "atrasada": bool(aberta and t.prazo and t.prazo < min(timezone.localtime(fim).date(), timezone.localdate(agora))),
    }


def gerar_foto(inicio, agora=None):
    """
    Dados da semana que começa em `inicio`:
      - concluídas na semana, criadas na semana e em aberto (criadas até o fim da semana);
      - reuniões da semana (não canceladas).
    """
    agora = agora or timezone.now()
    comeco, fim = limites(inicio)
    tarefas = (
        Tarefa.objects.select_related("solicitante", "projeto", "disciplina")
        .exclude(categoria=Categoria.REUNIAO)
        .filter(
            Q(concluida_em__gte=comeco, concluida_em__lt=fim)
            | Q(criado_em__gte=comeco, criado_em__lt=fim)
            | (Q(criado_em__lt=fim) & ~Q(status__in=ENCERRADAS))
        )
        .order_by("prazo", "titulo")
    )
    reunioes = (
        Tarefa.objects.filter(categoria=Categoria.REUNIAO, inicio__gte=comeco, inicio__lt=fim)
        .exclude(status=Status.CANCELADA)
        .order_by("inicio")
    )
    return {
        "versao": VERSAO,
        "inicio": inicio.isoformat(),
        "fim": (inicio + timedelta(days=6)).isoformat(),
        "gerado_em": agora.isoformat(),
        "parcial": agora < fim,
        "tarefas": [_linha(t, comeco, fim, agora) for t in tarefas],
        "reunioes": [
            {
                "titulo": r.titulo,
                "inicio": _iso(r.inicio),
                "fim": _iso(r.fim),
                "agenda": r.etiqueta_agenda,  # "Invoga" ou "" (agenda pessoal)
                "observacoes": r.observacoes,
            }
            for r in reunioes
        ],
    }


def garantir_relatorios(agora=None):
    """
    Gera as fotos das semanas encerradas que faltam. Na 1ª vez, só a semana passada
    (semanas mais antigas teriam o "em aberto" de hoje, não daquela época).
    Devolve quantas foram geradas.
    """
    agora = agora or timezone.now()
    ultima_encerrada = semana_de(timezone.localdate(agora)) - timedelta(days=7)
    mais_recente = RelatorioSemanal.objects.order_by("-semana_inicio").values_list("semana_inicio", flat=True).first()
    semana = mais_recente + timedelta(days=7) if mais_recente else ultima_encerrada
    geradas = 0
    while semana <= ultima_encerrada:
        RelatorioSemanal.objects.get_or_create(semana_inicio=semana, defaults={"dados": gerar_foto(semana, agora)})
        semana += timedelta(days=7)
        geradas += 1
    return geradas


# ===== Recortes (filtros na exportação) =====

def recortes_de(dados):
    """Opções de recorte que fazem sentido para esta foto: [(valor, rótulo), ...]."""
    tarefas = dados["tarefas"]
    opcoes = [("geral", "Geral (tudo)")]
    for cat in (Categoria.TRABALHO, Categoria.FACULDADE, Categoria.PESSOAL):
        if any(t["categoria"] == cat for t in tarefas) or (cat == Categoria.TRABALHO and any(r["agenda"] for r in dados["reunioes"])):
            opcoes.append((f"categoria:{cat.value}", cat.label))
    for campo, rotulo in (("solicitante", "Solicitante"), ("projeto", "Projeto"), ("disciplina", "Disciplina")):
        for nome in sorted({t[campo] for t in tarefas if t[campo]}):
            opcoes.append((f"{campo}:{nome}", f"{rotulo}: {nome}"))
    return opcoes


def aplicar_recorte(dados, recorte):
    """
    Devolve (tarefas, reuniões, rótulo) do recorte. Reuniões entram no Geral e,
    as da agenda da empresa (ex.: Invoga), também no recorte Trabalho.
    """
    rotulos = dict(recortes_de(dados))
    if recorte not in rotulos:
        recorte = "geral"
    if recorte == "geral":
        return dados["tarefas"], dados["reunioes"], rotulos["geral"]
    campo, valor = recorte.split(":", 1)
    tarefas = [t for t in dados["tarefas"] if t[campo] == valor]
    reunioes = [r for r in dados["reunioes"] if r["agenda"]] if recorte == "categoria:trabalho" else []
    return tarefas, reunioes, rotulos[recorte]
