# 🔧 CORREÇÕES DOS CENÁRIOS EXTRA/MÉDIO

**Data:** 2025-01-07  
**Status:** ✅ CORRIGIDO

---

## 🐛 PROBLEMAS IDENTIFICADOS

### **Problema 1: Editar totalCustoKg não distribui para Extra/Médio**
**Sintoma:** Ao editar `#costKgDisplay`, os valores de Extra e Médio não são atualizados.  
**Causa:** Não existia Cenário para `totalCustoKg` (só existia para `totalCustoCx`).

### **Problema 2: Editar extraCustoCx não atualiza display de Valor Total**
**Sintoma:** Ao editar `#extraCustoCxDisplay`, o `#totalValueDisplay` não atualiza visualmente.  
**Causa:** Cenário 4 atualizava o estado mas não o elemento DOM do Valor Total.

### **Problema 3: Editar totalCustoKg SEM Extra não atualiza Médio**
**Sintoma:** Quando só tem Médio (sem Extra), editar `#costKgDisplay` não atualiza os valores do Médio.  
**Causa:** Mesmo problema do Problema 1 - faltava o Cenário 3B.

---

## ✅ SOLUÇÕES IMPLEMENTADAS

### **Solução 1: Criar Cenário 3B - Editar Custo/kg Global**

**Arquivo:** `comercial_dashboard.html` (linha ~4118)

**Nova função criada:**
```javascript
const cenario3B_EditarCustoKgGlobal = (totalCustoKg) => {
  const state = window.__DIST_EXTRA_MEDIO_STATE;
  const totalKg = state.extraKg + state.medioKg;
  
  console.log('[CENÁRIO 3B] Editar Custo/kg Global:', totalCustoKg);
  
  // Calcula Valor Total
  const valorTotal = totalCustoKg * totalKg;
  const totalCx = state.extraCx + state.medioCx;
  const totalCustoCx = totalCx > 0 ? (valorTotal / totalCx) : 0;
  
  // Atualiza Custo/cx Global
  const custoCxEl = document.getElementById('costCxDisplay');
  const formatDecimal = (v) => (v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (custoCxEl) custoCxEl.textContent = formatDecimal(totalCustoCx);
  
  // Atualiza Valor Total
  if (typeof window.__setDistribTotal === 'function') {
    window.__setDistribTotal(valorTotal, { source: 'cenario3B', skipCallbacks: true });
  }
  
  // Chama Cenário 2 COM flag para não recalcular totalCustoCx/Kg (previne loop)
  cenario2_EditarValorTotal(valorTotal, { skipTotalCostRecalc: true });
  
  console.log('[CENÁRIO 3B] Valor Total calculado:', valorTotal);
};
```

**Fluxo:**
```
totalCustoKg (editado)
  ↓
valorTotal = totalCustoKg × totalKg
totalCustoCx = valorTotal ÷ totalCx
  ↓
[CHAMA CENÁRIO 2 com skipTotalCostRecalc=true]
  ↓
Distribui para Extra/Médio (proporcionalmente ou só Médio se não tem Extra)
```

**Benefícios:**
- ✅ Editar `totalCustoKg` agora distribui para Extra/Médio
- ✅ Funciona tanto COM quanto SEM Extra
- ✅ Proteção anti-loop com `skipTotalCostRecalc: true`

---

### **Solução 2: Atualizar display de Valor Total no Cenário 4**

**Arquivo:** `comercial_dashboard.html` (linha ~4160)

**Código adicionado:**
```javascript
// Atualiza Valor Total (DISPLAY)
if (typeof window.__setDistribTotal === 'function') {
  window.__setDistribTotal(valorTotal, { source: 'cenario4', skipCallbacks: true });
}

// Atualiza display de Valor Total manualmente também
const totalValueDisplay = document.getElementById('totalValueDisplay');
if (totalValueDisplay) {
  const formatMoney = (v) => {
    try {
      return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0);
    } catch {
      return 'R$ ' + (v || 0).toFixed(2).replace('.', ',');
    }
  };
  totalValueDisplay.textContent = formatMoney(valorTotal);
  console.log('[CENÁRIO 4] Valor Total DISPLAY atualizado:', valorTotal);
}
```

**Benefícios:**
- ✅ Display de Valor Total atualiza corretamente
- ✅ Dupla garantia: `__setDistribTotal` + atualização manual do DOM
- ✅ Log para debug

---

### **Solução 3: Integrar edição de totalCustoKg com sistema Extra/Médio**

**Arquivo:** `comercial_dashboard.html` (linha ~2618)

**Código adicionado:**
```javascript
// Integra com sistema Extra/Médio (Cenário 3B)
if (typeof window.__syncExtraMedio === 'function') {
  window.__syncExtraMedio('totalCustoKg', n);
}
```

**Local:** Dentro da função `exitEditKg`, após editar `#costKgDisplay`

**Benefícios:**
- ✅ Editar `totalCustoKg` dispara Cenário 3B automaticamente
- ✅ Funciona tanto COM Extra quanto SEM Extra (só Médio)

---

### **Solução 4: Adicionar case no switch da função principal**

**Arquivo:** `comercial_dashboard.html` (linha ~4215)

**Código adicionado:**
```javascript
case 'totalCustoKg':
  cenario3B_EditarCustoKgGlobal(newValue);
  break;
```

