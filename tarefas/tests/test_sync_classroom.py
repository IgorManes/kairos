"""Sincronização do Classroom com um "Classroom de mentira": nenhum teste chama a API real."""

import json
import tempfile
from datetime import date, time, timedelta
from pathlib import Path

from django.test import TestCase, override_settings
from django.utils import timezone

from tarefas.google import classroom as sync
from tarefas.google.credenciais import ESCOPOS, PrecisaReconectar, escopos_faltando, obter_credenciais
from tarefas.models import Disciplina, Origem, Status, Tarefa


def turma(id_, nome="Cálculo II", estado="ACTIVE"):
    return {"id": id_, "name": nome, "courseState": estado}


def atividade(id_, turma_id="T1", titulo="Lista 1", prazo=None, hora=None):
    a = {"id": id_, "courseId": turma_id, "title": titulo, "alternateLink": f"https://classroom.google.com/{id_}"}
    if prazo:
        a["dueDate"], a["dueTime"] = prazo, hora or {}
    return a


def aplicar(turmas, atividades, entregas=None, concluir=True):
    return sync.aplicar(turmas, atividades, entregas or {}, timezone.now(), concluir)


class PrazoTests(TestCase):
    def test_converte_de_utc_para_o_horario_de_brasilia(self):
        # 31/10 02:59 em Londres (UTC) = 30/10 23:59 em Brasília
        self.assertEqual(
            sync.prazo_local({"year": 2026, "month": 10, "day": 31}, {"hours": 2, "minutes": 59}),
            (date(2026, 10, 30), time(23, 59)),
        )

    def test_campos_zerados_nao_vem(self):
        # {"hours": 3} = 03:00 UTC = 00:00 em Brasília (minutos ausentes = 0)
        self.assertEqual(
            sync.prazo_local({"year": 2026, "month": 11, "day": 5}, {"hours": 3}), (date(2026, 11, 5), time(0, 0))
        )

    def test_sem_prazo(self):
        self.assertEqual(sync.prazo_local(None, None), (None, None))


class RegraDaEntregaTests(TestCase):
    def test_reage_so_a_mudanca(self):
        casos = [
            # (status atual, entrega antes, entrega agora, esperado)
            (Status.A_FAZER, "CREATED", "TURNED_IN", Status.CONCLUIDA),  # entregou
            (Status.EM_ANDAMENTO, "TURNED_IN", "RETURNED", Status.CONCLUIDA),  # devolvida
            (Status.A_FAZER, "TURNED_IN", "TURNED_IN", Status.A_FAZER),  # dono reabriu: não briga
            (Status.CONCLUIDA, "TURNED_IN", "RECLAIMED_BY_STUDENT", Status.A_FAZER),  # cancelou o envio
            (Status.CANCELADA, "CREATED", "TURNED_IN", Status.CANCELADA),  # cancelada fica cancelada
            (Status.A_FAZER, "", "NEW", Status.A_FAZER),
        ]
        for atual, antes, agora, esperado in casos:
            with self.subTest(atual=atual, antes=antes, agora=agora):
                self.assertEqual(sync.novo_status(atual, antes, agora), esperado)

    def test_chave_desligada_nao_mexe(self):
        self.assertEqual(sync.novo_status(Status.A_FAZER, "CREATED", "TURNED_IN", False), Status.A_FAZER)


