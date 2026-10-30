"""
Sincronização da Agenda com um "Google de mentira": nenhum teste chama a API real.
"""

import tempfile
from datetime import datetime, time, timedelta
from pathlib import Path

import httplib2
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from googleapiclient.errors import HttpError

from config.settings import ler_agendas_extras
from tarefas.google import agenda as sync
from tarefas.models import EstadoSync, Origem, Status, Tarefa

PRINCIPAL = {"id": "primary", "nome": "", "email": None, "regra": "aceitos"}
INVOGA = {"id": "empresa@invoga.com", "nome": "Invoga", "email": "empresa@invoga.com", "regra": "nao_recusados"}


class GoogleDeMentira:
    """Imita servico.events().list(...).execute(): devolve as respostas na ordem dada."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def events(self):
        return self

    def list(self, **parametros):
        self.chamadas.append(parametros)
        return self

    def execute(self, num_retries=0):
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def pagina(*eventos, token="token-1", proxima=None):
    resposta = {"items": list(eventos)}
    if proxima:
        resposta["nextPageToken"] = proxima
    else:
        resposta["nextSyncToken"] = token
    return resposta


def momento(dia=0, hora=14, minuto=0):
    data = timezone.localdate() + timedelta(days=dia)
    return timezone.make_aware(datetime.combine(data, time(hora, minuto)))


def evento(id_, titulo="Reunião", dia=0, hora=14, convidados=None, organizei=False, **extra):
    inicio = momento(dia, hora)
    e = {
        "id": id_, "status": "confirmed", "summary": titulo,
        "start": {"dateTime": inicio.isoformat()}, "end": {"dateTime": (inicio + timedelta(hours=1)).isoformat()},
        "organizer": {"self": organizei}, "htmlLink": f"https://calendar.google.com/{id_}",
    }
    if convidados is not None:
        e["attendees"] = convidados
    e.update(extra)
    return e


def eu(resposta):
    return [{"email": "outro@x.com", "responseStatus": "accepted"}, {"self": True, "responseStatus": resposta}]


class RegrasDeImportacaoTests(TestCase):
    def test_principal_importa_aceitos_e_organizados(self):
        casos = {
            "aceito": (evento("a", convidados=eu("accepted")), True),
            "sem resposta": (evento("b", convidados=eu("needsAction")), False),
            "talvez": (evento("c", convidados=eu("tentative")), False),
            "recusado": (evento("d", convidados=eu("declined")), False),
            "organizei": (evento("e", convidados=eu("needsAction"), organizei=True), True),
            "só meu, sem convidados": (evento("f"), True),
        }
        for nome, (e, esperado) in casos.items():
            with self.subTest(nome):
                self.assertEqual(sync.deve_importar(e, PRINCIPAL), esperado)

    def test_empresa_importa_tudo_menos_recusados(self):
        convidados = lambda r: [{"email": "EMPRESA@invoga.com", "responseStatus": r}]  # sem "self": acha pelo e-mail
        self.assertTrue(sync.deve_importar(evento("a", convidados=convidados("needsAction")), INVOGA))
        self.assertFalse(sync.deve_importar(evento("b", convidados=convidados("declined")), INVOGA))

    def test_dia_inteiro_nao_e_reuniao(self):
        feriado = {"id": "x", "status": "confirmed", "start": {"date": "2026-11-02"}, "end": {"date": "2026-11-03"}}
        self.assertFalse(sync.deve_importar(feriado, PRINCIPAL))

    def test_link_do_meet(self):
        self.assertEqual(sync.link_da_reuniao({"hangoutLink": "https://meet.google.com/abc"}), "https://meet.google.com/abc")
        video = {"conferenceData": {"entryPoints": [{"entryPointType": "phone", "uri": "tel:1"},
                                                    {"entryPointType": "video", "uri": "https://zoom.us/j/1"}]}}
        self.assertEqual(sync.link_da_reuniao(video), "https://zoom.us/j/1")


class SincronizacaoTests(TestCase):
    def sincronizar(self, google, agenda=PRINCIPAL, **kw):
        return sync.sincronizar_agenda(google, agenda, **kw)

    def test_primeiro_sync_e_completo_com_janela_e_salva_o_token(self):
        google = GoogleDeMentira(pagina(evento("a", "Daily", hangoutLink="https://meet.google.com/x"), token="T1"))
        resumo = self.sincronizar(google)
        self.assertTrue(resumo["completo"])
        self.assertIn("timeMin", google.chamadas[0])
        self.assertEqual(EstadoSync.objects.get(fonte="agenda:primary").sync_token, "T1")
        t = Tarefa.objects.get()
        self.assertEqual((t.titulo, t.origem, t.agenda_id, t.link_reuniao),
                         ("Daily", Origem.GOOGLE_AGENDA, "primary", "https://meet.google.com/x"))

    def test_varias_paginas(self):
        google = GoogleDeMentira(pagina(evento("a"), proxima="p2"), pagina(evento("b")))
        self.sincronizar(google)
        self.assertEqual(Tarefa.objects.count(), 2)
        self.assertEqual(google.chamadas[1]["pageToken"], "p2")

    def test_segundo_sync_no_mesmo_dia_e_incremental(self):
        self.sincronizar(GoogleDeMentira(pagina(evento("a"), token="T1")))
        google = GoogleDeMentira(pagina(token="T2"))
        resumo = self.sincronizar(google)
        self.assertFalse(resumo["completo"])
        self.assertEqual(google.chamadas[0]["syncToken"], "T1")
        self.assertNotIn("timeMin", google.chamadas[0])  # o Google não aceita janela junto com o token

    def test_primeiro_sync_do_dia_e_completo_mesmo_com_token(self):
        self.sincronizar(GoogleDeMentira(pagina(token="T1")), agora=timezone.now() - timedelta(days=1))
        resumo = self.sincronizar(GoogleDeMentira(pagina(token="T2")))
        self.assertTrue(resumo["completo"])

    def test_evento_apagado_chega_so_com_id_e_cancela(self):
        self.sincronizar(GoogleDeMentira(pagina(evento("a"), token="T1")))
        self.sincronizar(GoogleDeMentira(pagina({"id": "a", "status": "cancelled"}, token="T2")))
        self.assertEqual(Tarefa.objects.get().status, Status.CANCELADA)

    def test_sync_completo_cancela_o_que_sumiu_diferenca_de_conjuntos(self):
        self.sincronizar(GoogleDeMentira(pagina(evento("a"), evento("b"), evento("c"))))
        resumo = self.sincronizar(GoogleDeMentira(pagina(evento("a"), evento("c"))), forcar_completo=True)
        self.assertEqual(resumo["canceladas"], 1)
        self.assertEqual(Tarefa.objects.get(id_externo="b").status, Status.CANCELADA)

    def test_recusou_depois_vira_cancelada(self):
        self.sincronizar(GoogleDeMentira(pagina(evento("a", convidados=eu("accepted")))))
        self.sincronizar(GoogleDeMentira(pagina(evento("a", convidados=eu("declined")))), forcar_completo=True)
        self.assertEqual(Tarefa.objects.get().status, Status.CANCELADA)

    def test_token_vencido_refaz_completo(self):
        self.sincronizar(GoogleDeMentira(pagina(token="T1")))
        vencido = HttpError(httplib2.Response({"status": 410}), b"gone")
        google = GoogleDeMentira(vencido, pagina(evento("a"), token="T9"))
        resumo = self.sincronizar(google)
        self.assertTrue(resumo["completo"])
        self.assertIn("timeMin", google.chamadas[1])
        self.assertEqual(EstadoSync.objects.get().sync_token, "T9")

    def test_campos_do_dono_nao_sao_sobrescritos(self):
        self.sincronizar(GoogleDeMentira(pagina(evento("a", "Antes"))))
        t = Tarefa.objects.get()
        t.status, t.observacoes, t.prioridade = Status.EM_ANDAMENTO, "levar o notebook", "alta"
        t.save()
        self.sincronizar(GoogleDeMentira(pagina(evento("a", "Depois"))), forcar_completo=True)
        t.refresh_from_db()
        self.assertEqual(t.titulo, "Depois")  # do Google: atualiza
        self.assertEqual((t.status, t.observacoes, t.prioridade), (Status.EM_ANDAMENTO, "levar o notebook", "alta"))

    def test_nunca_ressuscita_reuniao_cancelada_pelo_dono(self):
        self.sincronizar(GoogleDeMentira(pagina(evento("a"))))
        Tarefa.objects.update(status=Status.CANCELADA)
        self.sincronizar(GoogleDeMentira(pagina(evento("a"))), forcar_completo=True)
        self.assertEqual(Tarefa.objects.get().status, Status.CANCELADA)

    def test_mesma_reuniao_nas_duas_agendas_vira_uma_so_com_etiqueta_da_empresa(self):
        reuniao = evento("mesma", convidados=eu("accepted"))
        self.sincronizar(GoogleDeMentira(pagina(reuniao)), agenda=PRINCIPAL)
        self.sincronizar(GoogleDeMentira(pagina(reuniao)), agenda=INVOGA)
        self.sincronizar(GoogleDeMentira(pagina(reuniao)), agenda=PRINCIPAL)  # de novo: não perde a etiqueta
        self.assertEqual(Tarefa.objects.count(), 1)
        self.assertEqual(Tarefa.objects.get().agenda_id, INVOGA["id"])

    def test_fora_da_janela_e_ignorado(self):
        self.sincronizar(GoogleDeMentira(pagina(evento("longe", dia=90))))
        self.assertFalse(Tarefa.objects.exists())

    def test_erro_fica_registrado(self):
        sync.registrar_erro(INVOGA, RuntimeError("sem internet"))
        estado = EstadoSync.objects.get(fonte="agenda:empresa@invoga.com")
        self.assertEqual(estado.ultimo_erro, "sem internet")


class ConfiguracaoTests(TestCase):
    def test_le_agendas_extras_do_env(self):
        self.assertEqual(ler_agendas_extras("Invoga=a@b.com, Outra = c@d.com,lixo"),
                         [("Invoga", "a@b.com"), ("Outra", "c@d.com")])
        self.assertEqual(ler_agendas_extras(None), [])

    def test_comando_sem_conexao_pede_para_conectar(self):
        with tempfile.TemporaryDirectory() as pasta:
            with override_settings(GOOGLE_TOKEN=Path(pasta) / "token.json"):
                with self.assertRaisesMessage(CommandError, "--conectar"):
                    call_command("sincronizar")


class EtiquetaTests(TestCase):
    @override_settings(GOOGLE_AGENDAS=[PRINCIPAL, INVOGA])
    def test_etiqueta_vem_do_nome_configurado(self):
        t = Tarefa(agenda_id=INVOGA["id"])
        self.assertEqual(t.etiqueta_agenda, "Invoga")
        self.assertEqual(Tarefa(agenda_id="primary").etiqueta_agenda, "")
