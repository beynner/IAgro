-- =============================================================================
-- Tabela: SANKHYA.AD_COLETA_CAIXAS
-- Pacote/Módulo: IAgro — Controle de Caixas (Vasilhame Retornável)
--
-- Objetivo
--   Registrar movimentações de RETORNO/PERDA/QUEBRA de caixas plásticas
--   retornáveis em campo (com clientes). Caixas plásticas saem com vendas
--   (TGFITE TOP 35/37 STATUSNOTA='L') e voltam por coleta física manual.
--
--   Saldo do cliente em qualquer momento:
--
--     saldo = Σ caixas_enviadas (vendas L)
--           − Σ caixas_devolvidas (devolução TOP 36 L)
--           − Σ AD_COLETA_CAIXAS (ESTORNADO='N')
--
--   Onde caixas_enviadas/devolvidas considera APENAS produtos cujo
--   CODPROD está mapeado como TIPO_CAIXA='PLASTICA' em AD_PRODUTO_CAIXA
--   (ou que estão sem mapeamento, que cai no default PLASTICA).
--   Produtos com TIPO_CAIXA='PAPELAO' são descartáveis e não contam saldo.
--
-- MOTIVO
--   Discrimina o tipo do evento pra dashboards e decisões de cobrança:
--     - 'COLETA'         → caixa voltou normalmente, motorista trouxe na rota
--     - 'QUEBRA'         → caixa voltou quebrada (visualmente identificado)
--     - 'PERDA'          → caixa não voltou e cliente assumiu (some do estoque)
--     - 'AJUSTE_SALDO'   → correção excepcional do saldo (qtd pode ser negativa)
--       Uso típico: saldo inicial (caixa que já estava em campo antes do
--       controle começar) ou ajuste pontual quando saldo divergir da realidade
--       física. NÃO deve ser usado no dia-a-dia — saldo tem que bater pela
--       operação normal (saídas/devoluções/coletas).
--
-- QTD_CAIXAS
--   - COLETA/QUEBRA/PERDA: sempre > 0 (CHECK)
--   - AJUSTE_SALDO: != 0 (positivo soma ao saldo, negativo desconta)
--
-- ESTORNADO
--   Soft-delete: 'S' não conta no saldo, mas linha continua no histórico
--   pra audit. Operador pode estornar coleta lançada por engano.
--   DELETE físico não é exposto pela UI.
--
-- Por que tabela auxiliar pura (sem mexer em TGFCAB)
--   Caixa não é nota fiscal — não passa pelo Sankhya. Saída automática é
--   derivada (calculada em runtime via CEIL(QTDNEG/PESO) das TGFITE
--   TOP 35/37). Coleta é evento operacional do dia-a-dia que não tem
--   contrapartida no ERP nativo. Tabela isolada, zero impacto em queries
--   existentes.
-- =============================================================================

CREATE TABLE SANKHYA.AD_COLETA_CAIXAS (
    ID            NUMBER          NOT NULL,
    CODPARC       NUMBER          NOT NULL,
    QTD_CAIXAS    NUMBER          NOT NULL,
    DATA_COLETA   DATE            NOT NULL,
    MOTIVO        VARCHAR2(20)    NOT NULL,
    OBSERVACAO    VARCHAR2(500),
    ESTORNADO     CHAR(1)         DEFAULT 'N' NOT NULL,
    ESTORNADO_EM  TIMESTAMP,
    ESTORNADO_POR NUMBER,
    MOTIVO_ESTORNO VARCHAR2(500),
    CODUSU        NUMBER          NOT NULL,
    NOMEUSU       VARCHAR2(80),
    CRIADO_EM     TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_AD_COLETA_CAIXAS PRIMARY KEY (ID),
    CONSTRAINT CK_AD_COLETA_MOTIVO CHECK (MOTIVO IN ('COLETA','QUEBRA','PERDA','AJUSTE_SALDO')),
    CONSTRAINT CK_AD_COLETA_QTD    CHECK (
        (MOTIVO = 'AJUSTE_SALDO' AND QTD_CAIXAS != 0)
        OR (MOTIVO IN ('COLETA','QUEBRA','PERDA') AND QTD_CAIXAS > 0)
    ),
    CONSTRAINT CK_AD_COLETA_EST    CHECK (ESTORNADO IN ('S', 'N'))
);

CREATE SEQUENCE SANKHYA.SEQ_AD_COLETA_CAIXAS START WITH 1 INCREMENT BY 1 NOCYCLE NOCACHE;

-- Índices: queries principais filtram por CODPARC (saldo) e por DATA_COLETA
-- (timeline). ESTORNADO usado em todos os WHERE pra pular linhas estornadas.
CREATE INDEX SANKHYA.IDX_AD_COLETA_CODPARC ON SANKHYA.AD_COLETA_CAIXAS (CODPARC, ESTORNADO);
CREATE INDEX SANKHYA.IDX_AD_COLETA_DATA    ON SANKHYA.AD_COLETA_CAIXAS (DATA_COLETA DESC);

COMMENT ON TABLE  SANKHYA.AD_COLETA_CAIXAS               IS 'IAgro — eventos manuais de retorno/quebra/perda de caixas plásticas retornáveis. Ver AD_COLETA_CAIXAS.sql';
COMMENT ON COLUMN SANKHYA.AD_COLETA_CAIXAS.CODPARC       IS 'TGFPAR.CODPARC do cliente que devolveu/perdeu/quebrou a caixa';
COMMENT ON COLUMN SANKHYA.AD_COLETA_CAIXAS.QTD_CAIXAS    IS 'Quantidade inteira de caixas movimentadas no evento';
COMMENT ON COLUMN SANKHYA.AD_COLETA_CAIXAS.MOTIVO        IS 'COLETA=devolução normal | QUEBRA=voltou quebrada | PERDA=não voltou | AJUSTE_SALDO=correção excepcional (qtd pode ser negativa)';
COMMENT ON COLUMN SANKHYA.AD_COLETA_CAIXAS.ESTORNADO     IS 'S=linha não conta no saldo (audit preserva). N=ativo';
