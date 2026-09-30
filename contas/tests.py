from datetime import timedelta

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import CodigoEmail, Sessao, Utilizador

DADOS = {'nomeCompleto': 'Maria Silva', 'username': 'maria', 'telefone': '923456789',
         'email': 'maria@exemplo.com', 'senha': 'segredo1',
         'aceitaTermos': True, 'maiorDeIdade': True, 'termosVersao': '2026-09-30'}


@override_settings(DEBUG=True)
class ContasTests(APITestCase):
    def setUp(self):
        cache.clear()  # os limites de pedidos usam a cache

    def registar(self, **extra):
        return self.client.post('/api/auth/registar/', {**DADOS, **extra}, format='json')

    def criar_conta_verificada(self):
        r = self.registar()
        v = self.client.post('/api/auth/verificar-email/', {'email': DADOS['email'], 'codigo': r.data['codigoDev']}, format='json')
        return v.data['token']

    def test_fluxo_registo_verificacao_login(self):
        r = self.registar()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.data['codigoDev']), 6)
        # sem verificar não entra
        l = self.client.post('/api/auth/login/', {'identificador': 'maria', 'senha': 'segredo1'}, format='json')
        self.assertEqual(l.status_code, 403)
        self.assertEqual(l.data['codigo'], 'email_nao_verificado')
        self.assertEqual(l.data['email'], 'maria@exemplo.com')
        # código errado
        v = self.client.post('/api/auth/verificar-email/', {'email': DADOS['email'], 'codigo': '000000'}, format='json')
        self.assertEqual(v.status_code, 400)
        # código certo
        v = self.client.post('/api/auth/verificar-email/', {'email': DADOS['email'], 'codigo': r.data['codigoDev']}, format='json')
        self.assertEqual(v.status_code, 200)
        self.assertEqual(v.data['perfil']['username'], 'maria')
        self.assertEqual(v.data['perfil']['estadoAssinatura'], 'gratuito')
        # login por username e por email (sem distinguir maiúsculas)
        for ident in ('MARIA', 'Maria@Exemplo.com'):
            l = self.client.post('/api/auth/login/', {'identificador': ident, 'senha': 'segredo1'}, format='json')
            self.assertEqual(l.status_code, 200, ident)
        l = self.client.post('/api/auth/login/', {'identificador': 'maria', 'senha': 'errada1'}, format='json')
        self.assertEqual(l.status_code, 400)

    def test_senha_nao_guardada_em_claro_e_chave_so_hash(self):
        token = self.criar_conta_verificada()
        u = Utilizador.objects.get(username='maria')
        self.assertNotIn('segredo1', u.password)
        self.assertFalse(Sessao.objects.filter(chave_hash=token).exists())  # só o hash está na BD

    def test_codigo_expira_e_limita_tentativas(self):
        r = self.registar()
        for _ in range(5):
            self.client.post('/api/auth/verificar-email/', {'email': DADOS['email'], 'codigo': '000000'}, format='json')
            cache.clear()
        # depois de 5 falhas, nem o código certo serve
        v = self.client.post('/api/auth/verificar-email/', {'email': DADOS['email'], 'codigo': r.data['codigoDev']}, format='json')
        self.assertEqual(v.status_code, 400)
        cache.clear()
        # expirado
        r2 = self.client.post('/api/auth/registar/', DADOS, format='json')
        self.assertEqual(r2.status_code, 429)  # reenvio antes de 60 s
        CodigoEmail.objects.update(criado_em=timezone.now() - timedelta(minutes=2))
        cache.clear()
        r3 = self.client.post('/api/auth/registar/', DADOS, format='json')
        self.assertEqual(r3.status_code, 201)
        CodigoEmail.objects.update(expira_em=timezone.now() - timedelta(minutes=1))
        v = self.client.post('/api/auth/verificar-email/', {'email': DADOS['email'], 'codigo': r3.data['codigoDev']}, format='json')
        self.assertEqual(v.status_code, 400)

    def test_duplicados(self):
        self.criar_conta_verificada()
        r = self.registar(username='outra')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['codigo'], 'email_existente')
        r = self.registar(email='outra@exemplo.com', username='MARIA')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['codigo'], 'username_existente')

    def test_validacao_de_campos(self):
        self.assertEqual(self.registar(senha='123').status_code, 400)
        self.assertEqual(self.registar(email='sem-arroba').status_code, 400)
        self.assertEqual(self.registar(username='com espaco').status_code, 400)
        self.assertEqual(self.registar(telefone='12').status_code, 400)

    def test_conta_nao_verificada_pode_recomecar(self):
        self.registar()
        cache.clear()
        CodigoEmail.objects.update(criado_em=timezone.now() - timedelta(minutes=2))
        r = self.registar(username='maria2')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Utilizador.objects.count(), 1)

    def test_eu_logout_e_edicao(self):
        token = self.criar_conta_verificada()
        self.assertEqual(self.client.get('/api/auth/eu/').status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.client.get('/api/auth/eu/').data['email'], 'maria@exemplo.com')
        p = self.client.patch('/api/auth/eu/', {'nomeCompleto': 'Maria S. Silva', 'email': 'hacker@x.com'}, format='json')
        self.assertEqual(p.data['nomeCompleto'], 'Maria S. Silva')
        self.assertEqual(p.data['email'], 'maria@exemplo.com')  # email não muda
        self.assertEqual(self.client.post('/api/auth/logout/').status_code, 204)
        self.assertEqual(self.client.get('/api/auth/eu/').status_code, 401)

    def test_sessao_expira_por_inatividade(self):
        token = self.criar_conta_verificada()
        Sessao.objects.update(ultimo_uso=timezone.now() - timedelta(days=91))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.client.get('/api/auth/eu/').status_code, 401)

    def test_recuperar_senha(self):
        token = self.criar_conta_verificada()
        cache.clear()
        # email inexistente: mesma resposta, sem código
        r = self.client.post('/api/auth/senha/pedir/', {'email': 'ninguem@x.com'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('codigoDev', r.data)
        r = self.client.post('/api/auth/senha/pedir/', {'email': DADOS['email']}, format='json')
        c = self.client.post('/api/auth/senha/confirmar/', {'email': DADOS['email'], 'codigo': r.data['codigoDev'], 'novaSenha': 'novasenha9'}, format='json')
        self.assertEqual(c.status_code, 200)
        self.assertEqual(self.client.post('/api/auth/login/', {'identificador': 'maria', 'senha': 'segredo1'}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/auth/login/', {'identificador': 'maria', 'senha': 'novasenha9'}, format='json').status_code, 200)
        # a sessão antiga foi terminada
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.client.get('/api/auth/eu/').status_code, 401)

    @override_settings(DEBUG=False)
    def test_codigo_nunca_vai_na_resposta_fora_de_debug(self):
        r = self.registar()
        self.assertNotIn('codigoDev', r.data)
