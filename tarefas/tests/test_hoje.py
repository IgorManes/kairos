from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from tarefas import consultas
from tarefas.management.commands.dados_exemplo import Command as DadosExemplo
from tarefas.models import Categoria, Pessoa, Prioridade, Status, Tarefa


def nova(titulo, categoria=Categoria.PESSOAL, **campos):
    return Tarefa.objects.create(titulo=titulo, categoria=categoria, **campos)


class SecoesHojeTests(TestCase):
    def setUp(self):
        self.hoje = timezone.localdate()

    def titulos(self, lista):
        return [t.titulo for t in lista]

    def test_ordem_pendentes_por_prioridade_e_concluidas_no_fim(self):
        nova("baixa", prioridade=Prioridade.BAIXA, prazo=self.hoje)
        nova("feita urgente", prioridade=Prioridade.URGENTE, prazo=self.hoje, status=Status.CONCLUIDA)
        nova("alta", prioridade=Prioridade.ALTA, prazo=self.hoje)
        nova("urgente", prioridade=Prioridade.URGENTE, prazo=self.hoje)
        nova("media", prazo=self.hoje)
        hoje = consultas.secoes_hoje(self.hoje)["hoje"]
        self.assertEqual(self.titulos(hoje), ["urgente", "alta", "media", "baixa", "feita urgente"])

    def test_mesma_prioridade_ordena_pela_hora_e_sem_hora_por_ultimo(self):
        nova("sem hora", prazo=self.hoje)
        nova("18h", prazo=self.hoje, prazo_hora=time(18))
        nova("9h", prazo=self.hoje, prazo_hora=time(9))
        self.assertEqual(self.titulos(consultas.secoes_hoje(self.hoje)["hoje"]), ["9h", "18h", "sem hora"])

    def test_atrasadas_ignora_concluidas_canceladas_e_reunioes(self):
        ontem = self.hoje - timedelta(days=1)
        nova("atrasada", prazo=ontem)
        nova("concluida", prazo=ontem, status=Status.CONCLUIDA)
        nova("cancelada", prazo=ontem, status=Status.CANCELADA)
        nova("reuniao", categoria=Categoria.REUNIAO, prazo=ontem, inicio=timezone.now())
        self.assertEqual(self.titulos(consultas.secoes_hoje(self.hoje)["atrasadas"]), ["atrasada"])

    def test_proximos_7_dias_inclui_o_7o_e_exclui_o_8o(self):
        for n in (1, 7, 8):
            nova(f"+{n}", prazo=self.hoje + timedelta(days=n))
        proximos = consultas.secoes_hoje(self.hoje)["proximos"]
        self.assertEqual([dia for dia, _ in proximos], [self.hoje + timedelta(days=1), self.hoje + timedelta(days=7)])

    def test_agrupa_varias_tarefas_no_mesmo_dia(self):
        amanha = self.hoje + timedelta(days=1)
        nova("a", prazo=amanha)
        nova("b", prazo=amanha)
        [(dia, itens)] = consultas.secoes_hoje(self.hoje)["proximos"]
        self.assertEqual(len(itens), 2)

    def test_filtro_por_categoria(self):
        ana = Pessoa.objects.create(nome="Ana")
        nova("trabalho", categoria=Categoria.TRABALHO, solicitante=ana, prazo=self.hoje)
        nova("pessoal", prazo=self.hoje)
        hoje = consultas.secoes_hoje(self.hoje, Categoria.TRABALHO)["hoje"]
        self.assertEqual(self.titulos(hoje), ["trabalho"])


class ContadoresTests(TestCase):
    def test_conta_abertas_e_atrasadas_por_categoria(self):
        hoje = timezone.localdate()
        nova("a", prazo=hoje - timedelta(days=1))
        nova("b", prazo=hoje)
        nova("c", status=Status.CONCLUIDA)
        por_cat = {c["categoria"]: c for c in consultas.contadores(hoje)}
        self.assertEqual((por_cat["pessoal"]["total"], por_cat["pessoal"]["atrasadas"]), (2, 1))
        self.assertEqual(por_cat["trabalho"]["total"], 0)  # categoria vazia aparece com zero


