"""
Sincronização Google Classroom → Kairos (somente leitura).

Cada sync lê tudo de novo (o Classroom não tem sync incremental):
  1. Turmas em que sou aluno → Disciplina (ativa ou arquivada).
  2. Para cada turma ativa: atividades publicadas + minhas entregas (1 consulta cada).
  3. Atividade → Tarefa de Faculdade. Campos do Google atualizados; os do dono não.
  4. Entrega: o status só muda quando a situação da entrega MUDA (entregou → conclui;
     cancelou o envio → reabre). Assim o sync não briga com o dono.
  5. Atividade que sumiu de uma turma ativa → cancelada (diferença de conjuntos).
"""

from datetime import datetime
from datetime import timezone as tz_utc

from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from ..models import Categoria, Disciplina, EstadoSync, Origem, Preferencias, Status, Tarefa

FONTE = "classroom"
ENTREGUE = ("TURNED_IN", "RETURNED")
ENVIO_CANCELADO = "RECLAIMED_BY_STUDENT"


# ===== Decisões (funções puras) =====

def prazo_local(data_utc, hora_utc):
    """
    O Classroom manda prazo em UTC: {"year","month","day"} + {"hours","minutes"}.
    Campos zerados não vêm ({"hours": 3} = 03:00). Devolve (data, hora) no fuso local.
    """
    if not data_utc:
        return None, None
    hora_utc = hora_utc or {}
    momento = datetime(
        data_utc["year"], data_utc["month"], data_utc["day"],
        hora_utc.get("hours", 0), hora_utc.get("minutes", 0), tzinfo=tz_utc.utc,
    )
    local = timezone.localtime(momento)
    return local.date(), local.time().replace(second=0, microsecond=0)


def deve_ignorar_nova(prazo, entregue, primeira_vez, hoje):
    """
    Atividade vista pela 1ª vez e NÃO entregue:
      - no 1º sync do Classroom ("marco zero"): só entra se tiver prazo no futuro
        (o que já existia sem prazo ou vencido não é pendência real);
      - depois: entra sempre, exceto se já aparecer vencida.
    Entregues sempre entram (como concluídas): histórico para os relatórios.
    """
    if entregue:
        return False
    if primeira_vez:
        return not (prazo and prazo >= hoje)
    return bool(prazo and prazo < hoje)


def novo_status(status_atual, entrega_anterior, entrega_nova, concluir_ao_entregar=True):
    """
    Só age quando a entrega MUDA:
      → entregue/devolvida: conclui (se não estiver concluída ou cancelada)
      → envio cancelado: reabre (se estava concluída)
    Sem mudança na entrega, o status é do dono e fica como está.
    """
    if not concluir_ao_entregar or entrega_nova == entrega_anterior:
        return status_atual
    if entrega_nova in ENTREGUE and status_atual not in (Status.CONCLUIDA, Status.CANCELADA):
        return Status.CONCLUIDA
    if entrega_nova == ENVIO_CANCELADO and status_atual == Status.CONCLUIDA:
        return Status.A_FAZER
    return status_atual


def campos_da_atividade(atividade, disciplina):
    prazo, hora = prazo_local(atividade.get("dueDate"), atividade.get("dueTime"))
    return {
        "titulo": (atividade.get("title") or "(sem título)")[:200],
        "prazo": prazo,
        "prazo_hora": hora,
        "disciplina": disciplina,
        "link_externo": atividade.get("alternateLink", "")[:500],
        "descricao_externa": strip_tags(atividade.get("description", "")),
    }


CAMPOS_COMPARADOS = ["titulo", "prazo", "prazo_hora", "disciplina_id", "link_externo",
                     "descricao_externa", "status", "estado_entrega"]


def _foto(tarefa):
    return tuple(getattr(tarefa, campo) for campo in CAMPOS_COMPARADOS)


def id_externo(atividade):
    # O id da atividade é único dentro da turma; prefixar com a turma garante unicidade geral.
    return f"{atividade['courseId']}:{atividade['id']}"


# ===== Conversa com o Google =====

def _todas_as_paginas(chamada, chave, **parametros):
    itens, pagina = [], None
    while True:
        resposta = chamada(pageToken=pagina, **parametros).execute(num_retries=3)
        itens.extend(resposta.get(chave, []))
        pagina = resposta.get("nextPageToken")
        if not pagina:
            return itens


