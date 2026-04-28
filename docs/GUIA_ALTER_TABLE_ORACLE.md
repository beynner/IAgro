# 🗄️ CRIAR COLUNAS NO ORACLE SANKHYA - Guia Completo

**Data:** 2025-01-07  
**Objetivo:** Explicar consequências, riscos e melhores práticas ao criar colunas customizadas

---

## 📋 O QUE É CRIAR UMA COLUNA?

### **Comando SQL:**
```sql
ALTER TABLE TGFITE ADD (
  AD_SIM_EXTRA_CX NUMBER(15,3)
);
```

### **O que acontece no banco:**
1. ✅ Oracle adiciona a coluna na **estrutura da tabela**
2. ✅ Coluna criada com valor **NULL** em todos os registros existentes
3. ✅ Espaço de armazenamento **não é ocupado** até inserir dados (Oracle é eficiente)
4. ✅ Não afeta dados existentes em outras colunas

---

## ⚠️ CONSEQUÊNCIAS E RISCOS

### **1. BACKUP E RECUPERAÇÃO**

#### **❌ RISCO CRÍTICO:**
```
Se você não tiver backup e algo der errado:
  ↓
Não há "UNDO" para ALTER TABLE!
  ↓
Perda potencial de dados
```

**✅ SOLUÇÃO:**
```sql
-- SEMPRE fazer backup antes
-- Opção 1: Backup da tabela
CREATE TABLE TGFITE_BACKUP_20250107 AS 
SELECT * FROM TGFITE;

-- Opção 2: Export/datapump
expdp user/pass@db tables=TGFITE file=tgfite_backup.dmp

-- Opção 3: Snapshot (se disponível)
CREATE RESTORE POINT ANTES_ALTER_TGFITE;
```

---

### **2. LOCKS E DISPONIBILIDADE**

#### **O que acontece durante ALTER TABLE:**

```
ALTER TABLE TGFITE ADD (coluna)
  ↓
Oracle BLOQUEIA a tabela (DDL Lock)
  ↓
Outras transações AGUARDAM
  ↓
Sistema pode ficar LENTO ou TRAVADO
```

**⏱️ TEMPO DE BLOQUEIO:**
- Tabela pequena (< 100k registros): **segundos**
- Tabela média (100k - 1M registros): **minutos**
- Tabela grande (> 1M registros): **10-30 minutos** ⚠️

**📊 TGFITE no Sankhya:**
- Típico: **500k - 5M registros**
- Tempo estimado: **5-15 minutos de bloqueio**

#### **✅ MELHOR PRÁTICA:**
```sql
-- Executar em HORÁRIO DE BAIXO MOVIMENTO
-- (madrugada, final de semana)

-- Verificar tamanho antes:
SELECT COUNT(*) FROM TGFITE;
-- Se > 1 milhão, agendar manutenção
```

---

### **3. TRIGGERS E INTEGRIDADE**

#### **Triggers Existentes:**

**Cenário 1: Trigger que faz SELECT * **
```sql
-- Trigger antigo (PERIGOSO!)
CREATE TRIGGER TRG_EXEMPLO
AFTER INSERT ON TGFITE
BEGIN
  INSERT INTO LOG_TABELA
  SELECT * FROM TGFITE WHERE ...;  -- ❌ Pode quebrar!
END;
```

**Problema:**
- `SELECT *` retorna TODAS as colunas
- Com nova coluna, estrutura muda
- Trigger pode **falhar** ou inserir dados errados

**✅ TGFITE é SEGURA:**
- Analisamos todos os triggers (docs/ANALISE_TGFITE_SIMULACAO.md)
- Nenhum usa `SELECT *` de forma perigosa
- Apenas COPY explícitos de colunas específicas

---

#### **Cenário 2: Validações e Constraints**

```sql
-- Se a tabela tem CHECK constraints:
ALTER TABLE TGFITE ADD CONSTRAINT CHK_VALOR
CHECK (VLRTOT >= 0);

-- Nova coluna precisa ser compatível
-- Senão, INSERT/UPDATE pode FALHAR
```

**✅ TGFITE:**
- Triggers não validam colunas customizadas (AD_*)
- Apenas colunas nativas têm validações

---

### **4. APLICAÇÕES E INTEGRAÇÕES**

#### **O que pode quebrar:**

