from datetime import datetime, time, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from tarefas import notificacoes
from tarefas.models import Categoria, Disciplina, Notificacao, Origem, Preferencias, Status, Tarefa


def as_horas(h, m=0, dias=0):
    return timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=dias), time(h, m)))


def nova(titulo, categoria=Categoria.PESSOAL, **campos):
    return Tarefa.objects.create(titulo=titulo, categoria=categoria, **campos)


class Base(TestCase):
    def setUp(self):
        # Ponto de partida comum: a 1ª verificação (silenciosa) já aconteceu.
        Notificacao.objects.create(chave="inicio", tipo="prazos", mostrada=False)

    def titulos(self, agora):
        return [a.titulo for a in notificacoes.verificar(agora)]


class PrimeiraVerificacaoTests(TestCase):
    def test_primeira_vez_registra_sem_mostrar(self):
        nova("Atrasada", prazo=timezone.localdate() - timedelta(days=2))
        self.assertEqual(notificacoes.verificar(as_horas(10)), [])
        self.assertFalse(Notificacao.objects.get().mostrada)
        self.assertEqual(notificacoes.verificar(as_horas(10, 5)), [])  # e não volta depois


class ReuniaoTests(Base):
    def test_avisa_uma_vez_dentro_dos_minutos(self):
        nova("Daily", Categoria.REUNIAO, inicio=as_horas(14), fim=as_horas(14, 15))
        self.assertEqual(self.titulos(as_horas(13, 40)), [])  # 20 min antes: ainda não
        self.assertEqual(self.titulos(as_horas(13, 52)), ["Reunião em 8 min"])
        self.assertEqual(self.titulos(as_horas(13, 55)), [])  # não repete

    def test_remarcada_avisa_de_novo(self):
        r = nova("Daily", Categoria.REUNIAO, inicio=as_horas(14))
        self.titulos(as_horas(13, 55))
        r.inicio = as_horas(15)
        r.save()
        self.assertEqual(self.titulos(as_horas(14, 55)), ["Reunião em 5 min"])

    def test_cancelada_nao_avisa(self):
        nova("Daily", Categoria.REUNIAO, inicio=as_horas(14), status=Status.CANCELADA)
        self.assertEqual(self.titulos(as_horas(13, 55)), [])


class PrazosTests(Base):
    def test_so_depois_do_horario_e_um_aviso_para_varias(self):
        hoje = timezone.localdate()
        for titulo in ("A", "B", "C", "D"):
            nova(titulo, prazo=hoje)
        self.assertEqual(self.titulos(as_horas(8, 59)), [])
        avisos = notificacoes.verificar(as_horas(9, 1))
        self.assertEqual([(a.titulo, a.texto) for a in avisos], [("4 tarefas para hoje", "A, B e mais 2")])
        self.assertEqual(self.titulos(as_horas(15)), [])  # uma vez por dia


class AtrasadasTests(Base):
    def test_avisa_so_as_novas_e_agrupa(self):
        ontem = timezone.localdate() - timedelta(days=1)
        t = nova("Relatório", prazo=ontem)
        avisos = notificacoes.verificar(as_horas(8))
        self.assertEqual((avisos[0].titulo, avisos[0].url), ("Tarefa atrasada", f"/?abrir={t.pk}"))
        nova("X", prazo=ontem)
        nova("Y", prazo=ontem)
        self.assertEqual(self.titulos(as_horas(8, 1)), ["2 tarefas ficaram atrasadas"])

    def test_concluida_nao_avisa(self):
        nova("Feita", prazo=timezone.localdate() - timedelta(days=1), status=Status.CONCLUIDA)
        self.assertEqual(self.titulos(as_horas(8)), [])


class ClassroomTests(Base):
    def test_atividade_nova_avisa_com_a_disciplina(self):
        calc = Disciplina.objects.create(nome="Cálculo II", classroom_id="T1")
        nova("Lista 4", Categoria.FACULDADE, origem=Origem.GOOGLE_CLASSROOM, id_externo="T1:1", disciplina=calc)
        avisos = notificacoes.verificar(as_horas(8))
        self.assertEqual((avisos[0].titulo, avisos[0].texto), ("Nova atividade · Cálculo II", "Lista 4"))


class PreferenciasTests(Base):
    def test_tudo_desligado_nao_avisa(self):
        Preferencias.objects.filter(pk=Preferencias.atual().pk).update(
            avisar_reuniao=False, avisar_prazos=False, avisar_atrasadas=False, avisar_classroom=False
        )
        nova("Daily", Categoria.REUNIAO, inicio=as_horas(14))
        nova("Atrasada", prazo=timezone.localdate() - timedelta(days=1))
        self.assertEqual(self.titulos(as_horas(13, 55)), [])


class ResumoTests(TestCase):
    def test_uma_vez_por_dia(self):
        nova("Atrasada", prazo=timezone.localdate() - timedelta(days=1))
        nova("Hoje", prazo=timezone.localdate())
        resumo = notificacoes.resumo_do_dia(as_horas(8))
        self.assertEqual(resumo.texto, "1 atrasada, 1 para hoje, 0 reuniões")
        self.assertIsNone(notificacoes.resumo_do_dia(as_horas(9)))
        self.assertIsNotNone(notificacoes.resumo_do_dia(as_horas(8, dias=1)))


class ConfiguracoesTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("dono", password="x-senha-123"))

    def test_salva_preferencias_e_recusa_valor_invalido(self):
        dados = {"avisar_reuniao": "on", "minutos_antes_reuniao": "15", "hora_aviso_prazos": "08:30"}
        self.client.post("/preferencias/notificacoes/", dados, HTTP_HX_REQUEST="true")
        p = Preferencias.atual()
        self.assertEqual((p.minutos_antes_reuniao, p.hora_aviso_prazos, p.avisar_prazos), (15, time(8, 30), False))
        resposta = self.client.post("/preferencias/notificacoes/", dict(dados, minutos_antes_reuniao="-5"))
        self.assertIn("Valor inválido", resposta.content.decode())
        self.assertEqual(Preferencias.atual().minutos_antes_reuniao, 15)

    @mock.patch("tarefas.views_google.definir_inicializacao")
    def test_iniciar_com_windows_liga_e_desliga(self, definir):
        self.client.post("/preferencias/inicializacao/", {"valor": "on"})
        self.client.post("/preferencias/inicializacao/", {})
        self.assertEqual([c.args for c in definir.call_args_list], [(True,), (False,)])

    @mock.patch("tarefas.windows._winreg")
    def test_comando_de_inicializacao_abre_na_bandeja_sem_terminal(self, _):
        from tarefas.windows import comando_inicializacao

        comando = comando_inicializacao()
        self.assertIn("pythonw.exe", comando)
        self.assertTrue(comando.endswith('iniciar.pyw" --bandeja'))


class OrdemNaAberturaTests(TestCase):
    def test_resumo_antes_nao_impede_a_primeira_verificacao_silenciosa(self):
        nova("Atrasada", prazo=timezone.localdate() - timedelta(days=2))
        notificacoes.resumo_do_dia(as_horas(8))  # na abertura, o resumo vem primeiro
        self.assertEqual(notificacoes.verificar(as_horas(8, 1)), [])  # e a 1ª verificação continua silenciosa
