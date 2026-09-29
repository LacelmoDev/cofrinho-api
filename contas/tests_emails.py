import io
import urllib.error
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from contas.emails import enviar_brevo


class RespostaFalsa:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@override_settings(BREVO_API_KEY='xkeysib-teste', BREVO_SENDER_EMAIL='remetente@exemplo.com')
class BrevoTests(SimpleTestCase):
    def test_sucesso(self):
        with mock.patch('contas.emails.urllib.request.urlopen', return_value=RespostaFalsa()):
            ok, detalhe = enviar_brevo('a@b.com', 'Ana', 'Assunto', '<p>x</p>')
        self.assertTrue(ok)
        self.assertIn('201', detalhe)

    def test_erro_mostra_o_motivo_da_brevo(self):
        erro = urllib.error.HTTPError('u', 401, 'Unauthorized', {}, io.BytesIO(b'{"message":"Key not found"}'))
        with mock.patch('contas.emails.urllib.request.urlopen', side_effect=erro):
            ok, detalhe = enviar_brevo('a@b.com', 'Ana', 'Assunto', '<p>x</p>')
        self.assertFalse(ok)
        self.assertIn('401', detalhe)
        self.assertIn('Key not found', detalhe)

    def test_comando_falha_com_mensagem_clara(self):
        erro = urllib.error.HTTPError('u', 400, 'Bad', {}, io.BytesIO(b'{"message":"sender not valid"}'))
        with mock.patch('contas.emails.urllib.request.urlopen', side_effect=erro):
            with self.assertRaises(CommandError) as c:
                call_command('testar_email', 'a@b.com')
        self.assertIn('sender not valid', str(c.exception))

    @override_settings(BREVO_API_KEY='')
    def test_sem_chave(self):
        ok, detalhe = enviar_brevo('a@b.com', 'Ana', 'x', 'y')
        self.assertFalse(ok)
        self.assertIn('BREVO_API_KEY', detalhe)
