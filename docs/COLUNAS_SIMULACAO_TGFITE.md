# 📊 COLUNAS TGFITE PARA SIMULAÇÃO - Análise Complementar

**Data:** 2025-01-07  
**Objetivo:** Identificar colunas adicionais na TGFITE para salvar dados da simulação (simExtraCx, simExtraTotal, simMedioCx, simMedioTotal)

---

## ❗ SITUAÇÃO ATUAL

### **Já Utilizados:**
- ✅ `VLRUNIT` = Custo/kg Extra (extraCustoCx)
- ✅ `VLRTOT` = Valor Total (extraCustoTotal + medioCustoTotal)

### **Necessários:**
Precisamos de **4 colunas adicionais** para salvar:

| Campo Frontend | Descrição | Tipo | Exemplo |
|----------------|-----------|------|---------|
| `simExtraCx` | Quantidade de caixas Extra | NUMBER | 50 |
| `simExtraTotal` | Custo total do Extra | NUMBER | 3500.00 |
| `simMedioCx` | Quantidade de caixas Médio | NUMBER | 110 |
| `simMedioTotal` | Custo total do Médio | NUMBER | 3850.00 |

---

## 🔍 COLUNAS CANDIDATAS NA TGFITE

### **OPÇÃO 1: Campos Numéricos Pouco Usados (RECOMENDADO)**

#### **1. VLRDESCBONIF** (Valor Desconto Bonificação)
```sql
-- Tipo: NUMBER(15,2)
-- Uso: Desconto por bonificação (raramente usado)
-- Trigger: Apenas histórico (TRG_DLT_TGFITE linha 381)
```

**✅ USAR PARA:** `simExtraTotal` (Custo Total Extra)

**Motivos:**
- ✅ Campo numérico decimal (NUMBER 15,2)
- ✅ Apenas copiado em histórico de exclusão
- ✅ Não há cálculos automáticos
- ✅ Raramente utilizado no Sankhya

---

#### **2. VLRACRESCDESC** (Valor Acréscimo/Desconto)
```sql
-- Tipo: NUMBER(15,2)  
-- Uso: Acréscimos e descontos em notas fiscais
-- Trigger: TRG_DLT_TGFCAC_FLEX (apenas para notas fiscais específicas)
```

**✅ USAR PARA:** `simMedioTotal` (Custo Total Médio)

**Motivos:**
- ✅ Campo numérico decimal (NUMBER 15,2)
- ⚠️ Trigger existe, MAS:
  - Só funciona em contexto de nota fiscal (TGFCAC)
  - Não afeta nossa entrada de classificação
  - Verificação condicional: `IF (P_GRUPORETENCAO <> 'PARCEIRO' OR :OLD.VLRACRESCDESC > 0)`

**Validação Necessária:**
- ❓ Confirmar que não afeta TOP 7/71 (entrada/compra)
- ❓ Verificar se GRUPORETENCAO é aplicável ao nosso cenário

---

#### **3. VLRDESC** (Valor Desconto)
```sql
-- Tipo: NUMBER(15,2)
-- Uso: Valor de desconto no item
-- Trigger: Apenas histórico (TRG_DLT_TGFITE linha 378)
```

**⚠️ NÃO RECOMENDADO:**
- ❌ Campo muito usado no Sankhya
- ❌ Pode ter impacto em relatórios fiscais
- ❌ Usado em cálculos de ICMS/IPI

---

#### **4. PERCDESC** (Percentual Desconto)
```sql
-- Tipo: NUMBER(5,2)
-- Uso: Percentual de desconto
-- Trigger: Apenas histórico (TRG_DLT_TGFITE linha 381)
```

**✅ USAR PARA:** `simExtraCx` (Qtd Caixas Extra)

**Observação:**
- ⚠️ Tipo NUMBER(5,2) - limitado a 999.99
- ✅ Para quantidades de caixas é suficiente (até 999 caixas)
- ✅ Não é usado em cálculos automáticos

---

#### **5. VLRREPRED** (Valor Repartição Redução)
```sql
-- Tipo: NUMBER(15,2)
-- Uso: Específico para repartição de valores (fiscal)
-- Trigger: Apenas histórico (TRG_DLT_TGFITE linha 381)
```

**✅ USAR PARA:** `simMedioCx` (Qtd Caixas Médio)

