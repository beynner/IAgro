# 📊 Sistema de Sincronização de Valores - Dashboard Comercial

## 🎯 Objetivo
Implementar sincronização bidirecional entre **Valor Total**, **Custo (R$/cx e R$/kg)**, e **Extra/Médio** sem loops infinitos.

---

## 🔄 Fluxos de Atualização

### 1️⃣ **Valor Total → Custo** (READ)
**Quando**: Valor Total é alterado (carregamento, edição manual, reset)
**Ação**: Recalcula Custo/cx e Custo/kg

```javascript
// Gatilho: window.__setDistribTotal(novoValor)
// Resultado:
custoCx = valorTotal / qtdeCx
custoKg = valorTotal / qtdeKg
```

**Fluxo**:
```
Valor Total (alterado)
    ↓
Calcula: custoCx = total / cx
Calcula: custoKg = total / kg
    ↓
Atualiza displays de Custo
    ↓
FIM (não atualiza Valor Total)
```

---

### 2️⃣ **Custo/cx → Valor Total** (WRITE)
**Quando**: Usuário edita campo R$/cx
**Ação**: Recalcula Valor Total e depois Custo/kg

```javascript
// Gatilho: Edição do campo #costCxDisplay
// Resultado:
valorTotal = custoCx * qtdeCx
custoKg = valorTotal / qtdeKg
```

**Fluxo**:
```
Custo/cx (editado pelo usuário)
    ↓
Calcula: valorTotal = custoCx * qtdeCx
    ↓
Atualiza display de Valor Total
    ↓
Calcula: custoKg = valorTotal / qtdeKg
    ↓
Atualiza display de Custo/kg
    ↓
Recalcula Extra e Médio (mantém proporção)
    ↓
FIM (flag isUpdating impede loop)
```

---

### 3️⃣ **Custo/kg → Valor Total** (WRITE)
**Quando**: Usuário edita campo R$/kg
**Ação**: Recalcula Valor Total e depois Custo/cx

```javascript
// Gatilho: Edição do campo #costKgDisplay
// Resultado:
valorTotal = custoKg * qtdeKg
custoCx = valorTotal / qtdeCx
```

**Fluxo**:
```
Custo/kg (editado pelo usuário)
    ↓
Calcula: valorTotal = custoKg * qtdeKg
    ↓
Atualiza display de Valor Total
    ↓
Calcula: custoCx = valorTotal / qtdeCx
    ↓
Atualiza display de Custo/cx
    ↓
Recalcula Extra e Médio (mantém proporção)
    ↓
FIM (flag isUpdating impede loop)
```

---

### 4️⃣ **Extra → Valor Total → Custo** (CASCATA)
**Quando**: Usuário altera valor Extra
**Ação**: Recalcula Valor Total e depois Custo

```javascript
// Gatilho: Edição de Extra
// Resultado:
valorTotal = valorExtra + valorMedio
custoCx = valorTotal / qtdeCx
custoKg = valorTotal / qtdeKg
```

**Fluxo**:
```
Extra (alterado)
    ↓
Calcula: valorTotal = extra + medio
    ↓
Atualiza display de Valor Total
    ↓
Calcula custos (cx e kg)
    ↓
Atualiza displays de Custo
    ↓
FIM (flag isUpdating impede loop)
```

---

### 5️⃣ **Classificação → Quantidades** (FONTE)
**Quando**: Produtos classificados são carregados
**Ação**: Atualiza qtdeCx e qtdeKg, recalcula Custos

```javascript
// Gatilho: loadAndRenderClassificacao()
// Resultado:
qtdeCx = classifiedKg / 22
qtdeKg = classifiedKg
// Depois recalcula custos com Valor Total atual
```

**Fluxo**:
```
Classificação carregada
    ↓
Extrai: qtdeKg = Σ kg classificados
    ↓
Calcula: qtdeCx = qtdeKg / 22
    ↓
Atualiza displays de Quantidade
    ↓
Pega Valor Total atual
    ↓
Recalcula custos: cx e kg
    ↓
Atualiza displays de Custo
    ↓
FIM
```

---

## 🛡️ Proteção contra Loop Infinito

### Flag Global: `window.__DIST_SYNC_STATE.isUpdating`

```javascript
const syncDistributionValues = (source, newValue) => {
  // 🚫 BLOQUEIO: Se já está atualizando, retorna
  if (window.__DIST_SYNC_STATE.isUpdating) {
    return;
  }

  try {
    // 🔒 TRAVA: Marca como atualizando
    window.__DIST_SYNC_STATE.isUpdating = true;
    
    // ✅ Processa atualizações...
    
  } finally {
    // 🔓 LIBERA: Sempre libera no final
    window.__DIST_SYNC_STATE.isUpdating = false;
  }
};
```

