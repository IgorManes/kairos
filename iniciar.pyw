"""
Abre o Kairos como aplicativo (sem janela de terminal: é para isso o .pyw).

    pythonw iniciar.pyw            # abre a janela
    pythonw iniciar.pyw --bandeja  # abre só na bandeja (usado ao iniciar com o Windows)

Ordem:
  1. Instância única: se o Kairos já está aberto, avisa o que está aberto para se mostrar.
  2. Erros vão para %LOCALAPPDATA%\\Kairos\\kairos.log (e erro fatal vira caixa de mensagem).
  3. Modo produção (DEBUG=False), independente do .env.
  4. Migrations pendentes: backup ANTES, migrate depois.
  5. Backup diário, fotos dos relatórios e CSS (gera se ainda não existe).
  6. Servidor waitress numa thread; espera responder.
  7. Janela (pywebview, motor do Edge) + ícone na bandeja. Fechar a janela só a esconde;
     "Sair" na bandeja encerra tudo.
  8. Relógio do app (a cada minuto, mesmo com a janela escondida): sync do Google,
     tarefas periódicas e notificações do Windows.
"""

import ctypes
import logging
import logging.handlers
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
os.chdir(RAIZ)
sys.path.insert(0, str(RAIZ))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DEBUG"] = "False"  # o app é sempre produção (vence o .env)

TITULO = "Kairos"
NOME_TRAVA = "Local\\Kairos.InstanciaUnica"
NOME_SINAL = "Local\\Kairos.Mostrar"
ICONE = RAIZ / "static" / "img" / "kairos.ico"
log = logging.getLogger("kairos")
kernel32 = ctypes.windll.kernel32
# Handles do Windows têm 64 bits; sem declarar, o ctypes os cortaria para 32.
for _nome in ("CreateMutexW", "CreateEventW", "OpenEventW"):
    getattr(kernel32, _nome).restype = ctypes.c_void_p
kernel32.SetEvent.argtypes = kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
kernel32.WaitForSingleObject.restype = ctypes.c_uint32


# ===== 1. Instância única =====


def ja_esta_aberto():
    """Trava com nome do Windows (mutex): se já existe, outro Kairos está rodando."""
    kernel32.CreateMutexW(None, False, NOME_TRAVA)
    return kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def pedir_para_mostrar():
    """Avisa o Kairos já aberto (talvez escondido na bandeja) para mostrar a janela."""
    sinal = kernel32.OpenEventW(0x0002, False, NOME_SINAL)  # EVENT_MODIFY_STATE
    if sinal:
        kernel32.SetEvent(sinal)
        kernel32.CloseHandle(sinal)


# ===== 2. Registro de erros (sem terminal, eles sumiriam) =====


