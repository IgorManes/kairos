"""
HTML → PDF usando o Microsoft Edge (já vem no Windows) em modo sem janela.
Nada a instalar e o PDF sai com o mesmo motor que desenha o app.
"""

import os
import subprocess
import tempfile
from pathlib import Path

CAMINHOS_EDGE = [
    os.environ.get("KAIROS_EDGE", ""),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


class ErroPDF(Exception):
    pass


def caminho_edge():
    for caminho in CAMINHOS_EDGE:
        if caminho and Path(caminho).exists():
            return caminho
    raise ErroPDF("Microsoft Edge não encontrado. Defina KAIROS_EDGE no .env com o caminho do msedge.exe.")


def html_para_pdf(html, tempo_limite=60):
    """Devolve os bytes do PDF."""
    edge = caminho_edge()
    with tempfile.TemporaryDirectory(prefix="kairos-pdf-") as pasta:
        pasta = Path(pasta)
        entrada, saida = pasta / "relatorio.html", pasta / "relatorio.pdf"
        entrada.write_text(html, encoding="utf-8")
        comando = [
            edge,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",  # sem data/URL nas margens
            f"--user-data-dir={pasta / 'perfil'}",  # não disputa o perfil do Edge aberto
            f"--print-to-pdf={saida}",
            entrada.as_uri(),
        ]
        try:
            subprocess.run(
                comando,
                capture_output=True,
                timeout=tempo_limite,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as erro:
            raise ErroPDF("O Edge demorou demais para gerar o PDF.") from erro
        if not saida.exists() or saida.stat().st_size == 0:
            raise ErroPDF("O Edge não gerou o PDF.")
        return saida.read_bytes()
