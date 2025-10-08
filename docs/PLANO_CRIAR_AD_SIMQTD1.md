# 📝 PLANO DE EXECUÇÃO - Criar Coluna AD_SIMQTD1

**Data:** 2025-01-07  
**Objetivo:** Adicionar 1 coluna customizada na TGFITE para quantidade simulação
**Risco:** Baixo (coluna nova, não afeta nada existente)

---

## 🎯 PASSO A PASSO

### **ETAPA 1: PREPARAÇÃO** 📋

#### **1.1 - Informações que preciso de você:**

- [ ] **Acesso ao banco:** Você tem acesso direto ao Oracle? (SQL Developer, Toad, DBeaver?)
- [ ] **Permissões:** Você tem permissão de ALTER TABLE? (normalmente precisa ser DBA ou ter grant)
- [ ] **Horário:** Qual melhor horário para executar? (recomendo fora do horário comercial)
- [ ] **Usuários:** Quantos usuários usam o sistema simultaneamente? (para estimar impacto)

#### **1.2 - Verificar tamanho da tabela:**

```sql
-- Execute no Oracle para ver quantos registros tem:
SELECT COUNT(*) AS total_registros FROM TGFITE;

-- Ver tamanho em MB:
SELECT 
    ROUND(SUM(BYTES)/1024/1024, 2) AS tamanho_mb
FROM USER_SEGMENTS
WHERE SEGMENT_NAME = 'TGFITE';
```

**Anote os resultados:**
- Total de registros: ______________
- Tamanho (MB): ______________

**Tempo estimado de bloqueio:**
- < 100k registros → 10-30 segundos
- 100k - 500k → 1-2 minutos
- 500k - 1M → 2-5 minutos
- > 1M → 5-15 minutos

---

### **ETAPA 2: BACKUP** 💾

#### **2.1 - Backup da estrutura (metadados):**

```sql
-- Salvar estrutura atual da TGFITE
SELECT DBMS_METADATA.GET_DDL('TABLE', 'TGFITE', 'SANKHYA') AS ddl
FROM DUAL;
```

**Copie e salve o resultado em um arquivo:** `TGFITE_estrutura_backup_20250107.sql`

---

#### **2.2 - Backup dos dados (OPCIONAL mas recomendado):**

**Opção A - Backup rápido (só estrutura para rollback):**
```sql
-- Criar tabela de backup vazia (rápido!)
CREATE TABLE TGFITE_ESTRUTURA_BAK AS 
SELECT * FROM TGFITE WHERE 1=0;

-- Verificar
DESC TGFITE_ESTRUTURA_BAK;
```

**Opção B - Backup completo (seguro, mas demora):**
```sql
-- ATENÇÃO: Pode demorar MUITO se tabela for grande!
CREATE TABLE TGFITE_BACKUP_20250107 AS 
SELECT * FROM TGFITE;

-- Verificar
SELECT COUNT(*) FROM TGFITE_BACKUP_20250107;
-- Deve ser igual ao total da TGFITE
```

**Escolha:**
- [ ] Opção A (rápido, backup só estrutura)
- [ ] Opção B (completo, backup com dados)

**Recomendação:** Se a tabela tem menos de 500k registros → Opção B. Se maior → Opção A.

---

### **ETAPA 3: EXECUÇÃO DO ALTER TABLE** 🚀

#### **3.1 - Script principal:**

```sql
-- ============================================
-- CRIAR COLUNA AD_SIMQTD1 NA TGFITE
-- Data: 2025-01-07
-- Autor: Semear / PackingHouse
-- ============================================

-- 1. Adicionar coluna
ALTER TABLE SANKHYA.TGFITE ADD (
  AD_SIMQTD1 NUMBER(15,3)
);

-- 2. Adicionar comentário (documentação)
COMMENT ON COLUMN SANKHYA.TGFITE.AD_SIMQTD1 IS 
'Simulacao Comercial: Quantidade Extra (caixas ou kg). Criado em 2025-01-07 pelo sistema PackingHouse.';

-- 3. Verificar criação
SELECT 
    COLUMN_NAME, 
    DATA_TYPE, 
    DATA_LENGTH, 
    DATA_PRECISION, 
    DATA_SCALE,
    NULLABLE
FROM ALL_TAB_COLUMNS
WHERE TABLE_NAME = 'TGFITE'
  AND COLUMN_NAME = 'AD_SIMQTD1'
  AND OWNER = 'SANKHYA';
```

