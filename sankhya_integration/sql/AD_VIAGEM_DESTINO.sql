-- =============================================================================
-- Tabela: SANKHYA.AD_VIAGEM_DESTINO
-- Pacote/Módulo: IAgro — Logística (destinos/paradas de uma viagem)
--
-- Objetivo
--   Cada linha representa 1 parada da viagem: cliente destino + qtd de
--   caixas + observação opcional. Ordem das paradas controlada pela coluna
--   ORDEM (renderização determinística na ficha do motorista).
--
-- FK ON DELETE CASCADE
--   Ao DELETE em AD_VIAGEM_ENTREGA, todos os destinos vinculados são
--   removidos atomicamente. Garantia de integridade sem código auxiliar.
--
-- UK (VIAGEM_ID, ORDEM)
--   Impede 2 destinos com mesma posição na mesma viagem (necessário pra
--   ficha numerada "1ª parada, 2ª parada..."). UI permite reordenar
--   excluindo + readicionando, ou via UPDATE em massa de ORDEM.
--
-- CK QTD_CAIXAS > 0
--   Parada com 0 caixas não existe — operador remove a linha em vez.
--
-- Sem FK física pra TGFPAR (CODPARC_DESTINO)
--   Padrão dos AD_* do projeto. Validação em código.
--
-- Índices
--   IDX_AD_VIAGEM_DEST_VIAGEM (VIAGEM_ID, ORDEM)
--     Cobre a query típica "SELECT * FROM destinos WHERE viagem_id=X
--     ORDER BY ordem" como index-only scan.
--   IDX_AD_VIAGEM_DEST_PARC (CODPARC_DESTINO)
--     Filtro "quais viagens passam na loja X" (relatório futuro).
-- =============================================================================

CREATE TABLE SANKHYA.AD_VIAGEM_DESTINO (
    ID                NUMBER         NOT NULL,
    VIAGEM_ID         NUMBER         NOT NULL,
    ORDEM             NUMBER         NOT NULL,
    CODPARC_DESTINO   NUMBER         NOT NULL,
    QTD_CAIXAS        NUMBER         NOT NULL,
    OBSERVACAO        VARCHAR2(500),
    CRIADO_EM         TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_AD_VIAGEM_DESTINO PRIMARY KEY (ID),
    CONSTRAINT FK_AD_VIAGEM_DEST_VIAG FOREIGN KEY (VIAGEM_ID)
        REFERENCES SANKHYA.AD_VIAGEM_ENTREGA (ID) ON DELETE CASCADE,
    CONSTRAINT UK_AD_VIAGEM_DEST_ORDEM UNIQUE (VIAGEM_ID, ORDEM),
    CONSTRAINT CK_AD_VIAGEM_DEST_QTD CHECK (QTD_CAIXAS > 0)
);

CREATE SEQUENCE SANKHYA.SEQ_AD_VIAGEM_DESTINO START WITH 1 INCREMENT BY 1 NOCYCLE NOCACHE;

-- Indice principal: cobre "SELECT * WHERE viagem_id=X ORDER BY ordem" (PK FK
-- redundante mas o composto fica mais rapido sem hash join). Embora exista
-- a UK (VIAGEM_ID, ORDEM) que cobre o mesmo prefixo, mantemos o nome
-- explicito por legibilidade e poupa o caso futuro de drop da UK.
CREATE INDEX SANKHYA.IDX_AD_VIAGEM_DEST_PARC ON SANKHYA.AD_VIAGEM_DESTINO (CODPARC_DESTINO);

COMMENT ON TABLE  SANKHYA.AD_VIAGEM_DESTINO                 IS 'IAgro Logistica - destinos (paradas) de uma viagem. FK CASCADE com AD_VIAGEM_ENTREGA. Ver AD_VIAGEM_DESTINO.sql';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_DESTINO.ID              IS 'PK interna (via SEQ_AD_VIAGEM_DESTINO)';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_DESTINO.VIAGEM_ID       IS 'FK para AD_VIAGEM_ENTREGA.ID (ON DELETE CASCADE)';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_DESTINO.ORDEM           IS 'Posicao da parada na viagem (1, 2, 3...). Unico por viagem';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_DESTINO.CODPARC_DESTINO IS 'FK logica para TGFPAR.CODPARC (parceiro com AD_PARCEIRO_TIPO.AD_CODTIPPARC=1 cliente)';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_DESTINO.QTD_CAIXAS      IS 'Qtd de caixas a entregar nesta parada (> 0)';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_DESTINO.OBSERVACAO      IS 'Texto livre da parada (ex: entregar antes 9h). Max 500';