**1. Relatórios Sankhya (Mago):**
```
Relatório com SELECT *
  ↓
Nova coluna aparece (AD_SIM_EXTRA_CX)
  ↓
Layout quebra (coluna extra não esperada)
```

**Probabilidade:** **BAIXA** (relatórios usam colunas específicas)

---

**2. Integrações externas:**
```
Sistema X lê TGFITE via API
  ↓
Estrutura mudou (nova coluna)
  ↓
Parser JSON/XML pode FALHAR
```

**Probabilidade:** **MÉDIA** (depende da integração)

**✅ CAMPOS AD_ SÃO SEGUROS:**
- Convenção Sankhya para customizações
- Sistemas externos ignoram campos AD_*
- Não aparecem em APIs padrão

---

**3. Nosso Sistema (IAgro):**
```python
# Nosso código atual:
cur.execute("SELECT NUNOTA, SEQUENCIA, VLRUNIT FROM TGFITE")
row = cur.fetchone()
# ✅ Não quebra! Continua pegando 3 colunas

# Se fizéssemos (NÃO fazemos):
cur.execute("SELECT * FROM TGFITE")
# ❌ Poderia quebrar se esperássemos índices fixos
```

**✅ NOSSO CÓDIGO É SEGURO:**
- Sempre usamos SELECTs explícitos
- Não dependemos de `SELECT *`
- Acessamos colunas por nome

---

### **5. PERFORMANCE E ÍNDICES**

#### **Impacto no desempenho:**

**Adicionar coluna:**
```sql
ALTER TABLE TGFITE ADD (AD_SIM_EXTRA_CX NUMBER);
```

**Impacto:**
- ✅ **Zero impacto** em queries que não usam a coluna
- ✅ Oracle não lê colunas NULL (otimização)
- ✅ Tabela cresce apenas quando dados são inseridos

**Preencher coluna:**
```sql
UPDATE TGFITE SET AD_SIM_EXTRA_CX = 50;
-- ⚠️ Pode demorar HORAS em tabela grande
```

**Impacto:**
- ⚠️ **Bloqueio prolongado**
- ⚠️ **Gera REDO/UNDO logs** (pode encher disco)
- ⚠️ **Invalida planos de execução** (queries ficam lentas temporariamente)

**✅ NOSSO CASO:**
- Apenas INSERT novos (não UPDATE em massa)
- Registros antigos ficam NULL (sem impacto)
- Performance mantida

---

#### **Índices:**

```sql
-- Se criar índice na coluna nova:
CREATE INDEX IDX_TGFITE_SIM_EXTRA ON TGFITE(AD_SIM_EXTRA_CX);

-- Impacto:
-- - Queries com WHERE/ORDER BY ficam RÁPIDAS
-- - INSERT/UPDATE ficam LEVEMENTE mais lentos (mantém índice)
-- - Ocupa espaço em disco (10-30% do tamanho da tabela)
```

**✅ RECOMENDAÇÃO:**
- **Não criar índice** inicialmente
- Apenas se houver queries frequentes tipo:
  ```sql
  WHERE AD_SIM_EXTRA_CX > 0
  ```

---

### **6. ESPAÇO EM DISCO**

#### **Quanto ocupa:**

**Estrutura (metadados):**
```
Adicionar coluna = ~1 KB (informações no dicionário Oracle)
```

**Dados:**
```
Por registro com valor:
- NUMBER(15,2) = 4-8 bytes
- VARCHAR2(100) = 1-100 bytes + overhead

Exemplo TGFITE:
- 1 milhão de registros
- 4 colunas NUMBER(15,2) = 16 bytes/registro
- Total: 16 MB (insignificante!)
```

**✅ SEM PREOCUPAÇÃO:**
- Espaço ocupado é mínimo
- Oracle compacta NULL (não ocupa espaço)

---

### **7. MANUTENÇÃO E DOCUMENTAÇÃO**

#### **❌ PROBLEMA COMUM:**

```sql
-- Alguém criou coluna há 2 anos:
ALTER TABLE TGFITE ADD (AD_TESTE_FULANO NUMBER);

-- Ninguém documenta
-- Ninguém lembra pra que serve
-- Vira "lixo técnico"
```

**✅ SOLUÇÃO:**

