# 🧪 Teste de Impressão Térmica - Guia Rápido

## ✅ Checklist de Teste

### **1. Verificar Preview no Modal**

1. ✅ Abra a página **Comercial**
2. ✅ Selecione um Vale na lista
3. ✅ Clique no botão de **impressão** (ícone de impressora ao lado do título do Vale)
4. ✅ **VERIFICAR:**
   - Modal de preview aparece?
   - Papel simulado (80mm) está visível?
   - Conteúdo está formatado e legível?
   - Título "IAGRO" aparece?
   - Dados do Vale (nº, pedido, emissão) aparecem?
   - Parceiro aparece?
   - Itens aparecem com nome, quantidade e valores?
   - Total geral aparece?

**Se o preview estiver em branco:**
- Pressione **F12** para abrir o Console do navegador
- Procure por mensagens `[PRINT DEBUG]`
- Verifique se há erros em vermelho

---

### **2. Verificar Console de Debug**

Abra o Console (F12 → Console) e procure por:

```
[PRINT DEBUG] Elementos: {
  previewModal: true,
  previewContent: true,
  printContainer: true,
  htmlLength: 1234,
  totalItens: 2
}
[PRINT DEBUG] Conteúdo inserido com sucesso!
[PRINT DEBUG] printContainer HTML: <div class="print-header" style="text-align:center...
```

**Possíveis mensagens de erro:**

| Mensagem | Problema | Solução |
|----------|----------|---------|
| `htmlLength: 0` | Nenhum item encontrado | Verifique se há itens no modal do Vale |
| `totalItens: 0` | Tabela vazia | Certifique-se de abrir um Vale com itens |
| `printContainer: false` | Elemento não existe | Recarregue a página |
| `[PRINT ERROR] Elementos não encontrados!` | HTML corrompido | Limpe cache e recarregue |

---

### **3. Testar Impressão Real (Sem Impressora)**

**Objetivo:** Verificar se o conteúdo aparece na janela de impressão do navegador

1. No modal de preview, clique em **"Imprimir Agora"**
2. A janela de impressão do navegador abrirá
3. **VERIFICAR NO PREVIEW:**
   - Conteúdo aparece (não está em branco)?
   - Largura parece 80mm?
   - Texto está legível?
   - Linhas tracejadas aparecem?

**Se aparecer em branco:**
1. No Console (F12), verifique logs de debug
2. Na janela de impressão, verifique se:
   - ✅ **Gráficos de fundo** está ATIVADO
   - ✅ **Escala** está em 100%
   - ✅ **Margens** está em "Nenhuma" ou "0"

---

### **4. Testar com Impressora Virtual (PDF)**

**Windows:**
1. Na janela de impressão, selecione **"Microsoft Print to PDF"**
2. Configure:
   - Layout: Retrato
   - Margens: Nenhuma
   - Gráficos de fundo: ATIVADO
3. Clique em **Imprimir**
4. Salve o PDF
5. **VERIFICAR no PDF:**
   - Conteúdo aparece?
   - Largura é compatível com 80mm (~302px)?
   - Formatação está correta?

---

### **5. Testar com Impressora Térmica Real (EPSON TM-T20X)**

**Configuração Inicial (fazer uma vez):**

1. **Windows → Configurações → Dispositivos → Impressoras**
2. Selecione **EPSON TM-T20X Receipt**
3. Clique em **Gerenciar → Preferências de impressão**
4. Configure:
   - **Tamanho do papel**: 80mm (ou Receipt)
   - **Margens**: 0mm (todas)
   - **Qualidade**: Alta / 203 DPI
5. Salve as preferências

**Impressão:**

1. Na janela de impressão do Chrome/Edge:
   - **Destino**: EPSON TM-T20X Receipt
   - **Layout**: Retrato
   - **Margens**: Nenhuma
   - **Escala**: 100%
   - ✅ **Gráficos de fundo**: ATIVADO
   - ❌ **Cabeçalhos e rodapés**: DESATIVADO

2. Clique em **Imprimir**

3. **VERIFICAR:**
   - Impressão saiu?
   - Largura está correta (não cortada)?
   - Texto está legível?
   - Linhas tracejadas aparecem?

---

## 🔍 Diagnóstico de Problemas

### **Problema: Preview do Modal OK, mas Impressão em Branco**

**Passo 1:** Verifique o Console
```javascript
// Deve aparecer:
[PRINT DEBUG] printContainer HTML: <div class="print-header" style="text-align:center...
```

**Passo 2:** Inspecione o elemento durante a impressão
1. Pressione **Ctrl+P** (ou clique em Imprimir)
2. **Antes de confirmar**, pressione **F12**
3. No Console, digite:
```javascript
document.getElementById('printContent').innerHTML
```
4. Deve retornar o HTML completo com os itens

**Passo 3:** Verifique os estilos CSS
```javascript
// No Console, durante a impressão:
window.getComputedStyle(document.getElementById('printContent')).display
// Deve retornar: "block" (não "none")
```

---

### **Problema: Texto Muito Pequeno**

**Causa:** Escala incorreta ou zoom do navegador

**Solução:**
1. Na janela de impressão: Escala = 100%
2. No navegador: Ctrl+0 (resetar zoom para 100%)
3. Se ainda estiver pequeno, ajuste no CSS:
```css
#printContent .print-title {
  font-size: 16pt; /* aumentar de 14pt para 16pt */
}
```

