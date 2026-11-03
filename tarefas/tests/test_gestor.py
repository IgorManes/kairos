from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from tarefas import consultas, gestor
from tarefas.models import Categoria, Projeto, Status, Tarefa
from tarefas.seguranca import ip_do_aparelho

SITE = {gestor.MARCA_SITE: True}  # o que o servidor do mini-site coloca em cada pedido
AGENDAS = [
    {"id": "primary", "nome": "", "email": None, "regra": "aceitos"},
    {"id": "agenda@empresa.example", "nome": "Empresa", "email": "agenda@empresa.example", "regra": "nao_recusados"},
]
SENHA_GESTOR = "gestor-senha-forte-123"
SENHA_DONO = "dono-senha-forte-123"


class Base(TestCase):
    def setUp(self):
        self.dono = get_user_model().objects.create_superuser("dono", password=SENHA_DONO)
        self.conta = gestor.definir_senha(SENHA_GESTOR)

    def entrar_como_gestor(self, senha=SENHA_GESTOR, usuario="gestor"):
        return self.client.post("/entrar/", {"username": usuario, "password": senha}, **SITE)


@override_settings(GOOGLE_AGENDAS=AGENDAS)
class PainelTests(Base):
    def setUp(self):
        super().setUp()
        agora = timezone.now()
        visivel = Projeto.objects.create(nome="Plataforma", categoria=Categoria.TRABALHO, visivel_gestor=True)
        oculto = Projeto.objects.create(nome="Segredo", categoria=Categoria.TRABALHO)
        hoje = timezone.localdate()
        Tarefa.objects.create(
            titulo="Tela de vistoria",
            categoria=Categoria.TRABALHO,
            projeto=visivel,
            prazo=hoje + timedelta(days=20),
            observacoes="Falar com o time de campo",
        )
        Tarefa.objects.create(
            titulo="Concluída recente",
            categoria=Categoria.TRABALHO,
            projeto=visivel,
            status=Status.CONCLUIDA,
            concluida_em=agora - timedelta(days=3),
        )
        Tarefa.objects.create(
            titulo="Concluída antiga",
            categoria=Categoria.TRABALHO,
            projeto=visivel,
            status=Status.CONCLUIDA,
            concluida_em=agora - timedelta(days=60),
        )
        Tarefa.objects.create(titulo="Projeto oculto", categoria=Categoria.TRABALHO, projeto=oculto)
        Tarefa.objects.create(titulo="Prova de cálculo", categoria=Categoria.FACULDADE)
        Tarefa.objects.create(
            titulo="Daily da empresa",
            categoria=Categoria.REUNIAO,
            agenda_id="agenda@empresa.example",
            inicio=agora + timedelta(hours=2),
        )
        Tarefa.objects.create(
            titulo="Dentista", categoria=Categoria.REUNIAO, agenda_id="primary", inicio=agora + timedelta(hours=3)
        )

    def test_clicar_em_concluidas_mostra_so_as_concluidas(self):
        self.entrar_como_gestor()
        html = self.client.get("/?ver=concluidas", **SITE).content.decode()
        self.assertIn("Concluída recente", html)
        self.assertNotIn("Tela de vistoria", html)  # aberta
        self.assertNotIn("Daily da empresa", html)  # reunião
        self.assertIn("Mostrando só", html)

    def test_filtro_atrasadas_e_filtro_invalido(self):
        dados = consultas.carga_gestor(ver="atrasadas")
        self.assertEqual(dados["abertas"], [])  # a única aberta vence daqui a 20 dias
        self.assertIsNone(dados["concluidas"])
        self.assertEqual(dados["resumo"]["abertas"], 1)  # os totais não mudam com o filtro
        self.assertIsNone(consultas.carga_gestor(ver="qualquer")["ver"])  # inválido = sem filtro

    def test_sem_login_vai_para_o_login_do_gestor(self):
        self.assertRedirects(self.client.get("/", **SITE), "/entrar/", fetch_redirect_response=False)

    def test_gestor_ve_so_o_que_foi_liberado(self):
        self.assertRedirects(self.entrar_como_gestor(), "/", fetch_redirect_response=False)
        html = self.client.get("/", **SITE).content.decode()
        for visivel in ("Tela de vistoria", "Falar com o time de campo", "Concluída recente", "Daily da empresa"):
            self.assertIn(visivel, html)
        for oculto in ("Concluída antiga", "Projeto oculto", "Prova de cálculo", "Dentista"):
            self.assertNotIn(oculto, html)

    def test_resumo(self):
        resumo = consultas.carga_gestor()["resumo"]
        self.assertEqual(resumo["abertas"], 1)  # a futura conta
        self.assertEqual(resumo["concluidas"], 1)  # só a dos últimos 30 dias


