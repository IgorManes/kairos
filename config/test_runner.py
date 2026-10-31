"""Executor dos testes: arquivos que o Kairos cria sozinho vão para uma pasta temporária."""

import tempfile
from pathlib import Path

from django.conf import settings
from django.test.runner import DiscoverRunner


class ExecutorKairos(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        # Sem isto, abrir a tela de Configurações num teste criaria a chave VAPID na pasta real.
        self._pasta = tempfile.TemporaryDirectory()
        settings.VAPID_ARQUIVO = Path(self._pasta.name) / "vapid.pem"

    def teardown_test_environment(self, **kwargs):
        self._pasta.cleanup()
        super().teardown_test_environment(**kwargs)