def buscar(servico):
    """Devolve (turmas, atividades_por_turma, entregas_por_atividade)."""
    turmas = _todas_as_paginas(servico.courses().list, "courses", studentId="me",
                               courseStates=["ACTIVE", "ARCHIVED"], pageSize=100)
    atividades, entregas = {}, {}
    for turma in turmas:
        if turma.get("courseState") != "ACTIVE":
            continue  # arquivada: não busca atividades (só marca a disciplina como inativa)
        atividades[turma["id"]] = _todas_as_paginas(
            servico.courses().courseWork().list, "courseWork", courseId=turma["id"], pageSize=100)
        for e in _todas_as_paginas(servico.courses().courseWork().studentSubmissions().list, "studentSubmissions",
                                   courseId=turma["id"], courseWorkId="-", userId="me", pageSize=100):
            entregas[e["courseWorkId"]] = e.get("state", "")
    return turmas, atividades, entregas


# ===== Aplicar no banco =====

def aplicar(turmas, atividades, entregas, agora, concluir_ao_entregar=True, primeira_vez=False):
    resumo = {"criadas": 0, "atualizadas": 0, "canceladas": 0, "concluidas": 0}

    # 1. Turmas → Disciplinas
    disciplinas = {}
    for turma in turmas:
        nome = turma.get("name", "(turma sem nome)")
        if turma.get("section"):
            nome = f"{nome} – {turma['section']}"
        disciplina, _ = Disciplina.objects.update_or_create(
            classroom_id=turma["id"], defaults={"nome": nome[:200], "ativo": turma.get("courseState") == "ACTIVE"})
        disciplinas[turma["id"]] = disciplina

    # 2. Atividades → Tarefas
    recebidas = set()
    todas = [a for lista in atividades.values() for a in lista]
    existentes = {
        t.id_externo: t for t in
        Tarefa.objects.filter(origem=Origem.GOOGLE_CLASSROOM, id_externo__in=[id_externo(a) for a in todas])
    }
    for atividade in todas:
        chave = id_externo(atividade)
        recebidas.add(chave)
        tarefa = existentes.get(chave)
        nova = tarefa is None
        entrega = entregas.get(atividade["id"], "")
        prazo, _ = prazo_local(atividade.get("dueDate"), atividade.get("dueTime"))
        if nova and deve_ignorar_nova(prazo, entrega in ENTREGUE, primeira_vez, timezone.localdate(agora)):
            continue  # uma que entrou a tempo e venceu depois continua aparecendo como atrasada
        if nova:
            tarefa = Tarefa(origem=Origem.GOOGLE_CLASSROOM, id_externo=chave, categoria=Categoria.FACULDADE)
        antes = _foto(tarefa)

        for campo, valor in campos_da_atividade(atividade, disciplinas[atividade["courseId"]]).items():
            setattr(tarefa, campo, valor)

        status = novo_status(tarefa.status, tarefa.estado_entrega, entrega, concluir_ao_entregar)
        if status == Status.CONCLUIDA and tarefa.status != Status.CONCLUIDA:
            resumo["concluidas"] += 1
        tarefa.status = status
        tarefa.estado_entrega = entrega

        # O Classroom lê tudo a cada sync: só grava (e só avisa a tela) se algo mudou.
        if not nova and _foto(tarefa) == antes:
            continue
        resumo["criadas" if nova else "atualizadas"] += 1
        tarefa.sincronizado_em = agora
        tarefa.full_clean()
        tarefa.save()

    # 3. Atividade que sumiu de uma turma ativa (apagada pelo professor) → cancelada
    sumidas = (
        Tarefa.objects.filter(origem=Origem.GOOGLE_CLASSROOM, disciplina__classroom_id__in=list(atividades))
        .exclude(status=Status.CANCELADA)
        .exclude(id_externo__in=recebidas)
    )
    for tarefa in sumidas:
        tarefa.status = Status.CANCELADA
        tarefa.sincronizado_em = agora
        tarefa.save(update_fields=["status", "sincronizado_em", "atualizado_em"])
        resumo["canceladas"] += 1
    return resumo


# ===== Orquestração =====

def sincronizar_classroom(servico, agora=None):
    agora = agora or timezone.now()
    turmas, atividades, entregas = buscar(servico)
    primeira_vez = not EstadoSync.objects.filter(fonte=FONTE, ultimo_completo_em__isnull=False).exists()
    with transaction.atomic():  # o lote entra inteiro ou nada entra
        resumo = aplicar(turmas, atividades, entregas, agora, Preferencias.atual().concluir_ao_entregar, primeira_vez)
        EstadoSync.objects.update_or_create(
            fonte=FONTE, defaults={"ultimo_sync_em": agora, "ultimo_completo_em": agora, "ultimo_erro": ""})
    resumo["completo"] = True
    return resumo


def registrar_erro(erro, agora=None):
    estado, _ = EstadoSync.objects.get_or_create(fonte=FONTE)
    estado.ultimo_erro = str(erro)[:2000]
    estado.ultimo_erro_em = agora or timezone.now()
    estado.save(update_fields=["ultimo_erro", "ultimo_erro_em"])
