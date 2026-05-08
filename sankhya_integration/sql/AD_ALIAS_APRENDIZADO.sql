-- =============================================================================
-- Tabelas: SANKHYA.AD_PRODUTO_ALIAS + SANKHYA.AD_PARCEIRO_ALIAS
-- Pacote/Módulo: IAgro — Aprendizado do módulo de Importação por E-mail
--
-- Objetivo
--   Após o operador confirmar um pré-pedido (clicar "Confirmar e criar pedido"),
--   gravamos as decisões dele aqui:
--     - Cada item:    (DESCRICAO_PDF normalizada → CODPROD escolhido)
--     - Cabeçalho:    (NOME_CLIENTE extraído pelo LLM normalizado → CODPARC escolhido)
--
--   Na próxima vez que o LLM extrair a MESMA descrição/nome (após normalização),
--   o matching consulta esta tabela ANTES de cair no fuzzy de TGFPRO/TGFPAR.
--   Se houver alias salvo, retorna direto — operador NÃO precisa corrigir de novo.
--
-- Importante
--   - Isto NÃO é Machine Learning. É um dicionário de-para com match exato em
--     string normalizada. Sem treinamento, sem inferência, sem black box.
--   - Auditável: cada linha tem CRIADO_EM, ULTIMO_USO, COUNT_USADO. Para reverter
--     uma decisão errada, basta DELETE da linha — sistema volta a usar fuzzy.
--   - O aprendizado SÓ acontece no clique de "Confirmar e criar pedido" — o
--     operador "aval" garante qualidade do alias.
--
-- Convenção de normalização
--   Idêntica à usada em services.matching:
--     produto:  strip de acentos, lowercase, remoção de sufixos KG/UN/BD/etc,
--               remoção de código numérico colado ao início, dedupe de tokens.
--     parceiro: strip de acentos, lowercase, remoção de sufixos LTDA/S/A/ME/etc,
--               dedupe de tokens.
--
-- =============================================================================

-- -----------------------------------------------------------------------------
-- TABELA: alias de produtos
-- 1 linha por (descricao_normalizada, codparc opcional). Quando codparc é NULL,
-- o alias vale pra qualquer cliente.
-- -----------------------------------------------------------------------------
CREATE TABLE AD_PRODUTO_ALIAS (
    ID                    NUMBER         NOT NULL,
    DESCRICAO_NORMALIZADA VARCHAR2(500)  NOT NULL,
    CODPROD               NUMBER         NOT NULL,
    CODPARC               NUMBER,                                 -- NULL = global
    COUNT_USADO           NUMBER         DEFAULT 0  NOT NULL,
    ULTIMO_USO            TIMESTAMP,
    CONFIRMADO_POR        NUMBER,                                 -- CODUSU operador
    CRIADO_EM             TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_AD_PRODUTO_ALIAS PRIMARY KEY (ID),
    -- Anti-duplicação: mesma descricao_normalizada + mesmo codparc só pode existir 1x.
    -- Tratamos NULL como valor distinto via NVL — Oracle UNIQUE permite múltiplas
    -- linhas com NULL na mesma coluna por padrão; usar NVL evita ambiguidade.
    CONSTRAINT UK_AD_PRODUTO_ALIAS UNIQUE (DESCRICAO_NORMALIZADA, CODPARC)
);

CREATE SEQUENCE SEQ_AD_PRODUTO_ALIAS
    START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;

-- Índice pra buscar por descricao_normalizada (lookup principal do matching)
CREATE INDEX IX_AD_PRODUTO_ALIAS_DESCR
    ON AD_PRODUTO_ALIAS (DESCRICAO_NORMALIZADA);

-- Índice opcional para auditoria por CODPROD: "quais descrições já mapearam pra X?"
CREATE INDEX IX_AD_PRODUTO_ALIAS_CODPROD
    ON AD_PRODUTO_ALIAS (CODPROD);

COMMENT ON TABLE  AD_PRODUTO_ALIAS IS
    'IAgro: aprendizado de mapeamento descricao_PDF -> CODPROD após confirmação humana';
COMMENT ON COLUMN AD_PRODUTO_ALIAS.DESCRICAO_NORMALIZADA IS
    'Descrição extraída do PDF, normalizada (lowercase, sem acentos, sem sufixos de unidade)';
COMMENT ON COLUMN AD_PRODUTO_ALIAS.CODPARC IS
    'NULL = alias vale pra qualquer cliente. Preenchido = scope-specific';
COMMENT ON COLUMN AD_PRODUTO_ALIAS.COUNT_USADO IS
    'Quantas vezes este alias resolveu um matching (incrementa em cada uso)';


-- -----------------------------------------------------------------------------
-- TABELA: alias de parceiros (clientes)
-- 1 linha por (nome_normalizado).
-- -----------------------------------------------------------------------------
CREATE TABLE AD_PARCEIRO_ALIAS (
    ID                NUMBER         NOT NULL,
    NOME_NORMALIZADO  VARCHAR2(500)  NOT NULL,
    CODPARC           NUMBER         NOT NULL,
    COUNT_USADO       NUMBER         DEFAULT 0  NOT NULL,
    ULTIMO_USO        TIMESTAMP,
    CONFIRMADO_POR    NUMBER,                                 -- CODUSU operador
    CRIADO_EM         TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_AD_PARCEIRO_ALIAS PRIMARY KEY (ID),
    CONSTRAINT UK_AD_PARCEIRO_ALIAS UNIQUE (NOME_NORMALIZADO)
);

CREATE SEQUENCE SEQ_AD_PARCEIRO_ALIAS
    START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;

-- Índice implícito do UNIQUE (NOME_NORMALIZADO) já cobre lookup principal —
-- não precisa criar IX_AD_PARCEIRO_ALIAS_NOME explícito.

CREATE INDEX IX_AD_PARCEIRO_ALIAS_CODPARC
    ON AD_PARCEIRO_ALIAS (CODPARC);

COMMENT ON TABLE  AD_PARCEIRO_ALIAS IS
    'IAgro: aprendizado de mapeamento nome_cliente_extraido -> CODPARC após confirmação';
COMMENT ON COLUMN AD_PARCEIRO_ALIAS.NOME_NORMALIZADO IS
    'Nome extraído do PDF, normalizado (lowercase, sem acentos, sem sufixos societários)';


-- -----------------------------------------------------------------------------
-- ROLLBACK (manual, se precisar reverter)
-- -----------------------------------------------------------------------------
-- DROP TABLE    SANKHYA.AD_PRODUTO_ALIAS  CASCADE CONSTRAINTS;
-- DROP TABLE    SANKHYA.AD_PARCEIRO_ALIAS CASCADE CONSTRAINTS;
-- DROP SEQUENCE SANKHYA.SEQ_AD_PRODUTO_ALIAS;
-- DROP SEQUENCE SANKHYA.SEQ_AD_PARCEIRO_ALIAS;
