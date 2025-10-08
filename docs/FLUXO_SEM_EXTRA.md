# 📊 FLUXO DE CARREGAMENTO - ITENS SEM EXTRA (Só Médio)

**Data:** 2025-01-07  
**Cenário:** Item com classificação que NÃO possui produto Extra (extraCx = 0 ou extraKg = 0)

---

## 🔍 DETECÇÃO: Quando NÃO tem Extra?

### **Função:** `hasExtra()`
```javascript
const hasExtra = () => {
  const state = window.__DIST_EXTRA_MEDIO_STATE;
  return state.extraCx > 0 || state.extraKg > 0;
};
```

**Retorna:**
- `true` = Tem Extra (extraCx > 0 OU extraKg > 0)
- `false` = NÃO tem Extra (extraCx = 0 E extraKg = 0)

---

## 📥 FLUXO DE CARREGAMENTO (CENÁRIO 1)

### **1. GATILHO**
```
Usuário seleciona item
  ↓
Classificação é carregada
  ↓
renderClassCardsFromClassification() detecta:
  - extraCx = 0 (sem produto "EXTRA")
  - medioCx > 0 (tem produto "MÉDIO")
  ↓
Chama: window.__syncExtraMedio('initial')
```

---

### **2. CENÁRIO 1 - Carga Inicial**

#### **2.1. Verifica se tem Extra**
```javascript
if (hasExtra()) {
  // ❌ NÃO entra aqui (extraCx = 0)
} else {
  // ✅ Entra aqui - SEM Extra
  calcMedioSemExtra();
}
```

---

### **2.2. Função `calcMedioSemExtra()`**

**Código:**
```javascript
const calcMedioSemExtra = () => {
  const state = window.__DIST_EXTRA_MEDIO_STATE;
  
  // 1. ZERA EXTRA
  state.extraCustoCx = 0;
  state.extraCustoTotal = 0;
  state.extraCustoKg = 0;
  
  // 2. CALCULA MÉDIO com precoBase/2
  if (state.precoBase > 0) {
    state.medioCustoCx = state.precoBase / 2;  ← REGRA ESPECIAL!
  } else {
    state.medioCustoCx = 0;
  }
  
  // 3. Assume cx = kg (quando não tem Extra como referência)
  state.medioCustoKg = state.medioCustoCx;
  
  // 4. Calcula Custo Total do Médio
  if (state.medioCx > 0) {
    state.medioCustoTotal = state.medioCx * state.medioCustoCx;
  } else if (state.medioKg > 0) {
    state.medioCustoTotal = state.medioKg * state.medioCustoKg;
  } else {
    state.medioCustoTotal = 0;
  }
};
```

**Fluxo Visual:**
```
precoBase (ex: 100)
  ↓
ZERA EXTRA:
  extraCustoCx = 0
  extraCustoTotal = 0
  extraCustoKg = 0
  ↓
CALCULA MÉDIO:
  medioCustoCx = precoBase ÷ 2 = 50
  medioCustoKg = medioCustoCx = 50  (assume cx = kg)
  ↓
SE medioCx > 0:
  medioCustoTotal = medioCx × medioCustoCx
  (ex: 10 cx × 50 = 500)
  ↓
SENÃO SE medioKg > 0:
  medioCustoTotal = medioKg × medioCustoKg
  (ex: 200 kg × 50 = 10.000)
```

---

### **2.3. Calcula Valor Total e Custo Global**

```javascript
// Valor Total = Extra + Médio
const valorTotal = state.extraCustoTotal + state.medioCustoTotal;
// valorTotal = 0 + 500 = 500 (ou 0 + 10.000 = 10.000)

const totalCx = state.extraCx + state.medioCx;
const totalKg = state.extraKg + state.medioKg;

const totalCustoCx = totalCx > 0 ? (valorTotal / totalCx) : 0;
// totalCustoCx = 500 ÷ 10 = 50

const totalCustoKg = totalKg > 0 ? (valorTotal / totalKg) : 0;
// totalCustoKg = 10.000 ÷ 200 = 50
```

