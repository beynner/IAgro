-- =============================================================================
-- Tabelas: SANKHYA.AD_PEDIDO_EMAIL_RECEBIDO + SANKHYA.AD_PEDIDO_EMAIL_ITEM
-- Pacote/Módulo: IAgro — Importação de pedidos por e-mail (com PDF + LLM local)
--
-- Objetivo
--   Persistir pré-pedidos extraídos automaticamente de e-mails com PDF anexo,
--   antes da promoção para TGFCAB (TOP 34). Mantém o ERP Sankhya limpo: rascunhos
--   de parser não vazam para painéis/cubos do Sankhya até confirmação humana.
--
--   Apenas após o operador clicar "Confirmar" na tela /sankhya/venda/email-importar/
--   o sistema reusa as APIs já testadas da Venda (api_criar_cabecalho_venda +
--   api_salvar_item_venda) para gravar em TGFCAB/TGFITE com TOP 34. O NUNOTA
--   gerado retorna para AD_PEDIDO_EMAIL_RECEBIDO.NUNOTA_GERADO como link reverso.
--
-- Convenção
--   Tabelas em prefixo AD_ (auxiliares de cliente, padrão Sankhya). Ficam no
--   mesmo schema/owner das demais (SANKHYA). Não interferem em queries existentes.
--
-- Status do registro (coluna STATUS de AD_PEDIDO_EMAIL_RECEBIDO)
--   AGUARDANDO_PARSER  → e-mail recebido, PDF salvo, ainda não passou pelo LLM
--   PENDENTE_REVISAO   → parser concluído com sucesso; aguarda operador
--   CONFIRMADO         → operador confirmou; NUNOTA_GERADO populado com TGFCAB.NUNOTA
--   DESCARTADO         → operador rejeitou (motivo em MOTIVO_DESCARTE)
--   ERRO_PARSER        → LLM falhou (timeout, JSON inválido, etc.) — passível de reparser
--   ERRO_PDF           → PDF não pôde ser lido (corrompido, sem texto, escaneado sem OCR)
--
-- Storage do PDF original
--   PDF_PATH guarda caminho ABSOLUTO no servidor (ex: z:\TI\NexusGTi\IAgro\IAgro\
--   media\pedidos_email\2026\05\<MSGID>.pdf). Não usa BLOB para manter a tabela
--   leve e permitir servir o arquivo via HTTP autenticado.
--
-- Anti-duplicação
--   Constraint UNIQUE em (MESSAGE_ID, SUB_ID). Se o worker for reiniciado e tentar
--   reprocessar o mesmo e-mail, o INSERT falha — worker captura essa condição e ignora.
--
-- Multi-pedido por PDF
--   Um e-mail pode trazer N pedidos no mesmo PDF (ex: redes de supermercado enviam
--   1 PDF com várias páginas, 1 loja por página). Cada pedido vira UMA linha em
--   AD_PEDIDO_EMAIL_RECEBIDO com mesmo MESSAGE_ID e SUB_ID sequencial (1, 2, 3, ...).
--   Operador revisa e confirma cada um independente; status, NUNOTA_GERADO,
--   CONFIRMADO_POR/EM são por linha. PDF_PATH e PDF_TEXTO são replicados (mesmo
--   PDF, mesmo texto bruto) — a especialização vem por SUB_ID.
--
-- Telemetria de LLM
--   LLM_TOKENS_IN / LLM_TOKENS_OUT / LLM_MODELO permitem auditar custo (mesmo que
--   o LLM seja local, é útil acompanhar carga de processamento).
--
-- Atribuição (CODUSU)
--   CONFIRMADO_POR é o CODUSU do operador que clicou "Confirmar" — mesmo CODUSU
--   que vai para TGFCAB.CODUSU via api_criar_cabecalho_venda. Garante auditoria.
--
-- =============================================================================

