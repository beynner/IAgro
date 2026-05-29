-- =============================================================================
-- Tabela: SANKHYA.AD_VIAGEM_AJUDANTE
-- Pacote/Módulo: IAgro — Logística (junção N:N viagem × ajudante)
--
-- Objetivo
--   Vincular zero ou mais ajudantes a uma viagem. Ajudante = parceiro com
--   AD_PARCEIRO_TIPO.AD_CODTIPPARC=5 (AJUDANTE — cadastro IAgro pois flag
--   nativa não existe em TGFPAR).
--
-- Modelo
--   PK composta (VIAGEM_ID, CODPARC_AJUDANTE) — impossível duplicar.
--   Sem sequence — PK composto é suficiente como identidade.
--
-- FK ON DELETE CASCADE
--   Ao DELETE em AD_VIAGEM_ENTREGA, ajudantes vinculados saem juntos.
--   Mesmo padrão de AD_VIAGEM_DESTINO.
--
-- Índice reverso IDX_AD_VIAGEM_AJUD_PARC (CODPARC_AJUDANTE)
--   Acelera relatório futuro "quantas viagens o ajudante X participou".
-- =============================================================================

CREATE TABLE SANKHYA.AD_VIAGEM_AJUDANTE (
    VIAGEM_ID         NUMBER         NOT NULL,
    CODPARC_AJUDANTE  NUMBER         NOT NULL,
    CRIADO_EM         TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_AD_VIAGEM_AJUDANTE PRIMARY KEY (VIAGEM_ID, CODPARC_AJUDANTE),
    CONSTRAINT FK_AD_VIAGEM_AJUD_VIAG FOREIGN KEY (VIAGEM_ID)
        REFERENCES SANKHYA.AD_VIAGEM_ENTREGA (ID) ON DELETE CASCADE
);

CREATE INDEX SANKHYA.IDX_AD_VIAGEM_AJUD_PARC ON SANKHYA.AD_VIAGEM_AJUDANTE (CODPARC_AJUDANTE);

COMMENT ON TABLE  SANKHYA.AD_VIAGEM_AJUDANTE                 IS 'IAgro Logistica - juncao N:N viagem x ajudante. FK CASCADE com AD_VIAGEM_ENTREGA. Ver AD_VIAGEM_AJUDANTE.sql';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_AJUDANTE.VIAGEM_ID        IS 'FK para AD_VIAGEM_ENTREGA.ID (ON DELETE CASCADE)';
COMMENT ON COLUMN SANKHYA.AD_VIAGEM_AJUDANTE.CODPARC_AJUDANTE IS 'FK logica para TGFPAR.CODPARC (parceiro com AD_PARCEIRO_TIPO.AD_CODTIPPARC=5)';
