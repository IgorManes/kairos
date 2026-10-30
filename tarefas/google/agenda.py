"""
Sincronização Google Agenda → Kairos (somente leitura).

Fluxo por agenda:
  1. Decide completo ou incremental (sem token, token vencido ou 1º do dia → completo).
  2. Busca os eventos (página por página).
  3. Aplica: cria, atualiza ou cancela. Campos do dono nunca são sobrescritos.
  4. No completo: o que o Kairos tem e o Google não mandou foi apagado → cancela
     (diferença de conjuntos).

As decisões (importar? quais campos?) são funções puras, testáveis sem o Google.
"""

from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from ..models import Categoria, EstadoSync, Origem, Status, Tarefa

DIAS_ATRAS, DIAS_FRENTE = 7, 60
# Campos que vêm do Google e são atualizados a cada sync. Os demais são do dono.
CAMPOS_DO_GOOGLE = ["titulo", "inicio", "fim", "link_reuniao", "link_externo", "descricao_externa", "agenda_id"]


class TokenVencido(Exception):
    """O Google respondeu 410: a marca de sync expirou; precisa de sync completo."""


# ===== Decisões (funções puras) =====


def participante_eu(evento, agenda):
    """
    O convidado que representa esta agenda. O Google marca com `self`
    ("este convidado é a agenda de onde veio esta cópia"); por garantia,
    também procura pelo e-mail da agenda.
    """
    convidados = evento.get("attendees", [])
    eu = next((c for c in convidados if c.get("self")), None)
    if eu is None and agenda.get("email"):
        eu = next((c for c in convidados if c.get("email", "").lower() == agenda["email"].lower()), None)
    return eu


def deve_importar(evento, agenda):
    """Regra de cada agenda: principal = aceitei ou organizei; empresa = tudo, menos recusados."""
    if evento.get("status") == "cancelled":
        return False
    if "dateTime" not in evento.get("start", {}):
        return False  # dia inteiro (feriado, férias): não é reunião
    eu = participante_eu(evento, agenda)
    resposta = eu.get("responseStatus") if eu else None

    if agenda["regra"] == "nao_recusados":
        return resposta != "declined"
    # "aceitos": organizei, aceitei, ou é um evento só meu (sem convidados)
    organizei = evento.get("organizer", {}).get("self", False)
    return organizei or not evento.get("attendees") or resposta == "accepted"


def _momento(valor):
    """'2026-10-30T14:00:00-03:00' → datetime com fuso."""
    if not valor:
        return None
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def link_da_reuniao(evento):
    if evento.get("hangoutLink"):
        return evento["hangoutLink"]
    for entrada in evento.get("conferenceData", {}).get("entryPoints", []):
        if entrada.get("entryPointType") == "video":
            return entrada.get("uri", "")
    return ""


def campos_do_evento(evento, agenda):
    """Os campos do Google, já no formato da Tarefa."""
    inicio = _momento(evento["start"].get("dateTime"))
    fim = _momento(evento.get("end", {}).get("dateTime"))
    return {
        "titulo": (evento.get("summary") or "(sem título)")[:200],
        "inicio": inicio,
        "fim": fim if fim and fim >= inicio else inicio,
        "link_reuniao": link_da_reuniao(evento)[:200],
        "link_externo": evento.get("htmlLink", "")[:500],
        "descricao_externa": strip_tags(evento.get("description", "")),
        "agenda_id": agenda["id"],
    }


def janela(agora):
    return agora - timedelta(days=DIAS_ATRAS), agora + timedelta(days=DIAS_FRENTE)


# ===== Conversa com o Google =====


def buscar_eventos(servico, agenda_id, sync_token, agora):
    """
    Todas as páginas de events.list. Completo: limitado à janela de datas.
    Incremental: só com o token (o Google não aceita janela junto).
    Devolve (eventos, novo_token).
    """
    from googleapiclient.errors import HttpError

    parametros = {"calendarId": agenda_id, "singleEvents": True, "showDeleted": True, "maxResults": 250}
    if sync_token:
        parametros["syncToken"] = sync_token
    else:
        inicio, fim = janela(agora)
        parametros.update(timeMin=inicio.isoformat(), timeMax=fim.isoformat())

    eventos, pagina = [], None
    while True:
        try:
            # num_retries: a biblioteca repete com espera crescente em 429/5xx.
            resposta = servico.events().list(pageToken=pagina, **parametros).execute(num_retries=3)
        except HttpError as erro:
            if erro.resp.status == 410:
                raise TokenVencido() from erro
            raise
        eventos.extend(resposta.get("items", []))
        pagina = resposta.get("nextPageToken")
        if not pagina:
            return eventos, resposta.get("nextSyncToken", "")


