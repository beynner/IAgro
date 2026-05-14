-- =====================================================================
-- AD_AUDITORIA_GERAL  -  Audit trail universal do IAgro (Mai/2026)
--
-- Tabela centraliza todas as operacoes de escrita do IAgro.
-- Cada linha = 1 evento auditavel com snapshot antes/depois em JSON.
--
-- POR QUE
--   Hoje a auditoria esta espalhada em 5 tabelas distintas (RastreioAudit
--   SQLite, AD_VINCULO_PEDIDO_NOTA, AD_PEDIDO_EMAIL_RECEBIDO,
--   AD_REQUISICAO_COMBUSTIVEL, AD_*_ALIAS) com schemas incompativeis.
--   Esta tabela permite consulta uniforme:
--     - quem fez X
--     - quando aconteceu
--     - o que mudou (antes vs depois)
--     - em qual modulo / qual registro
--
-- COMO ESCREVER
--   Via helper Python `registrar_auditoria(...)` em oracle_conn.py.
--   Helper roda em conexao propria APOS o commit da operacao principal -
--   se a auditoria falhar, a operacao nao e desfeita (eventos podem ser
--   perdidos raramente, mas dados nunca sao corrompidos). Mesmo padrao do
--   `_registrar_audit_rastreio` que ja existe.
--
-- VOLUME ESTIMADO
--   ~50 ops/dia x 365 x 5 anos = 91k linhas, ~150 MB com snapshots tipicos.
--
-- IDEMPOTENCIA
--   Este script NAO e idempotente. Se a tabela ja existir, ALTER ou
--   recriar manualmente. Indices podem ser dropados antes de re-rodar.
-- =====================================================================

CREATE TABLE SANKHYA.AD_AUDITORIA_GERAL (
    ID                 NUMBER PRIMARY KEY,
    MODULO             VARCHAR2(30) NOT NULL,
    OPERACAO           VARCHAR2(50) NOT NULL,
    TABELA_ALVO        VARCHAR2(50),
    REGISTRO_ID        VARCHAR2(80),
    CODUSU             NUMBER,
    NOMEUSU            VARCHAR2(80),
    DT                 TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    SNAPSHOT_ANTES     CLOB,
    SNAPSHOT_DEPOIS    CLOB,
    OBSERVACAO         VARCHAR2(500),
    CONSTRAINT CK_AD_AUDIT_MODULO CHECK (MODULO IN (
        'venda','combustivel','rastreio','comercial',
        'entrada','classificacao','email'
    ))
);

CREATE SEQUENCE SANKHYA.SEQ_AD_AUDITORIA_GERAL
    START WITH 1
    INCREMENT BY 1
    NOCACHE
    NOCYCLE;

-- Indices para os 4 padroes de busca da tela de auditoria:
--   1. Timeline (mais recente primeiro)
CREATE INDEX SANKHYA.IX_AD_AUDIT_GERAL_DT  ON SANKHYA.AD_AUDITORIA_GERAL(DT DESC);

--   2. Por usuario (o que o operador X fez?)
CREATE INDEX SANKHYA.IX_AD_AUDIT_GERAL_USU ON SANKHYA.AD_AUDITORIA_GERAL(CODUSU);

--   3. Por modulo (filtro lateral)
CREATE INDEX SANKHYA.IX_AD_AUDIT_GERAL_MOD ON SANKHYA.AD_AUDITORIA_GERAL(MODULO);

--   4. Por registro (historia da NUNOTA Y?)
CREATE INDEX SANKHYA.IX_AD_AUDIT_GERAL_REG ON SANKHYA.AD_AUDITORIA_GERAL(TABELA_ALVO, REGISTRO_ID);

COMMENT ON TABLE  SANKHYA.AD_AUDITORIA_GERAL                 IS 'Audit trail universal do IAgro - Mai/2026';
COMMENT ON COLUMN SANKHYA.AD_AUDITORIA_GERAL.MODULO          IS 'venda, combustivel, rastreio, comercial, entrada, classificacao ou email';
COMMENT ON COLUMN SANKHYA.AD_AUDITORIA_GERAL.OPERACAO        IS 'Tipo da operacao (CRIAR_PEDIDO, FATURAR, EXCLUIR_REQUISICAO, etc)';
COMMENT ON COLUMN SANKHYA.AD_AUDITORIA_GERAL.TABELA_ALVO     IS 'Tabela principal afetada (TGFCAB, AD_REQUISICAO_COMBUSTIVEL, etc)';
COMMENT ON COLUMN SANKHYA.AD_AUDITORIA_GERAL.REGISTRO_ID     IS 'NUNOTA, ID ou outro identificador do registro (string p/ suportar PKs compostas)';
COMMENT ON COLUMN SANKHYA.AD_AUDITORIA_GERAL.CODUSU          IS 'CODUSU do operador (request.session)';
COMMENT ON COLUMN SANKHYA.AD_AUDITORIA_GERAL.NOMEUSU         IS 'Nome legivel do operador';
COMMENT ON COLUMN SANKHYA.AD_AUDITORIA_GERAL.DT              IS 'Quando aconteceu (precisao de microssegundo)';
COMMENT ON COLUMN SANKHYA.AD_AUDITORIA_GERAL.SNAPSHOT_ANTES  IS 'JSON com estado antes da operacao (NULL em CRIAR)';
COMMENT ON COLUMN SANKHYA.AD_AUDITORIA_GERAL.SNAPSHOT_DEPOIS IS 'JSON com estado depois da operacao (NULL em EXCLUIR)';
COMMENT ON COLUMN SANKHYA.AD_AUDITORIA_GERAL.OBSERVACAO      IS 'Texto livre opcional (motivo de exclusao, contexto)';
