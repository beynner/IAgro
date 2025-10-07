# 🎯 FLUXO COMPLETO: Extra e Médio - Sistema de Sincronização

## 📊 ESTRUTURA DE CAMPOS

### Cards Extra e Médio
Cada card possui:
- **Quantidade**: `kg` e `cx` (vem da classificação)
- **Custos Unitários**: `custoKg` e `custoCx`
- **Custo Total**: `custo` (valor total do card)

### Campos Editáveis
- ✏️ **Extra Custo/cx** (`#extraCustoCxDisplay`) - ÚNICO campo editável pelo usuário
- 🔒 **Médio Custo/cx** - Sempre calculado (Extra / 2)
- ✏️ **Valor Total** (`#totalValueDisplay`) - Editável, afeta Extra e Médio

---

## 🔢 REGRAS DE CÁLCULO

### Regra 1: Custo/kg do Médio = Custo/kg do Extra ÷ 2
```javascript
medioCustoKg = extraCustoKg / 2
```

### Regra 2: Custo Total = Qtd/cx × Custo/cx
```javascript
extraCustoTotal = extraCx × extraCustoCx
medioCustoTotal = medioCx × medioCustoCx
```

### Regra 3: Extra Custo/cx é editável
```javascript
// Usuário pode clicar e editar diretamente
```

### Regra 4: Se não há Extra classificado
```javascript
medioCustoCx = (qtdCx_inNatura × PRECOBASE) / 2
```

### Regra 5: Inicialização padrão (sem negociação salva)
```javascript
extraCustoCx = qtdCx_inNatura × PRECOBASE
```

---

---

## 🚀 FLUXO DE INICIALIZAÇÃO (Abrir Página Pela Primeira Vez)

### **CENÁRIO A: Primeira Visita - Sem Item Selecionado**

```
1. Página carrega
   └─> Todos os campos vazios/zerados
   └─> Cards Extra e Médio ocultos ou zerados
   └─> Aguardando seleção de item
```

**Estado Inicial:**
- Valor Total: R$ 0,00
- Custo/cx: 0,00
- Custo/kg: 0,00
- Extra: não exibido
- Médio: não exibido

---

### **CENÁRIO B: Usuário Seleciona Item SEM Negociação Salva**

#### **Passo 1: Carrega Dados do Item**
```javascript
Item selecionado:
- qtdCx = 100 (in natura)
- PRECOBASE = 50.00
- VLRTOT = null (não tem negociação salva)
```

#### **Passo 2: Calcula Valor Total Inicial**
```javascript
// Como não tem VLRTOT salvo:
valorTotalInicial = qtdCx × PRECOBASE
valorTotalInicial = 100 × 50.00 = 5000.00
```

#### **Passo 3: Inicializa Extra com PRECOBASE**
```javascript
extraCustoCx = PRECOBASE = 50.00
// Salva no estado:
window.__DIST_STATE.categorias.extra.custoCx = 50.00
```

#### **Passo 4: Aguarda Carregamento da Classificação**
```javascript
// Neste ponto:
valorTotal = 5000.00 (temporário)
extraCustoCx = 50.00 (preparado)
// Cards Extra/Médio ainda vazios (aguardando classificação)
```

#### **Passo 5: Classificação Carrega (Ex: após 200ms)**
```javascript
Dados da classificação:
- Extra: 60 cx, 1320 kg
- Médio: 40 cx, 880 kg
```

#### **Passo 6: SOBRESCREVE Valor Total com Cálculo Extra/Médio**
```
🔒 TRAVA: isUpdating = true

A. Calcula Extra Total
   extraCustoTotal = extraCx × extraCustoCx
   extraCustoTotal = 60 × 50.00 = 3000.00

B. Calcula Extra Custo/kg
   extraCustoKg = extraCustoTotal / extraKg
   extraCustoKg = 3000 / 1320 = 2.27

C. Calcula Médio Custo/cx (metade do Extra)
   medioCustoCx = extraCustoCx / 2
   medioCustoCx = 50.00 / 2 = 25.00

D. Calcula Médio Custo/kg
   medioCustoKg = extraCustoKg / 2
   medioCustoKg = 2.27 / 2 = 1.14

E. Calcula Médio Custo Total
   medioCustoTotal = medioCx × medioCustoCx
   medioCustoTotal = 40 × 25.00 = 1000.00

F. SOBRESCREVE Valor Total
   valorTotal = extraCustoTotal + medioCustoTotal
   valorTotal = 3000 + 1000 = 4000.00 ⚡ (mudou de 5000!)

G. Recalcula Custo Global
   custoCx = valorTotal / (extraCx + medioCx)
   custoCx = 4000 / 100 = 40.00
   
   custoKg = valorTotal / (extraKg + medioKg)
   custoKg = 4000 / 2200 = 1.82

H. Atualiza TODOS os displays
   - Extra card: 60 cx, 1320 kg, R$ 50,00/cx, R$ 2,27/kg, R$ 3.000,00 total
   - Médio card: 40 cx, 880 kg, R$ 25,00/cx, R$ 1,14/kg, R$ 1.000,00 total
   - Valor Total: R$ 4.000,00
   - Custo: R$ 40,00/cx, R$ 1,82/kg
   - Qtde Total: 100 cx, 2200 kg

🔓 LIBERA: isUpdating = false
```

