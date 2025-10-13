# 📝 Alterações na Impressão Térmica - Dados Corretos

## ✅ Alterações Implementadas

### **1. VALE Nº → NUNOTA da TOP 13**

**ANTES:**
```
VALE Nº: N/A
```

**DEPOIS:**
```
VALE Nº: 92500  ← NUNOTA do Vale (TOP 13)
```

**Só aparece se existir um Vale gerado** para o pedido.

---

### **2. PEDIDO → NUNOTA da TOP 11**

**ANTES:**
```
PEDIDO: 92637  ← Já estava correto
```

**DEPOIS:**
```
PEDIDO: 92637  ← NUNOTA do Pedido (TOP 11)
```

**Sempre aparece** (é o pedido sendo visualizado).

---

### **3. EMISSÃO → DATA (Data da Compra)**

**ANTES:**
```
EMISSÃO: 13/10/2025, 13:17  ← Data/hora atual
```

**DEPOIS:**
```
DATA: 13/10/2025  ← Data da compra (DTNEG do pedido)
```

**Mostra a data real da compra** (campo `DTNEG` da TOP 11).

---

## 🔍 Como Funciona

### **Código Implementado:**

```javascript
function printVale(){
  // Obter números
  const pedidoNum = document.getElementById('valeResumoPedidoNum')?.textContent || ''; // TOP 11
  const valeNum = document.getElementById('valeResumoValeNum')?.textContent || ''; // TOP 13
  
  // Buscar data da compra do pedido (TOP 11)
  const nunota = pedidoNum;
  const rows = (window.__COM_LIST_ROWS||[]).filter(r=> String(r.nunota||'') === String(nunota||''));
  const dataCompra = rows[0]?.dtneg || null;
  
  // Formatar data (DD/MM/YYYY)
  let dataFormatada = '';
  if(dataCompra){
    const d = new Date(dataCompra);
    const dia = String(d.getDate()).padStart(2, '0');
    const mes = String(d.getMonth() + 1).padStart(2, '0');
    const ano = d.getFullYear();
    dataFormatada = `${dia}/${mes}/${ano}`;
  }
  
  // HTML gerado:
  const printHTML = `
    ${valeNum ? `VALE Nº: ${valeNum}` : ''}  ← Só mostra se existir
    ${pedidoNum ? `PEDIDO: ${pedidoNum}` : ''}
    ${dataFormatada ? `DATA: ${dataFormatada}` : ''}  ← Só mostra se tiver data
  `;
}
```

---

## 📊 Resultado na Impressão

### **Cenário 1: Vale JÁ FOI GERADO**

```
┌─────────────────────────────┐
│   PACKING HOUSE             │
│   Vale de Produtos          │
├─────────────────────────────┤
│ VALE Nº:        92500       │ ← TOP 13 (Vale)
│ PEDIDO:         92637       │ ← TOP 11 (Pedido)
│ DATA:       13/10/2025      │ ← Data da compra
├─────────────────────────────┤
│ PARCEIRO:                   │
│ ANDRE PATROCINIO            │
├─────────────────────────────┤
│ ITENS:                      │
│ • CHUCHU                    │
│   100kg  Unit: R$ 50,00  R$ 4.000,00
├─────────────────────────────┤
│ TOTAL GERAL: R$ 4.000,00    │
│ TOTAL ITENS: 1  PESO: 100kg │
├─────────────────────────────┤
│ Emitido em 13/10/2025, 14:30│
└─────────────────────────────┘
```

---

### **Cenário 2: Vale AINDA NÃO FOI GERADO**

```
┌─────────────────────────────┐
│   PACKING HOUSE             │
│   Vale de Produtos          │
├─────────────────────────────┤
│ PEDIDO:         92637       │ ← Só mostra o pedido
│ DATA:       13/10/2025      │ ← Data da compra
├─────────────────────────────┤
│ PARCEIRO:                   │
│ ANDRE PATROCINIO            │
├─────────────────────────────┤
│ ITENS:                      │
│ • CHUCHU                    │
│   100kg  Unit: R$ 50,00  R$ 4.000,00
├─────────────────────────────┤
│ TOTAL GERAL: R$ 4.000,00    │
│ TOTAL ITENS: 1  PESO: 100kg │
├─────────────────────────────┤
│ Emitido em 13/10/2025, 14:30│
└─────────────────────────────┘
```

**Nota:** O "VALE Nº" só aparece se o vale (TOP 13) já foi gerado.

---

## 🧪 Como Testar

### **1. Recarregar Página**
```
Ctrl + F5
```

### **2. Testar com Pedido SEM Vale**

1. Selecione um **Pedido (TOP 11)** que ainda não tem Vale gerado
2. Clique em **Imprimir**
3. **Verificar na impressão:**
   - ❌ "VALE Nº" não aparece
   - ✅ "PEDIDO" aparece com o NUNOTA do pedido
   - ✅ "DATA" aparece com a data da compra

---

### **3. Testar com Pedido COM Vale**

