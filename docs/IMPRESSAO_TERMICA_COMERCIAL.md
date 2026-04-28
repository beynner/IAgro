# Impressão Térmica - Página Comercial

## 📋 Visão Geral

Este documento explica as correções implementadas no layout de impressão térmica (80mm) da página **Comercial** e fornece orientações para configuração e uso correto.

---

## 🔧 Problemas Identificados e Soluções

### **Problema 1: Preview de Impressão em Branco**

**❌ Sintoma:**
- Ao clicar em "Imprimir Agora", a janela de impressão do navegador mostra uma página em branco
- O preview visual do modal funciona, mas a impressão real não

**🔍 Causas Identificadas:**
1. Container `#printContent` tinha classe `.print-only` que causava conflito
2. Estilos CSS não eram aplicados devido à falta de especificidade
3. HTML gerado não tinha estilos inline, dependendo apenas do CSS externo

**✅ Soluções Implementadas:**

1. **Removida classe conflitante:**
```html
<!-- ANTES -->
<div id="printContent" class="print-only" style="display:none;">

<!-- DEPOIS -->
<div id="printContent" style="display:none;">
```

2. **Adicionados estilos inline em TODO o HTML gerado:**
```javascript
const printHTML = `
  <div class="print-header" style="text-align:center; border-bottom:2px dashed #000; padding:3mm 4mm; margin:0; background:white;">
    <div class="print-title" style="font-weight:bold; font-size:14pt; margin:0 0 2mm 0;">IAGRO</div>
    <div style="font-size:10pt;">Vale de Produtos</div>
  </div>
  ...
`;
```

3. **Adicionado debug para diagnóstico:**
```javascript
console.log('[PRINT DEBUG] Elementos:', {
  previewModal: !!previewModal,
  previewContent: !!previewContent,
  printContainer: !!printContainer,
  htmlLength: printHTML.length,
  totalItens: totalItens
});
```

---

### **Problema 2: CSS de Impressão Não Era Aplicado Corretamente**

**❌ Antes:**
- Os estilos de impressão estavam dentro do `@media print` mas não forçavam a ocultação de elementos da tela
- O container `#printContent` tinha padding e width que não eram respeitados
- Faltavam seletores com `!important` para sobrescrever estilos da página

**✅ Solução Implementada:**
```css
/* Ocultar TUDO exceto o container de impressão */
body > *:not(#printContent) { 
  display: none !important; 
}

/* Mostrar APENAS o container de impressão */
#printContent {
  display: block !important;
  width: 80mm !important;
  max-width: 80mm !important;
  padding: 0 !important;
  margin: 0 !important;
  background: white !important;
}
```

---

### **Problema 2: Container de Impressão Estava Sempre Oculto**

**❌ Antes:**
- `#printContent` tinha `display:none` inline no HTML
- Durante a impressão (`window.print()`), o container continuava oculto
- O conteúdo era preenchido mas nunca exibido

**✅ Solução Implementada:**
```css
/* Estilos base - oculto na tela */
#printContent {
  display: none;
}

/* Durante impressão - forçar exibição */
@media print {
  #printContent {
    display: block !important;
  }
}
```

---

### **Problema 3: Formatação Inadequada para Impressora Térmica 80mm**

**❌ Antes:**
- Classes genéricas (`.print-header`, `.print-item`) sem escopo específico
- Padding e margins inconsistentes
- Fonte muito pequena (7pt-8pt)

**✅ Solução Implementada:**
- **Seletores específicos**: Todos os estilos agora usam `#printContent .classe` para evitar conflitos
- **Padding uniforme**: Todas as seções usam `padding: 3mm 4mm` ou `2mm 4mm`
- **Fonte legível**: Ajustada para 9pt-12pt dependendo do elemento
- **Espaçamento adequado**: Margem entre elementos de 2mm

```css
#printContent .print-header {
  text-align: center;
  border-bottom: 2px dashed #000;
  padding: 3mm 4mm;
  margin: 0;
  background: white;
}
```

---

## 🎯 Como Funciona Agora

### **Fluxo de Impressão**

1. **Usuário clica no botão de impressão** (`#valeResumoPrint`)
2. **Função `printVale()` é executada:**
   - Coleta dados do modal (título, itens, totais)
   - Gera HTML formatado para impressão térmica
   - Preenche `#printContent` e `#printPreviewContent`
   - Mostra modal de preview

3. **Usuário confirma impressão:**
   - Modal fecha
   - `window.print()` é chamado após 100ms
   - **CSS `@media print` é ativado**
   - Toda a página é oculta EXCETO `#printContent`
   - Impressora recebe documento formatado para 80mm