#### **Resultado Final:**
```
┌─────────────────────────────────────────┐
│  EXTRA                            75%   │
│  ████████████████████████░░░░░░░        │
│  60 cx   1320 kg                        │
│  R$ 2,27/kg   R$ 50,00/cx              │
│  Custo total: R$ 3.000,00              │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  MÉDIO                            25%   │
│  ████████░░░░░░░░░░░░░░░░░░░░░░░░        │
│  40 cx   880 kg                         │
│  R$ 1,14/kg   R$ 25,00/cx              │
│  Custo total: R$ 1.000,00              │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Valor Total: R$ 4.000,00              │
│  Custo: R$ 40,00/cx   R$ 1,82/kg       │
│  Qtde Total: 100 cx   2200 kg          │
└─────────────────────────────────────────┘
```

---

### **CENÁRIO C: Usuário Seleciona Item COM Negociação Salva**

#### **Passo 1: Carrega Dados do Item + Negociação**
```javascript
Item selecionado:
- qtdCx = 100
- PRECOBASE = 50.00
- VLRTOT = 4800.00 (negociação salva!)
- extraCustoCx = 60.00 (salvo no banco)
```

#### **Passo 2: Usa Valores Salvos**
```javascript
valorTotal = VLRTOT = 4800.00 (não calcula qtdCx × PRECOBASE)
extraCustoCx = 60.00 (do banco, não usa PRECOBASE)
```

#### **Passo 3: Classificação Carrega**
```javascript
- Extra: 60 cx, 1320 kg
- Médio: 40 cx, 880 kg
```

#### **Passo 4: Calcula com Valores Salvos**
```
🔒 TRAVA: isUpdating = true

A. Extra Custo/cx = 60.00 (do banco)
   extraCustoTotal = 60 × 60.00 = 3600.00
   extraCustoKg = 3600 / 1320 = 2.73

B. Médio (sempre metade)
   medioCustoCx = 60.00 / 2 = 30.00
   medioCustoKg = 2.73 / 2 = 1.36
   medioCustoTotal = 40 × 30.00 = 1200.00

C. Verifica consistência
   calculado = 3600 + 1200 = 4800 ✅ (bate com VLRTOT salvo)

D. Atualiza displays

🔓 LIBERA: isUpdating = false
```

#### **Resultado Final:**
- Extra: R$ 60,00/cx (valor editado pelo usuário anteriormente)
- Médio: R$ 30,00/cx (metade do Extra)
- Valor Total: R$ 4.800,00 (do banco)

---

### **CENÁRIO D: Item SEM Classificação (Só In Natura)**

#### **Passo 1: Carrega Item**
```javascript
- qtdCx = 100
- PRECOBASE = 50.00
- VLRTOT = null
```

#### **Passo 2: Calcula Valor Total**
```javascript
valorTotal = qtdCx × PRECOBASE = 5000.00
```

#### **Passo 3: Tenta Carregar Classificação**
```javascript
// Retorna vazio:
classificacao = { linhas: [] }
```

#### **Passo 4: Como NÃO há classificação**
```
🔒 TRAVA: isUpdating = true

A. Não sobrescreve Valor Total (mantém 5000.00)

B. Calcula Custo Global com dados In Natura
   // Precisa definir qtdKg in natura!
   custoCx = 5000 / 100 = 50.00
   custoKg = 5000 / qtdKg_inNatura

C. Cards Extra/Médio permanecem ocultos ou zerados

🔓 LIBERA: isUpdating = false
```

