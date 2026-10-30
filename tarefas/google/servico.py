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
from .credenciais import SemConexaoGoogle, obter_credenciais, servico_agenda

# Intervalo mínimo desde o último sync, por motivo.
INTERVALO_MINIMO = {
    "auto": timedelta(seconds=50),   # relógio da página (a cada 60 s)
    "foco": timedelta(seconds=15),   # voltou para o app
    "botao": timedelta(0),           # "Sincronizar agora": sempre
}

_trava = threading.Lock()  # só um sync por vez (duas abas, botão + relógio...)


class Resultado:
    def __init__(self, situacao, mudou=False, detalhes=None, erro=""):
        self.situacao = situacao  # "ok", "pulado", "ocupado", "desconectado", "erro"
        self.mudou = mudou
        self.detalhes = detalhes or []
        self.erro = erro


def ultimo_sync():
    return EstadoSync.objects.filter(fonte__startswith="agenda:").aggregate(m=Max("ultimo_sync_em"))["m"]


def sincronizar_tudo(motivo="botao", forcar_completo=False, interativo=False, agora=None):
    agora = agora or timezone.now()
    ultimo = ultimo_sync()
    if ultimo and agora - ultimo < INTERVALO_MINIMO.get(motivo, timedelta(0)) and not forcar_completo:
        return Resultado("pulado")

    if not _trava.acquire(blocking=False):
        return Resultado("ocupado")
    try:
        try:
            servico = servico_agenda(obter_credenciais(interativo=interativo))
        except SemConexaoGoogle as erro:
            return Resultado("desconectado", erro=str(erro))

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
        if erros:
            return Resultado("erro", mudou, detalhes, erro="; ".join(erros))
        return Resultado("ok", mudou, detalhes)
    finally:
        _trava.release()
