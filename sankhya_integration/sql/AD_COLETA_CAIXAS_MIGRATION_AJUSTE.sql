-- =============================================================================
-- Migration: AD_COLETA_CAIXAS ganha motivo 'AJUSTE_SALDO' + qtd pode ser negativa
-- Mai/2026 (2026-05-18)
--
-- Motivação
--   Inicialmente o controle de caixas registrava só eventos físicos
--   (COLETA/QUEBRA/PERDA). Em produção, descobrimos 2 cenários onde isso
--   não basta:
--
--   1. Saldo inicial: quando o controle começa, vários clientes já têm
--      caixas em campo do controle antigo (planilha/papel). Precisamos
--      registrar esse saldo de partida.
--
--   2. Ajuste pontual: eventualmente o saldo calculado diverge da
--      realidade física (caixa apareceu/sumiu sem registro). Operador
--      precisa corrigir.
--
--   Ambos os casos cabem no mesmo motivo 'AJUSTE_SALDO' — diferenciados
--   pelo contexto operacional, não pelo motivo formal.
--
-- Mudanças
--   - DROP+CREATE CK_AD_COLETA_MOTIVO: aceita 'AJUSTE_SALDO' como 4º valor
--   - DROP+CREATE CK_AD_COLETA_QTD: condicional ao motivo
--     - AJUSTE_SALDO: QTD_CAIXAS != 0 (positivo soma saldo, negativo desconta)
--     - COLETA/QUEBRA/PERDA: QTD_CAIXAS > 0 (como antes)
--   - COMMENT atualizado em MOTIVO
--
-- Rodar uma vez em servidores que aplicaram a DDL original (AD_COLETA_CAIXAS.sql).
-- Em servidores novos, a DDL canônica já contém essas constraints.
-- =============================================================================

ALTER TABLE SANKHYA.AD_COLETA_CAIXAS DROP CONSTRAINT CK_AD_COLETA_MOTIVO;
ALTER TABLE SANKHYA.AD_COLETA_CAIXAS DROP CONSTRAINT CK_AD_COLETA_QTD;

ALTER TABLE SANKHYA.AD_COLETA_CAIXAS ADD CONSTRAINT CK_AD_COLETA_MOTIVO
    CHECK (MOTIVO IN ('COLETA','QUEBRA','PERDA','AJUSTE_SALDO'));

ALTER TABLE SANKHYA.AD_COLETA_CAIXAS ADD CONSTRAINT CK_AD_COLETA_QTD
    CHECK (
        (MOTIVO = 'AJUSTE_SALDO' AND QTD_CAIXAS != 0)
        OR (MOTIVO IN ('COLETA','QUEBRA','PERDA') AND QTD_CAIXAS > 0)
    );

COMMENT ON COLUMN SANKHYA.AD_COLETA_CAIXAS.MOTIVO IS
    'COLETA=devolução normal | QUEBRA=voltou quebrada | PERDA=não voltou | AJUSTE_SALDO=correção excepcional (qtd pode ser negativa)';
