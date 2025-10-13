# 🎨 Novo Layout de Impressão Térmica - Baseado na Nota Fiscal Semear

## 📋 Visão Geral

O layout da impressão térmica foi completamente reformulado para seguir o padrão da nota fiscal da **Semear**, proporcionando um documento mais profissional e organizado.

---

## 🎯 Estrutura do Novo Layout

### **1. Cabeçalho (Informações do Vale)**
```
Vale: 92500 - 15/08/2025
Data da compra: 15/08/2025
```
- Vale Nº e data na mesma linha
- Data da compra destacada

---

### **2. Parceiro**
```
┌─────────────────────────────┐
│ Parceiro                    │
│ ALEMÃO                      │
└─────────────────────────────┘
```
- Nome em destaque e caixa alta
- Separado por bordas

---

### **3. Resumo de Valores**
```
Total recebido:         597,0
Total quebra negociada:    25
─────────────────────────────
TOMATE SALADA
```
- Total recebido (peso total)
- Quebra negociada
- Nome do produto principal

---

### **4. Resumo da Classificação (Tabela)**
```
┌────┬────┬─────────┬─────────┬────────┐
│Cód │Vol │Produto  │R$ Unit  │Total   │
├────┼────┼─────────┼─────────┼────────┤
│597 │CX  │EXTRA    │60,00    │35.820,00│
│0   │CX  │MÉDIO    │0,00     │0,00    │
└────┴────┴─────────┴─────────┴────────┘
```
- Tabela estruturada com bordas
- Colunas: Código, Volume, Produto, Preço Unit, Total
- Valores alinhados à direita

---

### **5. Totais**
```
Valor Bruto        R$ 35.820,00
INSS 1.5%          R$ 0,00
─────────────────────────────
Total Líquido      R$ 35.820,00
```
- Valor bruto
- Descontos (INSS)
- Total líquido em destaque

---

### **6. Observação**
```
┌─────────────────────────────┐
│ Observação                  │
│                             │
│ (espaço para anotações)     │
└─────────────────────────────┘
```
- Área em branco para observações manuais

---

### **7. Rodapé**
```
"Continue firme e tenha paciência.
Entre a plantação e a colheita, é 
preciso esperar..."

Emitido em 13/10/2025, 14:30
```
- Mensagem motivacional em itálico
- Data/hora de emissão

---

## 🎨 Comparação: Antes vs Depois

### **ANTES (Layout Simples):**
```
═══════════════════════════════
    PACKING HOUSE
    Vale de Produtos
───────────────────────────────
VALE Nº: 92500
PEDIDO: 92637
DATA: 15/08/2025
───────────────────────────────
PARCEIRO:
ALEMÃO
───────────────────────────────
ITENS:
• EXTRA
  100kg  Unit: R$ 50,00  R$ 4.000,00
───────────────────────────────
TOTAL GERAL: R$ 4.000,00
TOTAL ITENS: 1  PESO: 100kg
───────────────────────────────
Emitido em 13/10/2025, 14:30
```

---

### **DEPOIS (Layout Profissional - Semear):**
```
Vale: 92500 - 15/08/2025
Data da compra: 15/08/2025
═══════════════════════════════
Parceiro
ALEMÃO
═══════════════════════════════
Total recebido:         597,0
Total quebra negociada:    25
───────────────────────────────
TOMATE SALADA
═══════════════════════════════
Resumo da Classificação
┌────┬────┬─────────┬────────┬──────────┐
│Cód │Vol │Produto  │R$ Unit │Total     │
├────┼────┼─────────┼────────┼──────────┤
│597 │CX  │EXTRA    │60,00   │35.820,00 │
│0   │CX  │MÉDIO    │0,00    │0,00      │
└────┴────┴─────────┴────────┴──────────┘
═══════════════════════════════
Valor Bruto        R$ 35.820,00
INSS 1.5%          R$ 0,00
───────────────────────────────
Total Líquido      R$ 35.820,00
═══════════════════════════════
Observação
[espaço em branco]
═══════════════════════════════
"Continue firme e tenha paciência.
Entre a plantação e a colheita, é 
preciso esperar..."

Emitido em 13/10/2025, 14:30
```

---

## 📊 Detalhes Técnicos

### **Tamanhos de Fonte:**
| Elemento | Tamanho | Peso |
|----------|---------|------|
| Vale/Data | 8pt | Normal |
| Parceiro Nome | 10pt | Bold |
| Tabela Cabeçalho | 7pt | Bold |
| Tabela Conteúdo | 7pt | Normal |
| Totais Labels | 8pt | Normal |
| Total Líquido | 11pt | Bold |
| Rodapé Citação | 6pt | Italic |
| Data Emissão | 6pt | Normal |

---

### **Estrutura da Tabela de Itens:**

```html
<table style="width:100%; border-collapse:collapse; border:1px solid #000;">
  <thead>
    <tr style="background:#f0f0f0;">
      <th style="border:1px solid #000; padding:1mm; text-align:center;">Cód</th>
      <th style="border:1px solid #000; padding:1mm; text-align:center;">Vol</th>
      <th style="border:1px solid #000; padding:1mm; text-align:left;">Produto</th>
      <th style="border:1px solid #000; padding:1mm; text-align:right;">R$ Unit</th>
      <th style="border:1px solid #000; padding:1mm; text-align:right;">Total</th>
    </tr>
  </thead>
  <tbody>
    <!-- Linhas dinâmicas -->
  </tbody>
</table>
```

