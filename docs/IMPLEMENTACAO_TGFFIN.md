# 📋 IMPLEMENTAÇÃO TGFFIN - REGISTRO FINANCEIRO

## 🎯 OBJETIVO

Criar registro financeiro (TGFFIN) automaticamente ao clicar no botão **FATURAR** do `modalFaturamento`.

---

## ✅ IMPLEMENTADO

### **1. Parâmetros Configuráveis** (`oracle_conn.py`)

Adicionados em `DEFAULT_PARAMS`:

```python
'FINANCEIRO_BANCO_PADRAO': 33,          # CODBCO
'FINANCEIRO_CONTA_BANCARIA': 2,         # CODCTABCOINT
'FINANCEIRO_TIPO_TITULO': 13,           # CODTIPTIT
'FINANCEIRO_DIAS_VENCIMENTO': 30,       # Dias para vencimento
```

**Configuração via Django settings:**
```python
# settings.py
SANKHYA_CONFIG = {
    'PARAMS': {
        'FINANCEIRO_BANCO_PADRAO': 33,
        'FINANCEIRO_CONTA_BANCARIA': 2,
        'FINANCEIRO_TIPO_TITULO': 13,
        'FINANCEIRO_DIAS_VENCIMENTO': 30,
    }
}
```

---

### **2. Função `criar_tgffin`** (`oracle_conn.py`)

**Localização:** `sankhya_integration/services/oracle_conn.py` (linha ~4217)

**Assinatura:**
```python
def criar_tgffin(nunota_vale: int) -> Dict[str, Any]
```

**Parâmetros:**
- `nunota_vale`: NUNOTA do TOP 13 (vale de compra)

**Retorno:**
```python
{
    'ok': bool,           # True se sucesso
    'nufin': int,         # ID do financeiro gerado
    'vlrdesdob': float,   # Valor do desdobramento
    'dtvenc': str,        # Data de vencimento (DD/MM/YYYY)
    'error': str          # Mensagem de erro (se houver)
}
```

**Características:**
- ✅ Baseada na **Etapa 7** do rastreamento Sankhya
- ✅ Insere **67 colunas** conforme rastreamento
- ✅ Valores 0 são enviados como 0 (não NULL)
- ✅ Campos vazios/NULL são enviados como NULL
- ✅ `FINCONFIRMADO = 'S'` (já confirmado)
- ✅ `AUTORIZADO = 'N'` (não autorizado)
- ✅ Vencimento baseado em `DTFATUR` + dias configurados
- ✅ Parâmetros configuráveis via `get_params()`
- ✅ Logging detalhado

---

### **3. Integração no Endpoint** (`views.py`)

**Localização:** `sankhya_integration/views.py` - função `comercial_vale_save`

**Fluxo atualizado:**

```python
if faturar:
    # 1. Alterar STATUSNOTA para 'L' (Liberado)
    plan_h = update_cabecalho({'NUNOTA': nunota, 'STATUSNOTA': 'L'})
    
    if plan_h.get('executed'):
        # 2. CRIAR TGFFIN (Financeiro)
        nufin_result = criar_tgffin(nunota)
        
        if not nufin_result.get('ok'):
            # Erro ao criar TGFFIN - reportar mas manter TGFCAB
            errors.append(f'TGFFIN: {nufin_result.get("error")}')
```

**Estratégia de Rollback:**
- ✅ Se TGFFIN falhar → Manter TGFCAB alterado (STATUSNOTA='L')
- ✅ Reportar erro no response
- ✅ Log detalhado do erro

---

### **4. Response Atualizado**

**Antes:**
```json
{
  "ok": true,
  "updated": [1, 2, 3],
  "errors": null,
  "header": {"executed": true, "status": "L"}
}
```

**Depois:**
```json
{
  "ok": true,
  "updated": [1, 2, 3],
  "errors": null,
  "header": {"executed": true, "status": "L"},
  "financeiro": {
    "criado": true,
    "nufin": 418801,
    "vlrdesdob": 4000.0,
    "dtvenc": "10/11/2025",
    "error": null
  }
}
```

---

## 🧪 TESTE

**Script:** `test_criar_tgffin.py`

**Executar:**
```bash
python test_criar_tgffin.py
```

