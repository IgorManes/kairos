import json
import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from tarefas.models import Categoria, Origem, Status, Tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}


class AcoesTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("dono", password="x-senha-123"))
        self.tarefa = Tarefa.objects.create(titulo="Comprar pão", categoria=Categoria.PESSOAL, prazo=timezone.localdate())

    def post(self, url, dados=None):
        return self.client.post(url, dados or {}, **HTMX)

    def vals_do_desfazer(self, resposta):
        """Lê os dados do botão Desfazer no toast da resposta."""
        html = resposta.content.decode()
        bruto = re.search(r'data-desfazer hx-post="([^"]+)" hx-vals="([^"]+)"', html)
        vals = bruto.group(2).replace("&quot;", '"')
        return bruto.group(1), json.loads(vals)

    # --- Status ---
    def test_concluir_responde_painel_e_toast_com_desfazer(self):
        resposta = self.post(f"/tarefas/{self.tarefa.pk}/status/", {"status": "concluida"})
        self.tarefa.refresh_from_db()
        self.assertEqual(self.tarefa.status, Status.CONCLUIDA)
        self.assertIsNotNone(self.tarefa.concluida_em)
        html = resposta.content.decode()
        self.assertIn('id="painel"', html)
        self.assertIn("Tarefa concluída", html)

    def test_desfazer_status_volta_ao_anterior(self):
        resposta = self.post(f"/tarefas/{self.tarefa.pk}/status/", {"status": "aguardando"})
        url, vals = self.vals_do_desfazer(resposta)
        self.post(url, vals)
        self.tarefa.refresh_from_db()
        self.assertEqual(self.tarefa.status, Status.A_FAZER)

    def test_status_invalido_e_recusado(self):
        resposta = self.post(f"/tarefas/{self.tarefa.pk}/status/", {"status": "apagada"})
        self.assertEqual(resposta.status_code, 400)

    def test_get_nao_altera_nada(self):
        resposta = self.client.get(f"/tarefas/{self.tarefa.pk}/status/?status=concluida")
        self.assertEqual(resposta.status_code, 405)

    def test_filtro_ativo_continua_depois_da_acao(self):
        resposta = self.post(f"/tarefas/{self.tarefa.pk}/status/", {"status": "concluida", "filtro": "pessoal"})
        self.assertIn("Mostrando só", resposta.content.decode())

    def test_sem_htmx_volta_para_a_pagina(self):
        resposta = self.client.post(f"/tarefas/{self.tarefa.pk}/status/", {"status": "concluida"})
        self.assertRedirects(resposta, "/")

    # --- Excluir e desfazer ---
    def test_excluir_e_desfazer_restaura_identica(self):
        criado_em = self.tarefa.criado_em
        resposta = self.post(f"/tarefas/{self.tarefa.pk}/excluir/")
        self.assertFalse(Tarefa.objects.filter(pk=self.tarefa.pk).exists())

        url, vals = self.vals_do_desfazer(resposta)
        self.post(url, vals)
        restaurada = Tarefa.objects.get(pk=self.tarefa.pk)  # mesmo id
        self.assertEqual(restaurada.titulo, "Comprar pão")
        self.assertEqual(restaurada.criado_em, criado_em)  # mesmas datas

    def test_copia_adulterada_e_recusada(self):
        resposta = self.post(f"/tarefas/{self.tarefa.pk}/excluir/")
        url, vals = self.vals_do_desfazer(resposta)
        vals["copia"] = vals["copia"][:-3] + "abc"
        self.assertEqual(self.post(url, vals).status_code, 400)
        self.assertFalse(Tarefa.objects.filter(pk=self.tarefa.pk).exists())

    def test_copia_vencida_e_recusada(self):
        resposta = self.post(f"/tarefas/{self.tarefa.pk}/excluir/")
        url, vals = self.vals_do_desfazer(resposta)
        daqui_a_11_min = timezone.now().timestamp() + 11 * 60
        with mock.patch("django.core.signing.time.time", return_value=daqui_a_11_min):
            self.assertEqual(self.post(url, vals).status_code, 400)

    def test_item_do_google_nao_pode_ser_excluido(self):
        google = Tarefa.objects.create(titulo="Lista", categoria=Categoria.FACULDADE,
                                       origem=Origem.GOOGLE_CLASSROOM, id_externo="1")
        self.assertEqual(self.post(f"/tarefas/{google.pk}/excluir/").status_code, 400)
        self.assertTrue(Tarefa.objects.filter(pk=google.pk).exists())

    def test_item_do_google_pode_ser_cancelado(self):
        google = Tarefa.objects.create(titulo="Lista", categoria=Categoria.FACULDADE,
                                       origem=Origem.GOOGLE_CLASSROOM, id_externo="1",
                                       prazo=timezone.localdate() - timedelta(days=1))
        resposta = self.post(f"/tarefas/{google.pk}/status/", {"status": "cancelada"})
        self.assertIn("continua no Google", resposta.content.decode())
        google.refresh_from_db()
        self.assertEqual(google.status, Status.CANCELADA)
