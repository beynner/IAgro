# Implementação: Persistência de Simulação Extra/Médio com Colunas AD_*

**Data**: 2025-10-07  
**Objetivo**: Salvar e carregar dados de simulação Extra/Médio usando 4 colunas customizadas no Oracle (AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2)

---

## 📋 Contexto

O sistema Extra/Médio possui 5 cenários de cálculo que distribuem custos entre categorias. Os valores calculados precisam ser persistidos no banco de dados Oracle (tabela TGFITE) para que possam ser recuperados posteriormente quando o usuário recarregar a página.

### Campos Existentes vs Novos

**Campos já em uso** (NÃO MODIFICADOS):
- `VLRUNIT`: Custo/kg geral (usado para cálculos gerais, não específico de Extra)
- `VLRTOT`: Valor total da negociação (usado para valor total do item)

**Campos NOVOS criados** (pelo usuário no Oracle):
- `AD_SIMQTD1`: Quantidade Extra em caixas (extraCx)
- `AD_SIMVLR1`: Custo total Extra (extraCustoTotal)
- `AD_SIMQTD2`: Quantidade Médio em caixas (medioCx)
- `AD_SIMVLR2`: Custo total Médio (medioCustoTotal)

---

## 🔧 Alterações Implementadas

### 1. Backend: `oracle_conn.py`

**Arquivo**: `sankhya_integration/services/oracle_conn.py`  
**Função**: `listar_itens_portal_basico()`  
**Linha**: ~3200-3220

**Mudanças**:
1. ✅ Adicionadas 4 colunas no SELECT interno:
   ```sql
   SELECT ... i.AD_SIMQTD1, i.AD_SIMQTD2, i.AD_SIMVLR1, i.AD_SIMVLR2
   ```

2. ✅ Adicionadas 4 colunas no SELECT externo (paginação):
   ```sql
   SELECT NOMEPARC, PRODNAME, ..., AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2
   ```

3. ✅ Atualizada docstring da função com novo formato de tupla:
   ```python
   # Retorna tuplas: (NOMEPARC, PRODNAME, QTDNEG, DTNEG, CODVOL, CODPROD, 
   #                  NUNOTA, SEQUENCIA, GP, PESO, PRECOBASE, VLRUNIT, VLRTOT,
   #                  AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2)
   ```

**Impacto**: Query Oracle agora retorna 17 colunas (antes: 13)

---

### 2. Backend: `views.py`

**Arquivo**: `sankhya_integration/views.py`  
**Funções**: `comercial_lista()` e `comercial_dist_save()`

#### 2.1. Função `comercial_lista()` (Linha ~2490-2550)

**Mudanças**:
1. ✅ Extrair 4 novos valores da tupla:
   ```python
   ad_simqtd1_val = (r[13] if len(r) > 13 else None)
   ad_simqtd2_val = (r[14] if len(r) > 14 else None)
   ad_simvlr1_val = (r[15] if len(r) > 15 else None)
   ad_simvlr2_val = (r[16] if len(r) > 16 else None)
   ```

2. ✅ Adicionar 4 campos no JSON de resposta:
   ```python
   out.append({
       'parceiro': parc or '',
       'produto': prod or '',
       ...
       'ad_simqtd1': (float(ad_simqtd1_val) if ad_simqtd1_val not in (None, '') else None),
       'ad_simqtd2': (float(ad_simqtd2_val) if ad_simqtd2_val not in (None, '') else None),
       'ad_simvlr1': (float(ad_simvlr1_val) if ad_simvlr1_val not in (None, '') else None),
       'ad_simvlr2': (float(ad_simvlr2_val) if ad_simvlr2_val not in (None, '') else None),
   })
   ```

**Impacto**: API `/sankhya/comercial/lista/` agora retorna 4 campos adicionais

#### 2.2. Função `comercial_dist_save()` (Linha ~2340-2380)

