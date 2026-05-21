-- =====================================================================
-- AD_ITEM_PRECO_ORIGEM — Audit da origem do preço de cada item de venda
-- Mai/2026 — 2026-05-20
-- =====================================================================
-- Registra de onde veio o VLRUNIT de cada TGFITE: Tabela do cliente,
-- Promoção vigente ou digitação Manual. Origem MANUAL exige OBSERVACAO
-- preenchida (validado no service `registrar_origem_preco_item`).
--
-- Detalhes em .claude/modules/venda.md → "Origem do preço".
-- =====================================================================

CREATE TABLE SANKHYA.AD_ITEM_PRECO_ORIGEM (
    NUNOTA        NUMBER NOT NULL,
    SEQUENCIA     NUMBER NOT NULL,
    ORIGEM        VARCHAR2(20) NOT NULL,
    NUTAB         NUMBER NULL,
    PROMOCAO_ID   NUMBER NULL,
    OBSERVACAO    VARCHAR2(500) NULL,
    CODUSU        NUMBER,
    REGISTRADO_EM TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT PK_AD_ITEM_PRECO_ORIGEM PRIMARY KEY (NUNOTA, SEQUENCIA),
    CONSTRAINT CK_AD_ORIGEM_VALOR
      CHECK (ORIGEM IN ('TABELA','PROMOCAO','MANUAL'))
);

COMMENT ON TABLE SANKHYA.AD_ITEM_PRECO_ORIGEM
  IS 'Origem do VLRUNIT de cada TGFITE de venda. Mai/2026.';
COMMENT ON COLUMN SANKHYA.AD_ITEM_PRECO_ORIGEM.ORIGEM
  IS 'TABELA (TGFEXC do cliente) | PROMOCAO (AD_PROMOCAO) | MANUAL (operador digitou)';
COMMENT ON COLUMN SANKHYA.AD_ITEM_PRECO_ORIGEM.NUTAB
  IS 'TGFTAB.NUTAB resolvida quando ORIGEM=TABELA';
COMMENT ON COLUMN SANKHYA.AD_ITEM_PRECO_ORIGEM.PROMOCAO_ID
  IS 'FK lógica AD_PROMOCAO.ID quando ORIGEM=PROMOCAO';
COMMENT ON COLUMN SANKHYA.AD_ITEM_PRECO_ORIGEM.OBSERVACAO
  IS 'Obrigatória quando ORIGEM=MANUAL — operador explica o porquê do override';
