from django.apps import AppConfig
from django.db.backends.signals import connection_created


def registrar_funcoes_sqlite(sender, connection, **kwargs):
    """Ensina ao SQLite a função sem_acento(), usada na busca."""
    if connection.vendor == "sqlite":
        from .texto import sem_acento

        connection.connection.create_function("sem_acento", 1, sem_acento, deterministic=True)


class TarefasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tarefas"

    def ready(self):
        # Toda conexão nova com o banco recebe a função.
        connection_created.connect(registrar_funcoes_sqlite)
