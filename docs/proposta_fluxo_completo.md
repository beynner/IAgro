# Proposta: Fluxo Completo de Classificação - TOPs 11, 26 e 13

## Situação Atual vs Proposta

### ATUAL
- ✅ Portal: Lança TOP 11 (Pedido Compra)
- ⚠️ Classificação: TOP 26 criada manualmente
- ❌ Vale Compra: TOP 13 não implementada
- ❌ Financeiro: TGFFIN não gerado

### PROPOSTA
- ✅ Portal: Lança TOP 11 + Auto-duplica para TOP 26 (se classifica)
- ✅ Classificação: TOP 26 automática + Gera TOP 13
- ✅ Vale Compra: TOP 13 com TGFFIN automático
- ✅ Separação clara de interfaces

## Opções de Implementação

### 🏆 OPÇÃO A - AUTOMAÇÃO POR TRIGGER (RECOMENDADA)

#### Vantagens
- ✅ **Atomicidade**: Tudo em uma transação
- ✅ **Consistência**: Sempre sincronizado
- ✅ **Performance**: Execução no banco
- ✅ **Simplicidade**: Frontend não precisa saber do fluxo
- ✅ **Auditoria**: Triggers registram tudo

#### Implementação
1. **TRIGGER na TGFITE (AFTER INSERT/UPDATE)**
   ```sql
   -- Quando inserir/alterar item TOP 11 com GERAPRODUCAO='S'
   -- Automaticamente duplicar para TOP 26
   ```

2. **TRIGGER na TGFITE TOP 26 (AFTER INSERT)**
   ```sql
   -- Quando classificação estiver completa
   -- Automaticamente criar TOP 13 + TGFFIN
   ```

3. **Filtros nas Views**
   ```python
   # Portal: WHERE CODTIPOPER = 11
   # Classificação: WHERE CODTIPOPER = 26
   ```

### 📋 OPÇÃO B - CONTROLE POR APLICAÇÃO

#### Vantagens
- ✅ **Flexibilidade**: Controle total do fluxo
- ✅ **Debugabilidade**: Mais fácil debugar
- ✅ **Configurabilidade**: Pode desabilitar etapas

#### Desvantagens
- ❌ **Complexidade**: Mais código para manter
- ❌ **Inconsistência**: Pode sair de sincronia
- ❌ **Performance**: Múltiplas queries

#### Implementação
1. **Serviço de Duplicação**
   ```python
   def auto_duplicate_to_classification(nunota_11: int) -> dict:
       # 1. Carrega TGFCAB TOP 11
       # 2. Duplica para TOP 26
       # 3. Duplica itens classificáveis
       # 4. Retorna nunota_26
   ```

2. **Serviço de Vale de Compra**
   ```python
   def create_vale_compra(nunota_26: int) -> dict:
       # 1. Cria TGFCAB TOP 13
       # 2. Cria TGFITE TOP 13
       # 3. Gera TGFFIN
   ```

### 🔧 OPÇÃO C - HÍBRIDA (BALANCEADA)

#### Conceito
- **Trigger**: Duplicação TOP 11→26 automática
- **Aplicação**: Controle do TOP 13 + TGFFIN

#### Vantagens
- ✅ **Consistência**: Duplicação sempre acontece
- ✅ **Controle**: Vale de compra sob demanda
- ✅ **Flexibilidade**: Pode ajustar regras de vale

## Detalhamento da Opção Recomendada (A)

### 1. Portal - Comportamento Atual + Melhoria

```python
# Em item_save() - views.py
def item_save(request):
    # ... código atual ...
    
    # NOVO: Após salvar TOP 11, verificar se precisa duplicar
    if is_classificavel_product(codprod) and top_origem == 11:
        # Trigger no banco fará a duplicação automaticamente
        # Frontend não precisa fazer nada extra
        pass
    
    return JsonResponse({"ok": True, "nunota": nunota})
```

### 2. Trigger Principal - Duplicação TOP 11→26

```sql
CREATE OR REPLACE TRIGGER TRG_AUTO_DUPLICATE_TOP26
    AFTER INSERT OR UPDATE ON TGFITE
    FOR EACH ROW
DECLARE
    v_count NUMBER;
    v_nunota_26 NUMBER;
    v_exists NUMBER;
BEGIN
    -- Só processar TOP 11 com produtos classificáveis
    IF (:NEW.CODTIPOPER_ORIGEM = 11 AND :NEW.GERAPRODUCAO = 'S') THEN
        
        -- Verificar se já existe TOP 26 para este controle
        SELECT COUNT(*) INTO v_exists
        FROM TGFITE i
        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA  
        WHERE i.CODAGREGACAO = :NEW.CODAGREGACAO
        AND c.CODTIPOPER = 26;
        
        IF v_exists = 0 THEN
            -- 1. Duplicar TGFCAB 11→26
            INSERT INTO TGFCAB (
                NUNOTA, CODEMP, CODPARC, CODTIPOPER, CODNAT, 
                CODCENCUS, DTNEG, DTMOV, DTENTSAI, DHTIPOPER
            )
            SELECT 
                SQ_NUNOTA.NEXTVAL, CODEMP, CODPARC, 26, CODNAT,
                CODCENCUS, DTNEG, DTMOV, DTENTSAI, SYSDATE
            FROM TGFCAB 
            WHERE NUNOTA = :NEW.NUNOTA
            RETURNING NUNOTA INTO v_nunota_26;
            
            -- 2. Duplicar TGFITE 11→26 (apenas produtos classificáveis)
            INSERT INTO TGFITE (
                NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG,
                VLRUNIT, VLRTOT, CODVOL, CODAGREGACAO
            )
            SELECT 
                v_nunota_26, SEQUENCIA, CODEMP, CODPROD, QTDNEG,
                VLRUNIT, VLRTOT, CODVOL, CODAGREGACAO
            FROM TGFITE 
            WHERE NUNOTA = :NEW.NUNOTA 
            AND GERAPRODUCAO = 'S';
        END IF;
    END IF;
END;
```