#### **Resultado Final:**
```
┌─────────────────────────────────────────┐
│  Valor Total: R$ 5.000,00              │
│  Custo: R$ 50,00/cx   R$ ??,??/kg     │
│  Qtde Total: 100 cx   ??? kg           │
└─────────────────────────────────────────┘

(Cards Extra e Médio NÃO exibidos)
```

---

### **CENÁRIO E: Classificação Só Médio (Sem Extra)**

#### **Passo 1: Classificação Carrega**
```javascript
- Extra: 0 cx, 0 kg (não há Extra!)
- Médio: 100 cx, 2200 kg
```

#### **Passo 2: Detecta Ausência de Extra**
```javascript
if (extraCx === 0) {
  // Regra 4: Médio = (qtdCx × PRECOBASE) / 2
}
```

#### **Passo 3: Calcula Médio Sem Extra**
```
🔒 TRAVA: isUpdating = true

A. Calcula Médio Custo/cx
   // Usa metade do valor que seria do Extra
   medioCustoCx = (qtdCx_inNatura × PRECOBASE) / medioCx / 2
   medioCustoCx = (100 × 50.00) / 100 / 2 = 25.00

B. Calcula Médio Custo Total
   medioCustoTotal = 100 × 25.00 = 2500.00

C. Calcula Médio Custo/kg
   medioCustoKg = 2500 / 2200 = 1.14

D. Valor Total = só Médio
   valorTotal = 2500.00

E. Custo Global
   custoCx = 2500 / 100 = 25.00
   custoKg = 2500 / 2200 = 1.14

F. Card Extra OCULTO

🔓 LIBERA: isUpdating = false
```

#### **Resultado Final:**
```
(Card Extra não exibido)

┌─────────────────────────────────────────┐
│  MÉDIO                           100%   │
│  ████████████████████████████████████   │
│  100 cx   2200 kg                       │
│  R$ 1,14/kg   R$ 25,00/cx              │
│  Custo total: R$ 2.500,00              │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Valor Total: R$ 2.500,00              │
│  Custo: R$ 25,00/cx   R$ 1,14/kg       │
│  Qtde Total: 100 cx   2200 kg          │
└─────────────────────────────────────────┘
```

---

## 🔄 ORDEM DE EXECUÇÃO COMPLETA

```
1. Página Carrega
   └─> Inicializa estado global (tudo zerado)

2. Usuário Seleciona Item na Lista
   └─> Carrega dados do item (qtdCx, PRECOBASE, VLRTOT)
   └─> Se tem VLRTOT: usa valor salvo
   └─> Se NÃO tem VLRTOT: calcula qtdCx × PRECOBASE (temporário)
   └─> Inicializa Extra Custo/cx = PRECOBASE (ou valor salvo)
   └─> Atualiza Valor Total (temporário)

3. Dispara Carregamento da Classificação (assíncrono)
   └─> Aguarda resposta da API...

4. Classificação Retorna
   └─> Se vazio: mantém Valor Total = qtdCx × PRECOBASE
   └─> Se tem dados:
       ├─> Extrai quantidades (Extra cx/kg, Médio cx/kg)
       ├─> Calcula Extra Total (usa Extra Custo/cx já inicializado)
       ├─> Calcula Médio (sempre metade do Extra)
       ├─> SOBRESCREVE Valor Total = Extra + Médio
       └─> Recalcula Custo Global

5. Atualiza Todos os Displays
   └─> Cards Extra e Médio visíveis
   └─> Valor Total atualizado
   └─> Custo Global atualizado
   └─> Qtde Total atualizada

6. Pronto para Edição
   └─> Usuário pode editar Extra Custo/cx
   └─> Usuário pode editar Valor Total
```

---

## ⏱️ TIMING E SEQUÊNCIA

```
T0: Página carrega
    └─> Estado: vazio

T1: Usuário clica em item (ex: após 2s)
    └─> Estado: carregando item...

T2: Dados do item carregam (ex: +50ms)
    └─> valorTotal = 5000 (temporário)
    └─> extraCustoCx = 50 (preparado)
    └─> Dispara classificação...

T3: Classificação carrega (ex: +200ms)
    └─> extraCx = 60, medioCx = 40
    └─> Recalcula tudo
    └─> valorTotal = 4000 (FINAL) ⚡

T4: Interface estável
    └─> Usuário vê valores finais
```

---

## ⚠️ QUESTÕES A RESOLVER

### 1. **Qtde kg In Natura**
Se item não tem classificação, de onde vem `qtdKg` para calcular `custoKg`?