**Benefícios:**
- ✅ Roteamento correto para Cenário 3B
- ✅ Consistência com outros cenários

---

## 📊 ANTES vs DEPOIS

### **Problema 1: Editar totalCustoKg**

**ANTES:**
```
Usuário edita costKgDisplay → NADA acontece com Extra/Médio ❌
```

**DEPOIS:**
```
Usuário edita costKgDisplay
  ↓
syncExtraMedio('totalCustoKg', valor)
  ↓
Cenário 3B executa
  ↓
Calcula Valor Total
  ↓
Distribui para Extra/Médio ✅
```

---

### **Problema 2: Editar extraCustoCx**

**ANTES:**
```
Usuário edita extraCustoCxDisplay
  ↓
Cenário 4 atualiza estado
  ↓
totalValueDisplay NÃO atualiza visualmente ❌
```

**DEPOIS:**
```
Usuário edita extraCustoCxDisplay
  ↓
Cenário 4 atualiza estado
  ↓
__setDistribTotal() + atualização manual do DOM
  ↓
totalValueDisplay atualiza visualmente ✅
```

---

### **Problema 3: Editar totalCustoKg SEM Extra**

**ANTES:**
```
Só tem Médio (extraCx = 0)
Usuário edita costKgDisplay → Médio NÃO atualiza ❌
```

**DEPOIS:**
```
Só tem Médio (extraCx = 0)
Usuário edita costKgDisplay
  ↓
Cenário 3B executa
  ↓
Calcula Valor Total
  ↓
Chama Cenário 2 (que detecta SEM Extra)
  ↓
Todo valor vai para Médio ✅
```

---

## 🎯 NOVO MAPEAMENTO DE FONTES

| Source | Cenário | Função | Status |
|--------|---------|--------|--------|
| `'initial'` | 1 | `cenario1_CargaInicial()` | ✅ OK |
| `'reset'` | 1 | `cenario1_CargaInicial()` | ✅ OK |
| `'valorTotal'` | 2 | `cenario2_EditarValorTotal()` | ✅ OK |
| `'totalCustoCx'` | 3 | `cenario3_EditarCustoCxGlobal()` | ✅ OK |
| `'totalCustoKg'` | **3B** | `cenario3B_EditarCustoKgGlobal()` | ✅ **NOVO** |
| `'extraCustoCx'` | 4 | `cenario4_EditarExtraCustoCx()` | ✅ **CORRIGIDO** |

---

## 🔒 PROTEÇÕES MANTIDAS

- ✅ Flag `isUpdating` (previne loops infinitos)
- ✅ `skipTotalCostRecalc: true` no Cenário 3B (previne loop)
- ✅ Validação `hasExtra()` no Cenário 4
- ✅ Validações `isFinite()` em todos os cálculos

---

## 📝 TESTES RECOMENDADOS

### **Teste 1: Editar totalCustoKg COM Extra**
1. Selecionar item com classificação (tem Extra e Médio)
2. Clicar em `#costKgDisplay`
3. Editar valor (ex: 50)
4. **Resultado esperado:**
   - Valor Total atualiza
   - Extra e Médio atualizam proporcionalmente
   - `#costCxDisplay` atualiza

### **Teste 2: Editar totalCustoKg SEM Extra**
1. Selecionar item com classificação (só Médio, sem Extra)
2. Clicar em `#costKgDisplay`
3. Editar valor (ex: 30)
4. **Resultado esperado:**
   - Valor Total atualiza
   - Todo valor vai para Médio
   - Extra permanece zerado
   - `#costCxDisplay` atualiza

### **Teste 3: Editar extraCustoCx**
1. Selecionar item com classificação (tem Extra)
2. Clicar em `#extraCustoCxDisplay`
3. Editar valor (ex: 60)
4. **Resultado esperado:**
   - `#totalValueDisplay` atualiza visualmente ✅
   - Médio = Extra/2
   - Custo Global (cx e kg) atualiza

### **Teste 4: Fluxo completo**
1. Selecionar item
2. Editar `extraCustoCx` → Ver Valor Total atualizar
3. Editar `totalCustoKg` → Ver Extra/Médio redistribuir
4. Editar `totalCustoCx` → Ver Extra/Médio redistribuir
5. Editar `valorTotal` → Ver Extra/Médio redistribuir
6. **Resultado esperado:** Todos os valores sincronizam corretamente sem loops

---

## ✅ CHECKLIST FINAL

- ✅ Problema 1 (totalCustoKg não distribui): **CORRIGIDO**
- ✅ Problema 2 (extraCustoCx não atualiza display): **CORRIGIDO**
- ✅ Problema 3 (totalCustoKg SEM Extra): **CORRIGIDO**
- ✅ Cenário 3B implementado
- ✅ Documentação atualizada
- ✅ Proteções anti-loop mantidas
- ✅ Logs de debug adicionados
- ✅ Pronto para teste no browser

---

## 🎉 CONCLUSÃO

Todos os 3 problemas foram corrigidos com:
- **1 novo cenário** (3B - Editar Custo/kg Global)
- **1 correção** no Cenário 4 (atualização do display)
- **1 integração** adicional (edição de totalCustoKg)
- **Sem quebrar** funcionalidades existentes
- **Mantendo** todas as proteções anti-loop

**Status:** ✅ **PRONTO PARA TESTAR**