# ===== Aplicar no banco =====


def aplicar_eventos(eventos, agenda, completo, agora):
    """Cria/atualiza/cancela tarefas. Devolve um resumo com as contagens."""
    resumo = {"criadas": 0, "atualizadas": 0, "canceladas": 0}
    inicio_janela, fim_janela = janela(agora)
    existentes = {
        t.id_externo: t
        for t in Tarefa.objects.filter(origem=Origem.GOOGLE_AGENDA, id_externo__in=[e["id"] for e in eventos])
    }
    recebidos = set()

    for evento in eventos:
        recebidos.add(evento["id"])
        tarefa = existentes.get(evento["id"])

        if not deve_importar(evento, agenda):
            # Cancelado, recusado ou virou dia inteiro: cancela (nunca apaga).
            if tarefa and tarefa.status != Status.CANCELADA and tarefa.agenda_id in ("", agenda["id"]):
                _cancelar(tarefa, agora)
                resumo["canceladas"] += 1
            continue

        campos = campos_do_evento(evento, agenda)
        dentro = inicio_janela <= campos["inicio"] <= fim_janela
        if tarefa is None and not dentro:
            continue  # fora da janela e ainda não conhecido: ignora

        if tarefa is None:
            tarefa = Tarefa(origem=Origem.GOOGLE_AGENDA, id_externo=evento["id"], categoria=Categoria.REUNIAO)
            resumo["criadas"] += 1
        else:
            resumo["atualizadas"] += 1
            if tarefa.agenda_id and tarefa.agenda_id != agenda["id"] and agenda["regra"] == "aceitos":
                campos["agenda_id"] = tarefa.agenda_id  # mesma reunião na empresa: mantém a etiqueta da empresa

        for campo, valor in campos.items():
            setattr(tarefa, campo, valor)
        tarefa.sincronizado_em = agora
        tarefa.full_clean()
        tarefa.save()

    if completo:
        # Diferença de conjuntos: o que o Kairos tem desta agenda (na janela) e o Google não mandou.
        sumidas = (
            Tarefa.objects.filter(
                origem=Origem.GOOGLE_AGENDA, agenda_id=agenda["id"], inicio__range=(inicio_janela, fim_janela)
            )
            .exclude(status=Status.CANCELADA)
            .exclude(id_externo__in=recebidos)
        )
        for tarefa in sumidas:
            _cancelar(tarefa, agora)
            resumo["canceladas"] += 1
    return resumo


def _cancelar(tarefa, agora):
    tarefa.status = Status.CANCELADA
    tarefa.sincronizado_em = agora
    tarefa.save(update_fields=["status", "sincronizado_em", "atualizado_em"])


# ===== Orquestração =====


def sincronizar_agenda(servico, agenda, agora=None, forcar_completo=False):
    """Sincroniza uma agenda e atualiza o EstadoSync dela. Erros sobem para quem chamou."""
    agora = agora or timezone.now()
    estado, _ = EstadoSync.objects.get_or_create(fonte=f"agenda:{agenda['id']}")
    primeiro_do_dia = estado.ultimo_completo_em is None or timezone.localdate(
        estado.ultimo_completo_em
    ) != timezone.localdate(agora)
    completo = forcar_completo or not estado.sync_token or primeiro_do_dia

    try:
        eventos, token = buscar_eventos(servico, agenda["id"], None if completo else estado.sync_token, agora)
    except TokenVencido:
        completo = True
        eventos, token = buscar_eventos(servico, agenda["id"], None, agora)

    with transaction.atomic():  # o lote entra inteiro ou nada entra
        resumo = aplicar_eventos(eventos, agenda, completo, agora)
        estado.sync_token = token
        estado.ultimo_sync_em = agora
        if completo:
            estado.ultimo_completo_em = agora
        estado.ultimo_erro = ""
        estado.save()
    resumo["completo"] = completo
    return resumo


def registrar_erro(agenda, erro, agora=None):
    estado, _ = EstadoSync.objects.get_or_create(fonte=f"agenda:{agenda['id']}")
    estado.ultimo_erro = str(erro)[:2000]
    estado.ultimo_erro_em = agora or timezone.now()
    estado.save(update_fields=["ultimo_erro", "ultimo_erro_em"])