**Mudanças**:
1. ✅ Extrair 4 campos do payload recebido:
   ```python
   sim_qtd1 = _to_float_or(payload.get('sim_qtd1'))
   sim_vlr1 = _to_float_or(payload.get('sim_vlr1'))
   sim_qtd2 = _to_float_or(payload.get('sim_qtd2'))
   sim_vlr2 = _to_float_or(payload.get('sim_vlr2'))
   ```

2. ✅ Adicionar 4 campos no update_payload:
   ```python
   update_payload = {
       'NUNOTA': nunota,
       'SEQUENCIA': sequencia,
       'VLRUNIT': custo_kg,
       'VLRTOT': total,
       'AD_SIMQTD1': sim_qtd1,
       'AD_SIMVLR1': sim_vlr1,
       'AD_SIMQTD2': sim_qtd2,
       'AD_SIMVLR2': sim_vlr2,
   }
   ```

**Impacto**: API `/sankhya/comercial/dist/save/` agora aceita e salva 4 campos adicionais

---

### 3. Frontend: `comercial_dashboard.html`

**Arquivo**: `sankhya_integration/templates/sankhya_integration/comercial_dashboard.html`

#### 3.1. Função `handleSave()` (Linha ~4450-4500)

**Mudanças**:
1. ✅ Extrair valores de extraCx e medioCx do estado:
   ```javascript
   const extraCxRaw = Number(st?.extraCx ?? NaN);
   const medioCxRaw = Number(st?.medioCx ?? NaN);
   ```

2. ✅ Adicionar 4 campos no payload de save:
   ```javascript
   const payload = {
       nunota,
       sequencia,
       valor_total: Number(totalRaw.toFixed(2)),
       custo_kg: Number(custoKgRaw.toFixed(6)),
       ...
       sim_qtd1: Number.isFinite(extraCxRaw) ? Number(extraCxRaw.toFixed(2)) : null,
       sim_vlr1: Number.isFinite(extraTotalRaw) ? Number(extraTotalRaw.toFixed(2)) : null,
       sim_qtd2: Number.isFinite(medioCxRaw) ? Number(medioCxRaw.toFixed(2)) : null,
       sim_vlr2: Number.isFinite(medioTotalRaw) ? Number(medioTotalRaw.toFixed(2)) : null,
   };
   ```

**Impacto**: Ao clicar em "Salvar", envia 4 campos adicionais para o backend

#### 3.2. Função `applyItemToEntrada()` (Linha ~1910-1930)

**Mudanças**:
1. ✅ Extrair 4 campos do item carregado:
   ```javascript
   const simExtraCx = (item.ad_simqtd1 != null ? Number(item.ad_simqtd1) : null);
   const simExtraTotal = (item.ad_simvlr1 != null ? Number(item.ad_simvlr1) : null);
   const simMedioCx = (item.ad_simqtd2 != null ? Number(item.ad_simqtd2) : null);
   const simMedioTotal = (item.ad_simvlr2 != null ? Number(item.ad_simvlr2) : null);
   ```

2. ✅ Aplicar valores ao estado global (após linha ~1920):
   ```javascript
   if(typeof window.__DIST_EXTRA_MEDIO_STATE !== 'undefined' && window.__DIST_EXTRA_MEDIO_STATE){
       try{
           if(simExtraCx != null && Number.isFinite(simExtraCx)) 
               window.__DIST_EXTRA_MEDIO_STATE.extraCx = simExtraCx;
           if(simExtraTotal != null && Number.isFinite(simExtraTotal)) 
               window.__DIST_EXTRA_MEDIO_STATE.extraCustoTotal = simExtraTotal;
           if(simMedioCx != null && Number.isFinite(simMedioCx)) 
               window.__DIST_EXTRA_MEDIO_STATE.medioCx = simMedioCx;
           if(simMedioTotal != null && Number.isFinite(simMedioTotal)) 
               window.__DIST_EXTRA_MEDIO_STATE.medioCustoTotal = simMedioTotal;
       }catch(_){ }
   }
   ```

