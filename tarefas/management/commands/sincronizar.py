"""
Sincroniza o Google (somente leitura) com o Kairos.

    python manage.py sincronizar --conectar   # 1ª vez: abre o navegador para o login
    python manage.py sincronizar              # sync normal (incremental quando possível)
    python manage.py sincronizar --completo   # força sync completo
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from tarefas.google import agenda as sync_agenda
from tarefas.google.credenciais import SemConexaoGoogle, obter_credenciais, servico_agenda


class Command(BaseCommand):
    help = "Sincroniza Google Agenda → Kairos (somente leitura)."

    def add_arguments(self, parser):
        parser.add_argument("--conectar", action="store_true", help="Faz o login no Google (abre o navegador).")
        parser.add_argument("--completo", action="store_true", help="Força sincronização completa.")

    def handle(self, *args, **opcoes):
        try:
            credenciais = obter_credenciais(interativo=opcoes["conectar"])
        except SemConexaoGoogle as erro:
            raise CommandError(str(erro)) from None

        servico = servico_agenda(credenciais)
        falhas = 0
        for agenda in settings.GOOGLE_AGENDAS:
            nome = agenda["nome"] or "Agenda principal"
            try:
                r = sync_agenda.sincronizar_agenda(servico, agenda, forcar_completo=opcoes["completo"])
            except Exception as erro:  # uma agenda com erro não impede as outras
                falhas += 1
                sync_agenda.registrar_erro(agenda, erro)
                self.stderr.write(self.style.ERROR(f"{nome}: erro: {erro}"))
                continue
            tipo = "completo" if r["completo"] else "incremental"
            self.stdout.write(self.style.SUCCESS(
                f"{nome} ({tipo}): {r['criadas']} novas, {r['atualizadas']} atualizadas, {r['canceladas']} canceladas"
            ))
        if falhas:
            raise CommandError(f"{falhas} agenda(s) com erro; detalhes salvos para a tela de Configurações.")