**Opções:**
- A) Item tem campo `peso_total` ou `kg_total`
- B) Calcula: `qtdKg = qtdCx × pesoMedioPorCx`
- C) Não exibe custoKg se não houver classificação

### 2. **Flash de Valor Temporário**
O usuário vê:
1. Primeiro: R$ 5.000,00 (qtdCx × PRECOBASE)
2. Depois: R$ 4.000,00 (Extra + Médio)

**Soluções:**
- A) Mostrar loader até classificação carregar
- B) Aceitar o flash (é rápido)
- C) Não mostrar Valor Total até classificação carregar

### 3. **Validação ao Salvar**
Ao clicar em "Salvar", o que salva no banco?
- Extra Custo/cx
- Médio Custo/cx
- Valor Total
- Todos os custos calculados?

---

## 🔄 FLUXOS DE ATUALIZAÇÃO (SEM REFERÊNCIA CIRCULAR)

### 📍 Estado Global Centralizado
```javascript
window.__DIST_EXTRA_MEDIO_STATE = {
  isUpdating: false,  // Flag anti-loop
  
  // Quantidades (vem da classificação - READ ONLY)
  extraCx: 0,
  extraKg: 0,
  medioCx: 0,
  medioKg: 0,
  
  // Custos unitários
  extraCustoCx: 0,    // FONTE: editável ou PRECOBASE
  extraCustoKg: 0,    // Calculado
  medioCustoCx: 0,    // Sempre Extra/2
  medioCustoKg: 0,    // Sempre Extra/2
  
  // Custos totais
  extraCustoTotal: 0,
  medioCustoTotal: 0,
  
  // Dados auxiliares
  qtdCxInNatura: 0,
  precoBase: 0
};
```

---

## 🎬 CENÁRIO 1: Carregamento Inicial (sem negociação salva)

### Entrada:
- `qtdCx_inNatura = 100`
- `PRECOBASE = 50.00`
- Classificação carregada: `extraCx = 60`, `extraKg = 1320`, `medioCx = 40`, `medioKg = 880`

### Fluxo:
```
1. Inicializa Extra Custo/cx com PRECOBASE
   extraCustoCx = 50.00

2. Calcula Extra Custo/kg
   extraCustoKg = ?  // PRECISA DEFINIR LÓGICA

3. Calcula Extra Custo Total
   extraCustoTotal = extraCx × extraCustoCx
   extraCustoTotal = 60 × 50.00 = 3000.00

4. Calcula Médio Custo/cx (metade do Extra)
   medioCustoCx = extraCustoCx / 2
   medioCustoCx = 50.00 / 2 = 25.00

5. Calcula Médio Custo/kg (metade do Extra)
   medioCustoKg = extraCustoKg / 2

6. Calcula Médio Custo Total
   medioCustoTotal = medioCx × medioCustoCx
   medioCustoTotal = 40 × 25.00 = 1000.00

7. Atualiza Valor Total
   valorTotal = extraCustoTotal + medioCustoTotal
   valorTotal = 3000.00 + 1000.00 = 4000.00

8. Atualiza Custo Global (cx e kg)
   custoCx = valorTotal / (extraCx + medioCx)
   custoCx = 4000.00 / 100 = 40.00
   
   custoKg = valorTotal / (extraKg + medioKg)
   custoKg = 4000.00 / 2200 = 1.82
```

### Resultado:
- Extra: 60 cx, 1320 kg, R$ 50,00/cx, R$ 3.000,00 total
- Médio: 40 cx, 880 kg, R$ 25,00/cx, R$ 1.000,00 total
- **Valor Total: R$ 4.000,00**
- Custo Global: R$ 40,00/cx, R$ 1,82/kg

---

## 🎬 CENÁRIO 2: Usuário Edita Extra Custo/cx

### Entrada:
- Estado atual (do cenário 1)
- Usuário altera `Extra Custo/cx = 60.00`

### Fluxo:
```
🔒 TRAVA: isUpdating = true

1. Atualiza Extra Custo/cx
   extraCustoCx = 60.00

2. Recalcula Extra Custo/kg
   extraCustoKg = ?  // PRECISA DEFINIR LÓGICA

3. Recalcula Extra Custo Total
   extraCustoTotal = 60 × 60.00 = 3600.00

4. Recalcula Médio Custo/cx (CASCATA)
   medioCustoCx = 60.00 / 2 = 30.00

5. Recalcula Médio Custo/kg (CASCATA)
   medioCustoKg = extraCustoKg / 2

6. Recalcula Médio Custo Total
   medioCustoTotal = 40 × 30.00 = 1200.00

7. Recalcula Valor Total (CASCATA)
   valorTotal = 3600.00 + 1200.00 = 4800.00
   
8. Atualiza display Valor Total
   #totalValueDisplay.textContent = "R$ 4.800,00"

9. Recalcula Custo Global
   custoCx = 4800.00 / 100 = 48.00
   custoKg = 4800.00 / 2200 = 2.18

10. Atualiza todos os displays

🔓 LIBERA: isUpdating = false
```