def configurar_log(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = logging.handlers.RotatingFileHandler(
        pasta / "kairos.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    arquivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(arquivo)
    # Em .pyw, print() e erros não aparecem em lugar nenhum: manda tudo para o log.
    sys.stdout = sys.stderr = open(pasta / "kairos-saida.log", "a", encoding="utf-8", buffering=1)


def mostrar_erro(mensagem):
    ctypes.windll.user32.MessageBoxW(None, mensagem, "Kairos não conseguiu abrir", 0x10)


# ===== 3 a 5. Preparar o Django =====


def preparar():
    import django

    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    from tarefas.backup import fazer_backup
    from tarefas.periodico import rodar_periodicos
    from tarefas.windows import registrar_app

    executor = MigrationExecutor(connection)
    pendentes = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if pendentes:
        if Path(settings.DATABASES["default"]["NAME"]).exists():
            log.info("Backup antes de aplicar %d migration(s)", len(pendentes))
            fazer_backup("antes-de-migrar")
        call_command("migrate", interactive=False, verbosity=0)

    if not (RAIZ / "static" / "css" / "tailwind.css").exists():
        log.info("Gerando o CSS (primeira vez)")
        call_command("tailwind", "build")

    registrar_app()  # nome e ícone do Kairos nas notificações
    rodar_periodicos()  # backup diário e fotos semanais pendentes
    return settings


# ===== 6. Servidor =====


def iniciar_servidor(settings):
    from waitress import create_server

    from config.wsgi import application

    servidor = create_server(application, host=settings.KAIROS_HOST, port=settings.KAIROS_PORT, threads=8)
    threading.Thread(target=servidor.run, daemon=True, name="waitress").start()

    endereco = f"http://{settings.KAIROS_HOST}:{settings.KAIROS_PORT}/"
    for _ in range(50):  # até ~10 s
        try:
            urllib.request.urlopen(endereco + "entrar/", timeout=1)
            return servidor, endereco
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"O servidor não respondeu em {endereco}")


# ===== 7 e 8. Janela, bandeja e relógio =====


class App:
    def __init__(self, settings, servidor, endereco, na_bandeja):
        self.settings, self.servidor, self.endereco = settings, servidor, endereco
        self.na_bandeja = na_bandeja
        self.janela = None
        self.bandeja = None
        self.saindo = False
        self.avisou_bandeja = False
        self.url_do_aviso = "/"
        self.parar = threading.Event()

    # --- janela ---
    def abrir(self):
        import webview

        self.janela = webview.create_window(
            TITULO,
            self.endereco,
            width=1320,
            height=860,
            min_size=(380, 600),
            background_color="#07080f",
            hidden=self.na_bandeja,
        )
        self.janela.events.closing += self.ao_fechar
        self.janela.events.closed += self.ao_encerrar
        # private_mode=False + storage_path: guarda cookies (login de 30 dias) e o tema entre aberturas.
        webview.start(self.depois_de_abrir, private_mode=False, storage_path=str(self.settings.DATA_DIR / "janela"))

    def ao_fechar(self):
        """O ✕ esconde na bandeja (o sync e os avisos continuam). Só "Sair" fecha de verdade."""
        if self.saindo:
            return True
        self.janela.hide()
        if not self.avisou_bandeja:
            self.avisou_bandeja = True
            self.notificar(
                "O Kairos continua aberto", "Ele fica na bandeja, perto do relógio. Para fechar, use Sair.", "/"
            )
        return False

    def ao_encerrar(self):
        self.parar.set()
        self.servidor.close()

    def mostrar(self, url=None):
        self.janela.show()
        self.janela.restore()
        if url and url != "/":
            self.janela.load_url(self.endereco + url.lstrip("/"))
        self.na_ui(lambda: self.janela.native.Activate())  # traz para a frente

    def sair(self):
        self.saindo = True
        self.na_ui(lambda: setattr(self.bandeja, "Visible", False))
        self.janela.destroy()

    # --- tudo que mexe em WinForms roda na linha de execução da janela ---
    def na_ui(self, funcao):
        from System import Action

        if self.janela and self.janela.native:
            self.janela.native.BeginInvoke(Action(funcao))

    def depois_de_abrir(self):
        """Roda numa thread do pywebview depois que a janela existe."""
        for _ in range(100):
            if self.janela.native:
                break
            time.sleep(0.05)
        self.na_ui(self.criar_bandeja)
        threading.Thread(target=self.esperar_pedido_para_mostrar, daemon=True, name="sinal").start()
        threading.Thread(target=self.relogio, daemon=True, name="relogio").start()

    def criar_bandeja(self):
        import clr

        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")
        from System.Drawing import Font, FontStyle, Icon
        from System.Windows.Forms import ContextMenuStrip, NotifyIcon, ToolStripMenuItem, ToolStripSeparator

        icone = Icon(str(ICONE))
        self.janela.native.Icon = icone  # ícone da janela (aqui pode: estamos na thread da janela)

        menu = ContextMenuStrip()
        abrir = ToolStripMenuItem("Abrir Kairos")
        abrir.Font = Font(abrir.Font, FontStyle.Bold)
        abrir.Click += lambda *_: self.mostrar()
        sincronizar = ToolStripMenuItem("Sincronizar agora")
        sincronizar.Click += lambda *_: threading.Thread(target=self.sincronizar_agora, daemon=True).start()
        sair = ToolStripMenuItem("Sair")
        sair.Click += lambda *_: self.sair()
        for item in (abrir, sincronizar, ToolStripSeparator(), sair):
            menu.Items.Add(item)

        self.bandeja = NotifyIcon()
        self.bandeja.Icon = icone
        self.bandeja.Text = TITULO
        self.bandeja.ContextMenuStrip = menu
        self.bandeja.DoubleClick += lambda *_: self.mostrar()
        self.bandeja.BalloonTipClicked += lambda *_: self.mostrar(self.url_do_aviso)
        self.bandeja.Visible = True

    def notificar(self, titulo, texto, url="/"):
        from System.Windows.Forms import ToolTipIcon

        def mostrar_aviso():
            self.url_do_aviso = url  # o Windows só informa o clique no aviso mais recente
            self.bandeja.ShowBalloonTip(8000, titulo, texto, getattr(ToolTipIcon, "None"))

        if self.bandeja is not None:
            self.na_ui(mostrar_aviso)

    def esperar_pedido_para_mostrar(self):
        """Outra abertura do Kairos sinaliza este evento: mostra a janela."""
        sinal = kernel32.CreateEventW(None, False, False, NOME_SINAL)
        while not self.parar.is_set():
            if kernel32.WaitForSingleObject(sinal, 1000) == 0:  # WAIT_OBJECT_0
                self.mostrar()

    # --- relógio do app ---
    def relogio(self):
        from django.db import close_old_connections

        from tarefas.notificacoes import resumo_do_dia

        self.parar.wait(3)  # deixa a janela terminar de abrir
        close_old_connections()
        resumo = resumo_do_dia()
        if resumo:
            self.notificar(resumo.titulo, resumo.texto, resumo.url)
        while not self.parar.is_set():
            try:
                self.ciclo()
            except Exception:
                log.exception("Falha no relógio do app")
            self.parar.wait(60)

    def ciclo(self):
        from django.db import close_old_connections

        from tarefas.google.servico import sincronizar_tudo
        from tarefas.notificacoes import verificar
        from tarefas.periodico import rodar_periodicos

        close_old_connections()  # cada thread com conexões de banco em dia
        sincronizar_tudo(motivo="auto")
        rodar_periodicos()
        for aviso in verificar():
            self.notificar(aviso.titulo, aviso.texto, aviso.url)
            time.sleep(1)  # vários avisos em sequência: um de cada vez

    def sincronizar_agora(self):
        from django.db import close_old_connections

        from tarefas.google.servico import sincronizar_tudo

        close_old_connections()
        r = sincronizar_tudo(motivo="botao")
        textos = {
            "ok": "Tudo em dia" + (", com novidades" if r.mudou else ""),
            "ocupado": "Já estava sincronizando",
            "desconectado": "Conecte a conta Google nas Configurações",
            "erro": "Houve um erro (veja nas Configurações)",
        }
        self.notificar("Sincronização", textos.get(r.situacao, ""), "/configuracoes/" if r.situacao != "ok" else "/")


def main():
    if ja_esta_aberto():
        pedir_para_mostrar()
        return

    # O Windows agrupa a janela na barra de tarefas e as notificações como "Kairos", não como "Python".
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Kairos")

    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    pasta_dados = Path(os.environ.get("KAIROS_DATA_DIR") or Path(os.environ["LOCALAPPDATA"]) / "Kairos")
    configurar_log(pasta_dados)
    try:
        settings = preparar()
        servidor, endereco = iniciar_servidor(settings)
        log.info("Kairos aberto em %s%s", endereco, " (na bandeja)" if "--bandeja" in sys.argv else "")
        App(settings, servidor, endereco, na_bandeja="--bandeja" in sys.argv).abrir()
        log.info("Kairos fechado")
    except Exception as erro:
        log.exception("Falha ao abrir o Kairos")
        mostrar_erro(f"{erro}\n\nDetalhes em {pasta_dados / 'kairos.log'}")


if __name__ == "__main__":
    main()