**Fluxo Visual:**
```
medioCustoTotal = 500 (ou 10.000)
  ↓
valorTotal = 0 + 500 = 500
  ↓
totalCustoCx = 500 ÷ 10 cx = 50
totalCustoKg = 500 ÷ (10 cx × 20 kg/cx) = 2,5  (se kg informado)
```

---

### **2.4. Atualiza UI**

```javascript
// 1. Cards Extra e Médio
updateExtraCard();  // Mostra tudo zerado
updateMedioCard();  // Mostra valores do Médio

// 2. Valor Total
window.__setDistribTotal(valorTotal, { source: 'cenario1', skipCallbacks: true });

// 3. Custo Global
costCxDisplay.textContent = formatDecimal(totalCustoCx);
costKgDisplay.textContent = formatDecimal(totalCustoKg);
```

---

## 📊 EXEMPLO COMPLETO

### **Dados de Entrada:**
```javascript
// Item selecionado
precoBase = 100

// Classificação (só Médio)
extraCx = 0
extraKg = 0
medioCx = 10
medioKg = 200
```

### **Processamento:**
```
1. hasExtra() → false (extraCx = 0)
   ↓
2. calcMedioSemExtra()
   ↓
   extraCustoCx = 0
   extraCustoTotal = 0
   extraCustoKg = 0
   ↓
   medioCustoCx = 100 ÷ 2 = 50
   medioCustoKg = 50
   medioCustoTotal = 10 × 50 = 500
   ↓
3. Calcula Totais
   ↓
   valorTotal = 0 + 500 = 500
   totalCustoCx = 500 ÷ 10 = 50
   totalCustoKg = 500 ÷ 200 = 2,5
```

### **Resultado na UI:**

**Card Extra (distMiniExtra):**
```
Custo/cx: 0,00
Custo/kg: 0,00
Custo Total: R$ 0,00
```

**Card Médio (distMiniMedio):**
```
Custo/cx: 50,00
Custo/kg: 50,00
Custo Total: R$ 500,00
```

**Card Custo Global (distMini2):**
```
Custo/cx: 50,00
Custo/kg: 2,50
```

**Card Valor Total (distMini4):**
```
Valor Total: R$ 500,00
```

---

## 🔄 OUTROS CENÁRIOS SEM EXTRA

### **Cenário 2: Editar Valor Total (SEM Extra)**

**Fluxo:**
```
Usuário edita Valor Total para 1000
  ↓
cenario2_EditarValorTotal(1000)
  ↓
hasExtra() → false
  ↓
extraCustoTotal = 0
medioCustoTotal = 1000  ← TODO o valor!
  ↓
medioCustoCx = 1000 ÷ 10 cx = 100
medioCustoKg = 1000 ÷ 200 kg = 5
  ↓
totalCustoCx = 1000 ÷ 10 = 100
totalCustoKg = 1000 ÷ 200 = 5
```

**Resultado:**
- Extra permanece zerado
- Médio recebe 100% do valor
- Custo Global atualiza

---

### **Cenário 3B: Editar Custo/kg Global (SEM Extra)**

**Fluxo:**
```
Usuário edita totalCustoKg para 10
  ↓
cenario3B_EditarCustoKgGlobal(10)
  ↓
valorTotal = 10 × 200 kg = 2000
  ↓
Chama Cenário 2 (que detecta SEM Extra)
  ↓
medioCustoTotal = 2000
medioCustoCx = 2000 ÷ 10 = 200
medioCustoKg = 2000 ÷ 200 = 10
  ↓
totalCustoCx = 2000 ÷ 10 = 200
```

**Resultado:**
- Extra permanece zerado
- Médio atualiza com novo valor
- Custo/cx Global recalculado

---