-- -----------------------------------------------------------------------------
-- TABELA PRINCIPAL: um registro por e-mail processado
-- -----------------------------------------------------------------------------
CREATE TABLE AD_PEDIDO_EMAIL_RECEBIDO (
    ID                    NUMBER         NOT NULL,
    MESSAGE_ID            VARCHAR2(255)  NOT NULL,
    SUB_ID                NUMBER         DEFAULT 1 NOT NULL,
    REMETENTE             VARCHAR2(120),
    ASSUNTO               VARCHAR2(255),
    RECEBIDO_EM           TIMESTAMP,
    PROCESSADO_EM         TIMESTAMP,
    PDF_PATH              VARCHAR2(500),
    PDF_TEXTO             CLOB,
    LLM_RESPOSTA          CLOB,
    LLM_MODELO            VARCHAR2(50),
    LLM_TOKENS_IN         NUMBER,
    LLM_TOKENS_OUT        NUMBER,
    LLM_CONFIANCA_GERAL   NUMBER(3,2),
    CODPARC_SUGERIDO      NUMBER,
    CODEMP_SUGERIDO       NUMBER,
    DTNEG_SUGERIDA        DATE,
    CODTIPVENDA_SUGERIDO  NUMBER,
    OBSERVACAO_EXTRAIDA   VARCHAR2(2000),
    STATUS                VARCHAR2(30)   NOT NULL,
    MOTIVO_DESCARTE       VARCHAR2(500),
    NUNOTA_GERADO         NUMBER,
    CONFIRMADO_POR        NUMBER,
    CONFIRMADO_EM         TIMESTAMP,
    ORIGEM                VARCHAR2(20)   DEFAULT 'IMAP' NOT NULL,
    CRIADO_EM             TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_AD_PEDIDO_EMAIL_RECEBIDO PRIMARY KEY (ID),
    CONSTRAINT UK_AD_PEDIDO_EMAIL_MSGID    UNIQUE (MESSAGE_ID, SUB_ID),
    CONSTRAINT CK_AD_PEDIDO_EMAIL_STATUS CHECK (STATUS IN (
        'AGUARDANDO_PARSER',
        'PENDENTE_REVISAO',
        'CONFIRMADO',
        'DESCARTADO',
        'ERRO_PARSER',
        'ERRO_PDF'
    ))
);

CREATE SEQUENCE SEQ_AD_PEDIDO_EMAIL_RECEBIDO
    START WITH 1
    INCREMENT BY 1
    NOCACHE
    NOCYCLE;

-- Índice para a fila da tela de revisão (filtra por STATUS, ordena por data)
CREATE INDEX IX_AD_EMAIL_STATUS_DATA
    ON AD_PEDIDO_EMAIL_RECEBIDO (STATUS, RECEBIDO_EM);

-- Índice para o link reverso a partir de TGFCAB (auditoria: "esse pedido veio de e-mail?")
CREATE INDEX IX_AD_EMAIL_NUNOTA
    ON AD_PEDIDO_EMAIL_RECEBIDO (NUNOTA_GERADO);


-- -----------------------------------------------------------------------------
-- TABELA DE ITENS: um registro por linha extraída do PDF
-- Operador pode editar/remover/adicionar antes de confirmar.
-- -----------------------------------------------------------------------------
CREATE TABLE AD_PEDIDO_EMAIL_ITEM (
    ID                  NUMBER         NOT NULL,
    RECEBIDO_ID         NUMBER         NOT NULL,
    SEQUENCIA           NUMBER         NOT NULL,
    DESCRICAO_PDF       VARCHAR2(500),
    CODPROD_SUGERIDO    NUMBER,
    CODPROD_CONFIANCA   NUMBER(3,2),
    CODPROD_FINAL       NUMBER,
    QTD                 NUMBER(15,3),
    CODVOL              VARCHAR2(10),
    PRECO_UNIT          NUMBER(15,4),
    OBSERVACAO          VARCHAR2(500),
    CRIADO_EM           TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_AD_PEDIDO_EMAIL_ITEM PRIMARY KEY (ID),
    CONSTRAINT FK_AD_EMAIL_ITEM_RECEBIDO FOREIGN KEY (RECEBIDO_ID)
        REFERENCES AD_PEDIDO_EMAIL_RECEBIDO (ID) ON DELETE CASCADE
);

CREATE SEQUENCE SEQ_AD_PEDIDO_EMAIL_ITEM
    START WITH 1
    INCREMENT BY 1
    NOCACHE
    NOCYCLE;

-- Índice composto para listar itens em ordem de um recebido
CREATE INDEX IX_AD_EMAIL_ITEM_RECEBIDO
    ON AD_PEDIDO_EMAIL_ITEM (RECEBIDO_ID, SEQUENCIA);


