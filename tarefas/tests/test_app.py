"""Backup do banco e arquivos estáticos no modo produção."""

import sqlite3
import tempfile
from contextlib import closing
from datetime import timedelta
from pathlib import Path

from django.test import TestCase, override_settings
from django.utils import timezone

from tarefas import backup


class BackupTests(TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.banco = self.pasta / "kairos.sqlite3"
        # Um banco de verdade, pequeno. closing(): "with sqlite3.connect()" sozinho NÃO fecha
        # a conexão, e o Windows não deixa apagar arquivo aberto.
        with closing(sqlite3.connect(self.banco)) as con:
            con.execute("create table t (x)")
            con.execute("insert into t values (42)")
            con.commit()
        ajuste = override_settings(
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": self.banco}},
            BACKUP_DIR=self.pasta / "backups", BACKUPS_MANTIDOS=3,
        )
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    def test_backup_e_uma_copia_valida_do_banco(self):
        arquivo = backup.fazer_backup("teste")
        with closing(sqlite3.connect(arquivo)) as con:
            self.assertEqual(con.execute("select x from t").fetchone(), (42,))

    def test_mantem_so_os_mais_recentes(self):
        agora = timezone.now()
        for i in range(5):
            backup.fazer_backup("teste", agora + timedelta(minutes=i))
        restantes = backup.listar()
        self.assertEqual(len(restantes), 3)
        self.assertIn(f"{timezone.localtime(agora + timedelta(minutes=4)):%H%M}", restantes[0].name)  # o mais novo fica

    def test_backup_diario_so_uma_vez_por_dia(self):
        self.assertIsNotNone(backup.backup_diario())
        self.assertIsNone(backup.backup_diario())
        self.assertIsNotNone(backup.backup_diario(timezone.now() + timedelta(days=1)))


class EstaticosEmProducaoTests(TestCase):
    @override_settings(DEBUG=False)
    def test_css_fonte_e_icone_sao_servidos_sem_debug(self):
        for caminho in ("/static/js/kairos.js", "/static/fonts/InterVariable.woff2", "/static/img/kairos.ico"):
            with self.subTest(caminho=caminho):
                self.assertEqual(self.client.get(caminho).status_code, 200)
