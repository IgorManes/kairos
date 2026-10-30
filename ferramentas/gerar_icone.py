r"""
Gera static/img/kairos.ico a partir de static/img/kairos.svg, sem instalar nada:
o Edge desenha o SVG em PNG (fundo transparente) em vários tamanhos e este script
junta os PNGs num .ico (o formato .ico aceita PNGs dentro dele).

    venv\Scripts\python ferramentas\gerar_icone.py
"""

import struct
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from tarefas.pdf import caminho_edge  # noqa: E402

TAMANHOS = [16, 24, 32, 48, 64, 128, 256]


def png_do_svg(edge, svg, tamanho, pasta):
    html = pasta / f"icone-{tamanho}.html"
    html.write_text(
        f'<html><body style="margin:0;background:transparent">'
        f'<img src="{svg.as_uri()}" width="{tamanho}" height="{tamanho}" style="display:block"></body></html>',
        encoding="utf-8",
    )
    png = pasta / f"icone-{tamanho}.png"
    subprocess.run([edge, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--user-data-dir={pasta / 'perfil'}", "--default-background-color=00000000",
                    f"--window-size={tamanho},{tamanho}", f"--screenshot={png}", html.as_uri()],
                   capture_output=True, timeout=60, check=False)
    return png.read_bytes()


def montar_ico(pngs):
    """Cabeçalho ICONDIR + uma entrada ICONDIRENTRY por imagem + os PNGs em sequência."""
    cabecalho = struct.pack("<HHH", 0, 1, len(pngs))  # reservado, tipo 1 = ícone, quantidade
    entradas, dados = b"", b""
    deslocamento = 6 + 16 * len(pngs)
    for tamanho, png in pngs:
        lado = 0 if tamanho >= 256 else tamanho  # 0 significa 256
        entradas += struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(png), deslocamento)
        dados += png
        deslocamento += len(png)
    return cabecalho + entradas + dados


def main():
    svg = RAIZ / "static" / "img" / "kairos.svg"
    with tempfile.TemporaryDirectory() as pasta:
        pngs = [(t, png_do_svg(caminho_edge(), svg, t, Path(pasta))) for t in TAMANHOS]
    destino = RAIZ / "static" / "img" / "kairos.ico"
    destino.write_bytes(montar_ico(pngs))
    (RAIZ / "static" / "img" / "kairos-256.png").write_bytes(dict(pngs)[256])
    print(f"Gerado {destino} ({len(pngs)} tamanhos)")


if __name__ == "__main__":
    main()
