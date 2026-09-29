from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.views import exception_handler


def _primeira_mensagem(detalhe):
    if isinstance(detalhe, dict):
        for v in detalhe.values():
            m = _primeira_mensagem(v)
            if m:
                return m
    elif isinstance(detalhe, (list, tuple)):
        for v in detalhe:
            m = _primeira_mensagem(v)
            if m:
                return m
    elif detalhe:
        return str(detalhe)
    return None


def tratar_excecao(exc, contexto):
    """Formato único de erro: {"erro": "mensagem", "codigo": "...", "campos": {...}}"""
    resposta = exception_handler(exc, contexto)
    if resposta is None:
        return None
    if isinstance(exc, ValidationError):
        resposta.data = {
            'erro': _primeira_mensagem(resposta.data) or 'Dados inválidos.',
            'codigo': 'dados_invalidos',
            'campos': resposta.data,
        }
    elif isinstance(exc, Throttled):
        espera = int(exc.wait or 1)
        resposta.data = {'erro': f'Demasiados pedidos. Tenta outra vez dentro de {espera} segundos.', 'codigo': 'muitos_pedidos'}
    elif isinstance(resposta.data, dict) and 'detail' in resposta.data:
        resposta.data = {'erro': str(resposta.data['detail']), 'codigo': getattr(exc, 'default_code', 'erro')}
    return resposta