---

## 📐 Especificações Técnicas

### **Configuração de Página**
```css
@page { 
  size: 80mm auto;  /* Largura fixa 80mm, altura automática */
  margin: 0;        /* Sem margem (impressora térmica não precisa) */
}
```

### **Estrutura do Documento Impresso**

```
┌─────────────────────────────────────┐
│     IAGRO                   │ ← Header (12pt, bold, centralizado)
│     Vale de Produtos                │ ← Subtítulo (9pt)
├─────────────────────────────────────┤ ← Linha tracejada
│ VALE Nº: 92500                      │ ← Seção de dados (9pt)
│ PEDIDO: 91700                       │
│ EMISSÃO: 13/10/2025 14:30          │
├─────────────────────────────────────┤
│ PARCEIRO:                           │
│ João da Silva Ltda                  │
├─────────────────────────────────────┤
│ ITENS:                              │
│ • Tomate Extra                      │ ← Nome do produto (9pt bold)
│   100 CX   Unit: R$ 25,00  R$ 2.500│ ← Detalhes (8pt)
│ • Chuchu Médio                      │
│   50 CX    Unit: R$ 15,00  R$ 750  │
├─────────────────────────────────────┤
│ TOTAL GERAL: R$ 3.250,00           │ ← Total (10pt bold)
│ TOTAL ITENS: 2   PESO: 150.00kg    │
├─────────────────────────────────────┤
│ Emitido em 13/10/2025 14:30        │ ← Footer (8pt, centralizado)
└─────────────────────────────────────┘
```

### **Tamanhos de Fonte**
| Elemento | Tamanho | Peso |
|----------|---------|------|
| Título (IAGRO) | 12pt | Bold |
| Subtítulo | 9pt | Normal |
| Labels (VALE Nº, PARCEIRO) | 9pt | Bold |
| Valores | 9pt | Normal |
| Nome do produto | 9pt | Bold |
| Detalhes do item | 8pt | Normal |
| Total | 10pt | Bold |
| Footer | 8pt | Normal |

---

## 🖨️ Configuração da Impressora

### **1. Configurar Impressora no Sistema**

#### Windows:
1. Abra **Configurações** → **Dispositivos** → **Impressoras e scanners**
2. Selecione sua impressora térmica
3. Clique em **Gerenciar** → **Preferências de impressão**
4. Configure:
   - **Tamanho do papel**: Personalizado - 80mm de largura
   - **Orientação**: Retrato
   - **Margens**: 0mm (todas)
   - **Qualidade**: Alta / 203 DPI

#### Linux:
```bash
# Adicionar impressora via CUPS
sudo lpadmin -p ThermalPrinter -v usb://Your/Printer/URI -E

# Configurar tamanho de papel
lpoptions -p ThermalPrinter -o media=Custom.80x297mm
lpoptions -p ThermalPrinter -o PageSize=Custom.80x297mm
```

---

### **2. Configurar no Navegador**

#### Chrome/Edge:
1. Ao clicar em "Imprimir Agora", a janela de impressão abrirá
2. Configure:
   - **Destino**: Sua impressora térmica
   - **Layout**: Retrato
   - **Margens**: Nenhuma
   - **Escala**: 100%
   - ✅ **Gráficos de fundo**: ATIVADO (importante!)
   - ❌ **Cabeçalhos e rodapés**: DESATIVADO

#### Firefox:
1. Arquivo → Imprimir
2. Configure:
   - **Impressora**: Sua impressora térmica
   - **Tamanho do papel**: 80mm (personalizado)
   - **Margens**: 0mm
   - **Escala**: 100%
   - ✅ **Imprimir fundos**: ATIVADO

---

## 🧪 Como Testar

### **Teste 1: Preview Visual**
1. Acesse a página **Comercial**
2. Selecione um Vale na lista
3. Clique no botão de impressão (ícone de impressora)
4. **Verificar**:
   - Modal de preview aparece
   - Papel simulado tem 80mm de largura
   - Conteúdo está formatado corretamente
   - Linhas tracejadas estão visíveis

### **Teste 2: Impressão Real**
1. No modal de preview, clique em **"Imprimir Agora"**
2. Na janela de impressão do navegador:
   - Verifique se a impressora térmica está selecionada
   - Confirme que não há cabeçalhos/rodapés
   - Clique em **Imprimir**
3. **Verificar**:
   - Impressão sai na impressora térmica
   - Largura é exatamente 80mm
   - Sem margens laterais
   - Texto legível (não muito pequeno)
   - Linhas tracejadas aparecem