1. **Gere um Vale** clicando em "GERAR VALE"
2. Aguarde a confirmação
3. Reabra o modal do Vale
4. Clique em **Imprimir**
5. **Verificar na impressão:**
   - ✅ "VALE Nº" aparece com o NUNOTA do Vale (TOP 13)
   - ✅ "PEDIDO" aparece com o NUNOTA do Pedido (TOP 11)
   - ✅ "DATA" aparece com a data da compra

---

## 📋 Mapeamento de Dados

| Campo na Impressão | Origem | Tipo | Exemplo |
|-------------------|--------|------|---------|
| **VALE Nº** | `valeResumoValeNum` → NUNOTA do Vale (TOP 13) | Opcional | `92500` |
| **PEDIDO** | `valeResumoPedidoNum` → NUNOTA do Pedido (TOP 11) | Sempre | `92637` |
| **DATA** | `rows[0].dtneg` → DTNEG do Pedido (TOP 11) | Sempre | `13/10/2025` |
| **PARCEIRO** | `valeResumoTitle` → Nome do parceiro | Sempre | `ANDRE PATROCINIO` |

---

## 🔍 Comportamento Condicional

### **VALE Nº:**
- ✅ **Mostra** se `valeNum` tem valor (Vale foi gerado)
- ❌ **Oculta** se `valeNum` está vazio (Vale não foi gerado)

```javascript
${valeNum ? `<div>VALE Nº: ${valeNum}</div>` : ''}
```

### **PEDIDO:**
- ✅ **Sempre mostra** (é o pedido que está sendo visualizado)

```javascript
${pedidoNum ? `<div>PEDIDO: ${pedidoNum}</div>` : ''}
```

### **DATA:**
- ✅ **Mostra** se `dataFormatada` existe
- ❌ **Oculta** se não conseguir obter a data

```javascript
${dataFormatada ? `<div>DATA: ${dataFormatada}</div>` : ''}
```

---

## 🛠️ Troubleshooting

### **Problema: DATA não aparece**

**Causa:** Campo `dtneg` não está disponível

**Diagnóstico:**
```javascript
// Cole no Console (F12):
const pedidoNum = document.getElementById('valeResumoPedidoNum')?.textContent;
const rows = (window.__COM_LIST_ROWS||[]).filter(r=> String(r.nunota||'') === String(pedidoNum||''));
console.log('Data encontrada:', rows[0]?.dtneg);
```

**Se retornar `undefined`:**
- O pedido não está em `__COM_LIST_ROWS`
- Recarregue a lista de comercial

---

### **Problema: VALE Nº sempre vazio**

**Causa:** Vale ainda não foi gerado ou não foi vinculado corretamente

**Verificar:**
1. O botão "GERAR VALE" foi clicado?
2. O vale foi criado com sucesso?
3. O campo `NUMPEDIDO` do vale (TOP 13) está preenchido com o NUNOTA do pedido (TOP 11)?

**Diagnóstico:**
```javascript
// Cole no Console (F12):
const pedidoNum = document.getElementById('valeResumoPedidoNum')?.textContent;
console.log('Pedido:', pedidoNum);

const valeNum = document.getElementById('valeResumoValeNum')?.textContent;
console.log('Vale:', valeNum || 'NÃO GERADO');
```

---

### **Problema: Formato de data incorreto**

**Exemplo:** `2025-10-13T00:00:00` ao invés de `13/10/2025`

**Causa:** O código de formatação não funcionou

**Solução já implementada:**
```javascript
const d = new Date(dataCompra);
const dia = String(d.getDate()).padStart(2, '0');
const mes = String(d.getMonth() + 1).padStart(2, '0');
const ano = d.getFullYear();
dataFormatada = `${dia}/${mes}/${ano}`;
```

---

## ✅ Checklist de Validação

Após as alterações:

- [ ] Página recarregada (Ctrl+F5)
- [ ] Teste com pedido SEM vale:
  - [ ] "VALE Nº" não aparece
  - [ ] "PEDIDO" mostra NUNOTA correto
  - [ ] "DATA" mostra data da compra
- [ ] Teste com pedido COM vale:
  - [ ] "VALE Nº" mostra NUNOTA do vale (TOP 13)
  - [ ] "PEDIDO" mostra NUNOTA do pedido (TOP 11)
  - [ ] "DATA" mostra data da compra
- [ ] Formato de data está DD/MM/YYYY
- [ ] Impressão térmica funciona corretamente

---

## 📞 Resumo das Mudanças

**Arquivo alterado:** `comercial_dashboard.html`

**Função modificada:** `printVale()`

**Alterações:**
1. ✅ Buscar `dtneg` do pedido para obter data da compra
2. ✅ Formatar data como `DD/MM/YYYY`
3. ✅ Alterar label "EMISSÃO" para "DATA"
4. ✅ Tornar "VALE Nº" condicional (só mostra se existir)
5. ✅ Manter "PEDIDO" sempre visível
6. ✅ Usar dados corretos: VALE Nº = TOP 13, PEDIDO = TOP 11

---

**Data:** 13/10/2025  
**Versão:** 5.0 - Dados Corretos na Impressão  
**Status:** ✅ IMPLEMENTADO
