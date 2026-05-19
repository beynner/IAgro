-- =============================================================================
-- Tabela: SANKHYA.AD_SALDO_LOTE_CACHE
-- Pacote/Módulo: IAgro — Rastreio / WMS (cache de saldo)
--
-- Objetivo
--   Espelho materializado do retorno da view ANDRE_IAGRO_SALDO_LOTE. A view
--   é pesada (5 CTEs com agregações em TGFITE/TGFCAB/TGFVAR — centenas de
--   milhares de linhas em produção) e leva 10-22s por hit. O módulo Rastreio
--   abre essa view 2× por carga (lotes + pedidos), travando o operador.
--
--   Esta tabela é atualizada periodicamente (Windows Task Scheduler a cada
--   5 min) via comando Django:
--
--       python manage.py refresh_saldo_lote
--
--   que chama `refresh_saldo_lote_cache()` em oracle_conn.py. A função faz
--   TRUNCATE + INSERT-SELECT da view, executando em ~12s em background — o
--   operador NUNCA espera essa janela.
--
--   `consultar_saldo_lote_disponivel` consome desta tabela em vez da view,
--   reduzindo o tempo de hit para ~200-500ms (queries indexadas direto na
--   tabela física). Combinado com o cache Django (60s) em cima, a tela de
--   Rastreio responde virtualmente instantânea no uso típico.
--
-- Coerência
--   Latência máxima de até 5 min entre uma escrita (atribuir/desvincular
--   lote, criar TOP 26 confirmada, devolução, avaria) e o reflexo no saldo
--   exibido. O lock pessimista nas escritas (`atribuir_lote_item_pedido`)
--   continua validando saldo na **view real** (não no cache), garantindo
--   integridade transacional — o cache só governa a leitura para listagem.
--
-- Por que tabela auxiliar (AD_*) e não materialized view nativa Oracle
--   Materialized view com REFRESH FAST ON COMMIT exigiria criar materialized
--   view logs em TGFITE e TGFCAB — escritas em tabelas nativas Sankhya,
--   risco alto. Tabela AD_* segue o padrão do projeto (prefixo do espaço
--   reservado pro IAgro) e isola completamente do schema do ERP.
--
-- Estrutura
--   Mesmas colunas do retorno da view ANDRE_IAGRO_SALDO_LOTE + ATUALIZADO_EM
--   (timestamp do último refresh — útil pra alerta visual se Task Scheduler
--   parar e o cache congelar).
-- =============================================================================

CREATE TABLE SANKHYA.AD_SALDO_LOTE_CACHE (
    CODEMP              NUMBER          NOT NULL,
    CODPROD             NUMBER          NOT NULL,
    DESCRPROD           VARCHAR2(200),
    FABRICANTE          VARCHAR2(200),
    SELECIONADO         VARCHAR2(1),
    CODAGREGACAO        VARCHAR2(50)    NOT NULL,
    STATUS_LINHA        VARCHAR2(40)    NOT NULL,
    QTD_ENTRADA         NUMBER(15,3)    DEFAULT 0,
    QTD_BAIXADA_VENDA   NUMBER(15,3)    DEFAULT 0,
    QTD_BAIXADA_AVARIA  NUMBER(15,3)    DEFAULT 0,
    QTD_RESERVADA       NUMBER(15,3)    DEFAULT 0,
    QTD_DEVOLVIDA       NUMBER(15,3)    DEFAULT 0,
    QTD_DISPONIVEL      NUMBER(15,3)    DEFAULT 0,
    QTD_PENDENTE        NUMBER(15,3)    DEFAULT 0,
    QTD_AVARIA_INTERNA  NUMBER(15,3)    DEFAULT 0,
    VENDAVEL            VARCHAR2(1)     DEFAULT 'N',
    NUNOTA_ORIGEM       NUMBER,
    DTNEG_ORIGEM        DATE,
    CODPARC_ORIGEM      NUMBER,
    NOMEPARC_ORIGEM     VARCHAR2(120),
    ATUALIZADO_EM       TIMESTAMP       DEFAULT SYSTIMESTAMP,
    CONSTRAINT PK_AD_SALDO_LOTE_CACHE PRIMARY KEY (CODEMP, CODPROD, CODAGREGACAO, STATUS_LINHA)
);

COMMENT ON TABLE  SANKHYA.AD_SALDO_LOTE_CACHE                IS 'IAgro — espelho materializado de ANDRE_IAGRO_SALDO_LOTE. Refresh por Windows Task Scheduler 5min.';
COMMENT ON COLUMN SANKHYA.AD_SALDO_LOTE_CACHE.ATUALIZADO_EM  IS 'Timestamp do último TRUNCATE+INSERT. Frontend pode comparar com SYSTIMESTAMP pra detectar cache parada.';
COMMENT ON COLUMN SANKHYA.AD_SALDO_LOTE_CACHE.STATUS_LINHA   IS 'CLASSIFICADO | NAO_CLASSIFICAVEL | AGUARDANDO_CLASSIFICACAO | AVARIA_INTERNA | AVARIA_FORNECEDOR | DEVOLVIDO';
COMMENT ON COLUMN SANKHYA.AD_SALDO_LOTE_CACHE.VENDAVEL       IS 'S = vendável (perna A/B). N = informativa (C/D/E/F).';

-- Índices nas colunas mais filtradas pelo frontend (Rastreio)
-- ---------------------------------------------------------------------------
-- Listagem padrão: WHERE QTD_DISPONIVEL > 0 ORDER BY DTNEG_ORIGEM DESC, DESCRPROD
CREATE INDEX IDX_AD_SALDO_LOTE_DISP    ON SANKHYA.AD_SALDO_LOTE_CACHE (QTD_DISPONIVEL);
CREATE INDEX IDX_AD_SALDO_LOTE_DTNEG   ON SANKHYA.AD_SALDO_LOTE_CACHE (DTNEG_ORIGEM DESC);
CREATE INDEX IDX_AD_SALDO_LOTE_PROD    ON SANKHYA.AD_SALDO_LOTE_CACHE (CODPROD);
CREATE INDEX IDX_AD_SALDO_LOTE_VEND    ON SANKHYA.AD_SALDO_LOTE_CACHE (VENDAVEL);

COMMIT;

-- =============================================================================
-- SMOKE / VERIFICAÇÃO
-- =============================================================================
-- SELECT COUNT(*) FROM SANKHYA.AD_SALDO_LOTE_CACHE;
-- SELECT MAX(ATUALIZADO_EM) FROM SANKHYA.AD_SALDO_LOTE_CACHE;
-- SELECT * FROM SANKHYA.AD_SALDO_LOTE_CACHE WHERE QTD_DISPONIVEL > 0 AND ROWNUM <= 5;
