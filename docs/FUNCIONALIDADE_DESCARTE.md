# Funcionalidade: Campo Descarte

## Resumo

Campo **Descarte** no modal de Itens da página de Classificação permite registrar a quantidade total (em kg, 1 decimal) de produto descartado do lote.

## Localização

**Página:** Classificação (`compras_classificacao.html`)  
**Modal:** Itens (modal lateral que abre após selecionar um lote)  
**Posição:** Logo abaixo da tabela de "Produtos inseridos", ao lado esquerdo do toggle "Classificação Finalizada"

## Comportamento

### Interface
- **Campo não editável** exibindo o total de descarte atual em formato `0,0 kg` (padrão pt-BR)
- **Dois botões** ao lado do campo:
  - **+** (verde): Adicionar descarte
  - **−** (vermelho): Subtrair descarte

### Fluxo de Uso

1. **Abrir Modal de Itens**: Ao abrir o modal, o campo é populado com o valor de `TGFCAB.QTDBATIDAS` do cabeçalho TOP 26 (classificação) associado ao lote.

2. **Adicionar Descarte** (botão +):
   - Clique abre um mini modal com campo numérico
   - Digite a quantidade (ex: `5.0`)
   - Confirme: o valor é **somado** ao total atual
   - Salva automaticamente no banco

3. **Subtrair Descarte** (botão −):
   - Clique abre o mesmo mini modal
   - Digite a quantidade a remover
   - Confirme: o valor é **subtraído** do total atual
   - Salva automaticamente no banco

4. **Validações**:
   - Aceita apenas valores **> 0** (não permite zero ou negativos como entrada)
   - Total nunca fica **< 0** (se subtração ultrapassar, zera)
   - Precisão: **1 casa decimal**
   - Formato esperado: números com `.` ou `,` (ex: `5.0` ou `5,0`)

5. **Persistência**:
   - Usa endpoint `/sankhya/header/update/` com parâmetro `qtdbatidas`
   - Atualiza `TGFCAB.QTDBATIDAS` do cabeçalho TOP 26
   - Em caso de falha, exibe mensagem e **não altera** o valor exibido

## Backend

### Alterações em `oracle_conn.py`

#### Função `consultar_lote_light`
Agora retorna dois campos adicionais:
- `qtdbatidas`: valor de `TGFCAB.QTDBATIDAS` do cabeçalho TOP 26 (se existir)
- `prod_in_natura`: código do produto IN NATURA (863) usado no lote

**SQL adicionado:**
```sql
-- Buscar QTDBATIDAS
SELECT QTDBATIDAS FROM TGFCAB WHERE NUNOTA=:nunota_class

-- Buscar produto IN NATURA
SELECT i.CODPROD FROM TGFITE i
JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
WHERE i.CODAGREGACAO = :controle 
  AND c.CODTIPOPER = :TOP_ENTRADA 
  AND i.CODPROD = :PROD_IN_NATURA
  AND ROWNUM = 1
```

#### Função `plan_update_cabecalho`
Já estava preparada para aceitar `QTDBATIDAS` (implementado em sessão anterior).

**Exemplo de chamada:**
```python
update_cabecalho(nunota=92500, updates={'QTDBATIDAS': 12.5})
```

### Endpoint

**POST** `/sankhya/header/update/`

**Payload:**
```json
{
  "nunota": 92500,
  "qtdbatidas": 12.5
}
```

**Resposta (sucesso):**
```json
{
  "ok": true,
  "executed": true,
  "nunota": 92500
}
```

## Frontend

### Elementos HTML
```html
<!-- Campo não editável -->
<input type="text" id="descarteTotal" readonly value="0,0" />

<!-- Botões +/- -->
<button id="btnDescarteAdd">+</button>
<button id="btnDescarteSub">−</button>

<!-- Mini Modal -->
<div id="modalDescarte">
  <input type="number" id="descarteInput" step="0.1" min="0.1" />
  <button id="modalDescarteConfirmar">Confirmar</button>
  <button id="modalDescarteCancelar">Cancelar</button>
</div>
```

### Lógica JavaScript

**Variáveis globais:**
- `window.updateDescarteFromBackend(qtdbatidas)`: função para atualizar o campo ao abrir o modal