### **Teste 3: Simulação sem Impressora Física**
```bash
# Instalar impressora virtual (Windows)
# Use "Microsoft Print to PDF" com papel personalizado 80mm

# Ou no Chrome: "Salvar como PDF"
# Verifique o PDF gerado - deve ter 80mm de largura
```

---

## 🛠️ Solução de Problemas

### **Problema: Impressão sai cortada ou muito larga**
**Causa**: Impressora não está configurada para 80mm  
**Solução**:
- Configure manualmente o tamanho do papel nas preferências da impressora
- No Chrome: Configurações → Impressoras → Editar → Papel: Custom 80mm

---

### **Problema: Linhas tracejadas não aparecem**
**Causa**: "Gráficos de fundo" está desativado  
**Solução**:
- Na janela de impressão, ative "Gráficos de fundo" ou "Imprimir fundos"

---

### **Problema: Margens muito grandes**
**Causa**: Impressora está adicionando margens padrão  
**Solução**:
- Configure margens para 0mm nas preferências da impressora
- No CSS já está configurado `@page { margin: 0; }`

---

### **Problema: Fonte muito pequena ou grande**
**Causa**: Escala de impressão não está em 100%  
**Solução**:
- Na janela de impressão, ajuste escala para 100%
- Não use "Ajustar à página"

---

### **Problema: Preview mostra, mas impressão não sai**
**Causa**: Impressora não está acessível ou configurada incorretamente  
**Solução**:
1. Verifique se a impressora está ligada e conectada
2. Teste imprimindo uma página de teste do sistema
3. Reinstale o driver da impressora
4. Verifique logs do navegador (F12 → Console)

---

## 📝 Código JavaScript Relevante

### **Função Principal: `printVale()`**

```javascript
function printVale(){
  // 1. Coletar dados do modal
  const title = document.getElementById('valeResumoTitle')?.textContent || '—';
  const pedidoNum = document.getElementById('valeResumoPedidoNum')?.textContent || '';
  const valeNum = document.getElementById('valeResumoValeNum')?.textContent || '';
  const total = document.getElementById('valeResumoTotal')?.textContent || 'R$ 0,00';
  
  // 2. Gerar HTML formatado
  const printHTML = `...`;
  
  // 3. Preencher containers
  previewContent.innerHTML = printHTML;  // Para preview
  printContainer.innerHTML = printHTML;  // Para impressão real
  
  // 4. Mostrar modal de preview
  previewModal.style.display = 'flex';
}
```

### **Evento de Confirmação**

```javascript
document.getElementById('printPreviewConfirm')?.addEventListener('click', ()=>{
  document.getElementById('printPreviewModal').style.display = 'none';
  
  // Aguardar modal fechar completamente
  setTimeout(() => {
    window.print();  // Abre janela de impressão
  }, 100);
});
```

---

## ✅ Checklist de Implementação

- [x] Corrigir CSS `@media print` com `!important`
- [x] Garantir que `#printContent` seja exibido durante impressão
- [x] Adicionar seletores específicos (`#printContent .classe`)
- [x] Ajustar tamanhos de fonte para legibilidade
- [x] Padronizar padding e margins
- [x] Configurar `@page` para 80mm sem margens
- [x] Ocultar toda a página exceto conteúdo de impressão
- [x] Testar preview visual
- [x] Documentar processo completo

---

## 🔄 Próximos Passos (Opcional)

### **Melhorias Futuras:**

1. **Suporte a múltiplas larguras**:
   ```css
   /* Adicionar opção para 58mm ou 80mm */
   @media print and (max-width: 60mm) {
     #printContent { width: 58mm !important; }
   }
   ```

2. **Logo da empresa**:
   ```html
   <div class="print-header">
     <img src="/logo.png" style="width:40mm;height:auto;">
     <div class="print-title">IAGRO</div>
   </div>
   ```

3. **QR Code para rastreamento**:
   ```javascript
   // Adicionar QR Code com NUNOTA
   const qrCode = generateQRCode(valeNum);
   printHTML += `<img src="${qrCode}" style="width:20mm;height:20mm;">`;
   ```

4. **Salvar preferências de impressão**:
   ```javascript
   localStorage.setItem('printerPreferences', JSON.stringify({
     printerName: 'ThermalPrinter',
     paperWidth: '80mm'
   }));
   ```

---

## 📞 Suporte

Para problemas ou dúvidas sobre impressão térmica:
1. Verifique este documento primeiro
2. Teste com o checklist de testes
3. Consulte logs do navegador (F12 → Console)
4. Entre em contato com o time de desenvolvimento

---

**Última atualização**: 13/10/2025  
**Versão**: 1.0  
**Autor**: GitHub Copilot