**Anote a hora de execução:**
- Início: __:__
- Fim: __:__
- Tempo total: __ minutos

---

#### **3.2 - Validação pós-criação:**

```sql
-- Verificar que coluna foi criada
DESC SANKHYA.TGFITE;
-- Deve aparecer AD_SIMQTD1 no final

-- Verificar que dados antigos não foram afetados
SELECT COUNT(*) FROM TGFITE;
-- Deve ser o mesmo número de antes

-- Verificar que novos valores são NULL
SELECT COUNT(*) FROM TGFITE WHERE AD_SIMQTD1 IS NOT NULL;
-- Deve retornar 0 (zero)

-- Testar INSERT (criar registro de teste)
INSERT INTO TGFITE (
    NUNOTA, 
    SEQUENCIA, 
    CODPROD, 
    QTDNEG, 
    AD_SIMQTD1  -- Nova coluna
) VALUES (
    99999999,  -- Número fictício
    1, 
    12345, 
    100,
    50.5       -- Teste com decimal
);

-- Verificar se salvou
SELECT AD_SIMQTD1 FROM TGFITE WHERE NUNOTA = 99999999;
-- Deve retornar 50.5

-- Limpar teste
DELETE FROM TGFITE WHERE NUNOTA = 99999999;
COMMIT;
```

---

### **ETAPA 4: ATUALIZAR CÓDIGO BACKEND** 💻

#### **4.1 - Modificar views.py (salvamento):**

Localize a função `comercial_dist_save` (linha ~2340) e adicione o novo campo:

```python
# views.py - linha ~2366
def comercial_dist_save(request: HttpRequest) -> JsonResponse:
    # ... código existente ...
    
    # NOVO: Capturar quantidade simulação
    sim_qtd1 = _to_float_or(payload.get('sim_qtd1'))
    
    update_payload = {
        'NUNOTA': nunota,
        'SEQUENCIA': sequencia,
        'VLRUNIT': custo_kg,
        'VLRTOT': total,
        'AD_SIMQTD1': sim_qtd1,  # NOVO CAMPO
        'VLRDESCBONIF': _to_float_or(payload.get('sim_extra_total')),
        'VLRREPRED': _to_float_or(payload.get('sim_medio_cx')),
        # VLRACRESCDESC removido (conflito detectado)
    }
    
    # ... resto do código ...
```

---

#### **4.2 - Modificar views.py (carregamento):**

Atualizar queries que buscam dados da TGFITE:

```python
# Exemplo de SELECT que precisa incluir novo campo
sql = """
    SELECT 
        i.NUNOTA,
        i.SEQUENCIA,
        i.CODPROD,
        i.QTDNEG,
        i.VLRUNIT,
        i.VLRTOT,
        i.AD_SIMQTD1,      -- NOVO
        i.VLRDESCBONIF,
        i.VLRREPRED
    FROM TGFITE i
    WHERE i.NUNOTA = :nunota
      AND i.SEQUENCIA = :seq
"""

# Ao processar resultado:
row = cursor.fetchone()
if row:
    sim_qtd1 = row[6] if len(row) > 6 else None  # AD_SIMQTD1
```

---

### **ETAPA 5: ATUALIZAR CÓDIGO FRONTEND** 🎨

#### **5.1 - Modificar comercial_dashboard.html:**

