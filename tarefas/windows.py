"""
Integração com o Windows, só no usuário atual (HKEY_CURRENT_USER, sem administrador):

- registrar_app(): nome e ícone do Kairos nas notificações (AppUserModelId).
- Iniciar com o Windows: valor "Kairos" em ...\\CurrentVersion\\Run (aparece no
  Gerenciador de Tarefas → Aplicativos de inicialização).
"""

import sys
from pathlib import Path

from django.conf import settings

ID_APP = "Kairos"  # AppUserModelID: nome do remetente nas notificações
CHAVE_APP = rf"Software\Classes\AppUserModelId\{ID_APP}"
CHAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOME_RUN = "Kairos"


def _winreg():
    import winreg  # só existe no Windows; importado aqui para os testes poderem simular

    return winreg


def registrar_app():
    winreg = _winreg()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CHAVE_APP) as chave:
        winreg.SetValueEx(chave, "DisplayName", 0, winreg.REG_SZ, "Kairos")
        winreg.SetValueEx(chave, "IconUri", 0, winreg.REG_SZ, str(settings.BASE_DIR / "static" / "img" / "kairos-256.png"))


def comando_inicializacao():
    """pythonw.exe (sem terminal) do venv + iniciar.pyw, abrindo direto na bandeja."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{settings.BASE_DIR / "iniciar.pyw"}" --bandeja'


def inicializacao_ativa():
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_RUN) as chave:
            winreg.QueryValueEx(chave, NOME_RUN)
            return True
    except FileNotFoundError:
        return False


def definir_inicializacao(ativar):
    winreg = _winreg()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_RUN, 0, winreg.KEY_SET_VALUE) as chave:
        if ativar:
            winreg.SetValueEx(chave, NOME_RUN, 0, winreg.REG_SZ, comando_inicializacao())
        else:
            try:
                winreg.DeleteValue(chave, NOME_RUN)
            except FileNotFoundError:
                pass
