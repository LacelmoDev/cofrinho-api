import re

from rest_framework import serializers

from .models import Utilizador

RE_USERNAME = re.compile(r'^[\w.-]{3,30}$')


def _email(v):
    v = v.strip().lower()
    return v


class RegistarSerializer(serializers.Serializer):
    nomeCompleto = serializers.CharField(min_length=3, max_length=120, trim_whitespace=True)
    username = serializers.CharField(max_length=30, trim_whitespace=True)
    telefone = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    email = serializers.EmailField(max_length=254)
    aceitaTermos = serializers.BooleanField()
    maiorDeIdade = serializers.BooleanField()
    termosVersao = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    senha = serializers.CharField(min_length=6, max_length=128, trim_whitespace=False, write_only=True,
                                  error_messages={'min_length': 'A senha precisa de pelo menos 6 caracteres.'})

    def validate_username(self, v):
        if not RE_USERNAME.match(v):
            raise serializers.ValidationError('Utilizador: 3 a 30 caracteres (letras, números, ponto, hífen ou _), sem espaços.')
        return v

    def validate_telefone(self, v):
        v = v.strip()
        if v and len(re.sub(r'\D', '', v)) < 9:
            raise serializers.ValidationError('Escreve um telefone válido (ou deixa em branco).')
        return v

    def validate_aceitaTermos(self, v):
        if v is not True:
            raise serializers.ValidationError('Tens de aceitar os Termos e a Política de Privacidade.')
        return v

    def validate_maiorDeIdade(self, v):
        if v is not True:
            raise serializers.ValidationError('Tens de ter 18 anos ou mais para criar conta.')
        return v

    def validate_email(self, v):
        return _email(v)


class LoginSerializer(serializers.Serializer):
    identificador = serializers.CharField(max_length=254)
    senha = serializers.CharField(max_length=128, trim_whitespace=False)
    dispositivo = serializers.CharField(max_length=120, required=False, allow_blank=True, default='')


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, v):
        return _email(v)


class VerificarSerializer(EmailSerializer):
    codigo = serializers.CharField(min_length=6, max_length=6)
    dispositivo = serializers.CharField(max_length=120, required=False, allow_blank=True, default='')


class ConfirmarResetSerializer(EmailSerializer):
    codigo = serializers.CharField(min_length=6, max_length=6)
    novaSenha = serializers.CharField(min_length=6, max_length=128, trim_whitespace=False,
                                      error_messages={'min_length': 'A senha precisa de pelo menos 6 caracteres.'})


class PerfilSerializer(serializers.Serializer):
    nomeCompleto = serializers.CharField(min_length=3, max_length=120, required=False)
    username = serializers.CharField(max_length=30, required=False)
    telefone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_username(self, v):
        if not RE_USERNAME.match(v):
            raise serializers.ValidationError('Utilizador: 3 a 30 caracteres (letras, números, ponto, hífen ou _), sem espaços.')
        return v

    def validate_telefone(self, v):
        v = v.strip()
        if v and len(re.sub(r'\D', '', v)) < 9:
            raise serializers.ValidationError('Escreve um telefone válido (ou deixa em branco).')
        return v


class EliminarContaSerializer(serializers.Serializer):
    senha = serializers.CharField(max_length=128, trim_whitespace=False)
