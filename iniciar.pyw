"""
Abre o Kairos como aplicativo (sem janela de terminal: é para isso o .pyw).

Ordem:
  1. Instância única: se o Kairos já está aberto, só traz a janela para a frente.
  2. Erros vão para %LOCALAPPDATA%\\Kairos\\kairos.log (e erro fatal vira caixa de mensagem).
  3. Modo produção (DEBUG=False), independente do .env.
  4. Migrations pendentes: backup ANTES, migrate depois.
  5. Backup diário, fotos dos relatórios e CSS (gera se ainda não existe).
  6. Servidor waitress numa thread; espera responder.
  7. Janela própria (pywebview, motor do Edge). Fechar a janela encerra o servidor.
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
log = logging.getLogger("kairos")


# ===== 1. Instância única =====

def ja_esta_aberto():
    """Trava com nome do Windows (mutex): se já existe, outro Kairos está rodando."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, NOME_TRAVA)
    return kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def janelas_do_kairos(so_deste_processo=False):
    """Janelas visíveis cujo título termina em "Kairos" (o título acompanha a página: "Hoje · Kairos")."""
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    meu_pid, achadas = os.getpid(), []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visitar(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            texto = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, texto, 256)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if texto.value.endswith(TITULO) and (not so_deste_processo or pid.value == meu_pid):
                achadas.append(hwnd)
        return True

    user32.EnumWindows(visitar, 0)
    return achadas


def trazer_para_frente():
    user32 = ctypes.windll.user32
    for janela in janelas_do_kairos():
        user32.ShowWindow(janela, 9)  # SW_RESTORE (caso esteja minimizada)
        user32.SetForegroundWindow(janela)
        return


# ===== 2. Registro de erros (sem terminal, eles sumiriam) =====

def configurar_log(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = logging.handlers.RotatingFileHandler(pasta / "kairos.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
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


# ===== 7. Janela =====

def colocar_icone(icone):
    """
    A janela do pywebview herda o ícone do Python; troca pelo do Kairos usando a API
    do Windows (WM_SETICON), que funciona de qualquer thread (o WinForms não deixa).
    """
    user32 = ctypes.windll.user32
    user32.LoadImageW.restype = ctypes.c_void_p
    user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    for _ in range(20):  # a janela pode levar um instante para aparecer
        janelas = janelas_do_kairos(so_deste_processo=True)
        if janelas:
            break
        time.sleep(0.1)
    for janela in janelas:
        for tipo, lado in ((1, 32), (0, 16)):  # ICON_BIG, ICON_SMALL
            imagem = user32.LoadImageW(None, str(icone), 1, lado, lado, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if imagem:
                user32.SendMessageW(janela, 0x80, tipo, imagem)  # WM_SETICON


def abrir_janela(endereco, servidor, settings):
    import webview

    icone = RAIZ / "static" / "img" / "kairos.ico"
    janela = webview.create_window(TITULO, endereco, width=1320, height=860, min_size=(380, 600),
                                   background_color="#07080f")
    janela.events.shown += lambda: colocar_icone(icone)
    janela.events.closed += servidor.close
    # private_mode=False + storage_path: guarda cookies (login de 30 dias) e o tema entre aberturas.
    webview.start(private_mode=False, storage_path=str(settings.DATA_DIR / "janela"))


def main():
    if ja_esta_aberto():
        trazer_para_frente()
        return

    # O Windows agrupa a janela na barra de tarefas como "Kairos", não como "Python".
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Kairos.App")

    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    pasta_dados = Path(os.environ.get("KAIROS_DATA_DIR") or Path(os.environ["LOCALAPPDATA"]) / "Kairos")
    configurar_log(pasta_dados)
    try:
        settings = preparar()
        servidor, endereco = iniciar_servidor(settings)
        log.info("Kairos aberto em %s", endereco)
        abrir_janela(endereco, servidor, settings)
        log.info("Kairos fechado")
    except Exception as erro:
        log.exception("Falha ao abrir o Kairos")
        mostrar_erro(f"{erro}\n\nDetalhes em {pasta_dados / 'kairos.log'}")


if __name__ == "__main__":
    main()
