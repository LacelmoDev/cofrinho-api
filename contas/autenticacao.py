from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import Sessao, hash_chave


class BearerAuthentication(BaseAuthentication):
    """Cabeçalho:  Authorization: Bearer <chave>"""

    def authenticate(self, request):
        partes = get_authorization_header(request).split()
        if not partes or partes[0].lower() != b'bearer':
            return None
        if len(partes) != 2:
            raise AuthenticationFailed('Cabeçalho de autorização inválido.')
        try:
            chave = partes[1].decode()
        except UnicodeError:
            raise AuthenticationFailed('Cabeçalho de autorização inválido.')

        sessao = Sessao.objects.select_related('utilizador').filter(chave_hash=hash_chave(chave)).first()
        agora = timezone.now()
        limite = timedelta(days=settings.SESSAO_DIAS_INATIVIDADE)
        if not sessao or not sessao.utilizador.is_active or agora - sessao.ultimo_uso > limite:
            raise AuthenticationFailed('Sessão inválida ou expirada. Entra outra vez.')

        if agora - sessao.ultimo_uso > timedelta(hours=1):
            sessao.ultimo_uso = agora
            sessao.save(update_fields=['ultimo_uso'])
        return (sessao.utilizador, sessao)

    def authenticate_header(self, request):
        return 'Bearer'