```sql
-- 1. Adicionar comentário (obrigatório!)
COMMENT ON COLUMN TGFITE.AD_SIM_EXTRA_CX IS 
'Simulacao Comercial: Quantidade de caixas Extra. Criado em 2025-01-07 por Semear.';

-- 2. Documentar em arquivo
-- docs/CUSTOMIZACOES_BANCO.md

-- 3. Adicionar no Git
git commit -m "feat: adiciona colunas simulação em TGFITE"
```

---

### **8. REVERSÃO (Como Desfazer)**

#### **❌ NÃO TEM ROLLBACK!**

```sql
-- Depois de ALTER TABLE:
ROLLBACK; -- ❌ NÃO FUNCIONA! DDL é auto-commit

-- Única forma:
ALTER TABLE TGFITE DROP COLUMN AD_SIM_EXTRA_CX;
-- ⚠️ CUIDADO: Perde todos os dados da coluna!
```

**✅ MELHOR PRÁTICA:**

```sql
-- Se não tiver certeza, criar em etapas:

-- 1. Criar coluna
ALTER TABLE TGFITE ADD (AD_SIM_EXTRA_CX NUMBER);

-- 2. Testar por 1 semana (dados em NULL)
-- INSERT novos usam, antigos não

-- 3. Se funcionar, continuar
-- Se não funcionar:
ALTER TABLE TGFITE DROP COLUMN AD_SIM_EXTRA_CX;
-- (dados ainda não foram escritos, nada se perde)
```

---

## 🔍 ALTERNATIVAS AO ALTER TABLE

### **OPÇÃO 1: Tabela Auxiliar (RECOMENDADO para testes)**

```sql
-- Criar tabela separada
CREATE TABLE TGFITE_SIMULACAO (
  NUNOTA NUMBER(10) NOT NULL,
  SEQUENCIA NUMBER(10) NOT NULL,
  SIM_EXTRA_CX NUMBER(15,3),
  SIM_EXTRA_TOTAL NUMBER(15,2),
  SIM_MEDIO_CX NUMBER(15,3),
  SIM_MEDIO_TOTAL NUMBER(15,2),
  DT_CALCULO DATE DEFAULT SYSDATE,
  CONSTRAINT PK_TGFITE_SIM PRIMARY KEY (NUNOTA, SEQUENCIA),
  CONSTRAINT FK_TGFITE_SIM FOREIGN KEY (NUNOTA, SEQUENCIA)
    REFERENCES TGFITE(NUNOTA, SEQUENCIA)
);
```

**Prós:**
- ✅ **Zero risco** para TGFITE
- ✅ **Fácil rollback** (DROP TABLE)
- ✅ **Não bloqueia** TGFITE
- ✅ **Pode testar** quanto tempo quiser
- ✅ **Fácil manutenção** (tabela dedicada)

**Contras:**
- ❌ **JOIN adicional** em queries (leve impacto)
- ❌ **Mais complexo** para desenvolver

**Query exemplo:**
```sql
-- Buscar item com simulação
SELECT 
  i.NUNOTA,
  i.SEQUENCIA,
  i.VLRUNIT,
  i.VLRTOT,
  s.SIM_EXTRA_CX,
  s.SIM_EXTRA_TOTAL,
  s.SIM_MEDIO_CX,
  s.SIM_MEDIO_TOTAL
FROM TGFITE i
LEFT JOIN TGFITE_SIMULACAO s ON i.NUNOTA = s.NUNOTA AND i.SEQUENCIA = s.SEQUENCIA
WHERE i.NUNOTA = 12345;
```

---

### **OPÇÃO 2: Usar Campos Existentes (NOSSA RECOMENDAÇÃO ATUAL)**

```sql
-- Não criar nada! Usar campos pouco usados:
PERCDESC → simExtraCx
VLRDESCBONIF → simExtraTotal
VLRREPRED → simMedioCx
VLRACRESCDESC → simMedioTotal
```

**Prós:**
- ✅ **Zero mudança** no banco
- ✅ **Zero risco** de bloqueio
- ✅ **Zero teste de compatibilidade**
- ✅ **Funciona imediatamente**

**Contras:**
- ⚠️ **Precisa validar** se campos não são usados
- ⚠️ **Conflito potencial** com outros sistemas

---

### **OPÇÃO 3: Banco NoSQL/JSON (Futuro)**

