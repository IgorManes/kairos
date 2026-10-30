from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from tarefas import consultas
from tarefas.forms import FiltroTarefasForm
from tarefas.models import Categoria, Pessoa, Prioridade, Status, Tarefa


def nova(titulo, categoria=Categoria.PESSOAL, **campos):
    return Tarefa.objects.create(titulo=titulo, categoria=categoria, **campos)


def titulos(dados):
    return [t.titulo for t in consultas.listar_tarefas(FiltroTarefasForm(dados).filtros())]


class FiltrosTests(TestCase):
    def setUp(self):
        self.ana = Pessoa.objects.create(nome="Ana")
        self.bruno = Pessoa.objects.create(nome="Bruno")
        nova("Relatório da Ana", Categoria.TRABALHO, solicitante=self.ana, prioridade=Prioridade.ALTA)
        nova("Planilha da Ana", Categoria.TRABALHO, solicitante=self.ana)
        nova("Deploy do Bruno", Categoria.TRABALHO, solicitante=self.bruno, prioridade=Prioridade.ALTA)
        nova("Mercado", observacoes="comprar café")
        nova("Antiga", status=Status.CONCLUIDA)

    def test_padrao_mostra_so_as_abertas(self):
        self.assertNotIn("Antiga", titulos({}))

    def test_status_todas_inclui_concluidas(self):
        self.assertIn("Antiga", titulos({"status": "todas"}))

    def test_filtros_se_combinam(self):
        resultado = titulos({"categoria": "trabalho", "solicitante": self.ana.pk, "prioridade": "alta"})
        self.assertEqual(resultado, ["Relatório da Ana"])

    def test_busca_ignora_maiusculas_e_acentos(self):
        self.assertEqual(titulos({"q": "CAFÉ"}), ["Mercado"])      # observações
        self.assertEqual(titulos({"q": "cafe"}), ["Mercado"])
        self.assertEqual(titulos({"q": "relatorio"}), ["Relatório da Ana"])
        self.assertEqual(titulos({"q": "deploy"}), ["Deploy do Bruno"])

    def test_filtro_invalido_e_ignorado_sem_derrubar_os_outros(self):
        resultado = titulos({"categoria": "trabalho", "solicitante": "999", "prioridade": "<script>"})
        self.assertEqual(len(resultado), 3)  # só o filtro de categoria valeu

    def test_ordenar_por_prioridade(self):
        resultado = titulos({"categoria": "trabalho", "ordem": "prioridade"})
        self.assertEqual(resultado[-1], "Planilha da Ana")  # média depois das altas

    def test_ordenar_por_prazo_deixa_sem_prazo_no_fim(self):
        hoje = timezone.localdate()
        nova("Amanhã", prazo=hoje + timedelta(days=1))
        nova("Ontem", prazo=hoje - timedelta(days=1))
        resultado = titulos({"categoria": "pessoal"})
        self.assertEqual(resultado[:2], ["Ontem", "Amanhã"])
        self.assertEqual(resultado[-1], "Mercado")


class TelaTarefasTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("dono", password="x-senha-123"))

    def test_pagina_mostra_contagem_e_limpar_filtros(self):
        nova("Mercado")
        html = self.client.get("/tarefas/?categoria=pessoal").content.decode()
        self.assertIn("1 tarefa", html)
        self.assertIn("Limpar filtros", html)
        self.assertIn("Mercado", html)

    def test_paginacao_mantem_os_filtros(self):
        Tarefa.objects.bulk_create([Tarefa(titulo=f"T{i}", categoria=Categoria.PESSOAL) for i in range(55)])
        html = self.client.get("/tarefas/?categoria=pessoal").content.decode()
        self.assertIn("Página 1 de 2", html)
        self.assertIn("?categoria=pessoal&pagina=2", html)

    def test_pagina_inexistente_mostra_a_ultima(self):
        nova("Mercado")
        self.assertEqual(self.client.get("/tarefas/?pagina=99").status_code, 200)

    def test_telas_escutam_o_aviso_de_mudanca(self):
        for url in ("/", "/tarefas/"):
            with self.subTest(url=url):
                self.assertIn("dadosMudaram from:body", self.client.get(url).content.decode())


class ReunioesPassadasTests(TestCase):
    def test_reuniao_que_ja_terminou_sai_das_abertas_mas_aparece_em_todas(self):
        agora = timezone.now()
        nova("Passada", Categoria.REUNIAO, inicio=agora - timedelta(hours=3), fim=agora - timedelta(hours=2))
        nova("Futura", Categoria.REUNIAO, inicio=agora + timedelta(hours=2), fim=agora + timedelta(hours=3))
        self.assertEqual(titulos({"categoria": "reuniao"}), ["Futura"])
        self.assertEqual(sorted(titulos({"categoria": "reuniao", "status": "todas"})), ["Futura", "Passada"])
        self.assertEqual(Tarefa.objects.get(titulo="Passada").status, Status.A_FAZER)  # status intocado