### **Cenário 4: Editar Extra Custo/cx (SEM Extra)**

**Fluxo:**
```
Usuário tenta editar extraCustoCxDisplay
  ↓
cenario4_EditarExtraCustoCx() verifica:
  ↓
if (!hasExtra()) {
  console.warn('Tentativa de editar Extra sem quantidade!');
  return;  ← BLOQUEIA!
}
```

**Resultado:**
- ❌ Edição bloqueada
- Warning no console
- Nada acontece

**Recomendação UI:**
- Desabilitar campo `#extraCustoCxDisplay` quando `extraCx = 0`
- Adicionar classe `.disabled`
- Remover `role="button"`

---

## 🎯 REGRAS ESPECIAIS SEM EXTRA

| Situação | Regra |
|----------|-------|
| **Carga Inicial** | `medioCustoCx = precoBase ÷ 2` |
| **Sem precoBase** | `medioCustoCx = 0` |
| **Custo/kg** | `medioCustoKg = medioCustoCx` (assume cx = kg) |
| **Valor Total** | `valorTotal = medioCustoTotal` (Extra = 0) |
| **Editar Valor Total** | Todo valor vai para Médio (100%) |
| **Editar Custo Global** | Redistribui só para Médio |
| **Editar Extra** | ❌ BLOQUEADO (warning) |

---

## 📝 LOGS DE DEBUG

Ao carregar item SEM Extra, você verá no console:

```javascript
[CENÁRIO 1] Carga Inicial - precoBase: 100
[SEM EXTRA] Médio calculado: {
  custoCx: 50,
  custoKg: 50,
  custoTotal: 500
}
[CENÁRIO 1] Resultado: {
  valorTotal: 500,
  totalCustoCx: 50,
  totalCustoKg: 2.5,
  extra: { cx: 0, kg: 0, total: 0 },
  medio: { cx: 50, kg: 50, total: 500 }
}
[EXTRA/MÉDIO] Card Extra atualizado
[EXTRA/MÉDIO] Card Médio atualizado
```

---

## 🔍 VERIFICAÇÃO NO CONSOLE

Para verificar estado atual:

```javascript
// Ver estado completo
console.log(window.__DIST_EXTRA_MEDIO_STATE);

// Verificar se tem Extra
console.log('Tem Extra?', window.__DIST_EXTRA_MEDIO_STATE.extraCx > 0);

// Ver valores do Médio
const state = window.__DIST_EXTRA_MEDIO_STATE;
console.log('Médio:', {
  cx: state.medioCx,
  kg: state.medioKg,
  custoCx: state.medioCustoCx,
  custoKg: state.medioCustoKg,
  custoTotal: state.medioCustoTotal
});
```

---

## ✅ CHECKLIST DE VALIDAÇÃO

Ao testar item SEM Extra:

- [ ] Extra zerado (custoCx, custoKg, custoTotal = 0)
- [ ] Médio com `custoCx = precoBase ÷ 2`
- [ ] Valor Total = Custo Total do Médio
- [ ] Custo Global correto
- [ ] Editar Valor Total → 100% vai para Médio
- [ ] Editar Custo Global → Redistribui só Médio
- [ ] Editar Extra → Bloqueado com warning
- [ ] Card Extra mostra zeros
- [ ] Card Médio mostra valores corretos
- [ ] Sem erros no console

---

## 🎉 CONCLUSÃO

**Fluxo para itens SEM Extra:**

1. ✅ Detecta ausência de Extra (`hasExtra() = false`)
2. ✅ Zera todos os valores do Extra
3. ✅ Calcula Médio com `precoBase ÷ 2`
4. ✅ Valor Total = Custo Total do Médio
5. ✅ Edições redistribuem 100% para Médio
6. ✅ Edição do Extra é bloqueada
7. ✅ UI reflete estado correto

**Sem referências circulares, sem loops, funcionamento independente!** 🚀