---

### **Colunas da Tabela:**

1. **Cód** (Código do Produto)
   - Extraído do backend (TODO: implementar busca)
   - Padrão: `597` para classificáveis, `0` para outros

2. **Vol** (Volume/Unidade)
   - Detectado automaticamente: `CX`, `KG`, `UN`
   - Baseado no texto da quantidade

3. **Produto**
   - Nome do produto ou categoria (EXTRA, MÉDIO)
   - Alinhado à esquerda

4. **R$ Unit** (Preço Unitário)
   - Valor por unidade
   - Alinhado à direita

5. **Total**
   - Valor total do item
   - Alinhado à direita, em negrito

---

## 🎨 Estilos Aplicados

### **Bordas:**
- **Sólidas (`1px solid #000`)**: Separações principais (parceiro, tabela, totais)
- **Nenhuma**: Entre seções leves (cabeçalho, rodapé)

### **Backgrounds:**
- **Branco (`white`)**: Todo o documento
- **Cinza claro (`#f0f0f0`)**: Cabeçalho da tabela

### **Alinhamento:**
- **Esquerda**: Textos descritivos, nomes
- **Direita**: Valores numéricos, totais
- **Centro**: Códigos, unidades, cabeçalhos de colunas

---

## 🔧 Melhorias Implementadas

### **1. Layout mais Limpo**
- ✅ Menos linhas tracejadas
- ✅ Mais espaço em branco
- ✅ Bordas sólidas para estruturação

### **2. Tabela Profissional**
- ✅ Bordas em todas as células
- ✅ Cabeçalho com fundo cinza
- ✅ Alinhamento consistente
- ✅ Fonte menor (7pt) para caber mais informação

### **3. Hierarquia Visual**
- ✅ Tamanhos de fonte variados
- ✅ Pesos de fonte estratégicos (bold nos títulos)
- ✅ Separação clara entre seções

### **4. Informações Adicionais**
- ✅ Total recebido (peso total)
- ✅ Quebra negociada (campo preparado)
- ✅ INSS (desconto preparado)
- ✅ Área de observação

---

## 🧪 Como Testar

### **1. Recarregar Página**
```
Ctrl + F5
```

### **2. Imprimir um Vale**
1. Selecione um Vale com itens
2. Clique em **Imprimir**
3. Clique em **"Imprimir Agora"**

### **3. Verificar no Preview:**
- ✅ Layout segue o padrão Semear
- ✅ Tabela aparece com bordas
- ✅ Valores alinhados à direita
- ✅ Parceiro em destaque
- ✅ Rodapé com citação

### **4. Imprimir na Térmica:**
- ✅ Tabela mantém estrutura
- ✅ Bordas aparecem
- ✅ Texto legível
- ✅ Largura 80mm respeitada

---

## 📐 Largura 80mm - Ajustes

O layout foi otimizado para **80mm de largura**:

- **Padding lateral**: 3mm (conservador)
- **Largura útil**: ~74mm
- **Font mínima**: 6pt (legível em térmicas)
- **Tabela**: 5 colunas compactas
- **Quebra de linha**: Automática se necessário

---

## 🎯 Próximas Melhorias (Opcional)

### **1. Código do Produto Real**
Atualmente está fixo (`597`). Implementar busca do código real:
```javascript
// Buscar CODPROD do item
const codProd = item.codprod || '0';
```

### **2. Quebra Negociada**
Calcular quebra negociada real:
```javascript
const totalQuebraNegociada = totalRecebido - totalClassificado;
```

### **3. INSS 1.5%**
Calcular desconto real:
```javascript
const inss = (valorBruto * 0.015).toFixed(2);
const valorLiquido = (valorBruto - inss).toFixed(2);
```

### **4. Logo Empresa**
Adicionar logo no cabeçalho:
```html
<div style="text-align:center; padding:2mm;">
  <img src="/logo.png" style="width:30mm; height:auto;">
</div>
```

### **5. Código de Barras**
Adicionar código de barras com NUNOTA:
```html
<div style="text-align:center; padding:2mm;">
  <svg id="barcode"></svg>
  <script>JsBarcode("#barcode", "${valeNum}");</script>
</div>
```

---

## ✅ Checklist de Validação

- [x] Layout baseado na nota Semear
- [x] Tabela com bordas implementada
- [x] Colunas: Cód, Vol, Produto, R$ Unit, Total
- [x] Resumo de valores (Total recebido, Quebra)
- [x] Área de observação
- [x] Rodapé com citação
- [x] Estilos inline para compatibilidade
- [x] Tamanhos de fonte otimizados
- [ ] Teste na impressora térmica (próximo passo)

---

## 📞 Resultado Esperado

Uma impressão **profissional** e **organizada**, similar à nota fiscal da Semear, com:
- ✅ Tabela estruturada
- ✅ Valores alinhados
- ✅ Bordas limpas
- ✅ Informações claras
- ✅ Fácil leitura

---

**Data:** 13/10/2025  
**Versão:** 6.0 - Layout Profissional Semear  
**Baseado em:** Nota Fiscal Semear  
**Status:** ✅ IMPLEMENTADO