### Como funciona:

1. **Primeira chamada**: `isUpdating = false` → Processa normalmente
2. **Chamadas recursivas**: `isUpdating = true` → Retorna imediatamente
3. **Fim do processamento**: `finally` sempre executa e libera a flag

---

## 📋 Estado Global

```javascript
window.__DIST_SYNC_STATE = {
  isUpdating: false,           // Bloqueio de recursão
  lastSource: null,            // Última origem: 'valorTotal', 'custoCx', etc
  values: {
    valorTotal: 0,             // Valor total da distribuição
    qtdeCx: 0,                 // Quantidade em caixas (da classificação)
    qtdeKg: 0,                 // Quantidade em kg (da classificação)
    custoCx: 0,                // Custo por caixa (R$/cx)
    custoKg: 0,                // Custo por kg (R$/kg)
    valorExtra: 0,             // Valor categoria Extra
    valorMedio: 0              // Valor categoria Médio
  }
};
```

---

## 🔌 Funções de Integração

### 1. `window.__syncDistValues(source, newValue)`
**Uso**: Dispara sincronização a partir de qualquer campo
```javascript
// Exemplos:
window.__syncDistValues('valorTotal', 5000);
window.__syncDistValues('custoCx', 25.50);
window.__syncDistValues('custoKg', 1.16);
```

### 2. `window.__updateQtysFromClass(qtdeCx, qtdeKg)`
**Uso**: Atualiza quantidades vindas da classificação
```javascript
// Chamado automaticamente em loadAndRenderClassificacao
window.__updateQtysFromClass(114, 2508);
```

### 3. `window.__setDistribTotal(valor, opts)`
**Uso**: Define Valor Total (já integrado com sync)
```javascript
window.__setDistribTotal(5000, { source: 'item-select' });
```

---

## 📍 Pontos de Integração no Código

### ✅ Já Implementados:

1. **Linha ~1390**: `window.__setDistribTotal` → Dispara sync ao alterar Valor Total
2. **Linha ~2170**: Classificação carregada → Chama `window.__updateQtysFromClass`
3. **Linha ~2525**: Edição de Custo/cx → Chama `window.__syncDistValues('custoCx')`
4. **Linha ~2555**: Edição de Custo/kg → Chama `window.__syncDistValues('custoKg')`
5. **Linha ~3500+**: Sistema completo de sincronização com todas as funções

### ⏳ Pendentes (se necessário):

- [ ] Integrar edição de Extra/Médio (se campos forem editáveis)
- [ ] Adicionar validações de valores negativos
- [ ] Salvar estado sincronizado no backend

---

## 🧪 Testes Manuais

### Cenário 1: Editar Custo/cx
1. Carregar item com classificação
2. Clicar no campo R$/cx
3. Alterar valor (ex: 25,00)
4. **Esperado**: 
   - Valor Total recalculado
   - R$/kg recalculado
   - Sem loops/atualizações múltiplas

### Cenário 2: Editar Custo/kg
1. Carregar item com classificação
2. Clicar no campo R$/kg
3. Alterar valor (ex: 1,50)
4. **Esperado**: 
   - Valor Total recalculado
   - R$/cx recalculado
   - Sem loops/atualizações múltiplas

### Cenário 3: Alterar Valor Total
1. Carregar item
2. Alterar Valor Total diretamente
3. **Esperado**: 
   - Custos recalculados
   - Quantidade mantida
   - Sem loops

### Cenário 4: Carregar Classificação
1. Selecionar item
2. Carregar classificação (adicionar produtos)
3. **Esperado**: 
   - Quantidades atualizadas
   - Custos recalculados com base no Valor Total atual
   - Sem loops

---

## 🎯 Benefícios da Implementação

✅ **Sem Loops Infinitos**: Flag `isUpdating` garante uma única passagem
✅ **Fluxo Claro**: Cada fonte tem seu caminho bem definido
✅ **Estado Centralizado**: Todos os valores em `window.__DIST_SYNC_STATE`
✅ **Manutenível**: Fácil adicionar novos campos/regras
✅ **Debugável**: `lastSource` identifica origem das atualizações

---

## 🔧 Próximos Passos

1. ✅ Testar no navegador os 4 cenários
2. ⏳ Ajustar lógica de Extra/Médio (se necessário)
3. ⏳ Adicionar logs de debug (opcional)
4. ⏳ Persistir estado no backend quando salvar

---

**Última atualização**: 2025-10-07
**Arquivo principal**: `sankhya_integration/templates/sankhya_integration/comercial_dashboard.html`
