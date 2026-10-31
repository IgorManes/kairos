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


class TextosDeTempoTests(TestCase):
    def test_ha_quanto(self):
        from datetime import timedelta

        from django.utils import timezone

        from tarefas.templatetags.kairos import ha_quanto

        agora = timezone.now()
        casos = {20: "agora", 300: "há 5 min", 7200: "há 2 h", 86400 * 3: "há 3 dias"}
        for segundos, esperado in casos.items():
            with self.subTest(segundos=segundos):
                self.assertEqual(ha_quanto(agora - timedelta(seconds=segundos)), esperado)

    def test_reuniao_em_andamento_no_contador(self):
        from datetime import timedelta

        from django.utils import timezone

        from tarefas.models import Categoria, Tarefa

        self.client.force_login(get_user_model().objects.create_user("dono2", password="x-senha-123"))
        agora = timezone.now()
        Tarefa.objects.create(
            titulo="Agora",
            categoria=Categoria.REUNIAO,
            inicio=agora - timedelta(minutes=10),
            fim=agora + timedelta(minutes=20),
        )
        if timezone.localtime(agora - timedelta(minutes=10)).date() != timezone.localdate(agora):
            self.skipTest("logo após a meia-noite a reunião começou 'ontem'")
        self.assertIn("em andamento agora", self.client.get("/").content.decode())


class TemplatesTests(TestCase):
    def test_comentarios_curtos_fecham_na_mesma_linha(self):
        # {# ... #} só vale numa linha; quebrado em duas, aparece como texto na tela.
        from pathlib import Path

        from django.conf import settings

        problemas = []
        for arquivo in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
                if linha.count("{#") > linha.count("#}"):
                    problemas.append(f"{arquivo.name}:{numero}")
        self.assertEqual(problemas, [], "use {% comment %} para comentários de várias linhas")


class AppInstalavelTests(TestCase):
    """Manifesto e ícones para instalar o Kairos no iPhone e no Edge."""

    def test_manifesto_valido_com_icones_que_existem(self):
        import json
        from pathlib import Path

        from django.contrib.staticfiles import finders

        manifesto = json.loads(Path(finders.find("manifest.webmanifest")).read_text(encoding="utf-8"))
        self.assertEqual(manifesto["display"], "standalone")
        self.assertEqual(manifesto["start_url"], "/")
        tamanhos = {icone["sizes"] for icone in manifesto["icons"]}
        self.assertTrue({"192x192", "512x512"} <= tamanhos)
        for icone in manifesto["icons"]:
            caminho = icone["src"].removeprefix("/static/")
            self.assertIsNotNone(finders.find(caminho), icone["src"])

    def test_paginas_apontam_para_manifesto_e_icone_do_iphone(self):
        html = self.client.get("/entrar/").content.decode()
        self.assertIn('rel="manifest"', html)
        self.assertIn("kairos-app-180.png", html)
        self.assertIn("viewport-fit=cover", html)
