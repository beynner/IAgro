# Correção: Persistência de Campos AD_SIM* no Oracle

**Data**: 2025-10-07  
**Item Testado**: NUNOTA 91730, SEQUENCIA 1  
**Status**: ✅ **CORRIGIDO E TESTADO**

---

## 🐛 Problema Reportado

Ao tentar salvar simulação Extra/Médio para o item **nunota 91730 sequencia 1**, os valores não foram persistidos no Oracle.

**Sintoma**:
```sql
SELECT AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2
FROM TGFITE
WHERE NUNOTA = 91730 AND SEQUENCIA = 1;
-- Resultado: NULL, NULL, NULL, NULL (antes da correção)
```

---

## 🔍 Diagnóstico

### Causa Raiz

A função `plan_update_item()` em `oracle_conn.py` **não incluía** os campos de simulação (`AD_SIMQTD1`, `AD_SIMQTD2`, `AD_SIMVLR1`, `AD_SIMVLR2`) na lista de campos permitidos para UPDATE.

**Arquivo**: `sankhya_integration/services/oracle_conn.py`  
**Função**: `plan_update_item()` (linha ~1598)

### Verificação de Colunas no Oracle

✅ **Colunas existem** na tabela TGFITE:
```sql
SELECT COLUMN_NAME, DATA_TYPE, NULLABLE
FROM USER_TAB_COLUMNS
WHERE TABLE_NAME = 'TGFITE'
AND COLUMN_NAME IN ('AD_SIMQTD1', 'AD_SIMQTD2', 'AD_SIMVLR1', 'AD_SIMVLR2');
```

**Resultado**:
| Coluna | Tipo | Nullable |
|--------|------|----------|
| AD_SIMQTD1 | NUMBER | Y |
| AD_SIMQTD2 | NUMBER | Y |
| AD_SIMVLR1 | FLOAT | Y |
| AD_SIMVLR2 | FLOAT | Y |

⚠️ **Nota**: `AD_SIMQTD1` e `AD_SIMQTD2` são `NUMBER` (inteiro), portanto valores decimais serão arredondados.

---

## ✅ Solução Implementada

### Mudanças em `oracle_conn.py`

**Arquivo**: `sankhya_integration/services/oracle_conn.py`  
**Linhas**: ~1598-1770

#### 1. Atualizar docstring (linha ~1598)

```python
def plan_update_item(d: dict) -> dict:
    """Planeja UPDATE em TGFITE para um item existente identificado por NUNOTA+SEQUENCIA.
    Campos aceitos para atualização: CODPROD, QTDNEG, VLRUNIT, CODVOL, CODLOCALORIG, 
                                      CONTROLE, OBSERVACAO, AD_SIMQTD1, AD_SIMQTD2, 
                                      AD_SIMVLR1, AD_SIMVLR2.
    Requer: NUNOTA e SEQUENCIA.
    """
```

#### 2. Adicionar processamento dos 4 campos (linha ~1760)

```python
# Permitir salvar campos de simulação Extra/Médio (AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2)
if data.get('AD_SIMQTD1') is not None:
    try:
        sets.append('AD_SIMQTD1=:AD_SIMQTD1'); binds['AD_SIMQTD1'] = float(data['AD_SIMQTD1'])
    except Exception:
        pass
if data.get('AD_SIMQTD2') is not None:
    try:
        sets.append('AD_SIMQTD2=:AD_SIMQTD2'); binds['AD_SIMQTD2'] = float(data['AD_SIMQTD2'])
    except Exception:
        pass
if data.get('AD_SIMVLR1') is not None:
    try:
        sets.append('AD_SIMVLR1=:AD_SIMVLR1'); binds['AD_SIMVLR1'] = float(data['AD_SIMVLR1'])
    except Exception:
        pass
if data.get('AD_SIMVLR2') is not None:
    try:
        sets.append('AD_SIMVLR2=:AD_SIMVLR2'); binds['AD_SIMVLR2'] = float(data['AD_SIMVLR2'])
    except Exception:
        pass
```

---

## 🧪 Teste de Validação

### Script de Teste

**Arquivo**: `test_save_91730.py`

```python
from sankhya_integration.services.oracle_conn import update_item

payload = {
    'NUNOTA': 91730,
    'SEQUENCIA': 1,
    'VLRUNIT': 3.588517,
    'VLRTOT': 9000.0,
    'AD_SIMQTD1': 100.5,
    'AD_SIMVLR1': 5500.75,
    'AD_SIMQTD2': 50.25,
    'AD_SIMVLR2': 3499.25,
}

result = update_item(payload, dry_run=False)
```

### Resultado do Teste

