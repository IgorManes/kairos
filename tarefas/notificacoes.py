"""
O que avisar (sem saber nada de Windows): devolve uma lista de Aviso; quem mostra
na tela é o iniciar.pyw (bandeja). Assim tudo aqui é testável sem notificação real.

Nunca repete: cada aviso grava uma `chave` única em Notificacao. Na 1ª verificação
de todas, só registra o que já está pendente, sem mostrar (não inunda no 1º dia).
"""

from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Categoria, Notificacao, Origem, Preferencias, Status, Tarefa

ENCERRADAS = (Status.CONCLUIDA, Status.CANCELADA)
Tipo = Notificacao.Tipo


@dataclass
class Aviso:
    titulo: str
    texto: str
    url: str = "/"  # para onde o clique leva ("/?abrir=42" abre a tarefa 42)


def _lista(titulos, maximo=3):
    """'A, B e C' ou 'A, B e mais 2'."""
    titulos = list(titulos)
    if len(titulos) <= maximo:
        return " e ".join([", ".join(titulos[:-1]), titulos[-1]]) if len(titulos) > 1 else titulos[0]
    return f"{', '.join(titulos[: maximo - 1])} e mais {len(titulos) - (maximo - 1)}"


def _abertas():
    return Tarefa.objects.exclude(status__in=ENCERRADAS).exclude(categoria=Categoria.REUNIAO)


# ===== Candidatos: (chave, tipo, tarefa) de cada coisa que mereceria aviso =====


def _reunioes(agora, prefs):
    limite = agora + timedelta(minutes=prefs.minutos_antes_reuniao)
    reunioes = (
        Tarefa.objects.filter(categoria=Categoria.REUNIAO, inicio__gt=agora, inicio__lte=limite)
        .exclude(status=Status.CANCELADA)
        .order_by("inicio")
    )
    for r in reunioes:
        minutos = max(1, round((r.inicio - agora).total_seconds() / 60))
        local = timezone.localtime(r.inicio)
        detalhe = f"{r.titulo} · {local:%H:%M}" + (f" · {r.etiqueta_agenda}" if r.etiqueta_agenda else "")
        yield (
            [(f"reuniao:{r.pk}:{r.inicio.isoformat()}", Tipo.REUNIAO, r)],
            Aviso(f"Reunião em {minutos} min", detalhe, f"/?abrir={r.pk}"),
        )


def _prazos(agora, prefs):
    local = timezone.localtime(agora)
    if local.time() < prefs.hora_aviso_prazos:
        return
    de_hoje = list(_abertas().filter(prazo=local.date()).order_by("prazo_hora", "titulo"))
    if de_hoje:
        n = len(de_hoje)
        yield (
            [(f"prazos:{local.date().isoformat()}", Tipo.PRAZOS, None)],
            Aviso(f"{n} tarefa{'s' if n > 1 else ''} para hoje", _lista(t.titulo for t in de_hoje), "/"),
        )


def _atrasadas(agora, prefs):
    hoje = timezone.localdate(agora)
    atrasadas = list(_abertas().filter(prazo__lt=hoje).order_by("prazo"))
    chaves = [(f"atrasada:{t.pk}:{t.prazo.isoformat()}", Tipo.ATRASADA, t) for t in atrasadas]
    yield (
        chaves,
        lambda novas: (
            Aviso("Tarefa atrasada", novas[0].titulo, f"/?abrir={novas[0].pk}")
            if len(novas) == 1
            else Aviso(f"{len(novas)} tarefas ficaram atrasadas", _lista(t.titulo for t in novas), "/")
        ),
    )


def _classroom(agora, prefs):
    novas = list(_abertas().filter(origem=Origem.GOOGLE_CLASSROOM).select_related("disciplina"))
    chaves = [(f"classroom:{t.pk}", Tipo.CLASSROOM, t) for t in novas]

    def montar(lista):
        if len(lista) == 1:
            t = lista[0]
            prazo = f" · até {t.prazo:%d/%m}" if t.prazo else ""
            return Aviso(
                f"Nova atividade · {t.disciplina.nome if t.disciplina else 'Classroom'}",
                f"{t.titulo}{prazo}",
                f"/?abrir={t.pk}",
            )
        return Aviso(f"{len(lista)} atividades novas no Classroom", _lista(t.titulo for t in lista), "/")

    yield chaves, montar


# ===== Verificação =====


def _registrar(chave, tipo, tarefa, mostrada):
    """Grava a chave; devolve False se ela já existia (aviso já dado)."""
    try:
        # Ponto de salvamento: se a chave já existe, desfaz só esta gravação; sem isso,
        # o erro do banco "envenenaria" a transação inteira em volta.
        with transaction.atomic():
            Notificacao.objects.create(chave=chave, tipo=tipo, tarefa=tarefa, mostrada=mostrada)
        return True
    except IntegrityError:
        return False


def verificar(agora=None):
    """Avisos novos desde a última verificação (chamado pelo relógio do app, a cada minuto)."""
    agora = agora or timezone.now()
    prefs = Preferencias.atual()
    # 1ª verificação: só registra. O resumo do dia não conta (ele roda antes, na abertura,
    # e fazia a 1ª verificação achar que já tinha rodado e mostrar tudo de uma vez).
    silencioso = not Notificacao.objects.exclude(tipo=Tipo.RESUMO).exists()
    fontes = [
        (prefs.avisar_reuniao, _reunioes),
        (prefs.avisar_prazos, _prazos),
        (prefs.avisar_atrasadas, _atrasadas),
        (prefs.avisar_classroom, _classroom),
    ]
    existentes = set(Notificacao.objects.values_list("chave", flat=True))
    avisos = []
    for ligado, fonte in fontes:
        if not ligado:
            continue
        for chaves, aviso in fonte(agora, prefs):
            novas = [(c, t, tarefa) for c, t, tarefa in chaves if c not in existentes]
            novas = [(c, t, tarefa) for c, t, tarefa in novas if _registrar(c, t, tarefa, not silencioso)]
            if novas and not silencioso:
                avisos.append(aviso([tarefa for _, _, tarefa in novas]) if callable(aviso) else aviso)
    return avisos


def resumo_do_dia(agora=None):
    """Um aviso por dia, na abertura do app: "2 atrasadas, 4 para hoje, 3 reuniões"."""
    agora = agora or timezone.now()
    if not Preferencias.atual().avisar_resumo:
        return None
    hoje = timezone.localdate(agora)
    if not _registrar(f"resumo:{hoje.isoformat()}", Tipo.RESUMO, None, True):
        return None
    atrasadas = _abertas().filter(prazo__lt=hoje).count()
    para_hoje = _abertas().filter(prazo=hoje).count()
    reunioes = (
        Tarefa.objects.filter(categoria=Categoria.REUNIAO, inicio__date=hoje, inicio__gt=agora)
        .exclude(status=Status.CANCELADA)
        .count()
    )
    partes = []
    if atrasadas:
        partes.append(f"{atrasadas} atrasada{'s' if atrasadas > 1 else ''}")
    partes.append(f"{para_hoje} para hoje")
    partes.append(f"{reunioes} reuni{'ões' if reunioes != 1 else 'ão'}")
    return Aviso("Seu dia no Kairos", ", ".join(partes), "/")