class IsolamentoTests(Base):
    def test_mini_site_so_tem_login_painel_e_sair(self):
        self.entrar_como_gestor()
        for rota in ("/tarefas/", "/configuracoes/", "/admin/", "/sw.js", "/relatorios/"):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(rota, **SITE).status_code, 404)

    def test_conta_do_dono_e_recusada_no_mini_site(self):
        resposta = self.entrar_como_gestor(usuario="dono", senha=SENHA_DONO)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Usuário ou senha incorretos")
        self.assertNotIn(gestor.COOKIE, resposta.cookies)

    def test_sessao_do_dono_nao_vale_no_mini_site(self):
        # Cookies valem por endereço, não por porta: o navegador do dono mandaria a sessão dele.
        self.client.force_login(self.dono)
        self.assertEqual(self.client.get("/", **SITE).status_code, 302)

    def test_gestor_nao_entra_no_kairos_completo(self):
        resposta = self.client.post("/entrar/", {"username": "gestor", "password": SENHA_GESTOR})
        self.assertEqual(resposta.status_code, 200)  # ficou no login, com erro
        self.client.force_login(self.conta)  # mesmo que tivesse uma sessão...
        self.assertEqual(self.client.get("/").status_code, 302)  # ...é mandado para o login

    def test_cookie_do_gestor_nao_vale_no_kairos_completo(self):
        self.entrar_como_gestor()
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_trocar_senha_derruba_o_acesso(self):
        self.entrar_como_gestor()
        self.assertEqual(self.client.get("/", **SITE).status_code, 200)
        gestor.definir_senha("outra-senha-forte-456")
        self.assertEqual(self.client.get("/", **SITE).status_code, 302)

    def test_desligar_derruba_o_acesso(self):
        self.entrar_como_gestor()
        self.conta.is_active = False
        self.conta.save()
        self.assertEqual(self.client.get("/", **SITE).status_code, 302)

    def test_sair_apaga_o_cookie(self):
        self.entrar_como_gestor()
        self.client.post("/sair/", **SITE)
        self.assertEqual(self.client.get("/", **SITE).status_code, 302)


class BloqueioTests(Base):
    def test_ip_do_visitante_vem_do_funnel(self):
        pedido = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="179.249.68.245", **SITE)
        self.assertEqual(ip_do_aparelho(pedido), "179.249.68.245")

    def test_sem_ip_valido_conta_como_internet_e_nunca_como_o_pc(self):
        for valor in ("", "lixo", "127.0.0.1"):
            with self.subTest(valor=valor):
                pedido = RequestFactory().get("/", HTTP_X_FORWARDED_FOR=valor, **SITE)
                self.assertEqual(ip_do_aparelho(pedido), gestor.IP_INTERNET)

    def test_atacante_bloqueado_nao_trava_o_gestor(self):
        atacante = {**SITE, "HTTP_X_FORWARDED_FOR": "6.6.6.6"}
        for _ in range(5):
            self.client.post("/entrar/", {"username": "gestor", "password": "errada"}, **atacante)
        resposta = self.client.post("/entrar/", {"username": "gestor", "password": SENHA_GESTOR}, **atacante)
        self.assertEqual(resposta.status_code, 429)  # o atacante ficou bloqueado
        do_gestor = {**SITE, "HTTP_X_FORWARDED_FOR": "179.249.68.245"}
        resposta = self.client.post("/entrar/", {"username": "gestor", "password": SENHA_GESTOR}, **do_gestor)
        self.assertRedirects(resposta, "/", fetch_redirect_response=False)  # o gestor entra

    def test_senhas_erradas_no_mini_site_nao_trancam_o_dono(self):
        for _ in range(5):
            self.entrar_como_gestor(senha="errada")
        self.assertEqual(self.entrar_como_gestor().status_code, 429)  # o gestor ficou bloqueado
        resposta = self.client.post("/entrar/", {"username": "dono", "password": SENHA_DONO})
        self.assertRedirects(resposta, "/", fetch_redirect_response=False)  # a janela do PC continua entrando

    def test_tentativas_com_outro_usuario_tambem_contam(self):
        for _ in range(5):
            self.entrar_como_gestor(usuario="dono", senha="chute")
        self.assertEqual(self.entrar_como_gestor().status_code, 429)


class ConfiguracoesTests(TestCase):
    def setUp(self):
        self.dono = get_user_model().objects.create_superuser("dono", password=SENHA_DONO)
        self.client.force_login(self.dono)
        self.htmx = {"HTTP_HX_REQUEST": "true"}

    def test_criar_acesso_e_marcar_projeto(self):
        self.client.post("/gestor/senha/", {"senha": SENHA_GESTOR, "confirmacao": SENHA_GESTOR}, **self.htmx)
        self.assertTrue(gestor.e_gestor(gestor.usuario_gestor()))
        projeto = Projeto.objects.create(nome="Plataforma", categoria=Categoria.TRABALHO)
        self.client.post(f"/gestor/projeto/{projeto.pk}/", {"valor": "on"}, **self.htmx)
        projeto.refresh_from_db()
        self.assertTrue(projeto.visivel_gestor)

    def test_senha_fraca_ou_diferente_e_recusada(self):
        self.client.post("/gestor/senha/", {"senha": "123", "confirmacao": "123"}, **self.htmx)
        self.client.post("/gestor/senha/", {"senha": SENHA_GESTOR, "confirmacao": "outra"}, **self.htmx)
        self.assertIsNone(gestor.usuario_gestor())

    def test_secao_aparece_nas_configuracoes(self):
        self.assertContains(self.client.get("/configuracoes/"), 'id="config-gestor"')
