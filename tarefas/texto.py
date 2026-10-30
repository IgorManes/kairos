import unicodedata


def sem_acento(texto):
    """'Relatório FINAL' → 'relatorio final'. Usado na busca (no Python e dentro do SQLite)."""
    if texto is None:
        return ""
    decomposto = unicodedata.normalize("NFKD", texto)  # "ó" vira "o" + acento separado
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()
