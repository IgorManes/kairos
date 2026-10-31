r"""
Gera static/img/kairos.ico a partir de static/img/kairos.svg, sem instalar nada:
o Edge desenha o SVG em PNG (fundo transparente) em vários tamanhos e este script
junta os PNGs num .ico (o formato .ico aceita PNGs dentro dele).
Também gera os ícones do app instalado (iPhone e Edge): kairos-app-180/192/512.png.

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
TAMANHOS_APP = [180, 192, 512]  # 180 = iPhone (apple-touch-icon); 192 e 512 = manifesto
FUNDO_APP = "#07080f"  # mesmo fundo do tema escuro


def png_do_svg(edge, svg, tamanho, pasta, fundo=None, logo=1.0):
    """PNG quadrado do SVG. fundo=None deixa transparente; logo = fração do lado ocupada pelo logo."""
    nome = f"icone-{tamanho}-{'app' if fundo else 'ico'}"
    lado_logo = round(tamanho * logo)
    html = pasta / f"{nome}.html"
    html.write_text(
        f'<html><body style="margin:0;background:{fundo or "transparent"};width:{tamanho}px;height:{tamanho}px;'
        f'display:grid;place-items:center">'
        f'<img src="{svg.as_uri()}" width="{lado_logo}" height="{lado_logo}" style="display:block"></body></html>',
        encoding="utf-8",
    )
    png = pasta / f"{nome}.png"
    subprocess.run(
        [
            edge,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--user-data-dir={pasta / 'perfil'}",
            "--default-background-color=00000000",  # transparente onde a página não pinta
            f"--window-size={tamanho},{tamanho}",
            f"--screenshot={png}",
            html.as_uri(),
        ],
        capture_output=True,
        timeout=60,
        check=False,
    )
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
        # Ícones do app no celular/Edge: fundo sólido (o iPhone pinta transparência de preto e
        # arredonda os cantos sozinho) e logo com margem (Android corta em círculo: zona segura de 80%).
        apps = {t: png_do_svg(caminho_edge(), svg, t, Path(pasta), fundo=FUNDO_APP, logo=0.8) for t in TAMANHOS_APP}
    destino = RAIZ / "static" / "img" / "kairos.ico"
    destino.write_bytes(montar_ico(pngs))
    (RAIZ / "static" / "img" / "kairos-256.png").write_bytes(dict(pngs)[256])
    for tamanho, png in apps.items():
        (RAIZ / "static" / "img" / f"kairos-app-{tamanho}.png").write_bytes(png)
    print(f"Gerado {destino} ({len(pngs)} tamanhos) e ícones do app {list(apps)}")


if __name__ == "__main__":
    main()