```javascript
// Ao salvar distribuição (função de save)
const payload = {
  nunota: nunota,
  sequencia: sequencia,
  valor_total: valorTotal,
  custo_kg: custoKg,
  sim_qtd1: state.extraCx,  // NOVO: quantidade Extra
  sim_extra_total: state.extraCustoTotal,
  sim_medio_cx: state.medioCx,
  // sim_medio_total removido (era VLRACRESCDESC)
};

// Ao carregar item
const item = {
  // ... campos existentes ...
  sim_qtd1: row.ad_simqtd1 || 0,  // NOVO
  sim_extra_total: row.vlrdescbonif || 0,
  sim_medio_cx: row.vlrrepred || 0,
};
```

---

### **ETAPA 6: TESTE COMPLETO** 🧪

#### **6.1 - Teste manual (passo a passo):**

1. [ ] Abrir dashboard comercial
2. [ ] Selecionar um item da lista
3. [ ] Abrir classificação
4. [ ] Preencher valores de simulação
5. [ ] Clicar em "Salvar"
6. [ ] Verificar no banco:
   ```sql
   SELECT 
       NUNOTA, 
       SEQUENCIA, 
       AD_SIMQTD1,
       VLRDESCBONIF,
       VLRREPRED
   FROM TGFITE
   WHERE NUNOTA = [numero_do_teste]
     AND AD_SIMQTD1 IS NOT NULL;
   ```
7. [ ] Recarregar página
8. [ ] Verificar se valores aparecem corretamente

---

#### **6.2 - Teste de carga (opcional):**

```sql
-- Simular múltiplos registros
INSERT INTO TGFITE (NUNOTA, SEQUENCIA, CODPROD, QTDNEG, AD_SIMQTD1)
SELECT 
    NUNOTA, 
    SEQUENCIA, 
    CODPROD, 
    QTDNEG,
    50  -- Valor fixo para teste
FROM TGFITE
WHERE NUNOTA = [numero_existente]
  AND SEQUENCIA = 1
  AND ROWNUM <= 100;

-- Verificar performance de SELECT
SELECT COUNT(*), AVG(AD_SIMQTD1) FROM TGFITE WHERE AD_SIMQTD1 IS NOT NULL;

-- Limpar testes
DELETE FROM TGFITE WHERE AD_SIMQTD1 = 50;
COMMIT;
```

---

### **ETAPA 7: DOCUMENTAÇÃO** 📚

#### **7.1 - Criar arquivo de registro:**

Arquivo: `docs/CUSTOMIZACOES_BANCO.md`

```markdown
# Customizações no Banco Oracle Sankhya

## TGFITE - Itens de Nota Fiscal

### Colunas Customizadas (AD_*)

#### AD_SIMQTD1
- **Tipo:** NUMBER(15,3)
- **Descrição:** Quantidade simulação comercial (Extra - caixas ou kg)
- **Data criação:** 2025-01-07
- **Criado por:** Semear / PackingHouse
- **Sistema:** Dashboard Comercial
- **Uso:** Armazena quantidade de caixas Extra calculada na simulação
- **Relacionamento:** Usado junto com VLRDESCBONIF (custo Extra) e VLRREPRED (qtd Médio)
- **Script criação:** Ver arquivo `scripts/db/20250107_create_ad_simqtd1.sql`
```

---

#### **7.2 - Salvar script de criação:**

Arquivo: `scripts/db/20250107_create_ad_simqtd1.sql`

```sql
-- ============================================
-- CRIAR COLUNA AD_SIMQTD1 NA TGFITE
-- Data: 2025-01-07
-- Autor: Semear / PackingHouse
-- Sistema: Dashboard Comercial
-- ============================================

-- Verificar se coluna já existe
SELECT COUNT(*) AS existe
FROM ALL_TAB_COLUMNS
WHERE TABLE_NAME = 'TGFITE'
  AND COLUMN_NAME = 'AD_SIMQTD1'
  AND OWNER = 'SANKHYA';
-- Se retornar 1, coluna já existe (não executar script)

-- Adicionar coluna
ALTER TABLE SANKHYA.TGFITE ADD (
  AD_SIMQTD1 NUMBER(15,3)
);

-- Documentar
COMMENT ON COLUMN SANKHYA.TGFITE.AD_SIMQTD1 IS 
'Simulacao Comercial: Quantidade Extra (cx/kg). Criado 2025-01-07.';

-- Verificar criação
SELECT 
    COLUMN_NAME, 
    DATA_TYPE, 
    DATA_PRECISION, 
    DATA_SCALE
FROM ALL_TAB_COLUMNS
WHERE TABLE_NAME = 'TGFITE'
  AND COLUMN_NAME = 'AD_SIMQTD1'
  AND OWNER = 'SANKHYA';
```

