"""
Preenche o banco de DESENVOLVIMENTO com dados de exemplo, para ver as telas.

    python manage.py dados_exemplo

Travas: só roda no dev.sqlite3 e não roda se já houver dados de exemplo.
"""

from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tarefas.models import Categoria, Disciplina, Origem, Pessoa, Prioridade, Projeto, Status, Tarefa


class Command(BaseCommand):
    help = "Cria pessoas, projetos, disciplinas, tarefas e reuniões de exemplo (só no banco de desenvolvimento)."

    def handle(self, *args, **opcoes):
        banco = str(settings.DATABASES["default"]["NAME"])
        if not banco.endswith("dev.sqlite3"):
            raise CommandError(f"Recusado: o banco atual é {banco}. Este comando só roda no dev.sqlite3.")
        if Pessoa.objects.filter(nome="Ana").exists():
            raise CommandError("Os dados de exemplo já existem neste banco.")

        with transaction.atomic():  # tudo ou nada
            self.criar()
        self.stdout.write(self.style.SUCCESS("Dados de exemplo criados."))

    def criar(self):
        hoje = timezone.localdate()
        dia = lambda n: hoje + timedelta(days=n)  # noqa: E731

        eu = Pessoa.objects.create(nome="Eu", cor="#a3e635")
        ana = Pessoa.objects.create(nome="Ana", cor="#f59e0b")
        bruno = Pessoa.objects.create(nome="Bruno", cor="#22d3ee")
        carla = Pessoa.objects.create(nome="Carla", cor="#f472b6")
        kairos = Projeto.objects.create(nome="Kairos", categoria=Categoria.PESSOAL)
        viagem = Projeto.objects.create(nome="Viagem de dezembro", categoria=Categoria.PESSOAL)
        calc = Disciplina.objects.create(nome="Cálculo II", classroom_id="exemplo-calc")
        es = Disciplina.objects.create(nome="Engenharia de Software", classroom_id="exemplo-es")
        bd = Disciplina.objects.create(nome="Banco de Dados", classroom_id="exemplo-bd")

        T, F, P = Categoria.TRABALHO, Categoria.FACULDADE, Categoria.PESSOAL
        classroom = {"origem": Origem.GOOGLE_CLASSROOM, "link_externo": "https://classroom.google.com/"}
        tarefas = [
            dict(
                titulo="Enviar relatório de indicadores para a diretoria",
                categoria=T,
                solicitante=ana,
                prioridade=Prioridade.URGENTE,
                prazo=dia(-1),
                observacoes="Usar os números fechados de setembro.",
            ),
            dict(
                titulo="Lista de exercícios 3",
                categoria=F,
                disciplina=calc,
                prazo=dia(-2),
                prazo_hora=time(23, 59),
                id_externo="exemplo-1",
                **classroom,
            ),
            dict(
                titulo="Revisar PR da integração de pagamentos",
                categoria=T,
                solicitante=bruno,
                prioridade=Prioridade.ALTA,
                prazo=dia(0),
                prazo_hora=time(18, 0),
                status=Status.EM_ANDAMENTO,
            ),
            dict(
                titulo="Ajustar planilha de custos do projeto",
                categoria=T,
                solicitante=carla,
                prazo=dia(0),
                status=Status.AGUARDANDO,
            ),
            dict(
                titulo="Resumo do capítulo 4",
                categoria=F,
                disciplina=es,
                prazo=dia(0),
                prazo_hora=time(23, 59),
                id_externo="exemplo-2",
                **classroom,
            ),
            dict(titulo="Comprar presente de aniversário da mãe", categoria=P, prazo=dia(0)),
            dict(titulo="Pagar boleto da internet", categoria=P, prazo=dia(0), status=Status.CONCLUIDA),
            dict(
                titulo="Preparar apresentação de resultados do trimestre",
                categoria=T,
                solicitante=ana,
                prioridade=Prioridade.ALTA,
                prazo=dia(1),
            ),
            dict(titulo="Propor automação do relatório semanal", categoria=T, solicitante=eu, prazo=dia(1)),
            dict(titulo="Comprar ingresso da trilha", categoria=P, projeto=viagem, prazo=dia(2)),
            dict(
                titulo="Prova de Banco de Dados",
                categoria=F,
                disciplina=bd,
                prioridade=Prioridade.URGENTE,
                prazo=dia(5),
                prazo_hora=time(19, 0),
                id_externo="exemplo-3",
                **classroom,
            ),
            dict(titulo="Kairos: tela de tarefas", categoria=P, projeto=kairos, prazo=dia(5)),
            dict(titulo="Atualizar documentação da API", categoria=T, solicitante=bruno, prazo=dia(12)),
        ]
        for campos in tarefas:
            Tarefa.objects.create(**campos)

        def as_horas(h, m=0):
            return timezone.make_aware(datetime.combine(hoje, time(h, m)))

        reunioes = [
            ("Daily do time", as_horas(9, 30), as_horas(9, 45)),
            ("Revisão da sprint", as_horas(14), as_horas(15)),
            ("Orientação do TCC", as_horas(16, 30), as_horas(17)),
        ]
        for titulo, inicio, fim in reunioes:
            Tarefa.objects.create(
                titulo=titulo,
                categoria=Categoria.REUNIAO,
                inicio=inicio,
                fim=fim,
                link_reuniao="https://meet.google.com/",
            )
