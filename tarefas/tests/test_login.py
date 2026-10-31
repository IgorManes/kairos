from django.test import TestCase


class LoginTests(TestCase):
    """Login obrigatório e proteção contra força bruta (django-axes)."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        self.usuario = get_user_model().objects.create_user("dono", password="senha-certa-123")

    def entrar(self, senha):
        return self.client.post("/entrar/", {"username": "dono", "password": senha})

    def test_sem_login_redireciona_para_a_tela_de_login(self):
        resposta = self.client.get("/")
        self.assertRedirects(resposta, "/entrar/?next=/")

    def test_tela_de_login_e_publica(self):
        self.assertEqual(self.client.get("/entrar/").status_code, 200)

    def test_login_com_senha_certa_entra(self):
        self.assertRedirects(self.entrar("senha-certa-123"), "/")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_cinco_erros_bloqueiam_ate_a_senha_certa(self):
        for _ in range(5):
            self.entrar("errada")
        resposta = self.entrar("senha-certa-123")
        self.assertEqual(resposta.status_code, 429)  # 429 = muitas tentativas

    def test_bloqueio_do_celular_nao_tranca_a_janela_do_pc(self):
        # Pelo Tailscale, o IP real do aparelho vem no X-Forwarded-For.
        for _ in range(5):
            self.client.post("/entrar/", {"username": "dono", "password": "errada"}, HTTP_X_FORWARDED_FOR="100.64.0.7")
        bloqueado = self.client.post(
            "/entrar/", {"username": "dono", "password": "senha-certa-123"}, HTTP_X_FORWARDED_FOR="100.64.0.7"
        )
        self.assertEqual(bloqueado.status_code, 429)
        # A janela do PC não manda o cabeçalho: continua entrando.
        self.assertRedirects(self.entrar("senha-certa-123"), "/")

    def test_ip_falso_no_cabecalho_nao_engana_o_bloqueio(self):
        from django.test import RequestFactory

        from tarefas.seguranca import ip_do_aparelho

        # O Tailscale acrescenta o IP real no fim; o começo pode ter sido inventado.
        pedido = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 100.64.0.7")
        self.assertEqual(ip_do_aparelho(pedido), "100.64.0.7")
        self.assertEqual(ip_do_aparelho(RequestFactory().get("/")), "127.0.0.1")

    def test_acesso_pelo_tailscale_e_reconhecido_como_https(self):
        from django.test import RequestFactory

        pedido = RequestFactory().get("/", HTTP_X_FORWARDED_PROTO="https")
        self.assertTrue(pedido.is_secure())
        self.assertFalse(RequestFactory().get("/").is_secure())
        self.assertRedirects(self.client.get("/"), "/entrar/?next=/")

    def test_sessao_dura_30_dias(self):
        from django.conf import settings

        self.assertEqual(settings.SESSION_COOKIE_AGE, 30 * 24 * 60 * 60)
