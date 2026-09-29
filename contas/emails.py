import json
import logging
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)

ASSUNTOS = {
    'verificacao': 'O teu código de verificação — Cofrinho AO',
    'reset': 'Recuperar a senha — Cofrinho AO',
}
TEXTOS = {
    'verificacao': 'Usa este código para confirmar o teu email',
    'reset': 'Usa este código para definir uma nova senha',
}


def enviar_codigo(utilizador, finalidade, codigo):
    """Envia o código por email (Brevo). Devolve True se foi enviado.
    Sem BREVO_API_KEY (desenvolvimento) o código é escrito na consola."""
    if not settings.BREVO_API_KEY or not settings.BREVO_SENDER_EMAIL:
        log.warning('[DEV] Código %s para %s: %s', finalidade, utilizador.email, codigo)
        return False

    html = (
        f'<p>Olá {utilizador.nome_completo.split(" ")[0]},</p>'
        f'<p>{TEXTOS[finalidade]}:</p>'
        f'<p style="font-size:28px;font-weight:bold;letter-spacing:6px">{codigo}</p>'
        '<p>O código expira em 15 minutos. Se não foste tu, ignora esta mensagem.</p>'
    )
    corpo = {
        'sender': {'name': settings.BREVO_SENDER_NAME, 'email': settings.BREVO_SENDER_EMAIL},
        'to': [{'email': utilizador.email, 'name': utilizador.nome_completo}],
        'subject': ASSUNTOS[finalidade],
        'htmlContent': html,
    }
    pedido = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email',
        data=json.dumps(corpo).encode(),
        headers={'api-key': settings.BREVO_API_KEY, 'content-type': 'application/json', 'accept': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(pedido, timeout=10):
            return True
    except Exception:  # noqa: BLE001 — o envio nunca deve rebentar o pedido
        log.exception('Falha ao enviar email via Brevo')
        return False
