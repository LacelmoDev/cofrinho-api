from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from contas.emails import enviar_brevo


class Command(BaseCommand):
    help = 'Envia um email de teste pela Brevo e mostra o resultado (ou o motivo do erro).'

    def add_arguments(self, parser):
        parser.add_argument('destino', help='Email que vai receber o teste')

    def handle(self, *args, destino, **opcoes):
        self.stdout.write(f'Chave da API definida: {"sim" if settings.BREVO_API_KEY else "NÃO"}')
        self.stdout.write(f'Remetente: {settings.BREVO_SENDER_EMAIL or "(NÃO definido)"}')
        ok, detalhe = enviar_brevo(destino, 'Teste', 'Teste — Cofrinho AO',
                                   '<p>Se recebeste isto, a Brevo está bem configurada.</p>')
        if not ok:
            raise CommandError(f'Falhou: {detalhe}')
        self.stdout.write(self.style.SUCCESS(f'Enviado para {destino} ({detalhe}). Verifica a caixa de entrada e o spam.'))
