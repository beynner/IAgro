# sankhya_integration/decorators.py
import json
import logging
from functools import wraps
from django.http import HttpRequest
from django.shortcuts import redirect, render  # 👈 Adicionado 'render' aqui
from django.contrib import messages

logger = logging.getLogger(__name__)

# Mapeamento de grupos do Sankhya ERP (tabela TSIGRU, coluna CODGRU).
#
# Para consultar os IDs vigentes no banco:
#   SELECT CODGRU, DESCRGRU FROM TSIGRU ORDER BY CODGRU
#
# Grupos atualmente mapeados:
#   '1'  → Diretoria     — acesso irrestrito a todos os módulos
#   '6'  → Suporte TI    — acesso irrestrito para manutenção e suporte
#   '8'  → Operação      — acesso aos módulos de Entrada e Classificação
#   '9'  → Comercial     — acesso exclusivo ao módulo Comercial
#   '10' → Vendas        — acesso exclusivo ao módulo de Vendas
#
# Os IDs são armazenados como strings porque chegam da sessão via JSON.
# Para alterar permissões: edite as listas abaixo — não é necessário
# modificar nenhuma outra parte do código.
GRUPOS_PERMITIDOS = {
    'entrada':       ['1', '6', '8'],
    'classificacao': ['1', '6', '8'],
    'comercial':     ['1', '6', '9'],
    'venda':         ['1', '6', '10'],
    'rastreio':      ['1', '6', '8', '9', '10'],
}

def _get_json_payload(request: HttpRequest) -> dict:
    if request.method != 'POST' or not request.body:
        return {}
    try:
        return json.loads(request.body.decode('utf-8'))
    except Exception:
        return {}

def check_vale_lock(view_func):
    @wraps(view_func)
    def _wrapped_view(request: HttpRequest, *args, **kwargs):
        from .views import _respond_if_vale_locked 
        
        if request.method == 'POST':
            payload = _get_json_payload(request)
            nunota_val = None
            for key in ['nunota', 'nunota_pedido', 'nunota_11', 'nunota_origem']:
                nunota_val = payload.get(key) or request.POST.get(key)
                if nunota_val: break
            
            if nunota_val:
                lock_response = _respond_if_vale_locked(int(nunota_val))
                if lock_response: return lock_response
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def exige_grupo(modulo_alvo):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if 'codusu' not in request.session:
                return redirect('home')
            
            grupos_usuario = [str(g) for g in request.session.get('grupos', [])]
            permitidos = GRUPOS_PERMITIDOS.get(modulo_alvo, [])
            
            if not any(g in permitidos for g in grupos_usuario):
                # Mensagem que vai aparecer no balão vermelho
                messages.error(request, f"Acesso Negado: Seu grupo atual não tem permissão para o módulo {modulo_alvo}.")
                
                # 💡 A MUDANÇA É AQUI: Em vez de renderizar o 403.html, joga de volta pra Home
                return redirect('home') 
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