### Resultado:
- Extra: 60 cx, 1320 kg, **R$ 60,00/cx**, R$ 3.600,00 total
- Médio: 40 cx, 880 kg, **R$ 30,00/cx**, R$ 1.200,00 total
- **Valor Total: R$ 4.800,00** ✅ Atualizado
- Custo Global: R$ 48,00/cx, R$ 2,18/kg

**✅ SEM LOOP**: Alterou Extra → Calculou Médio → Atualizou Valor Total → FIM

---

## 🎬 CENÁRIO 3: Usuário Edita Valor Total

### Entrada:
- Estado atual (do cenário 2)
- Usuário altera `Valor Total = 6000.00`

### Fluxo:
```
🔒 TRAVA: isUpdating = true

1. Novo Valor Total
   valorTotal = 6000.00

2. Calcula proporção atual Extra/Médio
   totalAtual = extraCustoTotal + medioCustoTotal
   totalAtual = 3600 + 1200 = 4800
   
   propExtra = 3600 / 4800 = 0.75 (75%)
   propMedio = 1200 / 4800 = 0.25 (25%)

3. Distribui novo valor mantendo proporção
   novoExtraTotal = 6000 × 0.75 = 4500.00
   novoMedioTotal = 6000 × 0.25 = 1500.00

4. Recalcula Extra Custo/cx
   extraCustoCx = novoExtraTotal / extraCx
   extraCustoCx = 4500 / 60 = 75.00

5. Recalcula Extra Custo/kg
   extraCustoKg = novoExtraTotal / extraKg
   extraCustoKg = 4500 / 1320 = 3.41

6. Recalcula Médio Custo/cx (mantém regra ÷2)
   medioCustoCx = extraCustoCx / 2
   medioCustoCx = 75.00 / 2 = 37.50

7. Recalcula Médio Custo/kg (mantém regra ÷2)
   medioCustoKg = extraCustoKg / 2
   medioCustoKg = 3.41 / 2 = 1.70

8. Recalcula Custo Global
   custoCx = 6000 / 100 = 60.00
   custoKg = 6000 / 2200 = 2.73

9. Atualiza todos os displays

🔓 LIBERA: isUpdating = false
```

### Resultado:
- Extra: 60 cx, 1320 kg, **R$ 75,00/cx**, R$ 4.500,00 total
- Médio: 40 cx, 880 kg, **R$ 37,50/cx**, R$ 1.500,00 total
- **Valor Total: R$ 6.000,00** ✅ Mantido
- Custo Global: R$ 60,00/cx, R$ 2,73/kg

**✅ SEM LOOP**: Alterou Valor Total → Recalculou Extra e Médio proporcionalmente → FIM

---

## 🎬 CENÁRIO 4: Classificação sem Extra (só Médio)

### Entrada:
- `qtdCx_inNatura = 100`
- `PRECOBASE = 50.00`
- Classificação: `extraCx = 0`, `medioCx = 100`, `medioKg = 2200`

### Fluxo:
```
1. Detecta que não há Extra
   extraCx === 0  ✓

2. Calcula Médio Custo/cx baseado em PRECOBASE
   medioCustoCx = (qtdCx_inNatura × PRECOBASE) / medioCx / 2
   medioCustoCx = (100 × 50.00) / 100 / 2 = 25.00

3. Calcula Médio Custo/kg
   medioCustoKg = ?  // PRECISA DEFINIR

4. Calcula Médio Custo Total
   medioCustoTotal = 100 × 25.00 = 2500.00

5. Valor Total = só Médio
   valorTotal = 2500.00

6. Custo Global
   custoCx = 2500 / 100 = 25.00
   custoKg = 2500 / 2200 = 1.14
```

### Resultado:
- Extra: 0 cx (não exibido)
- Médio: 100 cx, 2200 kg, R$ 25,00/cx, R$ 2.500,00 total
- **Valor Total: R$ 2.500,00**

---

## ⚠️ QUESTÕES A DEFINIR

