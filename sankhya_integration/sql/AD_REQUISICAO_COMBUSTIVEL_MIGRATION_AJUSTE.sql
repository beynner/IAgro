-- =============================================================================
-- Migration: AD_REQUISICAO_COMBUSTIVEL → suportar AJUSTE_AVULSO (Mai/2026 — 2026-05-28)
--
-- Lançado pra alimentar a tela admin /sankhya/configuracoes/ajustes/, sub-aba
-- Combustível. Lançamentos avulsos sem veículo:
--   - Qtd positiva: TOP 10 (entrada) — encontrou combustível no balanço
--   - Qtd negativa: TOP 53 (saída)  — combustível perdido / consumo sem rastro
--   - Justificativa obrigatória (audit)
--
-- 2 alterações:
--   1. CODVEICULO NULL permitido (era NOT NULL)
--   2. CHECK do TIPO ganha 'AJUSTE_AVULSO'
--
-- Idempotente: detecta estado atual antes de cada operação. Pode ser rodada
-- múltiplas vezes sem erro.
-- =============================================================================

-- 1. Tornar CODVEICULO nullable
DECLARE
    v_nullable VARCHAR2(1);
BEGIN
    SELECT NULLABLE INTO v_nullable
      FROM USER_TAB_COLUMNS
     WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
       AND COLUMN_NAME = 'CODVEICULO';
    IF v_nullable = 'N' THEN
        EXECUTE IMMEDIATE 'ALTER TABLE AD_REQUISICAO_COMBUSTIVEL MODIFY CODVEICULO NULL';
        DBMS_OUTPUT.PUT_LINE('CODVEICULO virou NULL');
    ELSE
        DBMS_OUTPUT.PUT_LINE('CODVEICULO ja era NULL — skip');
    END IF;
END;
/

-- 2. Atualizar CHECK constraint do TIPO (DROP + ADD)
DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count
      FROM USER_CONSTRAINTS
     WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
       AND CONSTRAINT_NAME = 'CK_AD_REQ_COMBUST_TIPO';
    IF v_count > 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE AD_REQUISICAO_COMBUSTIVEL DROP CONSTRAINT CK_AD_REQ_COMBUST_TIPO';
        DBMS_OUTPUT.PUT_LINE('Constraint antiga removida');
    END IF;

    EXECUTE IMMEDIATE q'[
        ALTER TABLE AD_REQUISICAO_COMBUSTIVEL ADD CONSTRAINT CK_AD_REQ_COMBUST_TIPO
        CHECK (TIPO IN ('INTERNA_FROTA','INTERNA_MAQUINARIO','EXTERNA_FRETE','EXTERNA_POSTO','AJUSTE_AVULSO'))
    ]';
    DBMS_OUTPUT.PUT_LINE('Constraint nova com AJUSTE_AVULSO adicionada');
END;
/

COMMIT;
