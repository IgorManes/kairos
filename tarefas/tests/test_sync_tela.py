"""Sync automático, botão e Configurações (o sync em si é simulado)."""

import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from tarefas.google import servico
from tarefas.google.credenciais import ESCOPOS
from tarefas.models import EstadoSync

HTMX = {"HTTP_HX_REQUEST": "true"}
RESUMO_SEM_MUDANCA = {"criadas": 0, "atualizadas": 0, "canceladas": 0, "completo": False}


class ComTokenFalso(TestCase):
    """Cria um token.json falso numa pasta temporária (nunca o real)."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.token = Path(self.pasta.name) / "token.json"
        self.token.write_text(json.dumps({"scopes": ESCOPOS}), encoding="utf-8")
        ajuste = override_settings(
            GOOGLE_TOKEN=self.token, GOOGLE_CREDENCIAIS=Path(self.pasta.name) / "credentials.json"
        )
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.client.force_login(get_user_model().objects.create_user("dono", password="x-senha-123"))
        # Nada fala com o Google de verdade
        for alvo in (
            "tarefas.google.servico.obter_credenciais",
            "tarefas.google.servico.servico_agenda",
            "tarefas.google.servico.servico_classroom",
            "tarefas.google.classroom.buscar",
        ):
            patcher = mock.patch(alvo, return_value=([], {}, {})) if alvo.endswith("buscar") else mock.patch(alvo)
            patcher.start()
            self.addCleanup(patcher.stop)


class IntervaloTests(ComTokenFalso):
    def test_automatico_pula_se_sincronizou_ha_menos_de_50s(self):
        EstadoSync.objects.create(fonte="agenda:primary", ultimo_sync_em=timezone.now() - timedelta(seconds=20))
        self.assertEqual(servico.sincronizar_tudo("auto").situacao, "pulado")

    @mock.patch("tarefas.google.agenda.sincronizar_agenda", return_value=RESUMO_SEM_MUDANCA)
    def test_botao_sincroniza_sempre(self, sync):
        EstadoSync.objects.create(fonte="agenda:primary", ultimo_sync_em=timezone.now())
        self.assertEqual(servico.sincronizar_tudo("botao").situacao, "ok")
        sync.assert_called()

    def test_so_um_sync_por_vez(self):
        with servico._trava:  # outro sync em andamento
            self.assertEqual(servico.sincronizar_tudo("botao").situacao, "ocupado")

    @mock.patch("tarefas.google.agenda.sincronizar_agenda", side_effect=RuntimeError("sem internet"))
    def test_erro_fica_registrado_e_nao_derruba(self, _):
        r = servico.sincronizar_tudo("botao")
        self.assertEqual(r.situacao, "erro")
        self.assertIn("sem internet", EstadoSync.objects.get(fonte="agenda:primary").ultimo_erro)


class TelaTests(ComTokenFalso):
    @mock.patch(
        "tarefas.google.agenda.sincronizar_agenda",
        return_value={"criadas": 1, "atualizadas": 0, "canceladas": 0, "completo": False},
    )
    def test_com_novidades_avisa_as_telas(self, _):
        resposta = self.client.post("/sincronizar/", {"motivo": "auto"}, **HTMX)
        self.assertEqual(resposta["HX-Trigger"], "dadosMudaram")
        self.assertIn('id="sync-status"', resposta.content.decode())

    @mock.patch("tarefas.google.agenda.sincronizar_agenda", return_value=RESUMO_SEM_MUDANCA)
    def test_sem_novidades_nao_pisca_a_tela(self, _):
        resposta = self.client.post("/sincronizar/", {"motivo": "auto"}, **HTMX)
        self.assertNotIn("HX-Trigger", resposta)

    @mock.patch("tarefas.google.agenda.sincronizar_agenda", return_value=RESUMO_SEM_MUDANCA)
    def test_botao_mostra_toast(self, _):
        html = self.client.post("/sincronizar/", {"motivo": "botao"}, **HTMX).content.decode()
        self.assertIn("nada novo", html)

    def test_paginas_tem_o_relogio_do_sync_quando_conectado(self):
        html = self.client.get("/").content.decode()
        self.assertIn("every 60s", html)
        self.assertIn("visibilitychange", html)

    def test_configuracoes_mostra_erro_da_agenda(self):
        EstadoSync.objects.create(fonte="agenda:primary", ultimo_erro="cota excedida", ultimo_erro_em=timezone.now())
        html = self.client.get("/configuracoes/").content.decode()
        self.assertIn("cota excedida", html)
        self.assertIn("Erro no último sync", html)

    @mock.patch("requests.post")
    def test_desconectar_apaga_o_token_e_os_marcadores(self, revogar):
        EstadoSync.objects.create(fonte="agenda:primary", sync_token="T1")
        with mock.patch("google.oauth2.credentials.Credentials.from_authorized_user_file") as carregar:
            carregar.return_value.token = "abc"
            resposta = self.client.post("/google/desconectar/", **HTMX)
        self.assertFalse(self.token.exists())
        self.assertEqual(EstadoSync.objects.get().sync_token, "")
        self.assertEqual(resposta["HX-Refresh"], "true")
        revogar.assert_called_once()

    def test_desconectado_mantem_o_relogio_para_backup_e_relatorios(self):
        self.token.unlink()
        html = self.client.get("/").content.decode()
        self.assertIn("every 60s", html)  # backup diário e fotos semanais não dependem do Google
        self.assertIn("Google desconectado", html)


class IdUnicoTests(ComTokenFalso):
    def test_configuracoes_nao_repete_o_id_do_indicador(self):
        html = self.client.get("/configuracoes/").content.decode()
        self.assertEqual(html.count('id="sync-status"'), 1)