-- -----------------------------------------------------------------------------
-- COMENTÁRIOS DE DOCUMENTAÇÃO (úteis em ferramentas BI / SQL Developer)
-- -----------------------------------------------------------------------------
COMMENT ON TABLE  AD_PEDIDO_EMAIL_RECEBIDO IS 'IAgro: pedidos extraídos de e-mail com PDF, antes da promoção para TGFCAB';
COMMENT ON COLUMN AD_PEDIDO_EMAIL_RECEBIDO.MESSAGE_ID IS 'Header Message-ID do e-mail (anti-duplicação combinado com SUB_ID)';
COMMENT ON COLUMN AD_PEDIDO_EMAIL_RECEBIDO.SUB_ID IS 'Sequencial (1,2,3,...) quando 1 PDF traz N pedidos. PDF de 1 pedido = SUB_ID=1';
COMMENT ON COLUMN AD_PEDIDO_EMAIL_RECEBIDO.PDF_PATH IS 'Caminho absoluto do PDF original no disco';
COMMENT ON COLUMN AD_PEDIDO_EMAIL_RECEBIDO.LLM_RESPOSTA IS 'JSON cru retornado pelo LLM (auditoria/debug)';
COMMENT ON COLUMN AD_PEDIDO_EMAIL_RECEBIDO.STATUS IS 'AGUARDANDO_PARSER, PENDENTE_REVISAO, CONFIRMADO, DESCARTADO, ERRO_PARSER, ERRO_PDF';
COMMENT ON COLUMN AD_PEDIDO_EMAIL_RECEBIDO.NUNOTA_GERADO IS 'TGFCAB.NUNOTA gerado quando STATUS=CONFIRMADO';
COMMENT ON COLUMN AD_PEDIDO_EMAIL_RECEBIDO.CONFIRMADO_POR IS 'CODUSU do operador que clicou Confirmar';

COMMENT ON TABLE  AD_PEDIDO_EMAIL_ITEM IS 'IAgro: itens extraídos do PDF de pedido por e-mail';
COMMENT ON COLUMN AD_PEDIDO_EMAIL_ITEM.DESCRICAO_PDF IS 'Texto original do produto como extraído do PDF';
COMMENT ON COLUMN AD_PEDIDO_EMAIL_ITEM.CODPROD_SUGERIDO IS 'CODPROD inferido pelo LLM (pode ser NULL)';
COMMENT ON COLUMN AD_PEDIDO_EMAIL_ITEM.CODPROD_FINAL IS 'CODPROD escolhido pelo operador na revisão';


-- -----------------------------------------------------------------------------
-- GRANTS (executar conforme necessidade do ambiente — não obrigatório aqui)
-- -----------------------------------------------------------------------------
-- Caso o usuário Oracle do IAgro seja diferente do owner da tabela:
--   GRANT SELECT, INSERT, UPDATE, DELETE ON SANKHYA.AD_PEDIDO_EMAIL_RECEBIDO TO <usuario_iagro>;
--   GRANT SELECT, INSERT, UPDATE, DELETE ON SANKHYA.AD_PEDIDO_EMAIL_ITEM     TO <usuario_iagro>;
--   GRANT SELECT ON SANKHYA.SEQ_AD_PEDIDO_EMAIL_RECEBIDO TO <usuario_iagro>;
--   GRANT SELECT ON SANKHYA.SEQ_AD_PEDIDO_EMAIL_ITEM     TO <usuario_iagro>;


-- -----------------------------------------------------------------------------
-- ROLLBACK (se precisar desfazer tudo — manual, não automatizado)
-- -----------------------------------------------------------------------------
-- DROP TABLE    SANKHYA.AD_PEDIDO_EMAIL_ITEM      CASCADE CONSTRAINTS;
-- DROP TABLE    SANKHYA.AD_PEDIDO_EMAIL_RECEBIDO  CASCADE CONSTRAINTS;
-- DROP SEQUENCE SANKHYA.SEQ_AD_PEDIDO_EMAIL_ITEM;
-- DROP SEQUENCE SANKHYA.SEQ_AD_PEDIDO_EMAIL_RECEBIDO;
