from datetime import date, datetime, time, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from tarefas import relatorios
from tarefas.models import Categoria, Pessoa, RelatorioSemanal, Status, Tarefa
from tarefas.pdf import ErroPDF

SEGUNDA = date(2026, 10, 19)  # semana de 19/10 (segunda) a 25/10 (domingo)


def momento(dia, hora=12):
    return timezone.make_aware(datetime.combine(dia, time(hora)))


def nova(titulo, categoria=Categoria.PESSOAL, criada=None, **campos):
    t = Tarefa.objects.create(titulo=titulo, categoria=categoria, **campos)
    if criada:
        Tarefa.objects.filter(pk=t.pk).update(criado_em=criada)
        t.refresh_from_db()
    return t


def concluir(tarefa, quando):
    Tarefa.objects.filter(pk=tarefa.pk).update(status=Status.CONCLUIDA, concluida_em=quando)


class SemanaTests(TestCase):
    def test_segunda_feira_de_cada_dia(self):
        self.assertEqual(relatorios.semana_de(date(2026, 10, 22)), SEGUNDA)  # quinta
        self.assertEqual(relatorios.semana_de(date(2026, 10, 25)), SEGUNDA)  # domingo
        self.assertEqual(relatorios.semana_de(SEGUNDA), SEGUNDA)


class FotoTests(TestCase):
    def setUp(self):
        self.ana = Pessoa.objects.create(nome="Ana")
        self.agora = momento(SEGUNDA + timedelta(days=7), 9)  # segunda seguinte

    def foto(self):
        return relatorios.gerar_foto(SEGUNDA, self.agora)

    def por_titulo(self, dados):
        return {t["titulo"]: t for t in dados["tarefas"]}

    def test_o_que_entra_na_foto(self):
        concluida = nova("Relatório", Categoria.TRABALHO, solicitante=self.ana, criada=momento(SEGUNDA - timedelta(days=10)))
        concluir(concluida, momento(SEGUNDA + timedelta(days=2)))
        nova("Aberta antiga", criada=momento(SEGUNDA - timedelta(days=20)), prazo=SEGUNDA + timedelta(days=3))
        velha = nova("Concluída semana passada", criada=momento(SEGUNDA - timedelta(days=20)))
        concluir(velha, momento(SEGUNDA - timedelta(days=3)))
        nova("Criada depois", criada=momento(SEGUNDA + timedelta(days=9)))

        t = self.por_titulo(self.foto())
        self.assertEqual(set(t), {"Relatório", "Aberta antiga"})
        self.assertTrue(t["Relatório"]["concluida_na_semana"])
        self.assertEqual(t["Relatório"]["solicitante"], "Ana")
        self.assertTrue(t["Aberta antiga"]["atrasada"])  # prazo na quinta, aberta na segunda seguinte

    def test_reunioes_da_semana_sem_as_canceladas(self):
        nova("Daily", Categoria.REUNIAO, inicio=momento(SEGUNDA + timedelta(days=1), 9))
        nova("Cancelada", Categoria.REUNIAO, inicio=momento(SEGUNDA + timedelta(days=1), 10), status=Status.CANCELADA)
        self.assertEqual([r["titulo"] for r in self.foto()["reunioes"]], ["Daily"])

    def test_foto_salva_nao_muda_depois(self):
        t = nova("Relatório", Categoria.TRABALHO, solicitante=self.ana, criada=momento(SEGUNDA))
        concluir(t, momento(SEGUNDA + timedelta(days=1)))
        relatorios.garantir_relatorios(self.agora)
        self.ana.nome = "Ana Paula"
        self.ana.save()
        Tarefa.objects.all().delete()  # mesmo apagando a tarefa
        salva = RelatorioSemanal.objects.get(semana_inicio=SEGUNDA).dados
        self.assertEqual(salva["tarefas"][0]["solicitante"], "Ana")


class GarantirTests(TestCase):
    def test_primeira_vez_gera_so_a_semana_passada(self):
        relatorios.garantir_relatorios(momento(SEGUNDA + timedelta(days=9)))  # quarta da semana seguinte
        self.assertEqual(list(RelatorioSemanal.objects.values_list("semana_inicio", flat=True)), [SEGUNDA])

    def test_preenche_semanas_que_faltam_sem_duplicar(self):
        relatorios.garantir_relatorios(momento(SEGUNDA + timedelta(days=7)))
        geradas = relatorios.garantir_relatorios(momento(SEGUNDA + timedelta(days=21)))  # 2 semanas sem abrir
        self.assertEqual(geradas, 2)
        self.assertEqual(relatorios.garantir_relatorios(momento(SEGUNDA + timedelta(days=21))), 0)
        self.assertEqual(RelatorioSemanal.objects.count(), 3)


