"""
Tarefas periódicas do app, chamadas pelo relógio da página (a cada minuto) e na
abertura do app: foto semanal dos relatórios e backup diário. Ambas são baratas
quando não há nada a fazer.
"""

import logging

from .backup import backup_diario
from .relatorios import garantir_relatorios

log = logging.getLogger("kairos")


def rodar_periodicos():
    for tarefa in (garantir_relatorios, backup_diario):
        try:
            tarefa()
        except Exception:  # um problema aqui nunca pode derrubar a tela
            log.exception("Falha na tarefa periódica %s", tarefa.__name__)
