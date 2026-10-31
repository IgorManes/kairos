"""
Notificações no iPhone (Web Push), sem pacote extra: só `cryptography` e `requests`.

Caminho de um aviso:
    Kairos ──(criptografado + assinado)──► serviço de push (Apple) ──► aparelho

- VAPID (RFC 8292): o Kairos tem um par de chaves próprio. A pública vai para o aparelho
  na hora de assinar; a privada assina um "crachá" (JWT) em cada envio, provando ao serviço
  de push que o aviso vem do mesmo servidor que o aparelho autorizou.
- Criptografia (RFC 8291, "aes128gcm"): o serviço de push só repassa bytes embaralhados;
  só o aparelho consegue abrir.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import struct
import time
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

from .models import AssinaturaPush

log = logging.getLogger("kairos")

TAMANHO_REGISTRO = 4096  # o aviso inteiro cabe num único registro
VALIDADE_CRACHA = 12 * 3600  # o serviço de push aceita no máximo 24 h
VALIDADE_AVISO = 3600  # aviso não entregue em 1 h (aparelho desligado) é descartado
ASSINATURA_MORTA = (404, 410)  # app removido ou permissão retirada


def b64(dados):
    """Base64 "para URL" sem o '=' do fim, o formato usado em todo o Web Push."""
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def de_b64(texto):
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _hmac(chave, dados):
    return hmac.new(chave, dados, hashlib.sha256).digest()


def _bytes_da_publica(chave_publica):
    """Ponto da curva em 65 bytes: 0x04 + X (32) + Y (32)."""
    return chave_publica.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


# ===== Chaves VAPID =====


def chave_privada():
    """Lê o vapid.pem; na primeira vez, cria um par novo (curva P-256)."""
    arquivo = settings.VAPID_ARQUIVO
    if arquivo.exists():
        return serialization.load_pem_private_key(arquivo.read_bytes(), password=None)
    chave = ec.generate_private_key(ec.SECP256R1())
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_bytes(
        chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    return chave


def chave_publica_b64():
    """Vai para o aparelho na hora de assinar (applicationServerKey)."""
    return b64(_bytes_da_publica(chave_privada().public_key()))


def _contato():
    # O serviço de push exige um contato do remetente (https:// ou mailto:).
    dominio = settings.KAIROS_DOMINIO_REMOTO
    return f"https://{dominio}" if dominio else "mailto:kairos@example.com"


def cabecalho_vapid(endpoint, agora=None):
    """Header Authorization: "vapid t=<JWT assinado>, k=<chave pública>"."""
    partes = urlsplit(endpoint)
    agora = int(agora if agora is not None else time.time())
    cabecalho = {"typ": "JWT", "alg": "ES256"}
    corpo = {"aud": f"{partes.scheme}://{partes.netloc}", "exp": agora + VALIDADE_CRACHA, "sub": _contato()}
    a_assinar = ".".join(b64(json.dumps(p, separators=(",", ":")).encode()) for p in (cabecalho, corpo))

    chave = chave_privada()
    # A biblioteca devolve a assinatura no formato DER; o JWT usa r e s colados (32 + 32 bytes).
    r, s = decode_dss_signature(chave.sign(a_assinar.encode(), ec.ECDSA(hashes.SHA256())))
    assinatura = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"vapid t={a_assinar}.{b64(assinatura)}, k={b64(_bytes_da_publica(chave.public_key()))}"


# ===== Criptografia (RFC 8291) =====


def criptografar(mensagem, p256dh, auth, *, salt=None, chave_servidor=None):
    """
    Embaralha a mensagem para um aparelho. `salt` e `chave_servidor` só são passados
    nos testes (para comparar com o exemplo da RFC); no uso real são sempre novos.
    """
    publica_aparelho = de_b64(p256dh)
    segredo_auth = de_b64(auth)
    salt = salt or os.urandom(16)
    chave_servidor = chave_servidor or ec.generate_private_key(ec.SECP256R1())  # descartável
    publica_servidor = _bytes_da_publica(chave_servidor.public_key())

    # 1. ECDH: as duas pontas chegam ao mesmo segredo sem nunca enviá-lo.
    aparelho = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), publica_aparelho)
    segredo_ecdh = chave_servidor.exchange(ec.ECDH(), aparelho)

    # 2. HKDF (HMAC-SHA256 em dois passos): mistura o segredo com o "auth" do aparelho...
    prk_chave = _hmac(segredo_auth, segredo_ecdh)
    ikm = _hmac(prk_chave, b"WebPush: info\x00" + publica_aparelho + publica_servidor + b"\x01")
    # ...e com o salt, tirando dali a chave do AES (16 bytes) e o nonce (12 bytes).
    prk = _hmac(salt, ikm)
    chave_aes = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]

    # 3. AES-GCM. O byte 0x02 marca "último (e único) registro".
    cifrado = AESGCM(chave_aes).encrypt(nonce, mensagem + b"\x02", None)

    # Cabeçalho: salt | tamanho do registro | tamanho da chave | chave pública descartável.
    return salt + struct.pack("!IB", TAMANHO_REGISTRO, len(publica_servidor)) + publica_servidor + cifrado


# ===== Envio =====


def enviar(assinatura, titulo, texto, url="/"):
    """Manda um aviso para um aparelho; devolve a resposta do serviço de push."""
    mensagem = json.dumps({"title": titulo, "body": texto[:500], "url": url}).encode()
    return requests.post(
        assinatura.endpoint,
        data=criptografar(mensagem, assinatura.p256dh, assinatura.auth),
        headers={
            "Authorization": cabecalho_vapid(assinatura.endpoint),
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": str(VALIDADE_AVISO),
            "Urgency": "high",
        },
        timeout=10,
    )


def enviar_para_todos(titulo, texto, url="/"):
    """Manda para todos os aparelhos assinados; devolve quantos aceitaram."""
    aceitos = 0
    for assinatura in AssinaturaPush.objects.all():
        try:
            resposta = enviar(assinatura, titulo, texto, url)
        except requests.RequestException:
            # Sem internet ou serviço fora do ar: mantém a assinatura e tenta no próximo aviso.
            log.warning("Push não enviado para %s (sem conexão)", assinatura, exc_info=True)
            continue
        if resposta.status_code in ASSINATURA_MORTA:
            log.info("Assinatura de push apagada (%s): %s", resposta.status_code, assinatura)
            assinatura.delete()
        elif resposta.status_code >= 400:
            log.warning("Push recusado para %s: %s %s", assinatura, resposta.status_code, resposta.text[:300])
        else:
            aceitos += 1
    return aceitos
