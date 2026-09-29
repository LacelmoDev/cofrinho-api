from datetime import timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Categoria, Meta, Transacao

LIMITE_LOTE = 500
VALOR_MAXIMO = Decimal('999999999999')


class ErroItem(Exception):
    pass


# ---------- validação de campos ----------
def _uuid(v):
    try:
        return UUID(str(v))
    except (ValueError, AttributeError, TypeError):
        raise ErroItem('id inválido')


def _texto(item, campo, maximo, obrigatorio=True):
    v = item.get(campo)
    if v is None or v == '':
        if obrigatorio:
            raise ErroItem(f'{campo} em falta')
        return ''
    if not isinstance(v, str) or len(v) > maximo:
        raise ErroItem(f'{campo} inválido')
    return v.strip()


def _escolha(item, campo, opcoes):
    v = item.get(campo)
    if v not in opcoes:
        raise ErroItem(f'{campo} inválido')
    return v


def _valor(item, campo, minimo_exclusivo=False):
    try:
        d = Decimal(str(item.get(campo))).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        raise ErroItem(f'{campo} inválido')
    if not d.is_finite() or d > VALOR_MAXIMO or d < 0 or (minimo_exclusivo and d == 0):
        raise ErroItem(f'{campo} fora do limite')
    return d


def _data(v, campo, obrigatorio=True):
    if v in (None, ''):
        if obrigatorio:
            raise ErroItem(f'{campo} em falta')
        return None
    d = parse_datetime(str(v)) if isinstance(v, str) else None
    if d is None:
        raise ErroItem(f'{campo} inválido')
    if timezone.is_naive(d):
        d = timezone.make_aware(d, timezone.utc)
    return d


def campos_categoria(item):
    return {
        'nome': _texto(item, 'nome', 100),
        'tipo': _escolha(item, 'tipo', ('gasto', 'receita')),
        'escopo': _escolha(item, 'escopo', ('ambos', 'pessoal', 'negocio')),
        'padrao': bool(item.get('padrao', False)),
    }


def campos_transacao(item):
    return {
        'tipo': _escolha(item, 'tipo', ('gasto', 'receita')),
        'valor': _valor(item, 'valor', minimo_exclusivo=True),
        'data': _data(item.get('data'), 'data'),
        'descricao': _texto(item, 'descricao', 500, obrigatorio=False),
        'categoria': _texto(item, 'categoria', 100),
        'modo': _escolha(item, 'modo', ('pessoal', 'negocio')),
    }


def campos_meta(item):
    return {
        'nome': _texto(item, 'nome', 100),
        'valor_alvo': _valor(item, 'valorAlvo', minimo_exclusivo=True),
        'valor_atual': _valor(item, 'valorAtual'),
        'data_alvo': _data(item.get('dataAlvo'), 'dataAlvo', obrigatorio=False),
    }


# ---------- saída ----------
def _iso(d):
    return d.isoformat() if d else None


def _base(o):
    return {'id': str(o.id), 'atualizadoEm': _iso(o.atualizado_em), 'apagado': o.apagado}


def sair_categoria(o):
    return {**_base(o), 'nome': o.nome, 'tipo': o.tipo, 'escopo': o.escopo, 'padrao': o.padrao}


def sair_transacao(o):
    return {**_base(o), 'tipo': o.tipo, 'valor': float(o.valor), 'data': _iso(o.data),
            'descricao': o.descricao, 'categoria': o.categoria, 'modo': o.modo}


def sair_meta(o):
    return {**_base(o), 'nome': o.nome, 'valorAlvo': float(o.valor_alvo),
            'valorAtual': float(o.valor_atual), 'dataAlvo': _iso(o.data_alvo)}


# ---------- lógica de sincronização ----------
def aplicar(modelo, itens, dono, agora, validar_campos):
    """Aplica os registos vindos da app. Em conflito, ganha o `atualizadoEm` mais recente.
    Devolve a lista de registos rejeitados (com o motivo)."""
    rejeitados = []
    for item in itens:
        id_txt = item.get('id') if isinstance(item, dict) else None
        try:
            if not isinstance(item, dict):
                raise ErroItem('item inválido')
            pk = _uuid(item.get('id'))
            atualizado = _data(item.get('atualizadoEm'), 'atualizadoEm')
            if atualizado > agora + timedelta(minutes=5):  # relógio do telemóvel adiantado
                atualizado = agora
            apagado = bool(item.get('apagado', False))
        except ErroItem as e:
            rejeitados.append({'id': str(id_txt) if id_txt else None, 'motivo': str(e)})
            continue

        obj = modelo.objects.filter(pk=pk).first()
        if obj and obj.dono_id != dono.id:
            rejeitados.append({'id': str(pk), 'motivo': 'id já em uso'})
            continue
        if obj and obj.atualizado_em >= atualizado:
            continue  # a versão do servidor é igual ou mais recente

        try:
            campos = validar_campos(item)
        except ErroItem as e:
            if apagado and obj:
                campos = {}  # para apagar basta id + apagado
            else:
                rejeitados.append({'id': str(pk), 'motivo': str(e)})
                continue

        if obj:
            for k, v in campos.items():
                setattr(obj, k, v)
            obj.atualizado_em = atualizado
            obj.apagado = apagado
            obj.save()
        else:
            modelo.objects.create(pk=pk, dono=dono, atualizado_em=atualizado, apagado=apagado, **campos)
    return rejeitados


COLECOES = [
    ('categorias', Categoria, campos_categoria, sair_categoria),
    ('transacoes', Transacao, campos_transacao, sair_transacao),
    ('metas', Meta, campos_meta, sair_meta),
]


class Sincronizar(APIView):
    """POST /api/sync/
    Corpo:  {"desde": "<servidorAgora da última vez>" | null,
             "categorias": [...], "transacoes": [...], "metas": [...]}
    Resposta: alterações no servidor desde `desde` + `servidorAgora` (guardar para a próxima vez)."""
    throttle_scope = 'sync'

    def post(self, request):
        corpo = request.data if isinstance(request.data, dict) else {}
        agora = timezone.now()

        desde = None
        if corpo.get('desde'):
            try:
                desde = _data(corpo['desde'], 'desde')
            except ErroItem:
                raise ValidationError({'desde': 'Data inválida.'})

        recebidos = {}
        for nome, *_ in COLECOES:
            itens = corpo.get(nome, [])
            if not isinstance(itens, list):
                raise ValidationError({nome: 'Tem de ser uma lista.'})
            if len(itens) > LIMITE_LOTE:
                raise ValidationError({nome: f'Máximo de {LIMITE_LOTE} registos por pedido. Envia em lotes.'})
            recebidos[nome] = itens

        rejeitados = {}
        resposta = {}
        with transaction.atomic():
            for nome, modelo, validar, _ in COLECOES:
                rejeitados[nome] = aplicar(modelo, recebidos[nome], request.user, agora, validar)
            for nome, modelo, _, sair in COLECOES:
                qs = modelo.objects.filter(dono=request.user)
                if desde:
                    qs = qs.filter(modificado_servidor__gt=desde)
                resposta[nome] = [sair(o) for o in qs.order_by('modificado_servidor')]

        # Margem de 2 s: pode repetir alterações recentes, mas nunca falha nenhuma (a app trata isto como idempotente).
        resposta['servidorAgora'] = _iso(agora - timedelta(seconds=2))
        resposta['rejeitados'] = rejeitados
        return Response(resposta)
