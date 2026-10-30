"""
Sincroniza o Google (somente leitura) com o Kairos.

    python manage.py sincronizar --conectar   # 1ª vez: abre o navegador para o login
    python manage.py sincronizar              # sync normal (incremental quando possível)
    python manage.py sincronizar --completo   # força sync completo
"""

from django.core.management.base import BaseCommand, CommandError

from tarefas.google.servico import sincronizar_tudo


class Command(BaseCommand):
    help = "Sincroniza Google Agenda → Kairos (somente leitura)."

    def add_arguments(self, parser):
        parser.add_argument("--conectar", action="store_true", help="Faz o login no Google (abre o navegador).")
        parser.add_argument("--completo", action="store_true", help="Força sincronização completa.")

    def handle(self, *args, **opcoes):
        r = sincronizar_tudo(motivo="botao", forcar_completo=opcoes["completo"], interativo=opcoes["conectar"])
        if r.situacao == "desconectado":
            raise CommandError(r.erro)
        if r.situacao == "ocupado":
            raise CommandError("Já existe uma sincronização em andamento.")
        for nome, d in r.detalhes:
            tipo = "completo" if d["completo"] else "incremental"
            self.stdout.write(self.style.SUCCESS(
                f"{nome} ({tipo}): {d['criadas']} novas, {d['atualizadas']} atualizadas, {d['canceladas']} canceladas"
            ))
        if r.situacao == "erro":
            raise CommandError(f"Com erro: {r.erro} (detalhes salvos para a tela de Configurações).")