class AplicarTests(TestCase):
    def test_turmas_viram_disciplinas_e_arquivada_fica_inativa(self):
        aplicar([turma("T1"), turma("T2", "Física", "ARCHIVED")], {"T1": []})
        self.assertTrue(Disciplina.objects.get(classroom_id="T1").ativo)
        self.assertFalse(Disciplina.objects.get(classroom_id="T2").ativo)

    def test_atividade_vira_tarefa_de_faculdade(self):
        aplicar(
            [turma("T1")],
            {"T1": [atividade("A1", prazo={"year": 2026, "month": 11, "day": 6}, hora={"hours": 2, "minutes": 59})]},
        )
        t = Tarefa.objects.get()
        self.assertEqual(
            (t.categoria, t.origem, t.disciplina.nome), ("faculdade", Origem.GOOGLE_CLASSROOM, "Cálculo II")
        )
        self.assertEqual((t.prazo, t.prazo_hora), (date(2026, 11, 5), time(23, 59)))

    def test_primeira_importacao_de_atividade_ja_entregue_chega_concluida(self):
        aplicar([turma("T1")], {"T1": [atividade("A1")]}, {"A1": "TURNED_IN"})
        self.assertEqual(Tarefa.objects.get().status, Status.CONCLUIDA)

    def test_dono_reabriu_e_o_sync_nao_conclui_de_novo(self):
        aplicar([turma("T1")], {"T1": [atividade("A1")]}, {"A1": "TURNED_IN"})
        Tarefa.objects.update(status=Status.A_FAZER)  # reabriu no Kairos
        aplicar([turma("T1")], {"T1": [atividade("A1")]}, {"A1": "TURNED_IN"})
        self.assertEqual(Tarefa.objects.get().status, Status.A_FAZER)

    def test_campos_do_dono_nao_sao_sobrescritos(self):
        aplicar([turma("T1")], {"T1": [atividade("A1", titulo="Antes")]})
        Tarefa.objects.update(observacoes="fazer no sábado", prioridade="alta")
        aplicar([turma("T1")], {"T1": [atividade("A1", titulo="Depois")]})
        t = Tarefa.objects.get()
        self.assertEqual((t.titulo, t.observacoes, t.prioridade), ("Depois", "fazer no sábado", "alta"))

    def test_atividade_apagada_vira_cancelada(self):
        aplicar([turma("T1")], {"T1": [atividade("A1"), atividade("A2")]})
        resumo = aplicar([turma("T1")], {"T1": [atividade("A1")]})
        self.assertEqual(resumo["canceladas"], 1)
        self.assertEqual(Tarefa.objects.get(id_externo="T1:A2").status, Status.CANCELADA)

    def test_turma_arquivada_nao_cancela_as_atividades_dela(self):
        aplicar([turma("T1")], {"T1": [atividade("A1")]})
        aplicar([turma("T1", estado="ARCHIVED")], {})  # arquivada: atividades não são buscadas
        self.assertEqual(Tarefa.objects.get().status, Status.A_FAZER)

    def test_nada_mudou_nada_e_regravado(self):
        aplicar([turma("T1")], {"T1": [atividade("A1")]}, {"A1": "CREATED"})
        resumo = aplicar([turma("T1")], {"T1": [atividade("A1")]}, {"A1": "CREATED"})
        self.assertEqual((resumo["criadas"], resumo["atualizadas"]), (0, 0))


class EscoposTests(TestCase):
    def test_token_antigo_sem_classroom_pede_para_reconectar(self):
        with tempfile.TemporaryDirectory() as pasta:
            token = Path(pasta) / "token.json"
            token.write_text(json.dumps({"scopes": [ESCOPOS[0]]}), encoding="utf-8")  # só a Agenda
            with override_settings(GOOGLE_TOKEN=token):
                self.assertEqual(len(escopos_faltando()), 2)
                with self.assertRaises(PrecisaReconectar):
                    obter_credenciais()


class TokenConcedidoTests(TestCase):
    def test_grava_as_permissoes_concedidas_e_nao_as_pedidas(self):
        from unittest import mock

        from tarefas.google.credenciais import salvar_token

        credenciais = mock.Mock(granted_scopes=[ESCOPOS[0]])  # dono desmarcou o Classroom
        credenciais.to_json.return_value = json.dumps({"token": "x", "scopes": ESCOPOS})
        with tempfile.TemporaryDirectory() as pasta:
            with override_settings(GOOGLE_TOKEN=Path(pasta) / "token.json"):
                salvar_token(credenciais)
                self.assertEqual(len(escopos_faltando()), 2)  # o Kairos sabe que falta


class ApelidosDeEscopoTests(TestCase):
    def test_nome_atual_da_permissao_vale_pelo_nome_antigo(self):
        concedidos = [
            ESCOPOS[0],
            ESCOPOS[1],
            "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
        ]
        with tempfile.TemporaryDirectory() as pasta:
            token = Path(pasta) / "token.json"
            token.write_text(json.dumps({"scopes": concedidos}), encoding="utf-8")
            with override_settings(GOOGLE_TOKEN=token):
                self.assertEqual(escopos_faltando(), [])


def data_google(dias):
    """Data relativa a hoje, no formato do Classroom."""
    d = timezone.localdate() + timedelta(days=dias)
    return {"year": d.year, "month": d.month, "day": d.day}


