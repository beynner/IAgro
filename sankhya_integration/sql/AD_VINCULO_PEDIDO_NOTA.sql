-- =============================================================================
-- Tabela: SANKHYA.AD_VINCULO_PEDIDO_NOTA
-- Pacote/Módulo: IAgro — Rastreabilidade (WMS)
--
-- Objetivo
--   Suportar vinculações manuais pedido↔nota feitas pelo IAgro quando o
--   fluxo padrão do Sankhya (que popularia TGFVAR) não foi seguido. Casos
--   reais:
--
--     (a) ORIGEM = 'VINCULADO' (Leva A, Mai/2026)
--         Existe pedido TOP 34 STATUSNOTA='L' E nota TOP 35/37 STATUSNOTA='L'
--         pareáveis (mesmo CODPARC, DTNEG, valor), mas Sankhya não populou
--         TGFVAR. Operador vincula manualmente pelo IAgro pra rastreabilidade
--         funcionar igual ao caso natural.
--         Exemplo: NUNOTA 111975 (pedido) ↔ NUNOTA 111976 (nota 6267).
--
--     (b) ORIGEM = 'PEDIDO_RETROATIVO' (Leva B, planejada)
--         Nota foi venda direta sem pedido. IAgro cria pedido TOP 34
--         espelhando os itens da nota e registra o vínculo aqui.
--         Exemplo: NUNOTA 111825 (nota 6242) — sem pedido pareável.
--
-- Por que tabela auxiliar e não TGFVAR
--   TGFVAR é populada exclusivamente pela trigger interna do Sankhya
--   (TRG_INC_TGFVAR), que dispara cascata em TGMTRA (movimentação
--   financeira/meta-orçamento), TGFITE.QTDENTREGUE e outras. INSERT manual
--   sem ambiente de homologação Sankhya é arriscado — ver gotcha
--   ".claude/gotchas.md" → "TGFVAR é populada via trigger Sankhya".
--   Esta tabela vive 100% no schema IAgro/Sankhya como auxiliar; queries
--   do Rastreio leem TGFVAR + esta tabela em UNION pra resolver o par.
--
-- UNIQUE em NUNOTA_NOTA e NUNOTA_PEDIDO
--   Garante 1↔1. Operador não pode vincular a mesma nota a 2 pedidos nem
--   o mesmo pedido a 2 notas. Reverte com DELETE.
--
-- ORIGEM
--   Distingue os 2 fluxos pra audit / badge visual:
--     - 'VINCULADO'          → Op 1 (Leva A): pedido pré-existente
--     - 'PEDIDO_RETROATIVO'  → Op 2 (Leva B): pedido criado pelo IAgro
-- =============================================================================

CREATE TABLE SANKHYA.AD_VINCULO_PEDIDO_NOTA (
    ID            NUMBER          NOT NULL,
    NUNOTA_PEDIDO NUMBER          NOT NULL,
    NUNOTA_NOTA   NUMBER          NOT NULL,
    ORIGEM        VARCHAR2(20)    NOT NULL,
    CODUSU        NUMBER          NOT NULL,
    NOMEUSU       VARCHAR2(80),
    CRIADO_EM     TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    OBSERVACAO    VARCHAR2(500),
    CONSTRAINT PK_AD_VINCULO_PED_NOTA PRIMARY KEY (ID),
    CONSTRAINT UQ_AD_VINCULO_NOTA     UNIQUE (NUNOTA_NOTA),
    CONSTRAINT UQ_AD_VINCULO_PEDIDO   UNIQUE (NUNOTA_PEDIDO),
    CONSTRAINT CK_AD_VINCULO_ORIGEM   CHECK (ORIGEM IN ('VINCULADO', 'PEDIDO_RETROATIVO'))
);

CREATE SEQUENCE SANKHYA.SEQ_AD_VINCULO_PEDIDO_NOTA START WITH 1 INCREMENT BY 1 NOCYCLE NOCACHE;

-- Índice secundário pra busca por NUNOTA_PEDIDO (UNIQUE já cobre, mas
-- documentando que esse campo é consultado frequentemente em joins
-- da query principal).
COMMENT ON TABLE  SANKHYA.AD_VINCULO_PEDIDO_NOTA              IS 'IAgro — vínculo manual pedido↔nota quando TGFVAR não foi populado pelo Sankhya. Ver AD_VINCULO_PEDIDO_NOTA.sql';
COMMENT ON COLUMN SANKHYA.AD_VINCULO_PEDIDO_NOTA.NUNOTA_PEDIDO IS 'TGFCAB.NUNOTA do TOP 34 (pedido)';
COMMENT ON COLUMN SANKHYA.AD_VINCULO_PEDIDO_NOTA.NUNOTA_NOTA   IS 'TGFCAB.NUNOTA do TOP 35/37 (nota)';
COMMENT ON COLUMN SANKHYA.AD_VINCULO_PEDIDO_NOTA.ORIGEM        IS 'VINCULADO=Op 1 (pedido pré-existente) | PEDIDO_RETROATIVO=Op 2 (pedido criado pelo IAgro)';