**Motivos:**
- ✅ Campo raramente usado
- ✅ Sem triggers de cálculo
- ✅ Suficiente para quantidade de caixas

---

### **OPÇÃO 2: OBSERVACAO** (Campo Texto - Alternativa)

```sql
-- Tipo: VARCHAR2(4000)
-- Uso: Observações livres do item
-- Trigger: Apenas histórico
```

**Ideia: Salvar JSON estruturado**
```json
{
  "simulacao": {
    "extraCx": 50,
    "extraTotal": 3500.00,
    "medioCx": 110,
    "medioTotal": 3850.00,
    "dataCalculo": "2025-01-07T10:30:00",
    "usuario": "COMERCIAL"
  }
}
```

**Prós:**
- ✅ Totalmente flexível
- ✅ Pode adicionar mais campos no futuro
- ✅ Não conflita com outros campos

**Contras:**
- ❌ Precisa parsear JSON
- ❌ Não é consultável via SQL puro
- ❌ Pode ser sobrescrito por usuários

---

## 🎯 RECOMENDAÇÃO FINAL

### **✅ MAPEAMENTO RECOMENDADO:**

| Campo Frontend | Campo TGFITE | Tipo | Justificativa |
|----------------|--------------|------|---------------|
| `simExtraCx` | `PERCDESC` | NUMBER(5,2) | Pouco usado, sem triggers, suficiente para qtd |
| `simExtraTotal` | `VLRDESCBONIF` | NUMBER(15,2) | Raramente usado, sem cálculos |
| `simMedioCx` | `VLRREPRED` | NUMBER(15,2) | Raramente usado, sem triggers |
| `simMedioTotal` | `VLRACRESCDESC` | NUMBER(15,2) | Trigger só para notas fiscais específicas |

**VALIDAR:**
- ⚠️ `VLRACRESCDESC` - Confirmar que trigger não afeta TOP 7/71

---

### **✅ ALTERNATIVA SEGURA (100% sem conflitos):**

| Campo Frontend | Campo TGFITE | Tipo | Justificativa |
|----------------|--------------|------|---------------|
| `simExtraCx` | `VLRREPRED` | NUMBER(15,2) | Raramente usado, sem triggers |
| `simExtraTotal` | `VLRDESCBONIF` | NUMBER(15,2) | Raramente usado, sem triggers |
| `simMedioCx` | `PERCDESC` | NUMBER(5,2) | Sem triggers, suficiente |
| `simMedioTotal` | **OBSERVACAO** | VARCHAR2 | JSON estruturado, 100% seguro |

**Exemplo OBSERVACAO:**
```json
{"sim":{"mCx":110,"mTot":3850.00}}
```

---

## 📋 IMPLEMENTAÇÃO

### **1. Backend (views.py)**

```python
def comercial_dist_save(request: HttpRequest) -> JsonResponse:
    # ... código existente ...
    
    # Novos campos
    sim_extra_cx = _to_float_or(payload.get('sim_extra_cx'))
    sim_extra_total = _to_float_or(payload.get('sim_extra_total'))
    sim_medio_cx = _to_float_or(payload.get('sim_medio_cx'))
    sim_medio_total = _to_float_or(payload.get('sim_medio_total'))
    
    update_payload = {
        'NUNOTA': nunota,
        'SEQUENCIA': sequencia,
        'VLRUNIT': custo_kg,
        'VLRTOT': total,
        # Novos campos
        'PERCDESC': sim_extra_cx,      # simExtraCx
        'VLRDESCBONIF': sim_extra_total, # simExtraTotal
        'VLRREPRED': sim_medio_cx,      # simMedioCx
        'VLRACRESCDESC': sim_medio_total, # simMedioTotal
    }
    
    # ... resto do código ...
```

### **2. Frontend (comercial_dashboard.html)**

```javascript
// Ao salvar
const payload = {
  nunota: nunota,
  sequencia: sequencia,
  valor_total: valorTotal,
  custo_kg: custoKg,
  // Novos campos
  sim_extra_cx: state.extraCx,
  sim_extra_total: state.extraCustoTotal,
  sim_medio_cx: state.medioCx,
  sim_medio_total: state.medioCustoTotal
};

// Ao carregar
item.sim_extra_cx = item.percdesc;
item.sim_extra_total = item.vlrdescbonif;
item.sim_medio_cx = item.vlrrepred;
item.sim_medio_total = item.vlracrescdesc;
```