```python
# Salvar em MongoDB/Redis/Postgres JSONB
simulacao = {
  "nunota": 12345,
  "sequencia": 1,
  "extraCx": 50,
  "extraTotal": 3500,
  "medioCx": 110,
  "medioTotal": 3850
}
mongodb.simulacoes.insert_one(simulacao)
```

**Prós:**
- ✅ **Total flexibilidade**
- ✅ **Zero impacto** no Sankhya
- ✅ **Fácil evolução** (adicionar campos)

**Contras:**
- ❌ **Infraestrutura adicional** (novo banco)
- ❌ **Sincronização** necessária
- ❌ **Complexidade** aumentada

---

## 📊 COMPARAÇÃO DAS ABORDAGENS

| Critério | Campos Existentes | Tabela Auxiliar | ALTER TABLE | NoSQL |
|----------|-------------------|-----------------|-------------|-------|
| **Risco** | Baixo ⚠️ | Zero ✅ | Médio ⚠️ | Zero ✅ |
| **Tempo Setup** | Imediato ⚡ | 1 hora 🕐 | 30 min 🕐 | 1 dia 📅 |
| **Performance** | Ótima ✅ | Boa ✅ | Ótima ✅ | Boa ✅ |
| **Manutenção** | Simples ✅ | Média ⚠️ | Simples ✅ | Complexa ❌ |
| **Rollback** | Fácil ✅ | Fácil ✅ | Difícil ❌ | Fácil ✅ |
| **Compatibilidade** | Precisa validar ⚠️ | Total ✅ | Total ✅ | Total ✅ |
| **Custo** | Zero 💰 | Zero 💰 | Zero 💰 | Alto 💰💰 |

---

## 🎯 DECISÃO RECOMENDADA

### **FASE 1: VALIDAÇÃO (AGORA)**
```
Usar CAMPOS EXISTENTES (PERCDESC, VLRDESCBONIF, etc.)
  ↓
Executar queries de validação
  ↓
Se não houver conflito → IMPLEMENTAR
Se houver conflito → Fase 2
```

### **FASE 2: TESTE SEGURO (Se necessário)**
```
Criar TABELA AUXILIAR (TGFITE_SIMULACAO)
  ↓
Testar por 2-4 semanas
  ↓
Validar performance e usabilidade
  ↓
Se OK → Manter tabela auxiliar
Se problema → Fase 3
```

### **FASE 3: SOLUÇÃO DEFINITIVA (Se necessário)**
```
ALTER TABLE TGFITE ADD (AD_SIM_*)
  ↓
Agendar manutenção (madrugada/fim de semana)
  ↓
Backup completo antes
  ↓
Executar ALTER TABLE
  ↓
Migrar dados da tabela auxiliar
  ↓
DROP tabela auxiliar
```

---

## 🚨 CHECKLIST ANTES DE ALTER TABLE

### **Obrigatórios:**
- [ ] Backup completo do banco
- [ ] Backup específico da TGFITE
- [ ] Testar em ambiente de DESENVOLVIMENTO primeiro
- [ ] Agendar em horário de baixo movimento
- [ ] Notificar usuários (sistema ficará indisponível)
- [ ] Estimar tempo de bloqueio (SELECT COUNT(*) FROM TGFITE)
- [ ] Verificar espaço em disco (redo logs)
- [ ] Documentar as colunas (COMMENT ON COLUMN)

### **Recomendados:**
- [ ] Criar tabela de backup: `CREATE TABLE TGFITE_BAK AS SELECT * FROM TGFITE`
- [ ] Testar query de rollback (DROP COLUMN)
- [ ] Validar que não há `SELECT *` no código
- [ ] Verificar triggers afetados
- [ ] Criar plano de contingência (se der errado)
- [ ] Ter DBA disponível durante execução

---

## 📝 EXEMPLO COMPLETO: ALTER TABLE SEGURO

