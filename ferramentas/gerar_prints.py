r"""
Gera os prints do README (docs/img/) a partir de DADOS DE DEMONSTRAÇÃO, num banco
temporário: nunca usa o banco nem a conta Google reais.

    venv\Scripts\python ferramentas\gerar_prints.py

Precisa do Edge (o mesmo usado nos PDFs) e do CSS gerado (manage.py tailwind build).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TEMP = Path(tempfile.mkdtemp(prefix="kairos-prints-"))
SAIDA = RAIZ / "docs" / "img"

# Antes do Django carregar: pasta de dados temporária, empresa fictícia.
os.environ.update(
    {
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "KAIROS_DATA_DIR": str(TEMP / "dados"),
        "KAIROS_DB_NAME": "dev.sqlite3",  # o dados_exemplo só roda num banco com esse nome
        "GOOGLE_AGENDAS_EXTRAS": "Acme=agenda@acme.example",
        "DJANGO_DEBUG": "True",
    }
)
sys.path.insert(0, str(RAIZ))

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402

from tarefas.google.credenciais import ESCOPOS  # noqa: E402
from tarefas.models import EstadoSync, Origem, Tarefa  # noqa: E402
from tarefas.pdf import caminho_edge  # noqa: E402

TELAS = [  # (arquivo, caminho, tema, largura, altura)
    ("hoje", "/", "dark", 1440, 960),
    ("hoje-claro", "/", "light", 1440, 960),
    ("tarefas", "/tarefas/?categoria=trabalho&status=todas", "dark", 1440, 900),
    ("quadro", "/quadro/", "dark", 1440, 900),
    ("relatorios", "/relatorios/", "dark", 1440, 620),
    ("configuracoes", "/configuracoes/", "dark", 1440, 900),
]


def preparar_dados():
    assert str(settings.DATA_DIR).startswith(str(TEMP)), "Segurança: não é a pasta temporária!"
    call_command("migrate", verbosity=0)
    call_command("dados_exemplo")
    # Uma reunião "da empresa" para mostrar a etiqueta, e o sync como se estivesse em dia.
    reuniao = Tarefa.objects.get(titulo="Revisão da sprint")
    reuniao.origem, reuniao.agenda_id, reuniao.id_externo = Origem.GOOGLE_AGENDA, "agenda@acme.example", "demo-1"
    reuniao.save()
    # token falso (só a lista de permissões), para a tela mostrar "Sincronizado"
    settings.GOOGLE_TOKEN.write_text(json.dumps({"scopes": ESCOPOS}), encoding="utf-8")
    EstadoSync.objects.create(fonte="agenda:primary", ultimo_sync_em=timezone.now(), ultimo_completo_em=timezone.now())
    return get_user_model().objects.create_user("Igor", password="demo-nao-usada-123")


def renderizar(usuario, site):
    """Salva o HTML de cada tela (como o usuário logado vê) dentro do mini site."""
    settings.ALLOWED_HOSTS.append("testserver")
    cliente = Client()
    cliente.force_login(usuario)
    for nome, caminho, tema, *_ in TELAS:
        html = cliente.get(caminho).content.decode()
        html = html.replace('data-theme="dark"', f'data-theme="{tema}"', 1)
        html = html.replace('hx-trigger="load delay:3s, every 60s"', 'hx-trigger="never"')  # sem sync no print
        html = html.replace("localStorage.getItem", "(()=>null)")  # ignora o tema salvo no navegador
        (site / f"{nome}.html").write_text(html, encoding="utf-8")
    # Celular: a tela Hoje dentro de um quadro de 390 px (o Edge sem janela não encolhe tanto)
    (site / "celular.html").write_text(
        '<body style="margin:0;background:#04050a"><iframe src="hoje.html" width="390" height="844" '
        'style="border:0;display:block"></iframe></body>',
        encoding="utf-8",
    )


def fotografar(site, porta):
    edge, perfil = caminho_edge(), TEMP / "perfil"
    alvos = [(n, w, h) for n, _, _, w, h in TELAS] + [("celular", 390, 844)]
    for nome, largura, altura in alvos:
        subprocess.run(
            [
                edge,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--user-data-dir={perfil}",
                f"--window-size={largura},{altura}",
                "--virtual-time-budget=3000",
                f"--screenshot={SAIDA / (nome + '.png')}",
                f"http://127.0.0.1:{porta}/{nome}.html",
            ],
            capture_output=True,
            timeout=90,
            check=False,
        )
        print("print:", nome)


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    site = TEMP / "site"
    shutil.copytree(RAIZ / "static", site / "static")  # mesmo endereço do HTML: a fonte carrega
    usuario = preparar_dados()
    renderizar(usuario, site)
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(site)))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        fotografar(site, servidor.server_address[1])
    finally:
        servidor.shutdown()
        from django.db import connections

        connections.close_all()
        shutil.rmtree(TEMP, ignore_errors=True)
    print(f"Prints em {SAIDA}")


if __name__ == "__main__":
    main()
