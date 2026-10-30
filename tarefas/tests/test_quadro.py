from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from tarefas import consultas
from tarefas.models import Categoria, Status, Tarefa


def nova(titulo, categoria=Categoria.PESSOAL, **campos):
    return Tarefa.objects.create(titulo=titulo, categoria=categoria, **campos)


def colunas(categoria=None):
    return {c["status"]: [t.titulo for t in c["tarefas"]] for c in consultas.quadro(categoria)}


class QuadroTests(TestCase):
    def test_cada_tarefa_na_sua_coluna(self):
        nova("a", status=Status.A_FAZER)
        nova("b", status=Status.EM_ANDAMENTO)
        nova("c", status=Status.AGUARDANDO)
        nova("d", status=Status.CONCLUIDA)
        self.assertEqual(colunas(), {"a_fazer": ["a"], "em_andamento": ["b"], "aguardando": ["c"], "concluida": ["d"]})

    def test_concluidas_antigas_saem_da_coluna(self):
        recente = nova("ontem", status=Status.CONCLUIDA)
        antiga = nova("mes passado", status=Status.CONCLUIDA)
        Tarefa.objects.filter(pk=recente.pk).update(concluida_em=timezone.now() - timedelta(days=1))
        Tarefa.objects.filter(pk=antiga.pk).update(concluida_em=timezone.now() - timedelta(days=30))
        self.assertEqual(colunas()["concluida"], ["ontem"])

    def test_vizinhos_de_cada_coluna(self):
        nova("a", status=Status.A_FAZER)
        nova("d", status=Status.CONCLUIDA)
        por_status = {c["status"]: c["tarefas"] for c in consultas.quadro()}
        primeira, ultima = por_status["a_fazer"][0], por_status["concluida"][0]
        self.assertEqual((primeira.anterior, primeira.proximo), (None, Status.EM_ANDAMENTO))
        self.assertEqual((ultima.anterior, ultima.proximo), (Status.AGUARDANDO, None))

    def test_reunioes_e_canceladas_ficam_de_fora(self):
        nova("reuniao", categoria=Categoria.REUNIAO, inicio=timezone.now())
        nova("cancelada", status=Status.CANCELADA)
        self.assertEqual(sum(len(v) for v in colunas().values()), 0)

    def test_filtro_por_categoria(self):
        nova("pessoal")
        nova("facul", categoria=Categoria.FACULDADE)
        self.assertEqual(colunas(Categoria.FACULDADE)["a_fazer"], ["facul"])


class TelaQuadroTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("dono", password="x-senha-123"))

    def test_mostra_botoes_de_mover_e_escuta_o_aviso(self):
        nova("Estudar", status=Status.EM_ANDAMENTO)
        html = self.client.get("/quadro/").content.decode()
        self.assertIn("Mover para A fazer", html)
        self.assertIn("Mover para Aguardando", html)
        self.assertIn("dadosMudaram from:body", html)
        self.assertIn("últimos 7 dias", html)