---

### **Problema: Linhas Tracejadas Não Aparecem**

**Causa:** Gráficos de fundo desativados

**Solução:**
- Chrome/Edge: ✅ Marcar "Gráficos de fundo"
- Firefox: ✅ Marcar "Imprimir fundos"

---

### **Problema: Margens Muito Grandes**

**Causa:** Impressora está adicionando margens padrão

**Solução:**
1. Configurar margens para **0mm** nas preferências da impressora
2. Na janela de impressão: Margens = **Nenhuma**

---

### **Problema: Impressão Cortada**

**Causa:** Largura não é 80mm

**Solução:**
1. Verificar preferências da impressora: Papel = **80mm** ou **Receipt**
2. Se não houver opção 80mm, criar papel personalizado:
   - Windows: Preferências → Papel → Adicionar tamanho → 80mm x 297mm

---

## 📊 Exemplos de Saída Esperada

### **Console (OK):**
```
[PRINT DEBUG] Elementos: {
  previewModal: true,
  previewContent: true,
  printContainer: true,
  htmlLength: 1523,
  totalItens: 3
}
[PRINT DEBUG] Conteúdo inserido com sucesso!
[PRINT DEBUG] printContainer HTML: <div class="print-header" style="text-align:center; border-bottom:2px dashed #000; padding:3mm 4mm; margin:0; background:white;">
```

### **Console (ERRO - Nenhum item):**
```
[PRINT DEBUG] Elementos: {
  previewModal: true,
  previewContent: true,
  printContainer: true,
  htmlLength: 687,  ← Muito pequeno!
  totalItens: 0     ← Nenhum item!
}
```
**Solução:** Certifique-se de que o modal do Vale tenha itens antes de imprimir.

---

### **Console (ERRO - Elementos não encontrados):**
```
[PRINT ERROR] Elementos não encontrados!
```
**Solução:** 
1. Recarregue a página (Ctrl+F5)
2. Limpe o cache do navegador
3. Verifique se o HTML não foi modificado incorretamente

---

## 🚀 Teste Rápido (30 segundos)

**Objetivo:** Verificar se a correção funcionou

1. Abra a página Comercial
2. Clique em qualquer Vale com itens
3. Clique no botão de impressão (ícone de impressora)
4. **VERIFICAR:** Modal aparece com conteúdo formatado?
   - ✅ **SIM** → Continue para o passo 5
   - ❌ **NÃO** → Veja seção "Preview do Modal em Branco"
5. Clique em "Imprimir Agora"
6. **VERIFICAR:** Preview na janela do navegador mostra conteúdo?
   - ✅ **SIM** → Impressão está funcionando! 🎉
   - ❌ **NÃO** → Veja seção "Impressão em Branco"

---

## 📞 Ajuda Adicional

### **Logs Úteis para Debug:**

Cole isso no Console (F12) após clicar em "Imprimir Agora":

```javascript
// Verificar se o conteúdo existe
console.log('Conteúdo Length:', document.getElementById('printContent').innerHTML.length);

// Verificar estilos aplicados
console.log('Display:', window.getComputedStyle(document.getElementById('printContent')).display);

// Verificar se há itens
console.log('Itens:', document.getElementById('printContent').querySelectorAll('.print-item').length);

// Extrair HTML completo
console.log('HTML completo:', document.getElementById('printContent').innerHTML);
```

---

### **Teste Manual de HTML:**

Se nada funcionar, teste se o HTML está sendo gerado:

1. Abra o Console (F12)
2. Cole este código:
```javascript
document.getElementById('printContent').innerHTML = `
  <div style="text-align:center; padding:10mm; font-family:Arial;">
    <h1 style="font-size:20pt;">TESTE DE IMPRESSÃO</h1>
    <p style="font-size:14pt;">Se você vê este texto na impressão,</p>
    <p style="font-size:14pt;">o problema é no JavaScript que gera o conteúdo.</p>
    <p style="font-size:14pt;">Se não vê, o problema é no CSS.</p>
  </div>
`;
window.print();
```

3. **VERIFICAR:** O texto de teste aparece na impressão?
   - ✅ **SIM** → O problema é no JavaScript que gera o HTML dos itens
   - ❌ **NÃO** → O problema é no CSS `@media print`

---

## ✅ Checklist Final

Antes de reportar um problema, verifique:

- [ ] Página foi recarregada (Ctrl+F5) após as alterações
- [ ] Cache do navegador foi limpo
- [ ] Vale selecionado TEM itens (não está vazio)
- [ ] Console (F12) não mostra erros em vermelho
- [ ] Logs `[PRINT DEBUG]` aparecem no Console
- [ ] `htmlLength > 500` (indica que há conteúdo)
- [ ] `totalItens > 0` (indica que há itens)
- [ ] Gráficos de fundo está ATIVADO na janela de impressão
- [ ] Escala está em 100%
- [ ] Margens está em "Nenhuma"

---

**Data:** 13/10/2025  
**Versão:** 2.0 - Correção de Impressão em Branco  
**Navegadores Testados:** Chrome, Edge  
**Impressora Testada:** EPSON TM-T20X Receipt