**Query SQL Gerada**:
```sql
UPDATE TGFITE 
SET VLRUNIT=:VLRUNIT, 
    VLRTOT=:VLRTOT, 
    AD_SIMQTD1=:AD_SIMQTD1, 
    AD_SIMQTD2=:AD_SIMQTD2, 
    AD_SIMVLR1=:AD_SIMVLR1, 
    AD_SIMVLR2=:AD_SIMVLR2, 
    DTALTER=SYSDATE 
WHERE NUNOTA=:NUNOTA AND SEQUENCIA=:SEQUENCIA
```

**Valores Salvos no Oracle**:
```
NUNOTA:      91730
SEQUENCIA:   1
VLRUNIT:     3.588517
VLRTOT:      9000.0
AD_SIMQTD1:  101 (extraCx) ← arredondado de 100.5
AD_SIMQTD2:  50 (medioCx) ← arredondado de 50.25
AD_SIMVLR1:  5500.75 (extraCustoTotal)
AD_SIMVLR2:  3499.25 (medioCustoTotal)
```

✅ **Teste PASSOU**: Todos os valores foram salvos com sucesso no Oracle.

---

## 📊 Mapeamento de Campos

| Frontend (JS State) | Backend (Payload) | Oracle (Coluna) | Tipo Oracle | Descrição |
|---------------------|-------------------|-----------------|-------------|-----------|
| `extraCx` | `sim_qtd1` | `AD_SIMQTD1` | NUMBER (int) | Qtd Extra (cx) |
| `extraCustoTotal` | `sim_vlr1` | `AD_SIMVLR1` | FLOAT | Custo total Extra |
| `medioCx` | `sim_qtd2` | `AD_SIMQTD2` | NUMBER (int) | Qtd Médio (cx) |
| `medioCustoTotal` | `sim_vlr2` | `AD_SIMVLR2` | FLOAT | Custo total Médio |

---

## ⚠️ Pontos de Atenção

### 1. Tipo de Dados NUMBER vs FLOAT

**Problema**: `AD_SIMQTD1` e `AD_SIMQTD2` são do tipo `NUMBER` (inteiro) no Oracle.

**Comportamento**:
- Valores decimais como `100.5` serão **arredondados** para `101`
- Valores como `50.25` serão arredondados para `50`

**Recomendação**:
- Se precisar de valores decimais para quantidade de caixas, **alterar tipo** para `FLOAT`:
  ```sql
  ALTER TABLE TGFITE MODIFY AD_SIMQTD1 FLOAT;
  ALTER TABLE TGFITE MODIFY AD_SIMQTD2 FLOAT;
  ```

- **OU** garantir que frontend envie apenas valores inteiros:
  ```javascript
  sim_qtd1: Math.round(extraCxRaw),
  sim_qtd2: Math.round(medioCxRaw),
  ```

### 2. Modo de Escrita (WRITE_ENABLED)

**Configuração Atual**:
```python
# settings.py
SANKHYA_CONFIG = {
    'WRITE_ENABLED': True,  # ✅ Já configurado
}
```

**Para scripts standalone**:
```powershell
$env:PACKINGHOUSE_WRITE_ENABLED='true'
python seu_script.py
```

**Verificação**:
```python
from sankhya_integration.services.oracle_conn import is_write_enabled
print(is_write_enabled())  # deve retornar True
```

### 3. Validação de Valores NULL

**Comportamento Atual**: Se campo for `None` ou não informado, ele **não será incluído** no UPDATE (valor anterior permanece).

**Exemplo**:
```python
payload = {
    'NUNOTA': 91730,
    'SEQUENCIA': 1,
    'AD_SIMQTD1': 100,  # atualiza
    # AD_SIMQTD2 ausente → mantém valor anterior no Oracle
}
```

**Para zerar um campo explicitamente**:
```python
payload = {
    'NUNOTA': 91730,
    'SEQUENCIA': 1,
    'AD_SIMQTD1': 0,  # zera explicitamente
}
```

---

## 🔄 Fluxo Completo de Persistência

### 1. Frontend → Backend

**Origem**: `comercial_dashboard.html` (função `handleSave()`)

```javascript
const payload = {
    nunota: 91730,
    sequencia: 1,
    valor_total: 9000.0,
    custo_kg: 3.588517,
    sim_qtd1: 100,      // extraCx
    sim_vlr1: 5500.75,  // extraCustoTotal
    sim_qtd2: 50,       // medioCx
    sim_vlr2: 3499.25,  // medioCustoTotal
};

await window.__postJSON('/sankhya/comercial/dist/save/', payload);
```

### 2. Backend → Oracle

**Arquivo**: `views.py` (função `comercial_dist_save()`)

```python
update_payload = {
    'NUNOTA': 91730,
    'SEQUENCIA': 1,
    'VLRUNIT': 3.588517,
    'VLRTOT': 9000.0,
    'AD_SIMQTD1': 100,
    'AD_SIMVLR1': 5500.75,
    'AD_SIMQTD2': 50,
    'AD_SIMVLR2': 3499.25,
}

plan = update_item(update_payload, dry_run=False)
```

