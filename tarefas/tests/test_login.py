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
        self.assertRedirects(self.client.get("/"), "/entrar/?next=/")

    def test_sessao_dura_30_dias(self):
        from django.conf import settings

        self.assertEqual(settings.SESSION_COOKIE_AGE, 30 * 24 * 60 * 60)