**O que testa:**
1. ✅ Verifica se NUNOTA existe
2. ✅ Verifica se já existe TGFFIN
3. ✅ Cria novo registro TGFFIN
4. ✅ Valida campos inseridos:
   - CODBCO = 33
   - CODCTABCOINT = 2
   - CODTIPTIT = 13
   - FINCONFIRMADO = 'S'
   - AUTORIZADO = 'N'
   - RECDESP = 'E'
   - PROVISAO = 'A'

---

## 📊 MAPEAMENTO DE COLUNAS

### **Colunas TGFFIN (67 campos não vazios)**

| Coluna | Valor | Origem | Observação |
|--------|-------|--------|------------|
| **NUFIN** | Sequence | `SQ_TGFFIN_NUFIN.NEXTVAL` ou `MAX+1` | Chave primária |
| **CODEMP** | Variável | `TGFCAB.CODEMP` | Empresa |
| **NUMNOTA** | Variável | `TGFCAB.NUMNOTA` | Número da nota |
| **DTNEG** | Variável | `TGFCAB.DTNEG` ou `SYSDATE` | Data negociação |
| **DESDOBRAMENTO** | 1 | Fixo | Primeira parcela |
| **DHMOV** | SYSDATE | Sistema | Data/hora movimento |
| **DTVENCINIC** | Calculado | `DTFATUR + 30 dias` | Vencimento inicial |
| **DTVENC** | Calculado | Mesmo que `DTVENCINIC` | Vencimento |
| **CODPARC** | Variável | `TGFCAB.CODPARC` | Parceiro |
| **CODTIPOPER** | Variável | `TGFCAB.CODTIPOPER` | Tipo operação (13) |
| **DHTIPOPER** | Variável | `TGFTOP.DHALTER` | Data/hora tipo operação |
| **CODBCO** | **33** | **Parâmetro** | Banco padrão |
| **CODCTABCOINT** | **2** | **Parâmetro** | Conta bancária |
| **CODNAT** | Variável | `TGFCAB.CODNAT` | Natureza operação |
| **CODCENCUS** | Variável | `TGFCAB.CODCENCUS` | Centro de custo |
| **CODPROJ** | 0 | Fixo | Sem projeto |
| **CODVEND** | 0 | Fixo | Sem vendedor |
| **CODMOEDA** | 0 | Fixo | Real (BRL) |
| **CODTIPTIT** | **13** | **Parâmetro** | Tipo título |
| **VLRDESDOB** | Variável | `TGFCAB.VLRNOTA` | Valor do desdobramento |
| **VLRVENDOR** | 0 | Fixo | Sem vendedor |
| **VLRIRF** | 0 | Fixo | Sem IRRF |
| **VLRISS** | 0 | Fixo | Sem ISS |
| **DESPCART** | 0 | Fixo | Sem despesa cartório |
| **ISSRETIDO** | N | Fixo | ISS não retido |
| **VLRDESC** | 0 | Fixo | Sem desconto |
| **VLRMULTA** | 0 | Fixo | Sem multa |
| **VLRINSS** | 0 | Fixo | Sem INSS |
| **TIPMULTA** | 1 | Fixo | Tipo multa padrão |
| **VLRJURO** | 0 | Fixo | Sem juros |
| **TIPJURO** | 1 | Fixo | Tipo juros padrão |
| **BASEICMS** | 0 | Fixo | Sem ICMS |
| **ALIQICMS** | 0 | Fixo | Sem alíquota ICMS |
| **DHTIPOPERBAIXA** | 01/01/1998 | Fixo | Data tipo operação baixa |
| **VLRBAIXA** | 0 | Fixo | Não baixado |
| **AUTORIZADO** | **N** | **Fixo (Etapa 7)** | Não autorizado |
| **RECDESP** | E | Fixo | Entrada (despesa) |
| **PROVISAO** | A | Fixo | À aprovar |
| **ORIGEM** | Variável | `NUNOTA` do TOP 13 | Origem |
| **NUNOTA** | Variável | `NUNOTA` do TOP 13 | Nota vinculada |
| **RATEADO** | N | Fixo | Não rateado |
| **DTENTSAI** | Variável | `TGFCAB.DTENTSAI` | Data entrada/saída |
| **VLRPROV** | 0 | Fixo | Sem provisão |
| **IRFRETIDO** | S | Fixo | IRF retido |
| **INSSRETIDO** | S | Fixo | INSS retido |
| **CARTAODESC** | 0 | Fixo | Sem desconto cartão |
| **DTALTER** | SYSDATE | Sistema | Data alteração |
| **NUMCONTRATO** | 0 | Fixo | Sem contrato |
| **ORDEMCARGA** | 0 | Fixo | Sem ordem carga |
| **CODVEICULO** | 0 | Fixo | Sem veículo |
| **CODUSU** | 0 | Fixo | Usuário (pode adicionar) |
| **SEQUENCIA** | 1 | Fixo | Sequência parcela |
| **VLRDESCEMBUT** | 0 | Fixo | Desconto embutido |
| **VLRJUROEMBUT** | 0 | Fixo | Juros embutidos |
| **VLRMULTAEMBUT** | 0 | Fixo | Multa embutida |
| **VLRMOEDA** | 0 | Fixo | Valor moeda estrangeira |
| **VLRMOEDABAIXA** | 0 | Fixo | Valor moeda na baixa |
| **VLRMULTANEGOC** | 0 | Fixo | Multa negociada |
| **VLRJURONEGOC** | 0 | Fixo | Juros negociados |
| **VLRMULTALIB** | 0 | Fixo | Multa liberada |
| **VLRJUROLIB** | 0 | Fixo | Juros liberados |
| **VLRALIBERAR** | 0 | Fixo | Valor a liberar |
| **DTPRAZO** | Calculado | Mesmo que `DTVENC` | Data prazo |
| **FINCONFIRMADO** | **S** | **Fixo (Etapa 7)** | Confirmado |
| **VLRGNREDOIS** | 0 | Fixo | Sem GNRE |
| **RECEBIDO** | S | Fixo | Recebido |
| **VLRDESDOBCALC** | 0 | Fixo | Valor calculado |
| **NUMOCORRENCIAS** | 0 | Fixo | Sem ocorrências |

