-- =============================================================================
-- Tabela: SANKHYA.AD_VIAGEM_ENTREGA
-- Pacote/Módulo: IAgro — Logística (cabeçalho de viagem de entrega)
--
-- Objetivo
--   Cabeçalho de cada viagem planejada de entrega: caminhão + motorista +
--   data + hora de saída + observação livre do gestor. Destinos vinculados
--   em AD_VIAGEM_DESTINO; ajudantes em AD_VIAGEM_AJUDANTE.
--
-- Numeração visível ao operador
--   ID            = PK interna (sequence, estável pro código)
--   NUM_VIAGEM    = número sequencial visível na UI ("Nº 1", "Nº 2"...).
--                   Único pela constraint UK_AD_VIAGEM_NUM. Gerado por
--                   MAX(NUM_VIAGEM)+1 (sem sequence dedicada — operador
--                   espera continuidade visual após cada exclusão).
--
-- Sem coluna STATUS
--   Exclusão de viagem é DELETE físico — destinos e ajudantes saem em
--   cascata via FK ON DELETE CASCADE (DDLs AD_VIAGEM_DESTINO,
--   AD_VIAGEM_AJUDANTE). Histórico fica preservado em AD_AUDITORIA_GERAL
--   (snapshot ANTES do DELETE).
--
-- CHECK regex HORA_SAIDA
--   Formato 'HH:MM' validado no backend mesmo já validado no frontend
--   (defesa em profundidade). REGEXP_LIKE permite 00:00..29:59 (Oracle
--   regex não suporta intervalo numérico granular) — bug aceitável dado
--   que valor vem do <input type="time"> do navegador.
--
-- Sem FK física pra TGFVEI/TGFPAR
--   Padrão dos AD_* do projeto. Validação em código (`oracle_conn.py`).
--   Razão: spin-off futuro pode replicar TGFVEI/TGFPAR em schema próprio;
--   FK física dificultaria a migração suave.
--
-- Índices
--   IDX_AD_VIAGEM_DATA       - filtros de período (default da UI)
--   IDX_AD_VIAGEM_MOTORISTA  - filtro "viagens do João"
--   IDX_AD_VIAGEM_VEICULO    - filtro "viagens do JFO-5H79"
-- =============================================================================

CREATE TABLE SANKHYA.AD_VIAGEM_ENTREGA (
    ID                NUMBER          NOT NULL,
    NUM_VIAGEM        NUMBER          NOT NULL,
    DATA_VIAGEM       DATE            NOT NULL,
    HORA_SAIDA        VARCHAR2(5)     NOT NULL,
    CODVEICULO        NUMBER          NOT NULL,
    CODPARC_MOTORISTA NUMBER          NOT NULL,
    OBSERVACAO        VARCHAR2(1000),
    CODUSU            NUMBER,
    NOMEUSU           VARCHAR2(60),
    CRIADO_EM         TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    ATUALIZADO_EM     TIMESTAMP,
    ATUALIZADO_POR    NUMBER,
    CONSTRAINT PK_AD_VIAGEM_ENTREGA PRIMARY KEY (ID),
    CONSTRAINT UK_AD_VIAGEM_NUM     UNIQUE      (NUM_VIAGEM),
    CONSTRAINT CK_AD_VIAGEM_HORA    CHECK       (REGEXP_LIKE(HORA_SAIDA, '^[0-2][0-9]:[0-5][0-9]$'))
);

CREATE SEQUENCE SANKHYA.SEQ_AD_VIAGEM_ENTREGA START WITH 1 INCREMENT BY 1 NOCYCLE NOCACHE;

CREATE INDEX SANKHYA.IDX_AD_VIAGEM_DATA      ON SANKHYA.AD_VIAGEM_ENTREGA (DATA_VIAGEM);
CREATE INDEX SANKHYA.IDX_AD_VIAGEM_MOTORISTA ON SANKHYA.AD_VIAGEM_ENTREGA (CODPARC_MOTORISTA);
CREATE INDEX SANKHYA.IDX_AD_VIAGEM_VEICULO   ON SANKHYA.AD_VIAGEM_ENTREGA (CODVEICULO);

COMMENT ON TABLE  SANKHYA.AD_VIAGEM_ENTREGA                   IS 'IAgro Logistica - cabecalho de viagem de entrega (caminhao+motorista+data+hora). Destinos em AD_VIAGEM_DESTINO; ajudantes em AD_VIAGEM_AJUDANTE. Ver AD_VIAGEM_ENTREGA.sql';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_ENTREGA.ID                IS 'PK interna (via SEQ_AD_VIAGEM_ENTREGA)';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_ENTREGA.NUM_VIAGEM        IS 'Numero sequencial visivel ao operador (Nº 1, Nº 2...). Unico. Gerado por MAX+1';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_ENTREGA.HORA_SAIDA        IS 'Hora planejada de saida no formato HH:MM (regex valida)';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_ENTREGA.CODVEICULO        IS 'FK logica para TGFVEI.CODVEICULO';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_ENTREGA.CODPARC_MOTORISTA IS 'FK logica para TGFPAR.CODPARC (parceiro com AD_PARCEIRO_TIPO.AD_CODTIPPARC=4)';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_ENTREGA.OBSERVACAO        IS 'Texto livre do gestor pra rota toda (max 1000 chars)';
