-- =============================================================================
-- Tabela: SANKHYA.AD_PRODUTO_CAIXA
-- Pacote/Módulo: IAgro — Controle de Caixas
--
-- Objetivo
--   Mapear CODPROD → TIPO_CAIXA pra distinguir produtos que vão em
--   caixa plástica (controla saldo) de produtos em caixa de papelão
--   (descartável, não controla).
--
--   Hortifrúti em geral vai em plástica (default). Produtos que vão em
--   papelão são exceção (mudas, pequenas embalagens, etc.) e operador
--   cadastra explicitamente.
--
-- Default
--   Produto SEM linha nesta tabela é tratado como PLASTICA pelo backend.
--   Razão: maioria absoluta dos produtos da Agromil vai em plástica;
--   cadastrar 1-pra-1 todos seria custo desnecessário. Operador cadastra
--   apenas os que são papelão.
--
-- Por que tabela auxiliar (não coluna em TGFPRO)
--   Regra crítica #7 do CLAUDE.md: evitar adicionar colunas em tabelas
--   Sankhya nativas. Tabela auxiliar isola schema, facilita o spin-off
--   futuro do IAgro.
-- =============================================================================

CREATE TABLE SANKHYA.AD_PRODUTO_CAIXA (
    CODPROD     NUMBER          NOT NULL,
    TIPO_CAIXA  VARCHAR2(20)    NOT NULL,
    CODUSU      NUMBER          NOT NULL,
    NOMEUSU     VARCHAR2(80),
    CRIADO_EM   TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    ATUALIZADO_EM TIMESTAMP,
    ATUALIZADO_POR NUMBER,
    CONSTRAINT PK_AD_PRODUTO_CAIXA PRIMARY KEY (CODPROD),
    CONSTRAINT CK_AD_PRODUTO_CAIXA_TIPO CHECK (TIPO_CAIXA IN ('PLASTICA', 'PAPELAO'))
);

COMMENT ON TABLE  SANKHYA.AD_PRODUTO_CAIXA              IS 'IAgro — mapeamento CODPROD→tipo de caixa. Produto sem linha = PLASTICA (default). Ver AD_PRODUTO_CAIXA.sql';
COMMENT ON COLUMN SANKHYA.AD_PRODUTO_CAIXA.CODPROD      IS 'TGFPRO.CODPROD do produto';
COMMENT ON COLUMN SANKHYA.AD_PRODUTO_CAIXA.TIPO_CAIXA   IS 'PLASTICA=retornável, conta saldo | PAPELAO=descartável, não conta';
