-- =============================================================================
-- Tabela: SANKHYA.AD_TIPO_PARCEIRO
-- Pacote/Módulo: IAgro — Cadastro genérico de tipos de parceiro
--
-- Objetivo
--   Substituir, no contexto IAgro, as flags nativas booleanas dispersas em
--   TGFPAR (CLIENTE, FORNECEDOR, USUARIO, MOTORISTA, TRANSPORTADORA,
--   VENDEDOR) por um cadastro centralizado de tipos. Permite adicionar
--   tipos novos (ex.: AJUDANTE, OPER_PATIO, COMISSARIO) sem ALTER TABLE
--   em TGFPAR — basta INSERT nesta tabela.
--
--   Os tipos são vinculados a parceiros via AD_PARCEIRO_TIPO (N:N).
--
-- Estratégia de migração (one-time):
--   Sankhya nativo permanece com as flags em S — não deletamos nada.
--   Script de migração copia (CLIENTE='S' → AD_PARCEIRO_TIPO(tipo=1)) etc.
--   IAgro lê só de AD_PARCEIRO_TIPO; Sankhya continua usando as flags.
--   Tendência: IAgro vira fonte única conforme spin-off (vide
--   `.claude/dependencias_sankhya.md` §5.5).
--
-- Seed inicial (IDs fixos 1-7 pra estabilidade de código)
--   1 → CLIENTE        (migra TGFPAR.CLIENTE='S')
--   2 → FORNECEDOR     (migra TGFPAR.FORNECEDOR='S')
--   3 → USUARIO        (migra TGFPAR.USUARIO='S')
--   4 → MOTORISTA      (migra TGFPAR.MOTORISTA='S')
--   5 → AJUDANTE       (sem flag nativa — único cadastro manual)
--   6 → TRANSPORTADORA (migra TGFPAR.TRANSPORTADORA='S')
--   7 → VENDEDOR       (migra TGFPAR.VENDEDOR='S')
--
--   Sequence começa em 100 pra deixar 1-7 fixos. Novos tipos adicionados
--   pelo operador via UI vão pegar ID a partir de 100.
--
-- ORDEM_EXIBICAO
--   Controla a ordem dos chips/dropdowns na UI sem depender de ID/CODIGO.
--   Default 999 → tipos novos aparecem por último até operador ajustar.
--
-- ATIVO
--   'N' oculta da UI mas preserva vínculos históricos em AD_PARCEIRO_TIPO.
--   Operador pode reativar sem refazer cadastros.
-- =============================================================================

CREATE TABLE SANKHYA.AD_TIPO_PARCEIRO (
    ID             NUMBER          NOT NULL,
    CODIGO         VARCHAR2(20)    NOT NULL,
    DESCRICAO      VARCHAR2(100)   NOT NULL,
    ATIVO          CHAR(1)         DEFAULT 'S' NOT NULL,
    ORDEM_EXIBICAO NUMBER          DEFAULT 999,
    CODUSU         NUMBER,
    NOMEUSU        VARCHAR2(60),
    CRIADO_EM      TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_AD_TIPO_PARCEIRO     PRIMARY KEY (ID),
    CONSTRAINT UK_AD_TIPO_PARCEIRO_COD UNIQUE      (CODIGO),
    CONSTRAINT CK_AD_TIPO_PARC_ATV     CHECK       (ATIVO IN ('S','N'))
);

CREATE SEQUENCE SANKHYA.SEQ_AD_TIPO_PARCEIRO START WITH 100 INCREMENT BY 1 NOCYCLE NOCACHE;

-- Seed (IDs 1-7 fixos pra estabilidade de código)
INSERT INTO SANKHYA.AD_TIPO_PARCEIRO (ID, CODIGO, DESCRICAO, ORDEM_EXIBICAO, NOMEUSU)
VALUES (1, 'CLIENTE',        'Cliente (recebe vendas)',         10, 'SEED_INICIAL');
INSERT INTO SANKHYA.AD_TIPO_PARCEIRO (ID, CODIGO, DESCRICAO, ORDEM_EXIBICAO, NOMEUSU)
VALUES (2, 'FORNECEDOR',     'Fornecedor (entrega mercadoria)', 20, 'SEED_INICIAL');
INSERT INTO SANKHYA.AD_TIPO_PARCEIRO (ID, CODIGO, DESCRICAO, ORDEM_EXIBICAO, NOMEUSU)
VALUES (3, 'USUARIO',        'Usuario do sistema',              30, 'SEED_INICIAL');
INSERT INTO SANKHYA.AD_TIPO_PARCEIRO (ID, CODIGO, DESCRICAO, ORDEM_EXIBICAO, NOMEUSU)
VALUES (4, 'MOTORISTA',      'Motorista de entrega',            40, 'SEED_INICIAL');
INSERT INTO SANKHYA.AD_TIPO_PARCEIRO (ID, CODIGO, DESCRICAO, ORDEM_EXIBICAO, NOMEUSU)
VALUES (5, 'AJUDANTE',       'Ajudante de motorista',           50, 'SEED_INICIAL');
INSERT INTO SANKHYA.AD_TIPO_PARCEIRO (ID, CODIGO, DESCRICAO, ORDEM_EXIBICAO, NOMEUSU)
VALUES (6, 'TRANSPORTADORA', 'Transportadora terceira (PJ)',    60, 'SEED_INICIAL');
INSERT INTO SANKHYA.AD_TIPO_PARCEIRO (ID, CODIGO, DESCRICAO, ORDEM_EXIBICAO, NOMEUSU)
VALUES (7, 'VENDEDOR',       'Vendedor comissionado',           70, 'SEED_INICIAL');
COMMIT;

COMMENT ON TABLE  SANKHYA.AD_TIPO_PARCEIRO                IS 'IAgro - cadastro generico de tipos de parceiro (substitui flags TGFPAR no contexto IAgro). Ver AD_TIPO_PARCEIRO.sql';
COMMENT ON COLUMN SANKHYA.AD_TIPO_PARCEIRO.ID             IS 'PK. IDs 1-7 reservados ao seed inicial; novos tipos comecam em 100 via SEQ_AD_TIPO_PARCEIRO';
COMMENT ON COLUMN SANKHYA.AD_TIPO_PARCEIRO.CODIGO         IS 'Identificador textual estavel usado em codigo (ex.: CLIENTE, MOTORISTA)';
COMMENT ON COLUMN SANKHYA.AD_TIPO_PARCEIRO.DESCRICAO      IS 'Texto humano exibido na UI';
COMMENT ON COLUMN SANKHYA.AD_TIPO_PARCEIRO.ATIVO          IS 'S=visivel na UI; N=oculto mas preserva vinculos historicos';
COMMENT ON COLUMN SANKHYA.AD_TIPO_PARCEIRO.ORDEM_EXIBICAO IS 'Ordem dos chips/dropdowns. Menor aparece primeiro. Default 999';