---

#### **7.3 - Script de rollback (se precisar desfazer):**

Arquivo: `scripts/db/20250107_rollback_ad_simqtd1.sql`

```sql
-- ============================================
-- REMOVER COLUNA AD_SIMQTD1 DA TGFITE
-- ATENÇÃO: PERDE TODOS OS DADOS DA COLUNA!
-- ============================================

-- Verificar quantos registros têm dados
SELECT COUNT(*) AS registros_com_dados
FROM TGFITE
WHERE AD_SIMQTD1 IS NOT NULL;

-- Se realmente quer remover (IRREVERSÍVEL!):
-- ALTER TABLE SANKHYA.TGFITE DROP COLUMN AD_SIMQTD1;

-- Verificar remoção:
-- SELECT COUNT(*) FROM ALL_TAB_COLUMNS
-- WHERE TABLE_NAME = 'TGFITE' AND COLUMN_NAME = 'AD_SIMQTD1';
-- Deve retornar 0
```

---

### **ETAPA 8: COMMIT NO GIT** 📦

```bash
# Adicionar arquivos
git add docs/CUSTOMIZACOES_BANCO.md
git add scripts/db/20250107_create_ad_simqtd1.sql
git add scripts/db/20250107_rollback_ad_simqtd1.sql
git add sankhya_integration/views.py
git add sankhya_integration/templates/sankhya_integration/comercial_dashboard.html

# Commit
git commit -m "feat(db): adiciona coluna AD_SIMQTD1 na TGFITE para simulação

- Cria coluna AD_SIMQTD1 (NUMBER 15,3) para quantidade Extra
- Atualiza backend (views.py) para salvar/carregar novo campo
- Atualiza frontend (dashboard) para enviar/exibir novo campo
- Adiciona documentação e scripts de criação/rollback
- Remove uso de VLRACRESCDESC (conflito detectado)

Refs: #simulacao-comercial"

# Push
git push origin main
```

---

## 📋 CHECKLIST FINAL

### **Antes de Executar:**
- [ ] Verificou tamanho da TGFITE (SELECT COUNT)
- [ ] Anotou número de registros: ______________
- [ ] Escolheu horário de execução: __:__
- [ ] Fez backup (estrutura ou completo)
- [ ] Testou script em ambiente DEV (se tiver)

### **Execução:**
- [ ] Executou ALTER TABLE
- [ ] Executou COMMENT ON COLUMN
- [ ] Verificou com DESC TGFITE
- [ ] Testou INSERT de exemplo
- [ ] Limpou registro de teste

### **Pós-Execução:**
- [ ] Atualizou views.py (backend)
- [ ] Atualizou comercial_dashboard.html (frontend)
- [ ] Testou ciclo completo (salvar → carregar)
- [ ] Criou documentação
- [ ] Salvou scripts de criação/rollback
- [ ] Fez commit no Git

---

## ❓ PRÓXIMO PASSO

**Qual etapa você quer que eu detalhe mais ou te ajude a executar?**

1. [ ] Executar queries de verificação (ETAPA 1)
2. [ ] Criar script de backup (ETAPA 2)
3. [ ] Executar ALTER TABLE (ETAPA 3)
4. [ ] Modificar código backend (ETAPA 4)
5. [ ] Modificar código frontend (ETAPA 5)
6. [ ] Outro: ______________

**Me avise quando estiver pronto para prosseguir!** 🚀