class RecorteTests(TestCase):
    def dados(self):
        return {
            "tarefas": [
                {"titulo": "A", "categoria": "trabalho", "solicitante": "Ana", "projeto": "", "disciplina": ""},
                {"titulo": "B", "categoria": "faculdade", "solicitante": "", "projeto": "", "disciplina": "Cálculo II"},
            ],
            "reunioes": [{"titulo": "IA review", "agenda": "Invoga"}, {"titulo": "Dentista", "agenda": ""}],
        }

    def test_opcoes_vem_da_propria_foto(self):
        valores = [v for v, _ in relatorios.recortes_de(self.dados())]
        self.assertEqual(valores, ["geral", "categoria:trabalho", "categoria:faculdade",
                                   "solicitante:Ana", "disciplina:Cálculo II"])

    def test_trabalho_inclui_reunioes_da_empresa(self):
        tarefas, reunioes, _ = relatorios.aplicar_recorte(self.dados(), "categoria:trabalho")
        self.assertEqual(([t["titulo"] for t in tarefas], [r["titulo"] for r in reunioes]), (["A"], ["IA review"]))

    def test_recorte_por_pessoa_nao_traz_reunioes(self):
        tarefas, reunioes, rotulo = relatorios.aplicar_recorte(self.dados(), "solicitante:Ana")
        self.assertEqual(([t["titulo"] for t in tarefas], reunioes, rotulo), (["A"], [], "Solicitante: Ana"))

    def test_recorte_invalido_vira_geral(self):
        tarefas, _, rotulo = relatorios.aplicar_recorte(self.dados(), "solicitante:<script>")
        self.assertEqual((len(tarefas), rotulo), (2, "Geral (tudo)"))


class TelasTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("dono", password="x-senha-123"))
        hoje = timezone.localdate()
        self.atual = relatorios.semana_de(hoje)
        t = nova("Revisar contrato", Categoria.TRABALHO, observacoes="anotação pessoal",
                 solicitante=Pessoa.objects.create(nome="Ana"))
        concluir(t, timezone.now())

    def test_lista_mostra_semana_atual_sem_salvar_ela(self):
        html = self.client.get("/relatorios/").content.decode()
        self.assertIn("Semana atual · parcial", html)
        self.assertFalse(RelatorioSemanal.objects.filter(semana_inicio=self.atual).exists())

    def test_observacoes_so_entram_se_marcar(self):
        url = f"/relatorios/{self.atual:%Y-%m-%d}/ver/"
        self.assertNotIn("anotação pessoal", self.client.get(url).content.decode())
        self.assertIn("anotação pessoal", self.client.get(url + "?obs=1").content.decode())

    @mock.patch("tarefas.views_relatorios.html_para_pdf", return_value=b"%PDF-1.7 teste")
    def test_baixar_pdf(self, gerar):
        resposta = self.client.get(f"/relatorios/{self.atual:%Y-%m-%d}/pdf/?recorte=categoria:trabalho")
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        self.assertIn(f"kairos-semana-{self.atual:%Y-%m-%d}-trabalho-parcial.pdf", resposta["Content-Disposition"])
        self.assertIn("Revisar contrato", gerar.call_args[0][0])  # o HTML enviado ao Edge

    @mock.patch("tarefas.views_relatorios.html_para_pdf", side_effect=ErroPDF("Edge não encontrado"))
    def test_erro_do_edge_vira_mensagem_clara(self, _):
        resposta = self.client.get(f"/relatorios/{self.atual:%Y-%m-%d}/pdf/")
        self.assertEqual(resposta.status_code, 500)
        self.assertIn("Edge não encontrado", resposta.content.decode())

    def test_semana_sem_foto_ou_data_invalida_dao_404(self):
        self.assertEqual(self.client.get("/relatorios/2020-01-06/ver/").status_code, 404)
        self.assertEqual(self.client.get("/relatorios/banana/ver/").status_code, 404)


class EdgeTests(TestCase):
    @mock.patch("tarefas.pdf.CAMINHOS_EDGE", ["C:/nao/existe/msedge.exe"])
    def test_sem_edge_avisa(self):
        from tarefas.pdf import caminho_edge

        with self.assertRaisesMessage(ErroPDF, "KAIROS_EDGE"):
            caminho_edge()


class AtrasoNaSemanaAtualTests(TestCase):
    def test_na_semana_em_andamento_o_prazo_de_amanha_nao_esta_atrasado(self):
        quarta = momento(SEGUNDA + timedelta(days=2), 15)
        nova("Amanhã", criada=momento(SEGUNDA), prazo=SEGUNDA + timedelta(days=3))
        nova("Ontem", criada=momento(SEGUNDA), prazo=SEGUNDA + timedelta(days=1))
        t = {x["titulo"]: x for x in relatorios.gerar_foto(SEGUNDA, quarta)["tarefas"]}
        self.assertEqual((t["Amanhã"]["atrasada"], t["Ontem"]["atrasada"]), (False, True))