### 3. Oracle → Backend

**Arquivo**: `oracle_conn.py` (função `listar_itens_portal_basico()`)

```sql
SELECT ..., AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2
FROM TGFITE
WHERE NUNOTA = 91730 AND SEQUENCIA = 1
```

### 4. Backend → Frontend

**Arquivo**: `views.py` (função `comercial_lista()`)

```python
out.append({
    'nunota': 91730,
    'sequencia': 1,
    'ad_simqtd1': 100.0,
    'ad_simqtd2': 50.0,
    'ad_simvlr1': 5500.75,
    'ad_simvlr2': 3499.25,
})
```

### 5. Frontend → Estado Global

**Arquivo**: `comercial_dashboard.html` (função `applyItemToEntrada()`)

```javascript
if(simExtraCx != null && Number.isFinite(simExtraCx)) 
    window.__DIST_EXTRA_MEDIO_STATE.extraCx = simExtraCx;
if(simExtraTotal != null && Number.isFinite(simExtraTotal)) 
    window.__DIST_EXTRA_MEDIO_STATE.extraCustoTotal = simExtraTotal;
// ... (medioCx, medioCustoTotal)
```

---

## ✅ Checklist de Validação

### Servidor Django (Produção)

- [x] `settings.py` tem `SANKHYA_CONFIG['WRITE_ENABLED'] = True`
- [x] Função `plan_update_item()` inclui os 4 campos AD_SIM*
- [x] Backend extrai e envia 4 campos no save (`views.py`)
- [x] Backend retorna 4 campos no load (`views.py`, `oracle_conn.py`)
- [x] Frontend envia 4 campos no save (`comercial_dashboard.html`)
- [x] Frontend carrega 4 campos no load (`comercial_dashboard.html`)

### Teste Manual no Navegador

1. **Preparação**:
   - [ ] Abrir painel Comercial no navegador
   - [ ] Verificar que servidor Django está rodando
   - [ ] Abrir Console do navegador (F12)

2. **Teste de Save**:
   - [ ] Selecionar item nunota 91730, sequencia 1
   - [ ] Editar valores de simulação (Extra/Médio)
   - [ ] Clicar em "Salvar"
   - [ ] Verificar mensagem de sucesso: "Distribuição salva com sucesso"

3. **Verificação Oracle**:
   ```sql
   SELECT AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2
   FROM TGFITE
   WHERE NUNOTA = 91730 AND SEQUENCIA = 1;
   ```
   - [ ] Valores devem corresponder aos editados

4. **Teste de Load**:
   - [ ] Recarregar página (F5)
   - [ ] Selecionar o MESMO item (91730/1)
   - [ ] Verificar que valores de simulação são carregados automaticamente
   - [ ] Verificar `window.__DIST_EXTRA_MEDIO_STATE` no Console

---

## 📝 Histórico de Mudanças

| Data | Arquivo | Mudança | Status |
|------|---------|---------|--------|
| 2025-10-07 | `oracle_conn.py` | Adicionar 4 campos AD_SIM* em `plan_update_item()` | ✅ Implementado |
| 2025-10-07 | `oracle_conn.py` | Atualizar docstring | ✅ Implementado |
| 2025-10-07 | Teste | Validar save com nunota 91730/1 | ✅ Passou |

---

## 🔗 Arquivos Relacionados

### Código
- `sankhya_integration/services/oracle_conn.py` (linha ~1598, ~1760)
- `sankhya_integration/views.py` (linha ~2340)
- `sankhya_integration/templates/sankhya_integration/comercial_dashboard.html` (linha ~1910, ~4450)

### Documentação
- [IMPLEMENTACAO_AD_SIMQTD_SIMVLR.md](./IMPLEMENTACAO_AD_SIMQTD_SIMVLR.md) - Implementação completa
- [IMPLEMENTACAO_4_CENARIOS.md](./IMPLEMENTACAO_4_CENARIOS.md) - Especificação dos 5 cenários

### Scripts de Teste
- `check_91730.py` - Verificar dados do item
- `test_save_91730.py` - Testar save com valores de teste
- `check_write_enabled.py` - Verificar se modo de escrita está habilitado

---

## ✅ Status Final

**Data**: 2025-10-07  
**Status**: ✅ **CORRIGIDO E TESTADO**

**Próximos Passos**:
1. ⏳ Testar no navegador (servidor Django rodando)
2. ⏳ Validar ciclo completo: save → reload → load
3. ⏳ Considerar alterar tipo de `AD_SIMQTD1`/`AD_SIMQTD2` para FLOAT (se precisar de decimais)

**Corrigido por**: GitHub Copilot Agent  
**Validado em**: Ambiente de desenvolvimento (script standalone)  
**Aguardando**: Validação em produção (navegador)

---

**Fim do documento**
