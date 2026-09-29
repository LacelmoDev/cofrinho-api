import json
import logging
import urllib.error
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


def enviar_brevo(destino, nome, assunto, html):
    """Envia um email transacional pela API da Brevo. Devolve (ok, detalhe)."""
    if not settings.BREVO_API_KEY:
        return False, 'BREVO_API_KEY não está definida.'
    if not settings.BREVO_SENDER_EMAIL:
        return False, 'BREVO_SENDER_EMAIL não está definido.'
    corpo = {
        'sender': {'name': settings.BREVO_SENDER_NAME, 'email': settings.BREVO_SENDER_EMAIL},
        'to': [{'email': destino, 'name': nome}],
        'subject': assunto,
        'htmlContent': html,
    }
    pedido = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email',
        data=json.dumps(corpo).encode(),
        headers={'api-key': settings.BREVO_API_KEY, 'content-type': 'application/json', 'accept': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(pedido, timeout=10) as r:
            return True, f'HTTP {r.status}'
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode('utf-8', 'replace')[:500]  # a Brevo explica o motivo no corpo da resposta
        log.error('A Brevo recusou o envio (HTTP %s): %s', e.code, detalhe)
        return False, f'HTTP {e.code}: {detalhe}'
    except Exception as e:  # noqa: BLE001 — o envio nunca deve rebentar o pedido
        log.exception('Falha ao contactar a Brevo')
        return False, str(e)


def enviar_codigo(utilizador, finalidade, codigo):
    """Envia o código por email. Devolve True se foi enviado.
    Sem BREVO_API_KEY/BREVO_SENDER_EMAIL (desenvolvimento) o código é escrito na consola."""
    if not settings.BREVO_API_KEY or not settings.BREVO_SENDER_EMAIL:
        log.warning('[DEV] Código %s para %s: %s', finalidade, utilizador.email, codigo)
        return False

    html = (
        f'<p>Olá {utilizador.nome_completo.split(" ")[0]},</p>'
        f'<p>{TEXTOS[finalidade]}:</p>'
        f'<p style="font-size:28px;font-weight:bold;letter-spacing:6px">{codigo}</p>'
        '<p>O código expira em 15 minutos. Se não foste tu, ignora esta mensagem.</p>'
    )
    ok, _ = enviar_brevo(utilizador.email, utilizador.nome_completo, ASSUNTOS[finalidade], html)
    return ok