---

## 🔍 DECISÕES DE IMPLEMENTAÇÃO

### **1. Parâmetros Configuráveis**
✅ **DECISÃO:** Via tabela de parâmetros (`get_params()`)
- CODBCO = 33
- CODCTABCOINT = 2
- CODTIPTIT = 13

### **2. Vencimento**
✅ **DECISÃO:** Usar `DTFATUR` + dias configurados (padrão: 30 dias)

### **3. Valores 0 vs NULL**
✅ **DECISÃO:** Enviar exatamente como no rastreamento
- Valores 0 → Enviar 0
- Valores vazios/NULL → Enviar NULL

### **4. Estado do Financeiro**
✅ **DECISÃO:** Replicar **Etapa 7** (já confirmado)
- `FINCONFIRMADO = 'S'`
- `AUTORIZADO = 'N'`

### **5. Tratamento de Erro**
✅ **DECISÃO:** Rollback somente de TGFFIN
- Manter TGFCAB alterado (STATUSNOTA='L')
- Reportar erro no response
- Log detalhado

---

## 📝 PRÓXIMOS PASSOS

1. ✅ **Implementação concluída**
2. ⏳ **Testar em desenvolvimento** (`test_criar_tgffin.py`)
3. ⏳ **Testar fluxo completo** (Frontend → Backend → TGFFIN)
4. ⏳ **Validar com rastreamento Sankhya**
5. ⏳ **Deploy em produção**

---

## 🐛 TROUBLESHOOTING

### **Erro: "Escrita desabilitada no sistema"**
**Solução:** Verificar flag `WRITE_ENABLED` em `oracle_conn.py`

### **Erro: "NUNOTA não encontrada"**
**Solução:** Verificar se o TOP 13 existe antes de chamar `criar_tgffin`

### **Erro: "Sequence não existe"**
**Solução:** Sistema usa fallback automático para `MAX(NUFIN)+1`

### **Valores incorretos (CODBCO, CODTIPTIT, etc.)**
**Solução:** Ajustar parâmetros em `DEFAULT_PARAMS` ou `settings.py`

---

## 📚 REFERÊNCIAS

- **Rastreamento Sankhya:** `Rastreamento Banco Sankhya.txt`
- **Etapa 7:** TGFFIN confirmado (67 colunas não vazias)
- **Código:** `sankhya_integration/services/oracle_conn.py` - função `criar_tgffin`
- **View:** `sankhya_integration/views.py` - função `comercial_vale_save`
- **Teste:** `test_criar_tgffin.py`

---

**Última atualização:** 20/10/2025
**Versão:** 1.0
**Status:** ✅ Implementado
