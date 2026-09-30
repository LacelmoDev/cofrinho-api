import hashlib
import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Utilizador(AbstractUser):
    email = models.EmailField(unique=True)
    nome_completo = models.CharField(max_length=120)
    telefone = models.CharField(max_length=30, blank=True)
    email_verificado = models.BooleanField(default=False)
    # Sempre "gratuito" por agora. A monetização vem depois.
    estado_assinatura = models.CharField(max_length=20, default='gratuito')
    # Prova do consentimento (Termos + Política de Privacidade + maioridade) dado no registo
    termos_aceites_em = models.DateTimeField(null=True, blank=True)
    termos_versao = models.CharField(max_length=20, blank=True)

    REQUIRED_FIELDS = ['email']

    def save(self, *args, **kwargs):
        self.email = (self.email or '').strip().lower()
        super().save(*args, **kwargs)

    def perfil(self):
        """Formato igual ao perfil guardado na app (prefs.js)."""
        return {
            'nomeCompleto': self.nome_completo,
            'username': self.username,
            'telefone': self.telefone,
            'email': self.email,
            'estadoAssinatura': self.estado_assinatura,
        }


def hash_chave(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()


class Sessao(models.Model):
    """Uma sessão de login por dispositivo. Só se guarda o hash da chave."""
    utilizador = models.ForeignKey(Utilizador, on_delete=models.CASCADE, related_name='sessoes')
    chave_hash = models.CharField(max_length=64, unique=True)
    dispositivo = models.CharField(max_length=120, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(default=timezone.now)

    @classmethod
    def criar(cls, utilizador, dispositivo=''):
        chave = secrets.token_urlsafe(32)
        cls.objects.create(utilizador=utilizador, chave_hash=hash_chave(chave), dispositivo=(dispositivo or '')[:120])
        return chave


class CodigoEmail(models.Model):
    VERIFICACAO = 'verificacao'
    RESET = 'reset'

    utilizador = models.ForeignKey(Utilizador, on_delete=models.CASCADE, related_name='codigos')
    finalidade = models.CharField(max_length=20)
    codigo_hash = models.CharField(max_length=64)
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    tentativas = models.PositiveSmallIntegerField(default=0)
