# Correção: Erro 400 ao Salvar Descarte

> **⚠️ NOTA HISTÓRICA**: Este documento descreve um erro que ocorreu quando o campo Descarte usava `TGFCAB.CODRESIDUO`. 
> **O campo foi migrado para `TGFCAB.QTDBATIDAS`** mas este documento é mantido para referência histórica da correção do bug de tipo de dados.

## Problema Identificado

**Erro**: `POST http://localhost:8000/sankhya/header/update/ 400 (Bad Request)`

### Causas Raiz

1. **Tipo de dados incorreto**: `CODRESIDUO` estava sendo tratado como **inteiro** (`_to_int_or`) mas deveria aceitar **decimais**
2. **Validação excessiva**: A função `plan_update_cabecalho` estava aplicando validações pesadas de negócio (CODTIPVENDA obrigatório) mesmo quando apenas campos "livres" como CODRESIDUO estavam sendo atualizados

## Correções Aplicadas

### 1. Backend - Tipo de Dados (`views.py`)

#### ✅ Nova função `_to_float_or`
```python
def _to_float_or(val, default=None):
    """Convert value to float, return default if invalid."""
    v = _first(val)
    if v in (None, '', 'None', 'none', 'null'):
        return default
    try:
        return float(v)
    except Exception:
        try:
            return float(str(v))
        except Exception:
            return default
```

#### ✅ Alteração em `header_update`
**Antes:**
```python
'CODRESIDUO': _to_int_or(payload.get('codresiduo')),
```

**Depois:**
```python
'CODRESIDUO': _to_float_or(payload.get('codresiduo')),
```

### 2. Backend - Validação Condicional (`oracle_conn.py`)

#### ✅ Validação seletiva em `plan_update_cabecalho`

**Problema**: Validações pesadas (CODTIPVENDA obrigatório para TIPMOV P/V/D) eram aplicadas mesmo ao atualizar apenas CODRESIDUO.

**Solução**: Pular validações de negócio quando apenas "campos livres" estão sendo atualizados.

**Código adicionado:**
```python
# Validar conjunto SOMENTE se estamos alterando campos estruturais
# Campos "livres" (CODRESIDUO, OBSERVACAO, STATUSNOTA, PENDENTE) não exigem validação completa
campos_livres_apenas = all(
    data.get(k) is None 
    for k in ['CODPARC', 'CODTIPOPER', 'CODNAT', 'CODCENCUS', 'DTNEG', 'DTMOV', 'DTENTSAI', 'NUMNOTA']
)
if not campos_livres_apenas:
    v_errs, v_warns = validar_cabecalho_minimo(payload)
    errs.extend(v_errs)
    warns.extend(v_warns)
```

**Campos livres** (não exigem validação completa):
- `CODRESIDUO` - Total descartado
- `OBSERVACAO` - Observações gerais
- `STATUSNOTA` - Status (A/L)
- `PENDENTE` - Pendente (S/N)

**Campos estruturais** (exigem validação completa):
- `CODPARC` - Parceiro
- `CODTIPOPER` - Tipo de operação
- `CODNAT` - Natureza
- `CODCENCUS` - Centro de resultado
- `DTNEG`, `DTMOV`, `DTENTSAI` - Datas
- `NUMNOTA` - Número da nota

### 3. Backend - Mensagens de Erro (`views.py`)

#### ✅ Melhor tratamento de erros
```python
def header_update(request: HttpRequest) -> JsonResponse:
    # Validação de NUNOTA obrigatório
    if not nunota:
        return JsonResponse({"ok": False, "error": "NUNOTA obrigatório"}, status=400)
    
    # Resposta de erro mais descritiva
    if not plan.get('executed'):
        errors = plan.get('errors', [])
        error_msg = errors[0] if errors else 'Falha ao atualizar cabeçalho'
        return JsonResponse({
            "ok": False,
            "error": error_msg,
            "errors": errors,
            "db_error": plan.get('db_error')
        }, status=400)
```

### 4. Frontend - Logs de Debug (`compras_classificacao.html`)

#### ✅ Logs para diagnóstico
```javascript
console.log('[DESCARTE] Salvando:', { nunota: nun, codresiduo: rounded });
const res = await postJSON('/sankhya/header/update/', { nunota: nun, codresiduo: rounded });
console.log('[DESCARTE] Resposta:', res);
```

## Testes Realizados

### Teste 1: Float
```python
Input: {'NUNOTA': 92500, 'CODRESIDUO': 5.5}
Result: ✅ ok=True, errors=[]
SQL: UPDATE TGFCAB SET CODRESIDUO=:CODRESIDUO, DTALTER=SYSDATE WHERE NUNOTA=:NUNOTA
```

### Teste 2: String Numérica
```python
Input: {'NUNOTA': 92500, 'CODRESIDUO': '12.3'}
Result: ✅ ok=True, errors=[]
```

### Teste 3: Zero
```python
Input: {'NUNOTA': 92500, 'CODRESIDUO': 0}
Result: ✅ ok=True, errors=[]
```

### Teste 4: None (não atualiza)
```python
Input: {'NUNOTA': 92500, 'CODRESIDUO': None}
Result: ✅ ok=False, warnings=['Nenhuma alteração informada']
```
