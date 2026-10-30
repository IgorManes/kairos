"""
Backup do banco SQLite em %LOCALAPPDATA%\\Kairos\\backups\\.

- fazer_backup(): cópia consistente, mesmo com o app aberto (API de backup do
  SQLite; copiar o arquivo no meio de uma gravação poderia gerar cópia corrompida).
- backup_diario(): no máximo um por dia.
- Mantém só os últimos BACKUPS_MANTIDOS (14).
"""

import sqlite3
from pathlib import Path

from django.conf import settings
from django.utils import timezone

PREFIXO = "kairos-"


def _banco():
    return Path(settings.DATABASES["default"]["NAME"])


def _pasta():
    pasta = Path(settings.BACKUP_DIR)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def listar():
    """Backups existentes, do mais novo para o mais antigo."""
    return sorted(_pasta().glob(f"{PREFIXO}*.sqlite3"), reverse=True)


def fazer_backup(motivo="manual", agora=None):
    """Cria o backup e apaga os excedentes. Devolve o caminho do arquivo criado."""
    agora = timezone.localtime(agora or timezone.now())
    destino = _pasta() / f"{PREFIXO}{agora:%Y%m%d-%H%M%S}-{motivo}.sqlite3"
    origem = sqlite3.connect(str(_banco()))
    copia = sqlite3.connect(str(destino))
    try:
        origem.backup(copia)  # cópia consistente, mesmo com o banco em uso
    finally:
        copia.close()
        origem.close()
    manter_ultimos()
    return destino


def manter_ultimos(quantidade=None):
    quantidade = quantidade or settings.BACKUPS_MANTIDOS
    for velho in listar()[quantidade:]:
        velho.unlink(missing_ok=True)


def backup_diario(agora=None):
    """Faz o backup do dia se ainda não existe nenhum de hoje. Devolve o arquivo ou None."""
    hoje = f"{PREFIXO}{timezone.localtime(agora or timezone.now()):%Y%m%d}-"
    if any(b.name.startswith(hoje) for b in listar()):
        return None
    return fazer_backup("diario", agora)