```sql
-- ==================================================
-- SCRIPT: Adicionar colunas simulação em TGFITE
-- DATA: 2025-01-07
-- AUTOR: Semear
-- IMPACTO: MÉDIO (ALTER TABLE em tabela crítica)
-- TEMPO ESTIMADO: 10-20 minutos
-- ==================================================

-- 1. VERIFICAÇÕES PRÉ-EXECUÇÃO
-- ==================================================
SELECT COUNT(*) AS total_registros FROM TGFITE;
-- Anotar: _____________ registros

SELECT ROUND(SUM(BYTES)/1024/1024, 2) AS tamanho_mb
FROM USER_SEGMENTS
WHERE SEGMENT_NAME = 'TGFITE';
-- Anotar: _____________ MB

-- 2. BACKUP
-- ==================================================
CREATE TABLE TGFITE_BACKUP_20250107 AS 
SELECT * FROM TGFITE;
-- Anotar hora início: __:__

-- Verificar backup
SELECT COUNT(*) FROM TGFITE_BACKUP_20250107;
-- Deve ser igual ao total_registros

-- 3. EXECUÇÃO (PONTO SEM VOLTA!)
-- ==================================================
-- ⚠️ A PARTIR DAQUI, NÃO TEM ROLLBACK!

ALTER TABLE TGFITE ADD (
  AD_SIM_EXTRA_CX NUMBER(15,3),
  AD_SIM_EXTRA_TOTAL NUMBER(15,2),
  AD_SIM_MEDIO_CX NUMBER(15,3),
  AD_SIM_MEDIO_TOTAL NUMBER(15,2)
);
-- Anotar hora fim: __:__
-- Anotar tempo total: __:__

-- 4. DOCUMENTAÇÃO
-- ==================================================
COMMENT ON COLUMN TGFITE.AD_SIM_EXTRA_CX IS 
'Simulacao Comercial: Qtd caixas Extra. Criado 2025-01-07.';

COMMENT ON COLUMN TGFITE.AD_SIM_EXTRA_TOTAL IS 
'Simulacao Comercial: Custo total Extra (R$). Criado 2025-01-07.';

COMMENT ON COLUMN TGFITE.AD_SIM_MEDIO_CX IS 
'Simulacao Comercial: Qtd caixas Medio. Criado 2025-01-07.';

COMMENT ON COLUMN TGFITE.AD_SIM_MEDIO_TOTAL IS 
'Simulacao Comercial: Custo total Medio (R$). Criado 2025-01-07.';

-- 5. VALIDAÇÃO PÓS-EXECUÇÃO
-- ==================================================
-- Verificar estrutura
DESC TGFITE;

-- Verificar que dados antigos não foram afetados
SELECT COUNT(*) FROM TGFITE;
-- Deve ser igual ao total_registros

SELECT COUNT(*) FROM TGFITE WHERE AD_SIM_EXTRA_CX IS NOT NULL;
-- Deve ser 0 (nenhum dado ainda)

-- Testar INSERT
INSERT INTO TGFITE (
  NUNOTA, SEQUENCIA, CODPROD, QTDNEG, 
  AD_SIM_EXTRA_CX, AD_SIM_EXTRA_TOTAL
) VALUES (
  99999999, 1, 12345, 100,
  50, 3500
);
COMMIT;

-- Testar SELECT
SELECT AD_SIM_EXTRA_CX, AD_SIM_EXTRA_TOTAL
FROM TGFITE
WHERE NUNOTA = 99999999;

-- Limpar teste
DELETE FROM TGFITE WHERE NUNOTA = 99999999;
COMMIT;

-- 6. LIMPEZA (Após 1 mês de sucesso)
-- ==================================================
-- DROP TABLE TGFITE_BACKUP_20250107;
-- (Manter comentado por segurança)

-- ==================================================
-- FIM DO SCRIPT
-- ==================================================
```

---

## ✅ CONCLUSÃO

### **ALTER TABLE é seguro SE:**
1. ✅ Fizer backup antes
2. ✅ Testar em DEV primeiro
3. ✅ Agendar em horário adequado
4. ✅ Ter plano de contingência
5. ✅ Documentar tudo

### **ALTER TABLE é arriscado SE:**
1. ❌ Não tiver backup
2. ❌ Executar em horário de pico
3. ❌ Não testar antes
4. ❌ Não souber reverter

### **NOSSA RECOMENDAÇÃO:**
**Começar com campos existentes → Se necessário, tabela auxiliar → Só fazer ALTER TABLE se realmente precisar**

**Risco vs Benefício:**
- Campos existentes: **Baixo risco, alta recompensa** 🎯
- Tabela auxiliar: **Zero risco, média recompensa** ✅
- ALTER TABLE: **Médio risco, alta recompensa** ⚠️

---

**Alguma dúvida sobre algum ponto específico?** 🚀