class LinhaDoTempoTests(TestCase):
    def momento(self, h, m=0):
        return timezone.make_aware(datetime.combine(timezone.localdate(), time(h, m)))

    def reuniao(self, ini, fim):
        return nova("R", categoria=Categoria.REUNIAO, inicio=ini, fim=fim)

    def test_posicoes_usam_ponto_decimal(self):
        r = self.reuniao(self.momento(9, 30), self.momento(10))
        linha = consultas.linha_do_tempo([r], self.momento(11))
        evento = linha["eventos"][0]
        self.assertEqual((evento["topo"], evento["altura"]), ("1.500", "0.500"))
        self.assertTrue(evento["passada"])
        self.assertEqual(linha["agora"], "3.000")

    def test_estica_quando_reuniao_comeca_antes_das_8(self):
        r = self.reuniao(self.momento(7), self.momento(7, 30))
        linha = consultas.linha_do_tempo([r], self.momento(12))
        self.assertEqual(linha["horas"][0]["rotulo"], "07:00")

    def test_agora_fora_do_horario_nao_aparece(self):
        linha = consultas.linha_do_tempo([], self.momento(22))
        self.assertIsNone(linha["agora"])


class TelaHojeTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("dono", password="x-senha-123"))

    def test_mostra_tarefas_e_marca_filtro_ativo(self):
        nova("Comprar pão", prazo=timezone.localdate())
        html = self.client.get("/?categoria=pessoal").content.decode()
        self.assertIn("Comprar pão", html)
        self.assertIn("Mostrando só", html)

    def test_filtro_invalido_e_ignorado(self):
        resposta = self.client.get("/?categoria=<script>")
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("Mostrando só", resposta.content.decode())

    def test_estados_vazios(self):
        html = self.client.get("/").content.decode()
        self.assertIn("Nada atrasado", html)
        self.assertIn("Nenhuma reunião hoje", html)


class DadosExemploTests(TestCase):
    def test_recusa_fora_do_banco_de_desenvolvimento(self):
        with self.assertRaisesMessage(CommandError, "só roda no dev.sqlite3"):
            call_command("dados_exemplo")

    def test_cria_dados_validos(self):
        DadosExemplo().criar()
        self.assertEqual(Pessoa.objects.count(), 4)
        for tarefa in Tarefa.objects.all():
            tarefa.full_clean()  # todos obedecem às regras do modelo


class ColunasDaLinhaDoTempoTests(TestCase):
    def distribuir(self, *intervalos):
        eventos = [{"ini": i, "fim": f, "nome": n} for n, i, f in intervalos]
        consultas.distribuir_em_colunas(eventos)
        return {e["nome"]: (e["coluna"], e["colunas"]) for e in eventos}

    def test_sem_sobreposicao_cada_uma_ocupa_a_largura_toda(self):
        self.assertEqual(self.distribuir(("A", 9, 10), ("B", 14, 15)), {"A": (0, 1), "B": (0, 1)})

    def test_mesmo_horario_fica_lado_a_lado(self):
        self.assertEqual(self.distribuir(("A", 14, 15), ("B", 14, 15)), {"A": (0, 2), "B": (1, 2)})

    def test_reaproveita_coluna_livre_dentro_do_bloco(self):
        # C começa quando A termina, mas ainda sobrepõe B: vai para a coluna de A.
        resultado = self.distribuir(("A", 14, 15), ("B", 14, 16), ("C", 15, 16))
        self.assertEqual(resultado, {"A": (0, 2), "B": (1, 2), "C": (0, 2)})

    def test_blocos_separados_nao_se_influenciam(self):
        resultado = self.distribuir(("A", 9, 10), ("B", 9, 10), ("C", 14, 15))
        self.assertEqual(resultado["C"], (0, 1))
