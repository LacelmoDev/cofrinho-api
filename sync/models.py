from django.conf import settings
from django.db import models


class Base(models.Model):
    """Registo sincronizável. O id (UUID) é criado na app, no dispositivo."""
    id = models.UUIDField(primary_key=True, editable=False)
    # Relógio do cliente: decide quem ganha num conflito ("a última alteração ganha").
    atualizado_em = models.DateTimeField()
    # Relógio do servidor: usado só para saber o que mudou desde a última sincronização.
    modificado_servidor = models.DateTimeField(auto_now=True, db_index=True)
    apagado = models.BooleanField(default=False)

    class Meta:
        abstract = True


class Categoria(Base):
    dono = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='categorias')
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10)
    escopo = models.CharField(max_length=10)
    padrao = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['dono', 'modificado_servidor'])]


class Transacao(Base):
    dono = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transacoes')
    tipo = models.CharField(max_length=10)
    valor = models.DecimalField(max_digits=18, decimal_places=2)
    data = models.DateTimeField()
    descricao = models.CharField(max_length=500, blank=True)
    categoria = models.CharField(max_length=100)
    modo = models.CharField(max_length=10)

    class Meta:
        indexes = [models.Index(fields=['dono', 'modificado_servidor'])]


class Meta(Base):
    dono = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='metas')
    nome = models.CharField(max_length=100)
    valor_alvo = models.DecimalField(max_digits=18, decimal_places=2)
    valor_atual = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    data_alvo = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['dono', 'modificado_servidor'])]
