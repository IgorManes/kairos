import json
import tempfile
from pathlib import Path
from unittest import mock

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from django.test import TestCase, override_settings

from tarefas import push
from tarefas.models import AssinaturaPush


class CriptografiaTests(TestCase):
    def test_igual_ao_exemplo_da_rfc_8291(self):
        # Valores do apêndice A / seção 5 da RFC 8291: salt e chave do servidor fixos.
        chave_servidor = ec.derive_private_key(
            int.from_bytes(push.de_b64("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"), ec.SECP256R1()
        )
        resultado = push.criptografar(
            b"When I grow up, I want to be a watermelon",
            p256dh="BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4",
            auth="BTBZMqHH6r4Tts7J_aSIgg",
            salt=push.de_b64("DGv6ra1nlYgDCS1FRnbzlw"),
            chave_servidor=chave_servidor,
        )
        esperado = (
            "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6"
            "PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
        )
        self.assertEqual(push.b64(resultado), esperado)

    def test_cada_envio_usa_salt_e_chave_novos(self):
        aparelho = ec.generate_private_key(ec.SECP256R1()).public_key()
        p256dh = push.b64(push._bytes_da_publica(aparelho))
        a = push.criptografar(b"oi", p256dh, "BTBZMqHH6r4Tts7J_aSIgg")
        b = push.criptografar(b"oi", p256dh, "BTBZMqHH6r4Tts7J_aSIgg")
        self.assertNotEqual(a, b)


class VapidTests(TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        configuracao = override_settings(
            VAPID_ARQUIVO=Path(pasta.name) / "vapid.pem", KAIROS_DOMINIO_REMOTO="kairos.exemplo.ts.net"
        )
        configuracao.enable()
        self.addCleanup(configuracao.disable)

    def test_chave_criada_uma_vez_e_reaproveitada(self):
        primeira = push.chave_publica_b64()
        self.assertEqual(push.chave_publica_b64(), primeira)
        self.assertEqual(len(push.de_b64(primeira)), 65)  # 0x04 + X + Y

    def test_cracha_assinado_e_valido_para_o_servico_de_push(self):
        valor = push.cabecalho_vapid("https://web.push.apple.com/QGuQyavXut/abc", agora=1_000_000)
        token = valor.removeprefix("vapid t=").split(", k=")[0]
        cabecalho, corpo, assinatura = token.split(".")
        dados = json.loads(push.de_b64(corpo))
        self.assertEqual(dados["aud"], "https://web.push.apple.com")
        self.assertEqual(dados["exp"], 1_000_000 + 12 * 3600)
        self.assertEqual(dados["sub"], "https://kairos.exemplo.ts.net")

        # A assinatura confere com a chave pública que vai junto (lança erro se não conferir).
        bruta = push.de_b64(assinatura)
        der = encode_dss_signature(int.from_bytes(bruta[:32], "big"), int.from_bytes(bruta[32:], "big"))
        publica = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), push.de_b64(valor.split(", k=")[1]))
        publica.verify(der, f"{cabecalho}.{corpo}".encode(), ec.ECDSA(hashes.SHA256()))


class EnvioTests(TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        configuracao = override_settings(VAPID_ARQUIVO=Path(pasta.name) / "vapid.pem")
        configuracao.enable()
        self.addCleanup(configuracao.disable)
        p256dh = push.b64(push._bytes_da_publica(ec.generate_private_key(ec.SECP256R1()).public_key()))
        for nome in ("ok", "morta", "sem-rede", "recusada"):
            AssinaturaPush.objects.create(
                endpoint=f"https://push.exemplo/{nome}", p256dh=p256dh, auth="BTBZMqHH6r4Tts7J_aSIgg", aparelho=nome
            )

    def test_apaga_so_assinatura_morta_e_mantem_erros_temporarios(self):
        def responder(url, **kwargs):
            if url.endswith("sem-rede"):
                raise requests.ConnectionError("sem internet")
            codigo = {"ok": 201, "morta": 410, "recusada": 400}[url.rsplit("/", 1)[1]]
            return mock.Mock(status_code=codigo, text="")

        with mock.patch("tarefas.push.requests.post", side_effect=responder) as post:
            aceitos = push.enviar_para_todos("Reunião em 10 min", "Daily", "/?abrir=1")

        self.assertEqual(aceitos, 1)
        self.assertEqual(
            sorted(AssinaturaPush.objects.values_list("aparelho", flat=True)), ["ok", "recusada", "sem-rede"]
        )
        cabecalhos = post.call_args_list[0].kwargs["headers"]
        self.assertEqual(cabecalhos["Content-Encoding"], "aes128gcm")
        self.assertTrue(cabecalhos["Authorization"].startswith("vapid t="))


class TelasPushTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        usuario = get_user_model().objects.create_user("dono", password="senha-certa-123")
        self.client.force_login(usuario)
        self.p256dh = push.b64(push._bytes_da_publica(ec.generate_private_key(ec.SECP256R1()).public_key()))
        self.htmx = {"HTTP_HX_REQUEST": "true"}

    def assinar(self, **dados):
        valores = {
            "endpoint": "https://web.push.apple.com/abc",
            "p256dh": self.p256dh,
            "auth": "BTBZMqHH6r4Tts7J_aSIgg",
            **dados,
        }
        iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X)"
        return self.client.post("/push/assinar/", valores, HTTP_USER_AGENT=iphone, **self.htmx)

    def test_service_worker_na_raiz_e_sem_login(self):
        self.client.logout()
        resposta = self.client.get("/sw.js")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("javascript", resposta["Content-Type"])
        self.assertIn('addEventListener("push"', resposta.content.decode())

    def test_assinar_guarda_o_aparelho_uma_vez_so(self):
        self.assertEqual(self.assinar().status_code, 200)
        self.assinar()  # o mesmo aparelho de novo: atualiza, não duplica
        assinatura = AssinaturaPush.objects.get()
        self.assertEqual(assinatura.aparelho, "iPhone")

    def test_assinar_recusa_dados_invalidos(self):
        self.assertEqual(self.assinar(endpoint="http://inseguro/abc").status_code, 400)
        self.assertEqual(self.assinar(p256dh="curta").status_code, 400)
        self.assertEqual(self.assinar(auth="!!!").status_code, 400)
        self.assertFalse(AssinaturaPush.objects.exists())

    def test_assinar_exige_login(self):
        self.client.logout()
        self.assertEqual(self.assinar().status_code, 302)
        self.assertFalse(AssinaturaPush.objects.exists())

    def test_remover(self):
        self.assinar()
        resposta = self.client.post(f"/push/{AssinaturaPush.objects.get().pk}/remover/", **self.htmx)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(AssinaturaPush.objects.exists())

    def test_enviar_teste(self):
        self.assinar()
        with mock.patch("tarefas.push.requests.post", return_value=mock.Mock(status_code=201, text="")) as post:
            resposta = self.client.post("/push/testar/", **self.htmx)
        self.assertEqual(post.call_count, 1)
        self.assertIn("1 de 1", resposta.content.decode())

    def test_configuracoes_mostra_secao_com_a_chave_publica(self):
        self.assinar()
        html = self.client.get("/configuracoes/").content.decode()
        self.assertIn('id="config-push"', html)
        self.assertIn(f'data-push-chave="{push.chave_publica_b64()}"', html)
        self.assertIn("iPhone", html)

    def test_testes_nunca_usam_a_chave_da_pasta_real(self):
        from django.conf import settings

        self.assertNotEqual(settings.VAPID_ARQUIVO.parent, settings.DATA_DIR)
