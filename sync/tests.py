from django.core.cache import cache
from django.utils import timezone
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

CAT = '11111111-1111-4111-8111-111111111111'
TX = '22222222-2222-4222-8222-222222222222'
META = '33333333-3333-4333-8333-333333333333'


def t(hora):
    """Data de ontem às `hora` (sempre no passado, para não ser cortada pelo limite do relógio adiantado)."""
    return (timezone.now() - timezone.timedelta(days=1)).replace(hour=hora, minute=0, second=0, microsecond=0).isoformat()


def nova_conta(username):
    c = APIClient()
    d = {'nomeCompleto': 'Utilizador Teste', 'username': username, 'telefone': '923456789',
         'email': f'{username}@exemplo.com', 'senha': 'segredo1'}
    r = c.post('/api/auth/registar/', d, format='json')
    v = c.post('/api/auth/verificar-email/', {'email': d['email'], 'codigo': r.data['codigoDev']}, format='json')
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {v.data["token"]}')
    return c


def tx(valor=1500.5, quando=None, **extra):
    return {'id': TX, 'tipo': 'gasto', 'valor': valor, 'data': t(9), 'descricao': 'Pão',
            'categoria': 'Alimentação', 'modo': 'pessoal', 'atualizadoEm': quando or t(10), **extra}


@override_settings(DEBUG=True)
class SyncTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.a = nova_conta('ana')
        cache.clear()

    def sync(self, cliente=None, **corpo):
        return (cliente or self.a).post('/api/sync/', corpo, format='json')

    def test_exige_autenticacao(self):
        self.assertEqual(APIClient().post('/api/sync/', {}, format='json').status_code, 401)

    def test_envio_e_recepcao_entre_dispositivos(self):
        r = self.sync(
            categorias=[{'id': CAT, 'nome': 'Alimentação', 'tipo': 'gasto', 'escopo': 'ambos', 'padrao': True, 'atualizadoEm': t(10)}],
            transacoes=[tx()],
            metas=[{'id': META, 'nome': 'Telemóvel', 'valorAlvo': 90000, 'valorAtual': 0, 'dataAlvo': None, 'atualizadoEm': t(10)}],
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['rejeitados'], {'categorias': [], 'transacoes': [], 'metas': []})
        # um segundo dispositivo da mesma conta (sem "desde") recebe tudo
        b = APIClient()
        b.credentials(**{k: v for k, v in self.a._credentials.items()})
        cache.clear()
        r2 = b.post('/api/sync/', {}, format='json')
        self.assertEqual(len(r2.data['categorias']), 1)
        self.assertEqual(r2.data['transacoes'][0]['valor'], 1500.5)
        self.assertEqual(r2.data['transacoes'][0]['descricao'], 'Pão')
        self.assertEqual(r2.data['metas'][0]['nome'], 'Telemóvel')
        # pedido incremental: nada de novo
        cache.clear()
        r3 = b.post('/api/sync/', {'desde': r2.data['servidorAgora']}, format='json')
        # (margem de 2 s pode repetir o que acabou de mudar; é idempotente)
        cache.clear()
        r4 = b.post('/api/sync/', {'desde': '2099-01-01T00:00:00Z'}, format='json')
        self.assertEqual(r4.data['transacoes'], [])
        self.assertEqual(r3.status_code, 200)

    def test_ultima_alteracao_ganha(self):
        self.sync(transacoes=[tx(valor=100, quando=t(10))])
        cache.clear()
        # mais recente: aceite
        self.sync(transacoes=[tx(valor=200, quando=t(11))])
        cache.clear()
        # mais antiga (dispositivo que esteve offline): ignorada, e recebe a versão do servidor
        r = self.sync(transacoes=[tx(valor=50, quando=t(9))])
        self.assertEqual(r.data['transacoes'][0]['valor'], 200.0)

    def test_apagar_propaga(self):
        self.sync(transacoes=[tx()])
        cache.clear()
        self.sync(transacoes=[{'id': TX, 'apagado': True, 'atualizadoEm': t(12)}])
        cache.clear()
        r = self.sync()
        self.assertTrue(r.data['transacoes'][0]['apagado'])

    def test_isolamento_entre_contas(self):
        self.sync(transacoes=[tx()])
        cache.clear()
        b = nova_conta('bruno')
        cache.clear()
        self.assertEqual(self.sync(b).data['transacoes'], [])
        # b não consegue sobrescrever o registo da ana com o mesmo id
        cache.clear()
        r = self.sync(b, transacoes=[tx(valor=1, quando='2030-01-01T00:00:00Z')])
        self.assertEqual(r.data['rejeitados']['transacoes'][0]['motivo'], 'id já em uso')
        cache.clear()
        self.assertEqual(self.sync().data['transacoes'][0]['valor'], 1500.5)

    def test_validacao_rejeita_so_o_registo_invalido(self):
        r = self.sync(transacoes=[
            tx(),
            {**tx(), 'id': '44444444-4444-4444-8444-444444444444', 'valor': -5},
            {**tx(), 'id': '55555555-5555-4555-8555-555555555555', 'tipo': 'roubo'},
            {**tx(), 'id': '66666666-6666-4666-8666-666666666666', 'valor': 10 ** 15},
            {'id': 'nao-e-uuid', 'atualizadoEm': t(10)},
        ])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['rejeitados']['transacoes']), 4)
        self.assertEqual(len(r.data['transacoes']), 1)

    def test_lote_demasiado_grande_e_corpo_invalido(self):
        r = self.sync(transacoes=[tx()] * 501)
        self.assertEqual(r.status_code, 400)
        cache.clear()
        self.assertEqual(self.sync(transacoes='texto').status_code, 400)
        cache.clear()
        self.assertEqual(self.sync(desde='ontem').status_code, 400)

    def test_relogio_adiantado_nao_fica_para_sempre_a_ganhar(self):
        self.sync(transacoes=[tx(valor=10, quando='2099-01-01T00:00:00Z')])
        cache.clear()
        # uma alteração normal, feita agora, ainda consegue ganhar
        r = self.sync(transacoes=[tx(valor=20, quando=(timezone.now() + timezone.timedelta(minutes=10)).isoformat())])
        self.assertEqual(r.data['transacoes'][0]['valor'], 20.0)
