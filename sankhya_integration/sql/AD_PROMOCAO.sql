-- =====================================================================
-- AD_PROMOCAO — Promoções por (Tabela de cliente) OU (Parceiro específico)
-- Mai/2026 — 2026-05-20 (criada) · 2026-05-21 (ALTER: escopo flexível)
-- =====================================================================
-- Escopo pode ser:
--   • CODTAB preenchido → promoção pra TODOS os parceiros TGFPAR com esse CODTAB
--     (ex: CODTAB=5 = "Assaí DF" — afeta as 7 lojas Assaí DF de uma vez)
--   • CODPARC preenchido → promoção pra 1 cliente específico
--   • CHECK XOR garante exatamente 1 dos 2 preenchido
--
-- Detalhes em .claude/modules/venda.md → "Promoções por (Tabela × Produto)".
-- =====================================================================

CREATE TABLE SANKHYA.AD_PROMOCAO (
    ID            NUMBER PRIMARY KEY,
    CODPROD       NUMBER NOT NULL,
    CODTAB        NUMBER NULL,
    CODPARC       NUMBER NULL,
    VLRPROMO      NUMBER(15,4) NOT NULL,
    DT_INICIO     DATE NOT NULL,
    DT_FIM        DATE NOT NULL,
    ATIVO         CHAR(1) DEFAULT 'S' NOT NULL,
    OBSERVACAO    VARCHAR2(500),
    CODUSU        NUMBER,
    NOMEUSU       VARCHAR2(50),
    CRIADO_EM     TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT CK_AD_PROMO_ATV CHECK (ATIVO IN ('S','N')),
    CONSTRAINT CK_AD_PROMO_DT  CHECK (DT_FIM >= DT_INICIO),
    CONSTRAINT CK_AD_PROMO_VLR CHECK (VLRPROMO > 0),
    CONSTRAINT CK_AD_PROMO_ESCOPO CHECK (
        (CODTAB IS NOT NULL AND CODPARC IS NULL) OR
        (CODTAB IS NULL AND CODPARC IS NOT NULL)
    )
);

CREATE SEQUENCE SANKHYA.SEQ_AD_PROMOCAO START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE INDEX SANKHYA.IDX_AD_PROMO_VIGENTE
  ON SANKHYA.AD_PROMOCAO (CODPARC, CODPROD, ATIVO, DT_INICIO, DT_FIM);

CREATE INDEX SANKHYA.IDX_AD_PROMO_CODTAB
  ON SANKHYA.AD_PROMOCAO (CODTAB, CODPROD, ATIVO, DT_INICIO, DT_FIM);

COMMENT ON TABLE SANKHYA.AD_PROMOCAO
  IS 'Promoções IAgro por (CODTAB ou CODPARC) × CODPROD. Mai/2026.';
COMMENT ON COLUMN SANKHYA.AD_PROMOCAO.CODTAB
  IS 'TGFTAB.CODTAB — quando preenchido, afeta TODOS os TGFPAR com esse CODTAB';
COMMENT ON COLUMN SANKHYA.AD_PROMOCAO.CODPARC
  IS 'TGFPAR.CODPARC — quando preenchido, afeta só esse cliente';
COMMENT ON COLUMN SANKHYA.AD_PROMOCAO.VLRPROMO
  IS 'Preço promocional unitário (> 0)';
COMMENT ON COLUMN SANKHYA.AD_PROMOCAO.ATIVO
  IS 'S/N — promoção desligada (N) não aparece na consulta';
