from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .codigos import EsperaNecessaria, criar_codigo, validar_codigo
from .emails import enviar_codigo
from .models import CodigoEmail, Sessao, Utilizador, hash_chave
from .serializers import (ConfirmarResetSerializer, EmailSerializer, LoginSerializer, PerfilSerializer,
                          RegistarSerializer, VerificarSerializer)


def erro(mensagem, codigo, http=status.HTTP_400_BAD_REQUEST):
    return Response({'erro': mensagem, 'codigo': codigo}, status=http)


def _enviar(utilizador, finalidade):
    """Cria e envia um código. Devolve (enviado, codigo_dev, espera_seg)."""
    try:
        codigo = criar_codigo(utilizador, finalidade)
    except EsperaNecessaria as e:
        return None, None, e.segundos
    enviado = enviar_codigo(utilizador, finalidade, codigo)
    # O código só é devolvido em DEBUG e sem email configurado (desenvolvimento).
    dev = codigo if (settings.DEBUG and not enviado) else None
    return enviado, dev, 0


def _resposta_codigo(utilizador, finalidade, http=status.HTTP_200_OK):
    enviado, dev, espera = _enviar(utilizador, finalidade)
    if enviado is None:
        return erro(f'Espera {espera} segundos antes de pedir outro código.', 'espera_reenvio', status.HTTP_429_TOO_MANY_REQUESTS)
    corpo = {'email': utilizador.email, 'emailEnviado': enviado}
    if dev:
        corpo['codigoDev'] = dev
    return Response(corpo, status=http)


class Registar(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'auth'

    def post(self, request):
        s = RegistarSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        existente = Utilizador.objects.filter(email=d['email']).first()
        if existente and existente.email_verificado:
            return erro('Este email já tem conta. Entra com a tua senha.', 'email_existente', status.HTTP_409_CONFLICT)
        outros = Utilizador.objects.filter(username__iexact=d['username'])
        if existente:
            outros = outros.exclude(pk=existente.pk)
        if outros.exists():
            return erro('Esse nome de utilizador já está em uso.', 'username_existente', status.HTTP_409_CONFLICT)

        if existente:  # conta ainda não verificada: permite recomeçar sem ficar bloqueado
            u = existente
        else:
            u = Utilizador(email=d['email'])
        u.username = d['username']
        u.nome_completo = d['nomeCompleto']
        u.telefone = d['telefone']
        u.password = make_password(d['senha'])
        u.email_verificado = False
        u.save()
        return _resposta_codigo(u, CodigoEmail.VERIFICACAO, status.HTTP_201_CREATED)


class ReenviarCodigo(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'codigo'

    def post(self, request):
        s = EmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        u = Utilizador.objects.filter(email=s.validated_data['email'], email_verificado=False).first()
        if not u:  # não revela se o email existe
            return Response({'email': s.validated_data['email'], 'emailEnviado': True})
        return _resposta_codigo(u, CodigoEmail.VERIFICACAO)


class VerificarEmail(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'auth'

    def post(self, request):
        s = VerificarSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        u = Utilizador.objects.filter(email=d['email'], email_verificado=False).first()
        if not u or not validar_codigo(u, CodigoEmail.VERIFICACAO, d['codigo']):
            return erro('Código incorrecto ou expirado.', 'codigo_invalido')
        u.email_verificado = True
        u.save(update_fields=['email_verificado'])
        chave = Sessao.criar(u, d['dispositivo'])
        return Response({'token': chave, 'perfil': u.perfil()})


class Login(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'auth'

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        ident = d['identificador'].strip()
        u = Utilizador.objects.filter(Q(username__iexact=ident) | Q(email__iexact=ident)).first()
        if not u or not u.check_password(d['senha']) or not u.is_active:
            return erro('Utilizador/email ou senha incorrectos.', 'credenciais_invalidas')
        if not u.email_verificado:
            return erro('Ainda não confirmaste o teu email.', 'email_nao_verificado', status.HTTP_403_FORBIDDEN)
        chave = Sessao.criar(u, d['dispositivo'])
        return Response({'token': chave, 'perfil': u.perfil()})


class Logout(APIView):
    def post(self, request):
        request.auth.delete()  # termina só a sessão deste dispositivo
        return Response(status=status.HTTP_204_NO_CONTENT)


class Eu(APIView):
    def get(self, request):
        return Response(request.user.perfil())

    def patch(self, request):
        # O email não se altera por agora (exigiria nova verificação).
        s = PerfilSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        u = request.user
        if 'username' in d:
            if Utilizador.objects.filter(username__iexact=d['username']).exclude(pk=u.pk).exists():
                return erro('Esse nome de utilizador já está em uso.', 'username_existente', status.HTTP_409_CONFLICT)
            u.username = d['username']
        if 'nomeCompleto' in d:
            u.nome_completo = d['nomeCompleto']
        if 'telefone' in d:
            u.telefone = d['telefone']
        u.save()
        return Response(u.perfil())


class PedirReset(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'codigo'

    def post(self, request):
        s = EmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = s.validated_data['email']
        u = Utilizador.objects.filter(email=email, email_verificado=True, is_active=True).first()
        corpo = {'email': email, 'emailEnviado': True}
        if u:
            enviado, dev, _ = _enviar(u, CodigoEmail.RESET)
            if dev:
                corpo['codigoDev'] = dev
        return Response(corpo)  # resposta igual exista ou não a conta


class ConfirmarReset(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'auth'

    def post(self, request):
        s = ConfirmarResetSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        u = Utilizador.objects.filter(email=d['email'], email_verificado=True, is_active=True).first()
        if not u or not validar_codigo(u, CodigoEmail.RESET, d['codigo']):
            return erro('Código incorrecto ou expirado.', 'codigo_invalido')
        u.set_password(d['novaSenha'])
        u.save(update_fields=['password'])
        u.sessoes.all().delete()  # termina a sessão em todos os dispositivos
        return Response({'ok': True})
