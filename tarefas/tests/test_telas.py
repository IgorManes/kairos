from django.contrib.auth import get_user_model
from django.test import TestCase

from tarefas.views import saudacao


class SaudacaoTests(TestCase):
    def test_horas_de_virada(self):
        casos = {0: "Bom dia", 11: "Bom dia", 12: "Boa tarde", 17: "Boa tarde", 18: "Boa noite", 23: "Boa noite"}
        for hora, esperado in casos.items():
            with self.subTest(hora=hora):
                self.assertEqual(saudacao(hora), esperado)


class TelasTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("dono", password="senha-certa-123")

    def test_login_usa_o_visual_do_app(self):
        html = self.client.get("/entrar/").content.decode()
        self.assertIn("css/tailwind.css", html)
        self.assertIn("js/htmx.min.js", html)
        self.assertIn('data-theme="dark"', html)  # escuro é o padrão

    def test_hoje_tem_navegacao_e_botao_de_sair(self):
        self.client.force_login(self.usuario)
        html = self.client.get("/").content.decode()
        self.assertIn('aria-current="page"', html)
        self.assertIn('action="/sair/"', html)
        self.assertIn("Relatórios", html)

    def test_bloqueio_mostra_pagina_propria(self):
        for _ in range(5):
            self.client.post("/entrar/", {"username": "dono", "password": "errada"})
        resposta = self.client.post("/entrar/", {"username": "dono", "password": "errada"})
        self.assertEqual(resposta.status_code, 429)
        self.assertIn("Muitas tentativas", resposta.content.decode())