### 3. Views Filtradas

```python
# Portal - Filtrar apenas TOP 11
def compras_portal(request):
    # ... código atual ...
    # MODIFICAR consultas para WHERE CODTIPOPER = 11
    
# Classificação - Filtrar apenas TOP 26  
def compras_classificacao(request):
    # ... código atual ...
    # MODIFICAR consultas para WHERE CODTIPOPER = 26
```

### 4. Vale de Compra (TOP 13) - Trigger ou Serviço

```sql
-- Opção: Trigger quando classificação estiver completa
CREATE OR REPLACE TRIGGER TRG_AUTO_VALE_COMPRA
    AFTER UPDATE ON TGFCAB
    FOR EACH ROW
DECLARE
    v_nunota_13 NUMBER;
    v_total_classificado NUMBER;
    v_total_original NUMBER;
BEGIN
    -- Só processar TOP 26 quando status mudar para fechado
    IF (:NEW.CODTIPOPER = 26 AND :NEW.STATUSNOTA = 'L' AND :OLD.STATUSNOTA != 'L') THEN
        
        -- Verificar se classificação está completa
        SELECT SUM(QTDNEG) INTO v_total_classificado
        FROM TGFITE 
        WHERE NUNOTA = :NEW.NUNOTA;
        
        SELECT SUM(QTDNEG) INTO v_total_original  
        FROM TGFITE i
        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
        WHERE i.CODAGREGACAO = (SELECT DISTINCT CODAGREGACAO FROM TGFITE WHERE NUNOTA = :NEW.NUNOTA)
        AND c.CODTIPOPER = 11;
        
        -- Se classificação >= original, criar vale
        IF v_total_classificado >= v_total_original THEN
            -- Criar TGFCAB TOP 13
            -- Criar TGFITE TOP 13  
            -- Criar TGFFIN
        END IF;
    END IF;
END;
```

## Configuração Recomendada

### 1. Parâmetros Novos em oracle_conn.py

```python
DEFAULT_PARAMS = {
    'TOP_ENTRADA': 11,
    'TOP_CLASS': 26,
    'TOP_VALE_COMPRA': 13,  # NOVO
    'TOP_PED_VENDA': 34,
    'TOP_VENDAS': [35, 37],
    'TOP_AVARIA': 30,
    'PROD_IN_NATURA': 863,
    'PROD_CLASS_LIST': [358, 359, 907],
    'PROD_DESCARTE': 910,
    'AUTO_DUPLICATE_CLASSIFICATION': True,  # NOVO
    'AUTO_CREATE_VALE_COMPRA': True,  # NOVO
}
```

### 2. Flag de Controle em settings.py

```python
SANKHYA_CONFIG = {
    'WRITE_ENABLED': True,
    'AUTO_FLOWS': {
        'CLASSIFICATION_DUPLICATE': True,
        'VALE_COMPRA_AUTO': True,
    }
}
```

## Cronograma de Implementação

### Fase 1 (1-2 dias)
- ✅ Filtros nas views (Portal=TOP11, Classificação=TOP26)
- ✅ Parâmetros de configuração
- ✅ Testes de separação de interface

### Fase 2 (2-3 dias) 
- ✅ Trigger de duplicação TOP 11→26
- ✅ Serviço de duplicação via aplicação (backup)
- ✅ Testes de duplicação automática

### Fase 3 (3-4 dias)
- ✅ Implementação TOP 13 (Vale de Compra)
- ✅ Geração TGFFIN
- ✅ Testes de fluxo completo

### Fase 4 (1 dia)
- ✅ Documentação
- ✅ Testes de integração
- ✅ Deploy e monitoramento

## Riscos e Mitigações

### Riscos
- **Trigger Complex**: Pode travar em casos edge
- **Performance**: Duplicação pode ser lenta
- **Rollback**: Difícil reverter se algo der errado

### Mitigações
- **Flag de Controle**: Pode desabilitar automação
- **Logs Detalhados**: Auditoria completa
- **Backup Strategy**: Restore point antes de grandes mudanças
- **Testes Extensivos**: Cenários de borda bem testados

## Decisão Recomendada

**Implementar Opção A (Trigger) com fallback para Opção B (Aplicação)**:

1. **Trigger Principal**: Duplicação TOP 11→26 automática
2. **Serviço Backup**: Caso trigger falhe, aplicação pode fazer manualmente  
3. **Controle Granular**: Flags para habilitar/desabilitar cada etapa
4. **Monitoramento**: Logs e alertas para detectar problemas

Isso garante **máxima automação** com **flexibilidade** para casos especiais.