**Funções principais:**
- `formatDescarte(val)`: formata número para pt-BR (1 decimal)
- `updateDescarteDisplay(val)`: atualiza o campo visual
- `openModal(operation)`: abre mini modal ('+' ou '−')
- `validateInput()`: valida entrada (> 0, numérico)
- `saveDescarte(newTotal)`: persiste no backend via `/sankhya/header/update/`
- `confirm()`: calcula novo total, valida, salva e atualiza UI

**Event Listeners:**
- `btnDescarteAdd.click`: abre modal em modo '+'
- `btnDescarteSub.click`: abre modal em modo '−'
- `modalDescarteConfirmar.click`: confirma operação
- `modalDescarteCancelar.click`: fecha modal sem salvar
- `descarteInput.keydown(Enter)`: confirma
- `descarteInput.keydown(Escape)`: cancela
- `modalDescarte.click(fora)`: fecha modal

## Casos de Uso

### Exemplo 1: Adicionar 5kg de descarte
1. Total atual: `0,0 kg`
2. Clique em **+**
3. Digite `5.0`
4. Confirme
5. Total atualizado: `5,0 kg`
6. Backend: `QTDBATIDAS = 5.0`

### Exemplo 2: Adicionar mais 3.5kg
1. Total atual: `5,0 kg`
2. Clique em **+**
3. Digite `3.5`
4. Confirme
5. Total atualizado: `8,5 kg`
6. Backend: `QTDBATIDAS = 8.5`

### Exemplo 3: Subtrair 2kg
1. Total atual: `8,5 kg`
2. Clique em **−**
3. Digite `2.0`
4. Confirme
5. Total atualizado: `6,5 kg`
6. Backend: `QTDBATIDAS = 6.5`

### Exemplo 4: Subtrair mais do que existe
1. Total atual: `6,5 kg`
2. Clique em **−**
3. Digite `10.0`
4. Confirme
5. Total atualizado: `0,0 kg` (não fica negativo)
6. Backend: `QTDBATIDAS = 0.0`

### Exemplo 5: Entrada inválida
1. Clique em **+**
2. Digite `0` ou `-5` ou deixe vazio
3. Confirme
4. **Erro exibido**: "Valor deve ser maior que zero."
5. Modal permanece aberto para correção

## Testes Manuais

### Checklist UI
- [ ] Campo Descarte visível no modal de Itens
- [ ] Valor inicial correto (do backend ou `0,0`)
- [ ] Botões + e − funcionais e visíveis
- [ ] Mini modal abre ao clicar nos botões
- [ ] Título do modal correto ("Adicionar" / "Subtrair")
- [ ] Campo numérico aceita entrada
- [ ] Enter confirma, Escape cancela
- [ ] Validação: rejeita <= 0
- [ ] Formatação pt-BR (vírgula decimal)

### Checklist Backend
- [ ] Endpoint `/sankhya/header/update/` aceita `qtdbatidas`
- [ ] Valor salvo em `TGFCAB.QTDBATIDAS`
- [ ] Consulta retorna `qtdbatidas` correto
- [ ] Arredondamento para 1 decimal funciona
- [ ] Erro de banco é capturado e exibido

### Checklist Integração
- [ ] Abrir modal de Itens carrega descarte correto
- [ ] Adicionar descarte atualiza campo e banco
- [ ] Subtrair descarte atualiza campo e banco
- [ ] Total não fica negativo
- [ ] Fechar e reabrir modal mantém valor atualizado
- [ ] Erro de rede não corrompe UI

## Próximos Passos (Opcional)

- [ ] Histórico de alterações (log de descartes por data/usuário)
- [ ] Descarte por item (detalhamento de qual produto foi descartado)
- [ ] Motivo do descarte (avaria, qualidade, etc.)
- [ ] Relatório de descartes por lote/período
- [ ] Permissões específicas para editar descarte
- [ ] Limite máximo de descarte (ex: não pode exceder kg recebida)

## Notas Técnicas

- **Campo usado**: `TGFCAB.QTDBATIDAS` (NUMBER, permite decimais)
- **Triggers**: Nenhum trigger local identificado que restrinja QTDBATIDAS
- **Precisão**: 1 decimal (ex: 12.3 kg)
- **Unidade**: kg (quilogramas)
- **Auto-save**: Sim, após confirmação no mini modal
- **Cache**: Usa cache de lote (`window.__LOTES_CACHE`) para performance

---

**Data de implementação**: 21/10/2025  
**Autor**: Sistema de Classificação - Packing House  
**Versão**: 1.0
