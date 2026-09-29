import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import CodigoEmail

VALIDADE_MIN = 15
MAX_TENTATIVAS = 5
ESPERA_REENVIO_SEG = 60


class EsperaNecessaria(Exception):
    def __init__(self, segundos):
        self.segundos = segundos


def _hash(utilizador_id, finalidade, codigo):
    msg = f'{utilizador_id}:{finalidade}:{codigo}'.encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, 'sha256').hexdigest()


def criar_codigo(utilizador, finalidade):
    agora = timezone.now()
    ultimo = CodigoEmail.objects.filter(utilizador=utilizador, finalidade=finalidade).order_by('-criado_em').first()
    if ultimo:
        passou = (agora - ultimo.criado_em).total_seconds()
        if passou < ESPERA_REENVIO_SEG:
            raise EsperaNecessaria(int(ESPERA_REENVIO_SEG - passou) + 1)
    CodigoEmail.objects.filter(utilizador=utilizador, finalidade=finalidade).delete()
    codigo = f'{secrets.randbelow(10**6):06d}'
    CodigoEmail.objects.create(
        utilizador=utilizador,
        finalidade=finalidade,
        codigo_hash=_hash(utilizador.id, finalidade, codigo),
        expira_em=agora + timedelta(minutes=VALIDADE_MIN),
    )
    return codigo


def validar_codigo(utilizador, finalidade, codigo):
    c = CodigoEmail.objects.filter(utilizador=utilizador, finalidade=finalidade).order_by('-criado_em').first()
    if not c or c.expira_em < timezone.now() or c.tentativas >= MAX_TENTATIVAS:
        return False
    c.tentativas += 1
    c.save(update_fields=['tentativas'])
    certo = hmac.compare_digest(c.codigo_hash, _hash(utilizador.id, finalidade, str(codigo).strip()))
    if certo:
        c.delete()
    return certo