**Impacto**: Ao selecionar um item na lista, valores salvos são carregados e aplicados ao estado

---

## 🧪 Fluxo de Teste Completo

### Cenário de Teste 1: Salvar Simulação Nova

1. **Preparação**:
   - Abrir painel Comercial
   - Selecionar um item da lista (nunota + sequencia)
   - Verificar que simulação está zerada (primeira vez)

2. **Ação**:
   - Editar valores no card de simulação:
     * Extra: 100 cx, R$ 5.000,00 total
     * Médio: 50 cx, R$ 2.000,00 total
   - Clicar em "Salvar"

3. **Verificação**:
   ```sql
   SELECT NUNOTA, SEQUENCIA, AD_SIMQTD1, AD_SIMVLR1, AD_SIMQTD2, AD_SIMVLR2
   FROM TGFITE
   WHERE NUNOTA = <nunota> AND SEQUENCIA = <seq>;
   ```
   **Resultado esperado**:
   - AD_SIMQTD1 = 100
   - AD_SIMVLR1 = 5000
   - AD_SIMQTD2 = 50
   - AD_SIMVLR2 = 2000

### Cenário de Teste 2: Recarregar Simulação Salva

1. **Preparação**:
   - Garantir que teste 1 foi executado com sucesso
   - Recarregar página completa (F5)

2. **Ação**:
   - Selecionar o MESMO item da lista (nunota + sequencia do teste 1)

3. **Verificação Frontend**:
   - Abrir console do navegador
   - Verificar `window.__DIST_EXTRA_MEDIO_STATE`:
     ```javascript
     console.log(window.__DIST_EXTRA_MEDIO_STATE.extraCx); // 100
     console.log(window.__DIST_EXTRA_MEDIO_STATE.extraCustoTotal); // 5000
     console.log(window.__DIST_EXTRA_MEDIO_STATE.medioCx); // 50
     console.log(window.__DIST_EXTRA_MEDIO_STATE.medioCustoTotal); // 2000
     ```
   - Verificar que cards de simulação exibem valores corretos

### Cenário de Teste 3: Atualizar Simulação Existente

1. **Preparação**:
   - Selecionar item com simulação salva (teste 1)

2. **Ação**:
   - Editar valores:
     * Extra: 120 cx (era 100), R$ 6.000,00 total (era 5.000)
     * Médio: 60 cx (era 50), R$ 2.500,00 total (era 2.000)
   - Clicar em "Salvar"

3. **Verificação Oracle**:
   ```sql
   SELECT AD_SIMQTD1, AD_SIMVLR1, AD_SIMQTD2, AD_SIMVLR2
   FROM TGFITE
   WHERE NUNOTA = <nunota> AND SEQUENCIA = <seq>;
   ```
   **Resultado esperado**:
   - AD_SIMQTD1 = 120 (atualizado)
   - AD_SIMVLR1 = 6000 (atualizado)
   - AD_SIMQTD2 = 60 (atualizado)
   - AD_SIMVLR2 = 2500 (atualizado)

### Cenário de Teste 4: Zerar Negociação

1. **Preparação**:
   - Selecionar item com simulação salva

2. **Ação**:
   - Clicar em "Zerar negociação"

3. **Verificação Oracle**:
   ```sql
   SELECT VLRUNIT, VLRTOT, AD_SIMQTD1, AD_SIMVLR1, AD_SIMQTD2, AD_SIMVLR2
   FROM TGFITE
   WHERE NUNOTA = <nunota> AND SEQUENCIA = <seq>;
   ```
   **Resultado esperado**:
   - VLRUNIT = 0
   - VLRTOT = 0
   - AD_SIMQTD1, AD_SIMVLR1, AD_SIMQTD2, AD_SIMVLR2: **permanecem** com valores anteriores
   
   ⚠️ **Nota**: Função `comercial_dist_reset()` atualmente só zera VLRUNIT e VLRTOT. Se desejado, pode ser atualizada para zerar também os 4 campos AD_*.

