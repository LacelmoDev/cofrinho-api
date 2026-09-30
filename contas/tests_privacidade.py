from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from sync.models import Transacao

from .models import CodigoEmail, Sessao, Utilizador

DADOS = {'nomeCompleto': 'Maria Silva', 'username': 'maria', 'telefone': '923456789',
         'email': 'maria@exemplo.com', 'senha': 'segredo1',
         'aceitaTermos': True, 'maiorDeIdade': True, 'termosVersao': '2026-09-30'}
TX = '22222222-2222-4222-8222-222222222222'


@override_settings(DEBUG=True)
class PrivacidadeTests(APITestCase):
    def setUp(self):
        cache.clear()

    def registar(self, **extra):
        return self.client.post('/api/auth/registar/', {**DADOS, **extra}, format='json')

    def conta(self):
        r = self.registar()
        v = self.client.post('/api/auth/verificar-email/', {'email': DADOS['email'], 'codigo': r.data['codigoDev']}, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {v.data['token']}")

    def test_consentimento_e_maioridade_obrigatorios(self):
        self.assertEqual(self.registar(aceitaTermos=False).status_code, 400)
        self.assertEqual(self.registar(maiorDeIdade=False).status_code, 400)
        d = {k: v for k, v in DADOS.items() if k != 'aceitaTermos'}
        self.assertEqual(self.client.post('/api/auth/registar/', d, format='json').status_code, 400)
        self.assertEqual(Utilizador.objects.count(), 0)  # nada é guardado sem consentimento

    def test_consentimento_fica_registado(self):
        self.registar()
        u = Utilizador.objects.get(username='maria')
        self.assertIsNotNone(u.termos_aceites_em)
        self.assertEqual(u.termos_versao, '2026-09-30')

    def test_telefone_e_opcional(self):
        r = self.registar(telefone='')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Utilizador.objects.get(username='maria').telefone, '')
        cache.clear()
        self.assertEqual(self.registar(username='outra', email='o@x.com', telefone='12').status_code, 400)

    def test_exportar_dados(self):
        self.conta()
        cache.clear()
        self.client.post('/api/sync/', {'transacoes': [{
            'id': TX, 'tipo': 'gasto', 'valor': 500, 'data': '2026-09-01T10:00:00Z', 'categoria': 'Casa',
            'modo': 'pessoal', 'atualizadoEm': '2026-09-01T10:00:00Z'}]}, format='json')
        cache.clear()
        r = self.client.get('/api/auth/exportar/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['conta']['email'], 'maria@exemplo.com')
        self.assertEqual(r.data['conta']['termosVersao'], '2026-09-30')
        self.assertEqual(len(r.data['transacoes']), 1)
        self.assertNotIn('senha', str(r.data).lower())
        self.assertNotIn('password', str(r.data).lower())

    def test_exportar_exige_login(self):
        self.assertEqual(self.client.get('/api/auth/exportar/').status_code, 401)

    def test_eliminar_conta_apaga_tudo(self):
        self.conta()
        cache.clear()
        self.client.post('/api/sync/', {'transacoes': [{
            'id': TX, 'tipo': 'gasto', 'valor': 500, 'data': '2026-09-01T10:00:00Z', 'categoria': 'Casa',
            'modo': 'pessoal', 'atualizadoEm': '2026-09-01T10:00:00Z'}]}, format='json')
        cache.clear()
        errada = self.client.post('/api/auth/eliminar-conta/', {'senha': 'errada'}, format='json')
        self.assertEqual(errada.status_code, 400)
        self.assertTrue(Utilizador.objects.filter(username='maria').exists())
        cache.clear()
        ok = self.client.post('/api/auth/eliminar-conta/', {'senha': 'segredo1'}, format='json')
        self.assertEqual(ok.status_code, 204)
        self.assertFalse(Utilizador.objects.exists())
        self.assertFalse(Transacao.objects.exists())
        self.assertFalse(Sessao.objects.exists())
        self.assertFalse(CodigoEmail.objects.exists())
        # o token deixou de valer
        self.assertEqual(self.client.get('/api/auth/eu/').status_code, 401)

    def test_admin_nao_se_elimina_pela_app(self):
        self.conta()
        Utilizador.objects.update(is_staff=True)
        cache.clear()
        r = self.client.post('/api/auth/eliminar-conta/', {'senha': 'segredo1'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Utilizador.objects.exists())
