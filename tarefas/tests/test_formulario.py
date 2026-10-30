import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from tarefas.models import Categoria, Origem, Pessoa, Status, Tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}


def dados_form(**campos):
    """Envio completo do formulário, como o navegador faria."""
    base = {"titulo": "Nova", "categoria": "pessoal", "status": "a_fazer", "prioridade": "media",
            "prazo": timezone.localdate().isoformat(), "prazo_hora": "", "solicitante": "", "disciplina": "",
            "projeto": "", "inicio": "", "fim": "", "link_reuniao": "", "observacoes": ""}
    base.update(campos)
    return base


class CriacaoRapidaTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("dono", password="x-senha-123"))

    def test_cria_para_hoje(self):
        self.client.post("/tarefas/rapida/", {"titulo": "Ligar pro banco", "cat_rapida": "pessoal"}, **HTMX)
        tarefa = Tarefa.objects.get()
        self.assertEqual((tarefa.titulo, tarefa.prazo), ("Ligar pro banco", timezone.localdate()))

    def test_trabalho_usa_eu_e_cria_na_primeira_vez(self):
        self.client.post("/tarefas/rapida/", {"titulo": "Melhoria", "cat_rapida": "trabalho"}, **HTMX)
        self.client.post("/tarefas/rapida/", {"titulo": "Outra", "cat_rapida": "trabalho"}, **HTMX)
        self.assertEqual(Pessoa.objects.filter(nome="Eu").count(), 1)  # não duplica
        self.assertTrue(all(t.solicitante.nome == "Eu" for t in Tarefa.objects.all()))

    def test_titulo_vazio_e_recusado(self):
        resposta = self.client.post("/tarefas/rapida/", {"titulo": "   ", "cat_rapida": "pessoal"}, **HTMX)
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(Tarefa.objects.exists())


class PainelTarefaTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("dono", password="x-senha-123"))
        self.ana = Pessoa.objects.create(nome="Ana")

    def test_nova_tarefa_preseleciona_eu(self):
        eu = Pessoa.objects.create(nome="Eu")
        html = self.client.get("/tarefas/nova/", **HTMX).content.decode()
        self.assertIn(f'<option value="{eu.pk}" selected>', html)

    def test_salvar_cria_e_pede_para_fechar_o_painel(self):
        resposta = self.client.post("/tarefas/nova/", dados_form(titulo="Estudar"), **HTMX)
        self.assertEqual(set(json.loads(resposta["HX-Trigger"])), {"tarefasMudaram", "fecharPainel"})
        self.assertTrue(Tarefa.objects.filter(titulo="Estudar").exists())

    def test_regra_do_modelo_aparece_como_erro_no_formulario(self):
        resposta = self.client.post("/tarefas/nova/", dados_form(categoria="trabalho"), **HTMX)
        self.assertEqual(resposta["HX-Retarget"], "#drawer-conteudo")
        self.assertIn("precisa de solicitante", resposta.content.decode())
        self.assertFalse(Tarefa.objects.exists())

    def test_campo_escondido_de_outra_categoria_e_limpo(self):
        # Escolheu a Ana em Trabalho e depois trocou para Pessoal: o "Ana" ainda é enviado.
        self.client.post("/tarefas/nova/", dados_form(categoria="pessoal", solicitante=self.ana.pk), **HTMX)
        self.assertIsNone(Tarefa.objects.get().solicitante)

    def test_reuniao_manual_exige_inicio(self):
        resposta = self.client.post("/tarefas/nova/", dados_form(categoria="reuniao"), **HTMX)
        self.assertIn("precisa de horário de início", resposta.content.decode())

    def test_editar_salva_alteracoes(self):
        tarefa = Tarefa.objects.create(titulo="Antes", categoria=Categoria.PESSOAL)
        self.client.post(f"/tarefas/{tarefa.pk}/editar/", dados_form(titulo="Depois", prioridade="alta"), **HTMX)
        tarefa.refresh_from_db()
        self.assertEqual((tarefa.titulo, tarefa.prioridade), ("Depois", "alta"))

    def test_campos_do_google_ignoram_envio_forjado(self):
        tarefa = Tarefa.objects.create(titulo="Lista 3", categoria=Categoria.FACULDADE,
                                       origem=Origem.GOOGLE_CLASSROOM, id_externo="1")
        self.client.post(f"/tarefas/{tarefa.pk}/editar/",
                         dados_form(titulo="Hackeado", categoria="faculdade", observacoes="minha nota",
                                    status="em_andamento"), **HTMX)
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.titulo, "Lista 3")          # do Google: não mudou
        self.assertEqual(tarefa.observacoes, "minha nota")  # do dono: mudou
        self.assertEqual(tarefa.status, Status.EM_ANDAMENTO)

    def test_pessoa_inativa_some_do_seletor_mas_fica_na_tarefa_dela(self):
        self.ana.ativo = False
        self.ana.save()
        html_nova = self.client.get("/tarefas/nova/", **HTMX).content.decode()
        self.assertNotIn(">Ana<", html_nova)
        tarefa = Tarefa.objects.create(titulo="Antiga", categoria=Categoria.TRABALHO, solicitante=self.ana)
        html_editar = self.client.get(f"/tarefas/{tarefa.pk}/editar/", **HTMX).content.decode()
        self.assertIn(">Ana<", html_editar)
