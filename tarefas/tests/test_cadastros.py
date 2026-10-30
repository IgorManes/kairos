import json
import re

from django.contrib.auth import get_user_model
from django.test import TestCase

from tarefas.models import Categoria, Pessoa, Projeto, Status, Tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}


class CadastrosTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("dono", password="x-senha-123"))
        self.ana = Pessoa.objects.create(nome="Ana", cor="#f59e0b")

    def test_lista_mostra_contagens(self):
        Tarefa.objects.create(titulo="A", categoria=Categoria.TRABALHO, solicitante=self.ana)
        Tarefa.objects.create(titulo="B", categoria=Categoria.TRABALHO, solicitante=self.ana, status=Status.CONCLUIDA)
        html = self.client.get("/pessoas/").content.decode()
        self.assertRegex(html, r'<b class="num text-text-2">1</b> aberta · <span class="num">2</span> no total')

    def test_ver_tarefas_leva_ao_filtro_certo(self):
        html = self.client.get("/pessoas/").content.decode()
        self.assertIn(f"/tarefas/?solicitante={self.ana.pk}&status=todas", html)

    def test_criar_pessoa(self):
        resposta = self.client.post("/pessoa/novo/", {"nome": "Bruno", "cor": "#22d3ee", "ativo": "on"}, **HTMX)
        self.assertIn("fecharPainel", json.loads(resposta["HX-Trigger"]))
        self.assertTrue(Pessoa.objects.filter(nome="Bruno", ativo=True).exists())

    def test_nome_repetido_aparece_como_erro(self):
        resposta = self.client.post("/pessoa/novo/", {"nome": "Ana", "cor": "#000000"}, **HTMX)
        self.assertEqual(resposta["HX-Retarget"], "#drawer-conteudo")
        self.assertEqual(Pessoa.objects.filter(nome="Ana").count(), 1)

    def test_editar_pessoa(self):
        self.client.post(f"/pessoa/{self.ana.pk}/editar/", {"nome": "Ana Paula", "cor": "#f59e0b", "ativo": "on"}, **HTMX)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.nome, "Ana Paula")

    def test_desativar_e_desfazer(self):
        resposta = self.client.post(f"/pessoa/{self.ana.pk}/ativo/", **HTMX)
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.ativo)
        # O "Desfazer" do toast chama a mesma ação de novo
        url = re.search(r'data-desfazer hx-post="([^"]+)"', resposta.content.decode()).group(1)
        self.client.post(url, **HTMX)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.ativo)

    def test_inativos_ficam_em_secao_propria(self):
        Pessoa.objects.create(nome="Zé", ativo=False)
        html = self.client.get("/pessoas/").content.decode()
        self.assertIn("Inativas", html)

    def test_projeto_nao_aceita_categoria_reuniao(self):
        self.client.post("/projeto/novo/", {"nome": "X", "categoria": "reuniao", "ativo": "on"}, **HTMX)
        self.assertFalse(Projeto.objects.exists())

    def test_criar_projeto_e_barra_de_progresso(self):
        self.client.post("/projeto/novo/", {"nome": "Kairos", "categoria": "pessoal", "ativo": "on"}, **HTMX)
        projeto = Projeto.objects.get()
        Tarefa.objects.create(titulo="A", categoria=Categoria.PESSOAL, projeto=projeto, status=Status.CONCLUIDA)
        Tarefa.objects.create(titulo="B", categoria=Categoria.PESSOAL, projeto=projeto)
        html = self.client.get("/projetos/").content.decode()
        self.assertIn('aria-valuenow="50"', html)

    def test_tipo_inventado_na_url_da_404(self):
        self.assertEqual(self.client.get("/usuario/novo/").status_code, 404)

    def test_pagina_mais_do_celular(self):
        html = self.client.get("/mais/").content.decode()
        self.assertIn("/pessoas/", html)
        self.assertIn("/projetos/", html)