### **3. Query de Carregamento (views.py)**

```python
# Adicionar aos SELECTs existentes:
"""
SELECT 
    i.NUNOTA,
    i.SEQUENCIA,
    i.QTDNEG,
    i.VLRUNIT,
    i.VLRTOT,
    i.PERCDESC,      -- simExtraCx
    i.VLRDESCBONIF,  -- simExtraTotal  
    i.VLRREPRED,     -- simMedioCx
    i.VLRACRESCDESC  -- simMedioTotal
FROM TGFITE i
WHERE i.NUNOTA = :nunota
  AND i.SEQUENCIA = :seq
"""
```

---

## 🚨 VALIDAÇÕES NECESSÁRIAS

### **1. Testar VLRACRESCDESC com TOP 7/71**

```sql
-- Verificar se trigger TRG_DLT_TGFCAC_FLEX afeta entrada
SELECT 
    c.NUNOTA,
    c.CODTIPOPER,
    c.TIPMOV,
    i.VLRACRESCDESC
FROM TGFCAB c
JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
WHERE c.CODTIPOPER IN (7, 71)
  AND i.VLRACRESCDESC <> 0;
```

### **2. Verificar Uso Atual dos Campos**

```sql
-- Verificar se algum item já usa esses campos
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN PERCDESC <> 0 THEN 1 END) as percdesc_usado,
    COUNT(CASE WHEN VLRDESCBONIF <> 0 THEN 1 END) as vlrdescbonif_usado,
    COUNT(CASE WHEN VLRREPRED <> 0 THEN 1 END) as vlrrepred_usado,
    COUNT(CASE WHEN VLRACRESCDESC <> 0 THEN 1 END) as vlracrescdesc_usado
FROM TGFITE
WHERE CODTIPOPER IN (7, 71);
```

---

## 🔄 PLANO B: Usar Campos AD_ (Customizados)

Se houver conflito, criar colunas customizadas:

```sql
-- Executar no Oracle (requer DBA)
ALTER TABLE TGFITE ADD (
  AD_SIM_EXTRA_CX NUMBER(15,3),
  AD_SIM_EXTRA_TOTAL NUMBER(15,2),
  AD_SIM_MEDIO_CX NUMBER(15,3),
  AD_SIM_MEDIO_TOTAL NUMBER(15,2)
);

COMMENT ON COLUMN TGFITE.AD_SIM_EXTRA_CX IS 'Simulacao: Qtd Caixas Extra';
COMMENT ON COLUMN TGFITE.AD_SIM_EXTRA_TOTAL IS 'Simulacao: Custo Total Extra';
COMMENT ON COLUMN TGFITE.AD_SIM_MEDIO_CX IS 'Simulacao: Qtd Caixas Medio';
COMMENT ON COLUMN TGFITE.AD_SIM_MEDIO_TOTAL IS 'Simulacao: Custo Total Medio';
```

**Prós:**
- ✅ 100% sem conflitos
- ✅ Zero risco de triggers
- ✅ Nomes descritivos

**Contras:**
- ❌ Requer ALTER TABLE (permissão DBA)
- ❌ Não aparece em telas padrão Sankhya

---

## ✅ DECISÃO RECOMENDADA

### **ABORDAGEM HÍBRIDA:**

1. **COMEÇAR com campos nativos** (PERCDESC, VLRDESCBONIF, VLRREPRED, VLRACRESCDESC)
2. **VALIDAR** em ambiente de testes
3. **SE houver conflito**, migrar para campos AD_ customizados

### **Próximos Passos:**

1. ✅ Executar queries de validação (verificar uso atual)
2. ✅ Testar salvamento em ambiente de DEV
3. ✅ Verificar se trigger VLRACRESCDESC afeta TOP 7/71
4. ✅ Implementar backend e frontend
5. ✅ Testar ciclo completo (salvar → carregar → exibir)

---

## 📚 REFERÊNCIAS

- `sankhya_integration/triggers/triggers/SANKHYA.TRG_DLT_TGFITE.sql`
- `sankhya_integration/triggers/triggers/SANKHYA.TRG_DLT_TGFCAC_FLEX.sql`
- `sankhya_integration/views.py` (linha 2340-2390)
- `docs/ANALISE_TGFITE_SIMULACAO.md` (análise anterior)

---

**Aguardando validação das queries antes de prosseguir com implementação!** 🚀