---

## 📊 Mapeamento de Campos

### Completo (Frontend ↔ Backend ↔ Oracle)

| Frontend (JavaScript)                        | Backend (Python)  | Oracle (SQL)     | Descrição                          |
|----------------------------------------------|-------------------|------------------|------------------------------------|
| `window.__DIST_EXTRA_MEDIO_STATE.extraCx`   | `payload['sim_qtd1']` | `AD_SIMQTD1` | Quantidade Extra em caixas         |
| `window.__DIST_EXTRA_MEDIO_STATE.extraCustoTotal` | `payload['sim_vlr1']` | `AD_SIMVLR1` | Custo total Extra                  |
| `window.__DIST_EXTRA_MEDIO_STATE.medioCx`   | `payload['sim_qtd2']` | `AD_SIMQTD2` | Quantidade Médio em caixas         |
| `window.__DIST_EXTRA_MEDIO_STATE.medioCustoTotal` | `payload['sim_vlr2']` | `AD_SIMVLR2` | Custo total Médio                  |

### Campos Relacionados (NÃO MODIFICADOS)

| Frontend (JavaScript)                        | Backend (Python)  | Oracle (SQL)     | Uso Atual                          |
|----------------------------------------------|-------------------|------------------|------------------------------------|
| `window.__DIST_EXTRA_MEDIO_STATE.totalCustoKg` | `payload['custo_kg']` | `VLRUNIT`    | Custo/kg geral (NÃO específico de Extra) |
| `window.__DIST_EXTRA_MEDIO_STATE.valorTotal` | `payload['valor_total']` | `VLRTOT`     | Valor total da negociação          |

---

## 🔍 Verificações de Integridade

### Checklist de Implementação

- [x] Backend: SELECT inclui 4 novas colunas (oracle_conn.py)
- [x] Backend: Extração de 4 valores da tupla (views.py, comercial_lista)
- [x] Backend: JSON de resposta inclui 4 novos campos (views.py, comercial_lista)
- [x] Backend: Save endpoint aceita 4 novos campos (views.py, comercial_dist_save)
- [x] Backend: update_payload inclui 4 novos campos (views.py, comercial_dist_save)
- [x] Frontend: handleSave() extrai 4 valores do estado
- [x] Frontend: handleSave() envia 4 campos no payload
- [x] Frontend: applyItemToEntrada() extrai 4 campos do item
- [x] Frontend: applyItemToEntrada() aplica 4 valores ao estado global

### Checklist de Teste (A FAZER)

- [ ] Teste 1: Salvar simulação nova (verificar Oracle)
- [ ] Teste 2: Recarregar página e carregar simulação salva
- [ ] Teste 3: Atualizar simulação existente
- [ ] Teste 4: Verificar comportamento de "Zerar negociação"
- [ ] Teste 5: Verificar que VLRUNIT e VLRTOT não são afetados por edições de simulação
- [ ] Teste 6: Verificar que valores NULL são tratados corretamente

---

## 🚨 Pontos de Atenção

### 1. Campos NULL vs 0

**Comportamento atual**:
- Backend converte valores ausentes/NULL para `None` em Python
- Frontend verifica `Number.isFinite()` antes de enviar
- Se campo for NULL, será enviado como `null` (não como `0`)

**Recomendação**: Manter NULL quando não houver valor (não confundir com zero real)

### 2. Função `comercial_dist_reset()`

**Estado atual**: Zera apenas `VLRUNIT` e `VLRTOT`

**Opção 1 (atual)**: Manter simulação intacta ao zerar negociação  
**Opção 2**: Zerar também os 4 campos AD_* ao zerar negociação

Se optar por zerar simulação junto, adicionar em `views.py` (~linha 2410):
```python
update_payload = {
    'NUNOTA': nunota,
    'SEQUENCIA': sequencia,
    'VLRUNIT': 0,
    'VLRTOT': 0,
    'AD_SIMQTD1': 0,  # adicionar
    'AD_SIMVLR1': 0,  # adicionar
    'AD_SIMQTD2': 0,  # adicionar
    'AD_SIMVLR2': 0,  # adicionar
}
```

