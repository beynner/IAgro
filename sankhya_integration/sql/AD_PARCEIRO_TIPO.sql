-- =============================================================================
-- Tabela: SANKHYA.AD_PARCEIRO_TIPO
-- Pacote/Módulo: IAgro — Junção N:N parceiro × tipo de parceiro
--
-- Objetivo
--   Vincular cada parceiro (TGFPAR.CODPARC) a um ou mais tipos cadastrados
--   em AD_TIPO_PARCEIRO. Substitui as flags nativas TGFPAR.{CLIENTE,
--   FORNECEDOR, USUARIO, MOTORISTA, TRANSPORTADORA, VENDEDOR} no contexto
--   IAgro, permitindo classificações ricas (ex.: parceiro 536 = CLIENTE +
--   FORNECEDOR + USUARIO em 3 linhas separadas).
--
-- Modelo
--   PK composta (CODPARC, AD_CODTIPPARC) garante unicidade do vínculo —
--   impossível ter 2 linhas idênticas. INSERT idempotente via NOT EXISTS.
--
-- FK lógicas (sem constraint física, padrão dos AD_* do projeto)
--   - CODPARC          → TGFPAR.CODPARC
--   - AD_CODTIPPARC    → AD_TIPO_PARCEIRO.ID
--
--   Razão da ausência de FK física:
--     a) Spin-off do IAgro vai recriar TGFPAR em schema próprio — FK física
--        dificultaria a migração suave.
--     b) Sankhya nativo continua escrevendo em TGFPAR sem conhecer essa
--        tabela; FK CASCADE poderia gerar inconsistências.
--     c) Performance — INSERT sem checagem de FK é levemente mais rápido,
--        e validação acontece no código (`oracle_conn.py`).
--
-- Índice reverso IDX_AD_PARC_TIPO_TIPO (AD_CODTIPPARC, CODPARC)
--   Acelera typeaheads "lista todos os MOTORISTAs" (WHERE AD_CODTIPPARC=4)
--   — o índice cobre o WHERE e a coluna retornada (CODPARC), virando index-only
--   scan na maioria das queries.
--
-- Inativação de parceiro
--   Vínculos em AD_PARCEIRO_TIPO PERMANECEM mesmo após TGFPAR.ATIVO='N'.
--   IAgro filtra pelo ATIVO da TGFPAR nas queries de typeahead — preserva
--   histórico de "este parceiro foi cliente entre X e Y datas".
-- =============================================================================

CREATE TABLE SANKHYA.AD_PARCEIRO_TIPO (
    CODPARC        NUMBER         NOT NULL,
    AD_CODTIPPARC  NUMBER         NOT NULL,
    CODUSU         NUMBER,
    NOMEUSU        VARCHAR2(60),
    CRIADO_EM      TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_AD_PARCEIRO_TIPO PRIMARY KEY (CODPARC, AD_CODTIPPARC)
);

-- Índice reverso (typeahead "lista parceiros de tipo X" começa pelo tipo)
CREATE INDEX SANKHYA.IDX_AD_PARC_TIPO_TIPO
    ON SANKHYA.AD_PARCEIRO_TIPO (AD_CODTIPPARC, CODPARC);

COMMENT ON TABLE  SANKHYA.AD_PARCEIRO_TIPO               IS 'IAgro - junção N:N parceiro (TGFPAR.CODPARC) x tipo (AD_TIPO_PARCEIRO.ID). Substitui flags nativas TGFPAR no contexto IAgro. Ver AD_PARCEIRO_TIPO.sql';
COMMENT ON COLUMN SANKHYA.AD_PARCEIRO_TIPO.CODPARC       IS 'FK logica para TGFPAR.CODPARC';
COMMENT ON COLUMN SANKHYA.AD_PARCEIRO_TIPO.AD_CODTIPPARC IS 'FK logica para AD_TIPO_PARCEIRO.ID';
COMMENT ON COLUMN SANKHYA.AD_PARCEIRO_TIPO.CODUSU        IS 'Usuario que criou o vinculo (NULL em migracao inicial)';
COMMENT ON COLUMN SANKHYA.AD_PARCEIRO_TIPO.NOMEUSU       IS 'Nome do usuario. Migracao inicial grava SEED_INICIAL/MIGRACAO_INICIAL';
