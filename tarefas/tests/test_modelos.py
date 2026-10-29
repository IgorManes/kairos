from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from tarefas.models import Categoria, Disciplina, Origem, Pessoa, Status, Tarefa


class RegrasDaTarefaTests(TestCase):
    """Regras de validação do clean()."""

    def setUp(self):
        self.pessoa = Pessoa.objects.create(nome="Ana")
        self.disciplina = Disciplina.objects.create(nome="Cálculo", classroom_id="c1")
        self.agora = timezone.now()

    def assertErroNoCampo(self, tarefa, campo):
        with self.assertRaises(ValidationError) as ctx:
            tarefa.full_clean()
        self.assertIn(campo, ctx.exception.message_dict)

    # Solicitante
    def test_trabalho_sem_solicitante_e_invalido(self):
        t = Tarefa(titulo="Relatório", categoria=Categoria.TRABALHO)
        self.assertErroNoCampo(t, "solicitante")

    def test_trabalho_com_solicitante_e_valido(self):
        t = Tarefa(titulo="Relatório", categoria=Categoria.TRABALHO, solicitante=self.pessoa)
        t.full_clean()

    def test_outras_categorias_nao_podem_ter_solicitante(self):
        for categoria in (Categoria.PESSOAL, Categoria.FACULDADE):
            with self.subTest(categoria=categoria):
                t = Tarefa(titulo="X", categoria=categoria, solicitante=self.pessoa)
                self.assertErroNoCampo(t, "solicitante")

    # Reunião
    def test_reuniao_sem_inicio_e_invalida(self):
        t = Tarefa(titulo="Daily", categoria=Categoria.REUNIAO)
        self.assertErroNoCampo(t, "inicio")

    def test_reuniao_com_fim_antes_do_inicio_e_invalida(self):
        t = Tarefa(
            titulo="Daily", categoria=Categoria.REUNIAO,
            inicio=self.agora, fim=self.agora - timedelta(minutes=1),
        )
        self.assertErroNoCampo(t, "fim")

    def test_reuniao_com_fim_igual_ao_inicio_e_valida(self):
        t = Tarefa(
            titulo="Daily", categoria=Categoria.REUNIAO,
            inicio=self.agora, fim=self.agora,
        )
        t.full_clean()

    def test_inicio_so_em_reuniao(self):
        t = Tarefa(titulo="Estudar", categoria=Categoria.PESSOAL, inicio=self.agora)
        self.assertErroNoCampo(t, "inicio")

    # Disciplina
    def test_disciplina_fora_da_faculdade_e_invalida(self):
        t = Tarefa(titulo="X", categoria=Categoria.PESSOAL, disciplina=self.disciplina)
        self.assertErroNoCampo(t, "disciplina")

    def test_disciplina_na_faculdade_e_valida(self):
        t = Tarefa(titulo="Lista 1", categoria=Categoria.FACULDADE, disciplina=self.disciplina)
        t.full_clean()


class ConcluidaEmTests(TestCase):
    """concluida_em é preenchido/limpo sozinho no save()."""

    def setUp(self):
        self.tarefa = Tarefa.objects.create(titulo="X", categoria=Categoria.PESSOAL)

    def test_comeca_vazio(self):
        self.assertIsNone(self.tarefa.concluida_em)

    def test_preenche_ao_concluir(self):
        self.tarefa.status = Status.CONCLUIDA
        self.tarefa.save()
        self.assertIsNotNone(self.tarefa.concluida_em)

    def test_salvar_de_novo_nao_troca_a_data(self):
        self.tarefa.status = Status.CONCLUIDA
        self.tarefa.save()
        data_original = self.tarefa.concluida_em

        self.tarefa.titulo = "Título editado"
        self.tarefa.save()
        self.tarefa.refresh_from_db()
        self.assertEqual(self.tarefa.concluida_em, data_original)

    def test_reabrir_limpa_e_concluir_de_novo_gera_data_nova(self):
        self.tarefa.status = Status.CONCLUIDA
        self.tarefa.save()
        primeira = self.tarefa.concluida_em

        self.tarefa.status = Status.A_FAZER
        self.tarefa.save()
        self.assertIsNone(self.tarefa.concluida_em)

        self.tarefa.status = Status.CONCLUIDA
        self.tarefa.save()
        self.assertGreaterEqual(self.tarefa.concluida_em, primeira)

    def test_salvar_so_o_status_grava_concluida_em(self):
        self.tarefa.status = Status.CONCLUIDA
        self.tarefa.save(update_fields=["status"])
        self.tarefa.refresh_from_db()
        self.assertIsNotNone(self.tarefa.concluida_em)


class AtrasadaTests(TestCase):
    """'Atrasada' é calculado: prazo < hoje e não concluída/cancelada."""

    def setUp(self):
        self.hoje = timezone.localdate()

    def nova(self, **campos):
        return Tarefa(titulo="X", categoria=Categoria.PESSOAL, **campos)

    def test_prazo_no_passado_em_aberto_esta_atrasada(self):
        self.assertTrue(self.nova(prazo=self.hoje - timedelta(days=1)).atrasada)

    def test_prazo_hoje_nao_esta_atrasada(self):
        self.assertFalse(self.nova(prazo=self.hoje).atrasada)

    def test_sem_prazo_nao_esta_atrasada(self):
        self.assertFalse(self.nova().atrasada)

    def test_concluida_ou_cancelada_nunca_esta_atrasada(self):
        ontem = self.hoje - timedelta(days=1)
        for status in (Status.CONCLUIDA, Status.CANCELADA):
            with self.subTest(status=status):
                self.assertFalse(self.nova(prazo=ontem, status=status).atrasada)


class BancoTests(TestCase):
    """Regras garantidas pelo próprio banco."""

    def test_item_do_google_nao_pode_ser_importado_duas_vezes(self):
        Tarefa.objects.create(
            titulo="A", categoria=Categoria.FACULDADE,
            origem=Origem.GOOGLE_CLASSROOM, id_externo="123",
        )
        with self.assertRaises(IntegrityError):
            Tarefa.objects.create(
                titulo="B", categoria=Categoria.FACULDADE,
                origem=Origem.GOOGLE_CLASSROOM, id_externo="123",
            )

    def test_mesmo_id_em_origens_diferentes_pode(self):
        Tarefa.objects.create(titulo="A", categoria=Categoria.FACULDADE,
                              origem=Origem.GOOGLE_CLASSROOM, id_externo="123")
        Tarefa.objects.create(titulo="B", categoria=Categoria.REUNIAO,
                              origem=Origem.GOOGLE_AGENDA, id_externo="123",
                              inicio=timezone.now())

    def test_varias_tarefas_manuais_sem_id_externo_podem(self):
        Tarefa.objects.create(titulo="A", categoria=Categoria.PESSOAL)
        Tarefa.objects.create(titulo="B", categoria=Categoria.PESSOAL)

    def test_pessoa_com_tarefas_nao_pode_ser_apagada(self):
        pessoa = Pessoa.objects.create(nome="Ana")
        Tarefa.objects.create(titulo="X", categoria=Categoria.TRABALHO, solicitante=pessoa)
        with self.assertRaises(ProtectedError):
            pessoa.delete()


class PessoaTests(TestCase):
    def test_cor_em_formato_errado_e_invalida(self):
        with self.assertRaises(ValidationError):
            Pessoa(nome="Ana", cor="azul").full_clean()

    def test_cor_hex_e_valida(self):
        Pessoa(nome="Ana", cor="#3b82f6").full_clean()