### 3. Triggers Oracle

**Validação feita**: Analisados todos os triggers que afetam TGFITE

**Conclusão**: 
- ✅ Nenhum trigger usa os campos AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2
- ✅ Seguro usar esses campos sem risco de conflitos
- ✅ Triggers `TRG_DLT_TGFITE` e `TRG_AUTO_DUPLICATE_CLASS` não são afetados

### 4. Performance

**Impacto estimado**:
- Query SELECT: +4 colunas (aumento mínimo, ~0.1% overhead)
- UPDATE: +4 colunas (aumento mínimo, sem índices envolvidos)
- Payload JSON: +4 campos (~50 bytes adicionais por item)

**Conclusão**: Impacto de performance negligível

---

## 📝 Histórico de Decisões

### Por que criar colunas AD_* customizadas?

**Alternativas consideradas**:
1. ❌ Usar colunas existentes (PERCDESC, VLRDESCBONIF, etc.)
   - **Problema**: VLRACRESCDESC tinha conflito com triggers
   - **Risco**: Campos existentes podem ter lógica de negócio oculta

2. ❌ Criar tabela auxiliar (TGFITE_SIMULACAO)
   - **Problema**: Overhead de JOIN em todas as queries
   - **Complexidade**: Manutenção de 2 tabelas sincronizadas

3. ✅ Criar 4 colunas AD_* customizadas
   - **Vantagem**: Sem conflitos com triggers
   - **Vantagem**: Performance otimizada (sem JOINs)
   - **Vantagem**: Fácil manutenção (tudo em TGFITE)

### Por que AD_SIMQTD e AD_SIMVLR (não AD_EXTRACX, AD_MEDIOCX)?

**Decisão**: Usar nomes genéricos (QTD1/QTD2, VLR1/VLR2) em vez de específicos (EXTRACX/MEDIOCX)

**Motivação**:
- Permite reutilização futura para outros tipos de simulação
- Mais flexível para mudanças de lógica de negócio
- Padrão AD_* já usado no sistema Sankhya para customizações

---

## 🔗 Arquivos Relacionados

### Documentação
- [IMPLEMENTACAO_4_CENARIOS.md](./IMPLEMENTACAO_4_CENARIOS.md) - Especificação dos 5 cenários
- [CORRECOES_CENARIOS.md](./CORRECOES_CENARIOS.md) - Histórico de bugs corrigidos
- [ANALISE_TGFITE_SIMULACAO.md](./ANALISE_TGFITE_SIMULACAO.md) - Análise de colunas TGFITE
- [GUIA_ALTER_TABLE_ORACLE.md](./GUIA_ALTER_TABLE_ORACLE.md) - Guia sobre ALTER TABLE
- [PLANO_CRIAR_AD_SIMQTD1.md](./PLANO_CRIAR_AD_SIMQTD1.md) - Plano de criação de colunas

### Código
- `sankhya_integration/services/oracle_conn.py` (linha ~3147)
- `sankhya_integration/views.py` (linhas ~2340, ~2459)
- `sankhya_integration/templates/sankhya_integration/comercial_dashboard.html` (linhas ~1910, ~4450)

---

## ✅ Status Final

**Data de Conclusão**: 2025-10-07  
**Status**: ✅ **IMPLEMENTADO E PRONTO PARA TESTE**

**Próximos Passos**:
1. ⏳ Executar checklist de testes (ver seção "Fluxo de Teste Completo")
2. ⏳ Validar comportamento em ambiente de desenvolvimento
3. ⏳ Decidir se função `comercial_dist_reset()` deve zerar simulação
4. ⏳ Validar em ambiente de produção

**Implementado por**: GitHub Copilot Agent  
**Validado por**: _Pendente_

---

**Fim do documento**
