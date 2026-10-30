"""
"Sincronizar tudo": usado pelo comando, pelo botão, pelo relógio da página e
(etapa 6.1) pela bandeja. Decide se vale sincronizar agora e garante que só
um sync rode por vez.
"""

import threading
from datetime import timedelta

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from ..models import EstadoSync
from . import agenda as sync_agenda
from . import classroom as sync_classroom
from .credenciais import SemConexaoGoogle, obter_credenciais, servico_agenda, servico_classroom

# Intervalo mínimo desde o último sync, por motivo.
INTERVALO_MINIMO = {
    "auto": timedelta(seconds=50),   # relógio da página (a cada 60 s)
    "foco": timedelta(seconds=15),   # voltou para o app
    "botao": timedelta(0),           # "Sincronizar agora": sempre
}

# O Classroom não tem sync incremental (lê tudo a cada vez): no máximo a cada 5 min.
INTERVALO_CLASSROOM = timedelta(minutes=5)

_trava = threading.Lock()  # só um sync por vez (duas abas, botão + relógio...)


class Resultado:
    def __init__(self, situacao, mudou=False, detalhes=None, erro=""):
        self.situacao = situacao  # "ok", "pulado", "ocupado", "desconectado", "erro"
        self.mudou = mudou
        self.detalhes = detalhes or []
        self.erro = erro


def ultimo_sync():
    return EstadoSync.objects.filter(fonte__startswith="agenda:").aggregate(m=Max("ultimo_sync_em"))["m"]


def classroom_na_hora(motivo, agora):
    if motivo == "botao":
        return True
    ultimo = EstadoSync.objects.filter(fonte=sync_classroom.FONTE).values_list("ultimo_sync_em", flat=True).first()
    return ultimo is None or agora - ultimo >= INTERVALO_CLASSROOM


def sincronizar_tudo(motivo="botao", forcar_completo=False, interativo=False, agora=None):
    agora = agora or timezone.now()
    ultimo = ultimo_sync()
    if ultimo and agora - ultimo < INTERVALO_MINIMO.get(motivo, timedelta(0)) and not forcar_completo:
        return Resultado("pulado")

    if not _trava.acquire(blocking=False):
        return Resultado("ocupado")
    try:
        try:
            credenciais = obter_credenciais(interativo=interativo)
        except SemConexaoGoogle as erro:
            return Resultado("desconectado", erro=str(erro))
        servico = servico_agenda(credenciais)

        mudou, detalhes, erros = False, [], []
        for agenda in settings.GOOGLE_AGENDAS:
            nome = agenda["nome"] or "Agenda principal"
            try:
                r = sync_agenda.sincronizar_agenda(servico, agenda, forcar_completo=forcar_completo)
            except Exception as erro:  # uma agenda com erro não impede as outras
                sync_agenda.registrar_erro(agenda, erro)
                erros.append(f"{nome}: {erro}")
                continue
            detalhes.append((nome, r))
            mudou = mudou or any(r[k] for k in ("criadas", "atualizadas", "canceladas"))
        if classroom_na_hora(motivo, agora) or forcar_completo:
            try:
                r = sync_classroom.sincronizar_classroom(servico_classroom(credenciais), agora)
                detalhes.append(("Classroom", r))
                mudou = mudou or any(r[k] for k in ("criadas", "atualizadas", "canceladas"))
            except Exception as erro:
                sync_classroom.registrar_erro(erro)
                erros.append(f"Classroom: {erro}")

        if erros:
            return Resultado("erro", mudou, detalhes, erro="; ".join(erros))
        return Resultado("ok", mudou, detalhes)
    finally:
        _trava.release()
