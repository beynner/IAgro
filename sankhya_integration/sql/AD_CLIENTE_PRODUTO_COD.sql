-- =============================================================================
-- TABELA: SANKHYA.AD_CLIENTE_PRODUTO_COD
-- Pacote: IAgro — Importação de pedidos por e-mail (LLM + Matching híbrido)
-- Data:   Maio/2026
--
-- Objetivo
--   Mapear (CODPARC, COD_CLIENTE) -> CODPROD interno (TGFPRO).
--   Em pedidos de redes (Assaí/SENDAS/Consinco), o PDF traz o "Cod Forn"
--   na primeira coluna da tabela de itens — código que o CLIENTE usa pra
--   identificar nosso produto (ex: 8117 = "PIMENTAO VERDE", 8132 = "BERINJELA").
--
--   Após o operador confirmar 1 pedido daquele cliente, a vinculação
--   (CODPARC, COD_CLIENTE) -> CODPROD fica gravada aqui, e os pedidos
--   futuros do mesmo cliente são casados AUTOMATICAMENTE com confiança 100%
--   — sem precisar de fuzzy/alias por descrição.
--
--   Hierarquia de matching de produto (do mais forte ao mais fraco):
--     Nível 1: COD_CLIENTE casa em AD_CLIENTE_PRODUTO_COD          (esta tabela)
--     Nível 2: descrição casa em AD_PRODUTO_ALIAS                  (alias por texto)
--     Nível 3: fuzzy contra TGFPRO (rapidfuzz)                     (fallback)
--
-- Auditável e reversível
--   `CONFIRMADO_POR` registra qual CODUSU gravou. Se uma decisão se mostrar
--   errada, basta DELETE da linha — sistema volta a usar fuzzy. Sem caixa
--   preta, sem ML.
-- =============================================================================

-- 1. Tabela principal
CREATE TABLE AD_CLIENTE_PRODUTO_COD (
    ID                NUMBER         NOT NULL,
    CODPARC           NUMBER         NOT NULL,
    COD_CLIENTE       VARCHAR2(50)   NOT NULL,
    CODPROD           NUMBER         NOT NULL,
    COUNT_USADO       NUMBER         DEFAULT 0,
    ULTIMO_USO        TIMESTAMP,
    CONFIRMADO_POR    NUMBER,
    CRIADO_EM         TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_AD_CLIENTE_PRODUTO_COD PRIMARY KEY (ID),
    CONSTRAINT UK_AD_CLIENTE_PRODUTO_COD UNIQUE (CODPARC, COD_CLIENTE)
);

CREATE SEQUENCE SEQ_AD_CLIENTE_PRODUTO_COD
    START WITH 1
    INCREMENT BY 1
    NOCACHE
    NOCYCLE;

-- 2. Índice pra acelerar lookup mais comum (CODPARC + COD_CLIENTE)
-- Já temos UNIQUE constraint na tupla — Oracle cria índice automaticamente.
-- Não precisa de índice adicional.

-- 3. Comentários descritivos (úteis em SQL Developer / BI)
COMMENT ON TABLE AD_CLIENTE_PRODUTO_COD IS
    'Mapeamento (CODPARC, COD_CLIENTE) -> CODPROD. Aprendizado por pedido confirmado.';
COMMENT ON COLUMN AD_CLIENTE_PRODUTO_COD.CODPARC IS
    'Nosso parceiro (Assaí, etc.) — FK lógica para TGFPAR.CODPARC';
COMMENT ON COLUMN AD_CLIENTE_PRODUTO_COD.COD_CLIENTE IS
    'Código que o CLIENTE usa pra identificar este produto no PDF dele';
COMMENT ON COLUMN AD_CLIENTE_PRODUTO_COD.CODPROD IS
    'Nosso CODPROD interno — FK lógica para TGFPRO.CODPROD';
COMMENT ON COLUMN AD_CLIENTE_PRODUTO_COD.COUNT_USADO IS
    'Quantas vezes este mapeamento já foi usado (analytics; incrementa a cada hit)';

-- =============================================================================
-- ALTER em AD_PEDIDO_EMAIL_ITEM: nova coluna COD_CLIENTE pra persistir o
-- código extraído do PDF (mesmo antes da confirmação) — usada no matching
-- e gravada como alias após confirmação humana.
-- =============================================================================
ALTER TABLE AD_PEDIDO_EMAIL_ITEM
    ADD COD_CLIENTE VARCHAR2(50);

COMMENT ON COLUMN AD_PEDIDO_EMAIL_ITEM.COD_CLIENTE IS
    'Código do produto na visão do CLIENTE (ex: 8117 = PIMENTAO VERDE em pedidos Consinco). Usado pra matching híbrido + aprendizado.';

-- =============================================================================
-- Permissões para o usuário da aplicação (descomentar e ajustar nome)
-- =============================================================================
-- GRANT SELECT, INSERT, UPDATE, DELETE ON SANKHYA.AD_CLIENTE_PRODUTO_COD TO <usuario_iagro>;
-- GRANT SELECT                          ON SANKHYA.SEQ_AD_CLIENTE_PRODUTO_COD TO <usuario_iagro>;

-- =============================================================================
-- Verificação após aplicação
-- =============================================================================
-- SELECT COUNT(*) FROM AD_CLIENTE_PRODUTO_COD;     -- deve ser 0 (vazia)
-- SELECT COLUMN_NAME, DATA_TYPE, NULLABLE
--   FROM USER_TAB_COLUMNS
--  WHERE TABLE_NAME = 'AD_PEDIDO_EMAIL_ITEM'
--    AND COLUMN_NAME = 'COD_CLIENTE';
-- Resultado esperado: COD_CLIENTE  VARCHAR2  Y
--
-- =============================================================================
-- ROLLBACK (manual, se precisar reverter)
-- =============================================================================
-- DROP TABLE SANKHYA.AD_CLIENTE_PRODUTO_COD;
-- DROP SEQUENCE SANKHYA.SEQ_AD_CLIENTE_PRODUTO_COD;
-- ALTER TABLE SANKHYA.AD_PEDIDO_EMAIL_ITEM DROP COLUMN COD_CLIENTE;