class VencidasTests(TestCase):
    MEIO_DIA = {"hours": 15}  # 15:00 UTC = 12:00 em Brasília: a conversão não muda o dia

    def test_vencida_e_nao_entregue_nao_e_importada(self):
        aplicar([turma("T1")], {"T1": [atividade("A1", prazo=data_google(-1), hora=self.MEIO_DIA)]}, {"A1": "CREATED"})
        self.assertFalse(Tarefa.objects.exists())

    def test_vencida_mas_entregue_entra_concluida(self):
        aplicar(
            [turma("T1")], {"T1": [atividade("A1", prazo=data_google(-1), hora=self.MEIO_DIA)]}, {"A1": "TURNED_IN"}
        )
        self.assertEqual(Tarefa.objects.get().status, Status.CONCLUIDA)

    def test_entrou_no_prazo_e_venceu_depois_continua_atrasada(self):
        aplicar([turma("T1")], {"T1": [atividade("A1", prazo=data_google(2), hora=self.MEIO_DIA)]}, {"A1": "CREATED"})
        # Dias depois: o prazo passou e não foi entregue. Já era conhecida, então continua.
        aplicar([turma("T1")], {"T1": [atividade("A1", prazo=data_google(-1), hora=self.MEIO_DIA)]}, {"A1": "CREATED"})
        self.assertTrue(Tarefa.objects.get().atrasada)


class MarcoZeroTests(TestCase):
    """O que já existia sem prazo antes do Kairos acompanhar o Classroom não entra — em NENHUM sync."""

    def setUp(self):
        self.marco = timezone.now()

    def publicada(self, dias_em_relacao_ao_marco):
        return (self.marco + timedelta(days=dias_em_relacao_ao_marco)).isoformat()

    def sync(self, atividades, entregas):
        return sync.aplicar([turma("T1")], {"T1": atividades}, entregas, timezone.now(), True, marco_zero=self.marco)

    def test_sem_prazo_publicada_antes_do_marco_nao_entra_nem_no_segundo_sync(self):
        antiga = atividade("A1") | {"creationTime": self.publicada(-30)}
        for _ in range(3):  # vários syncs em sequência: o bug era ela voltar no 2º
            self.sync([antiga], {"A1": "CREATED"})
        self.assertFalse(Tarefa.objects.exists())

    def test_sem_prazo_publicada_depois_do_marco_entra(self):
        nova = atividade("A1") | {"creationTime": self.publicada(+1)}
        self.sync([nova], {"A1": "CREATED"})
        self.assertTrue(Tarefa.objects.exists())

    def test_prazo_futuro_entra_e_vencido_nao(self):
        self.sync(
            [
                atividade("A1", prazo=data_google(3), hora={"hours": 15}),
                atividade("A2", prazo=data_google(-3), hora={"hours": 15}),
            ],
            {"A1": "CREATED", "A2": "CREATED"},
        )
        self.assertEqual([t.id_externo for t in Tarefa.objects.all()], ["T1:A1"])

    def test_entregue_entra_concluida_mesmo_antiga(self):
        self.sync([atividade("A1") | {"creationTime": self.publicada(-90)}], {"A1": "TURNED_IN"})
        self.assertEqual(Tarefa.objects.get().status, Status.CONCLUIDA)


class DatasReaisTests(TestCase):
    def test_criada_e_concluida_usam_as_datas_do_classroom(self):
        a = atividade("A1") | {"creationTime": "2026-09-01T12:00:00Z"}
        entregas = {"A1": {"estado": "TURNED_IN", "atualizada_em": "2026-09-10T15:30:00Z"}}
        aplicar([turma("T1")], {"T1": [a]}, entregas)
        t = Tarefa.objects.get()
        self.assertEqual(t.criado_em.date(), date(2026, 9, 1))
        self.assertEqual(t.concluida_em.date(), date(2026, 9, 10))

    def test_conclusao_feita_pelo_dono_mantem_a_data_dele(self):
        aplicar([turma("T1")], {"T1": [atividade("A1")]}, {"A1": "CREATED"})
        t = Tarefa.objects.get()
        t.status = Status.CONCLUIDA
        t.save()
        concluida_pelo_dono = Tarefa.objects.get().concluida_em
        entregas = {"A1": {"estado": "CREATED", "atualizada_em": "2020-01-01T00:00:00Z"}}
        aplicar([turma("T1")], {"T1": [atividade("A1")]}, entregas)
        self.assertEqual(Tarefa.objects.get().concluida_em, concluida_pelo_dono)
