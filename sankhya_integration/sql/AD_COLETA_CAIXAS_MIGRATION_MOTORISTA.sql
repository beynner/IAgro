-- =============================================================================
-- AD_COLETA_CAIXAS — Migration adicionando CODPARC_MOTORISTA (Mai/2026 — 2026-05-29)
--
-- Objetivo: registrar QUEM foi buscar fisicamente as caixas no cliente
-- (motorista). Hoje a coluna CODUSU/NOMEUSU registra apenas o gestor que
-- clicou o lançamento — não o motorista que executou a coleta.
--
-- Decisões de design:
--   - NULL permitido pra preservar compatibilidade com linhas existentes
--     (coletas anteriores à 29/05/2026 ficam com motorista vazio).
--   - Validação "obrigatório quando motivo=COLETA" é feita na camada de
--     service (criar_coleta_caixas_banco) — não como CHECK constraint, pra
--     não invalidar dados legados.
--   - FK lógica (não física) pra TGFPAR.CODPARC. Motorista é validado via
--     AD_PARCEIRO_TIPO.AD_CODTIPPARC=4 (tipo MOTORISTA — mesmo cadastro da
--     Logística) — validação no service, não como CHECK aqui.
--   - QUEBRA/PERDA/AJUSTE_SALDO continuam SEM exigir motorista (são lançamentos
--     internos do gestor, sem motorista envolvido).
-- =============================================================================

DECLARE
    v_cnt NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_cnt
      FROM ALL_TAB_COLUMNS
     WHERE OWNER = 'SANKHYA'
       AND TABLE_NAME = 'AD_COLETA_CAIXAS'
       AND COLUMN_NAME = 'CODPARC_MOTORISTA';

    IF v_cnt = 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE SANKHYA.AD_COLETA_CAIXAS
                           ADD CODPARC_MOTORISTA NUMBER NULL';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN SANKHYA.AD_COLETA_CAIXAS.CODPARC_MOTORISTA
                           IS ''TGFPAR.CODPARC do motorista que buscou as caixas (tipo MOTORISTA em AD_PARCEIRO_TIPO). Obrigatório em motivo=COLETA, opcional nas demais. CODUSU/NOMEUSU continuam registrando o GESTOR que lançou o evento.''';
    END IF;
END;
/