### 1. Como calcular Custo/kg do Extra e Médio?

**Opção A**: Usar peso médio por caixa
```javascript
extraCustoKg = extraCustoCx / (extraKg / extraCx)
// Se extraCx=60, extraKg=1320 → peso médio = 22kg/cx
// extraCustoKg = 50 / 22 = 2.27
```

**Opção B**: Usar total distribuído
```javascript
extraCustoKg = extraCustoTotal / extraKg
// extraCustoKg = 3000 / 1320 = 2.27
```

**Recomendação**: Opção B (mais simples e direto)

### 2. Comportamento ao salvar negociação

Quando salva:
- Extra Custo/cx → salva no banco
- Ao recarregar: carrega do banco (não recalcula com PRECOBASE)

### 3. Validações necessárias

- ✅ Extra Custo/cx > 0
- ✅ Valor Total > 0
- ✅ Quantidades > 0 antes de calcular custos
- ⚠️ Se Extra = 0, não permitir editar Extra Custo/cx
- ⚠️ Se Médio = 0, ocultar card Médio

---

## 🛡️ PROTEÇÃO ANTI-LOOP

```javascript
function syncExtraMedioValues(source, newValue) {
  // 🚫 Bloqueia se já está processando
  if (window.__DIST_EXTRA_MEDIO_STATE.isUpdating) {
    return;
  }
  
  try {
    // 🔒 Trava
    window.__DIST_EXTRA_MEDIO_STATE.isUpdating = true;
    
    if (source === 'extraCustoCx') {
      // Fluxo: Extra → Médio → Valor Total → Custo Global
      // NÃO volta para Extra
    }
    else if (source === 'valorTotal') {
      // Fluxo: Valor Total → Extra e Médio (proporção) → Custo Global
      // NÃO volta para Valor Total
    }
    
  } finally {
    // 🔓 Sempre libera
    window.__DIST_EXTRA_MEDIO_STATE.isUpdating = false;
  }
}
```

---

## 📋 CAMPOS AFETADOS POR MUDANÇA

### Ao editar Extra Custo/cx:
1. ✅ Extra Custo/kg (recalcula)
2. ✅ Extra Custo Total (recalcula)
3. ✅ Médio Custo/cx (÷2)
4. ✅ Médio Custo/kg (÷2)
5. ✅ Médio Custo Total (recalcula)
6. ✅ **Valor Total** (soma Extra + Médio)
7. ✅ Custo/cx Global (card Custo)
8. ✅ Custo/kg Global (card Custo)

### Ao editar Valor Total:
1. ✅ Extra Custo/cx (proporção)
2. ✅ Extra Custo/kg (proporção)
3. ✅ Extra Custo Total (proporção)
4. ✅ Médio Custo/cx (Extra/2)
5. ✅ Médio Custo/kg (Extra/2)
6. ✅ Médio Custo Total (proporção)
7. ✅ Custo/cx Global
8. ✅ Custo/kg Global

---

## 🎯 IMPLEMENTAÇÃO SUGERIDA

### Estrutura de Funções:

```javascript
// 1. Função principal de sincronização
syncExtraMedioValues(source, value)

// 2. Cálculos específicos
calcExtraFromCustoCx(custoCx)
calcMedioFromExtra(extraState)
calcValorTotalFromExtraMedio(extra, medio)
calcExtraMedioFromValorTotal(valorTotal, proportion)
calcCustoGlobal(valorTotal, qtdCx, qtdKg)

// 3. Atualização de displays
updateExtraDisplays(extraState)
updateMedioDisplays(medioState)
updateValorTotalDisplay(valorTotal)
updateCustoGlobalDisplays(custoCx, custoKg)
```

---

## ✅ VALIDAÇÃO DO FLUXO

### Teste 1: Extra Custo/cx
```
Editar Extra: 50 → 60
Espera: Médio 25 → 30, Valor Total 4000 → 4800
✅ SEM retornar para Extra
```

### Teste 2: Valor Total
```
Editar Valor Total: 4800 → 6000
Espera: Extra 60 → 75, Médio 30 → 37.50
✅ SEM retornar para Valor Total
```

### Teste 3: Classificação atualizada
```
Carregar nova classificação
Espera: Recalcula tudo mantendo Extra Custo/cx
✅ SEM loops
```

---

**Próximo Passo**: Com base neste fluxo, posso implementar o código completo. Você concorda com esta estrutura? Há alguma regra adicional ou comportamento específico que eu não capturei?
