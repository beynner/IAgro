-- =============================================================================
-- View: SANKHYA.ANDRE_IAGRO_SALDO_LOTE
-- Pacote/Módulo: IAgro — Rastreabilidade (WMS)
--
-- Objetivo
--   Calcular o saldo disponível de estoque por (CODEMP, CODPROD, CODAGREGACAO)
--   sem tocar na TGFEST nativa do Sankhya nem criar triggers customizadas.
--   Toda a leitura é derivada de TGFITE + TGFCAB.
--
-- Pernas (cada lote pode aparecer em mais de uma — pernas A/B/C são exclusivas
-- entre si pelo discriminador "tem TOP 26?"; D e E são informativas paralelas):
--   A) CLASSIFICADO              → fonte TOP 26 (lote tem TOP 26 confirmada)
--   B) NAO_CLASSIFICAVEL         → fonte TOP 13 (lote NÃO tem TOP 26)
--   C) AGUARDANDO_CLASSIFICACAO  → in natura pendente:
--                                  QTDNEG(TOP11) − AD_QTDAVARIA − Σ QTDNEG(TOP26)
--   D) AVARIA_INTERNA            → fonte TOP 30 (informativo, perda no estoque)
--   E) AVARIA_FORNECEDOR         → fonte AD_QTDAVARIA da TOP 11 (informativo,
--                                  descarte da classificação repassado ao fornecedor)
--
-- Baixas e reservas que reduzem QTD_DISPONIVEL nas pernas A e B:
--   QTD_BAIXADA_VENDA  = baixa de venda (ver detalhe abaixo)
--   QTD_BAIXADA_AVARIA = Σ QTDNEG  TOP 30    com STATUSNOTA = 'L'
--   QTD_RESERVADA      = Σ QTDNEG  TOP 34    com STATUSNOTA NOT IN ('L','E')
--
-- QTD_BAIXADA_VENDA (Mai/2026): a vinculação de lote do IAgro vive no pedido
-- (TOP 34), mesmo após faturamento. O Sankhya direto pode também vincular pela
-- nota (TOP 35/37). Para evitar contar duas vezes o mesmo CODAGREGACAO,
-- a baixa é a UNIÃO de:
--   1) TOP 34 STATUSNOTA='L' com CODAGREGACAO (verdade IAgro)
--   2) TOP 35/37 STATUSNOTA='L' com CODAGREGACAO, mas SÓ quando o item
--      origem via TGFVAR NÃO tem CODAGREGACAO no pedido (TOP 34) — evita
--      duplicar quando o operador vinculou pela IAgro (no pedido).
-- Resultado: lote sai do disponível em qualquer um dos cenários, sem dobrar.
--
-- Fórmula final (apenas pernas A e B; C e D retornam 0):
--   QTD_DISPONIVEL = GREATEST( QTD_ENTRADA
--                              − QTD_BAIXADA_VENDA
--                              − QTD_BAIXADA_AVARIA
--                              − QTD_RESERVADA, 0 )
--
-- Convenções de STATUSNOTA neste cálculo:
--   Entradas (TOP 11/13/26): STATUSNOTA <> 'E'  (não excluída)
--   Baixas   (TOP 35/37/30): STATUSNOTA  = 'L'  (liberada/confirmada)
--   Reservas (TOP 34)      : STATUSNOTA NOT IN ('L','E')  (em aberto)
--
-- Como testar:
--   Rode este arquivo UMA VEZ para criar a view (CREATE OR REPLACE).
--   Depois use o arquivo ANDRE_IAGRO_SALDO_LOTE_teste.sql para conferir lotes.
-- =============================================================================
CREATE OR REPLACE VIEW SANKHYA.ANDRE_IAGRO_SALDO_LOTE AS
WITH
  -- -------------------------------------------------------------------------
  -- Origem TOP 11: identifica o produto-pai, GERAPRODUCAO, avaria do fornecedor
  -- e dados de cabeçalho do lote (data e parceiro)
  -- -------------------------------------------------------------------------
  lotes_origem AS (
    SELECT
      i11.CODEMP,
      i11.CODPROD                    AS CODPROD_PAI,
      i11.CODAGREGACAO,
      MAX(i11.GERAPRODUCAO)          AS GERAPRODUCAO,
      SUM(NVL(i11.QTDNEG,        0)) AS QTD_TOP11,
      SUM(NVL(i11.AD_QTDAVARIA,  0)) AS QTD_AVARIA_FORNECEDOR,
      MIN(c11.NUNOTA)                AS NUNOTA_ORIGEM,
      MIN(c11.DTNEG)                 AS DTNEG_ORIGEM,
      MIN(c11.CODPARC)               AS CODPARC_ORIGEM
    FROM TGFITE i11
    JOIN TGFCAB c11 ON c11.NUNOTA = i11.NUNOTA
    WHERE c11.CODTIPOPER     = 11
      AND c11.STATUSNOTA    <> 'E'
      AND i11.CODAGREGACAO IS NOT NULL
    GROUP BY i11.CODEMP, i11.CODPROD, i11.CODAGREGACAO
  ),

  -- Soma da TOP 26 por lote (usada na perna C para calcular pendente)
  top26_por_lote AS (
    SELECT
      i26.CODAGREGACAO,
      SUM(NVL(i26.QTDNEG, 0)) AS QTD_TOP26
    FROM TGFITE i26
    JOIN TGFCAB c26 ON c26.NUNOTA = i26.NUNOTA
    WHERE c26.CODTIPOPER     = 26
      AND c26.STATUSNOTA    <> 'E'
      AND i26.CODAGREGACAO IS NOT NULL
    GROUP BY i26.CODAGREGACAO
  ),

  -- Conjunto dos lotes que JÁ têm TOP 26 (discriminador A vs B)
  lotes_com_top26 AS (
    SELECT DISTINCT CODAGREGACAO FROM top26_por_lote
  ),

  -- -------------------------------------------------------------------------
  -- Baixas e reservas (agregadas por (CODPROD, CODAGREGACAO) GLOBALMENTE,
  -- ignorando CODEMP — pra permitir vincular lote da empresa A em pedido da B
  -- e ainda assim fazer a reserva descontar do saldo.)
  -- -------------------------------------------------------------------------
  baixas_venda AS (
    SELECT CODPROD, CODAGREGACAO, SUM(QTDNEG) AS QTD_BAIXADA_VENDA
    FROM (
      -- (1) Verdade IAgro: TOP 34 já atendido (STATUSNOTA='L') com lote vinculado
      SELECT i.CODPROD, i.CODAGREGACAO, NVL(i.QTDNEG, 0) AS QTDNEG
        FROM TGFITE i
        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
       WHERE c.CODTIPOPER     = 34
         AND c.STATUSNOTA     = 'L'
         AND i.CODAGREGACAO IS NOT NULL
      UNION ALL
      -- (2) Fallback Sankhya nativo: TOP 35/37 vinculado direto na nota,
      -- somente quando o par TGFVAR no pedido NÃO tem lote (sem duplicar)
      SELECT i.CODPROD, i.CODAGREGACAO, NVL(i.QTDNEG, 0) AS QTDNEG
        FROM TGFITE i
        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
       WHERE c.CODTIPOPER IN (35, 37)
         AND c.STATUSNOTA   = 'L'
         AND i.CODAGREGACAO IS NOT NULL
         AND NOT EXISTS (
           SELECT 1
             FROM TGFVAR v
             JOIN TGFITE i34 ON i34.NUNOTA = v.NUNOTAORIG
                            AND i34.SEQUENCIA = v.SEQUENCIAORIG
            WHERE v.NUNOTA = i.NUNOTA
              AND v.SEQUENCIA = i.SEQUENCIA
              AND i34.CODAGREGACAO IS NOT NULL
         )
    )
    GROUP BY CODPROD, CODAGREGACAO
  ),

  baixas_avaria AS (
    SELECT
      i.CODPROD, i.CODAGREGACAO,
      SUM(NVL(i.QTDNEG, 0)) AS QTD_BAIXADA_AVARIA
    FROM TGFITE i
    JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
    WHERE c.CODTIPOPER     = 30
      AND c.STATUSNOTA     = 'L'
      AND i.CODAGREGACAO IS NOT NULL
    GROUP BY i.CODPROD, i.CODAGREGACAO
  ),

  reservas_pedido AS (
    SELECT
      i.CODPROD, i.CODAGREGACAO,
      SUM(NVL(i.QTDNEG, 0)) AS QTD_RESERVADA
    FROM TGFITE i
    JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
    WHERE c.CODTIPOPER         = 34
      AND c.STATUSNOTA NOT IN ('L', 'E')
      AND i.CODAGREGACAO IS NOT NULL
    GROUP BY i.CODPROD, i.CODAGREGACAO
  ),

  -- -------------------------------------------------------------------------
  -- PERNA A — CLASSIFICADO (fonte TOP 26)
  -- -------------------------------------------------------------------------
  perna_a AS (
    SELECT
      i26.CODEMP,
      i26.CODPROD,
      i26.CODAGREGACAO,
      'CLASSIFICADO'              AS STATUS_LINHA,
      SUM(NVL(i26.QTDNEG, 0))     AS QTD_ENTRADA,
      0                           AS QTD_PENDENTE
    FROM TGFITE i26
    JOIN TGFCAB c26 ON c26.NUNOTA = i26.NUNOTA
    WHERE c26.CODTIPOPER     = 26
      AND c26.STATUSNOTA    <> 'E'
      AND i26.CODAGREGACAO IS NOT NULL
    GROUP BY i26.CODEMP, i26.CODPROD, i26.CODAGREGACAO
  ),

  -- -------------------------------------------------------------------------
  -- PERNA B — NAO_CLASSIFICAVEL (fonte TOP 13, somente lotes SEM TOP 26)
  -- -------------------------------------------------------------------------
  perna_b AS (
    SELECT
      i13.CODEMP,
      i13.CODPROD,
      i13.CODAGREGACAO,
      'NAO_CLASSIFICAVEL'         AS STATUS_LINHA,
      SUM(NVL(i13.QTDNEG, 0))     AS QTD_ENTRADA,
      0                           AS QTD_PENDENTE
    FROM TGFITE i13
    JOIN TGFCAB c13 ON c13.NUNOTA = i13.NUNOTA
    WHERE c13.CODTIPOPER     = 13
      AND c13.STATUSNOTA    <> 'E'
      AND i13.CODAGREGACAO IS NOT NULL
      AND i13.CODAGREGACAO NOT IN (SELECT CODAGREGACAO FROM lotes_com_top26)
    GROUP BY i13.CODEMP, i13.CODPROD, i13.CODAGREGACAO
  ),

  -- -------------------------------------------------------------------------
  -- PERNA C — AGUARDANDO_CLASSIFICACAO (in natura ainda não triado)
  -- QTD_PENDENTE = QTD_TOP11 − QTD_AVARIA_FORNECEDOR − QTD_TOP26
  -- (renderizada apenas se > 0)
  -- -------------------------------------------------------------------------
  perna_c AS (
    SELECT
      lo.CODEMP,
      lo.CODPROD_PAI                AS CODPROD,
      lo.CODAGREGACAO,
      'AGUARDANDO_CLASSIFICACAO'    AS STATUS_LINHA,
      0                             AS QTD_ENTRADA,
      lo.QTD_TOP11
        - lo.QTD_AVARIA_FORNECEDOR
        - NVL(t26.QTD_TOP26, 0)     AS QTD_PENDENTE
    FROM lotes_origem lo
    LEFT JOIN top26_por_lote t26 ON t26.CODAGREGACAO = lo.CODAGREGACAO
    WHERE lo.GERAPRODUCAO = 'S'
      AND (lo.QTD_TOP11 - lo.QTD_AVARIA_FORNECEDOR - NVL(t26.QTD_TOP26, 0)) > 0
  ),

  -- -------------------------------------------------------------------------
  -- PERNA D — AVARIA_INTERNA (fonte TOP 30, informativa)
  -- A baixa de fato no QTD_DISPONIVEL acontece via baixas_avaria nas pernas A/B.
  -- Esta linha é mantida na view para uso futuro (Opção B na UI) ou relatórios.
  -- -------------------------------------------------------------------------
  perna_d AS (
    SELECT
      i30.CODEMP,
      i30.CODPROD,
      i30.CODAGREGACAO,
      'AVARIA_INTERNA'              AS STATUS_LINHA,
      SUM(NVL(i30.QTDNEG, 0))       AS QTD_ENTRADA,
      0                             AS QTD_PENDENTE
    FROM TGFITE i30
    JOIN TGFCAB c30 ON c30.NUNOTA = i30.NUNOTA
    WHERE c30.CODTIPOPER     = 30
      AND c30.STATUSNOTA     = 'L'
      AND i30.CODAGREGACAO IS NOT NULL
    GROUP BY i30.CODEMP, i30.CODPROD, i30.CODAGREGACAO
  ),

  -- -------------------------------------------------------------------------
  -- PERNA E — AVARIA_FORNECEDOR (fonte AD_QTDAVARIA da TOP 11, informativa)
  -- Descarte da classificação repassado ao fornecedor.
  -- Renderizada como linha NÃO VENDÁVEL (cinza) no Rastreio para o operador
  -- ver o histórico completo do lote (Extra/Médio/Molho/Descarte/Avaria).
  -- -------------------------------------------------------------------------
  perna_e AS (
    SELECT
      lo.CODEMP,
      lo.CODPROD_PAI                AS CODPROD,
      lo.CODAGREGACAO,
      'AVARIA_FORNECEDOR'           AS STATUS_LINHA,
      lo.QTD_AVARIA_FORNECEDOR      AS QTD_ENTRADA,
      0                             AS QTD_PENDENTE
    FROM lotes_origem lo
    WHERE lo.QTD_AVARIA_FORNECEDOR > 0
  ),

  -- União das 5 pernas
  todas_pernas AS (
    SELECT * FROM perna_a
    UNION ALL
    SELECT * FROM perna_b
    UNION ALL
    SELECT * FROM perna_c
    UNION ALL
    SELECT * FROM perna_d
    UNION ALL
    SELECT * FROM perna_e
  )

-- =============================================================================
-- SELECT FINAL: enriquece com baixas, reservas, descrição do produto e parceiro
-- =============================================================================
SELECT
  tp.CODEMP,
  tp.CODPROD,
  pr.DESCRPROD,
  pr.FABRICANTE,
  pr.SELECIONADO,
  tp.CODAGREGACAO,
  tp.STATUS_LINHA,
  tp.QTD_ENTRADA,
  NVL(bv.QTD_BAIXADA_VENDA,  0) AS QTD_BAIXADA_VENDA,
  NVL(ba.QTD_BAIXADA_AVARIA, 0) AS QTD_BAIXADA_AVARIA,
  NVL(rp.QTD_RESERVADA,      0) AS QTD_RESERVADA,
  CASE
    WHEN tp.STATUS_LINHA IN ('CLASSIFICADO', 'NAO_CLASSIFICAVEL') THEN
      GREATEST(
        tp.QTD_ENTRADA
          - NVL(bv.QTD_BAIXADA_VENDA,  0)
          - NVL(ba.QTD_BAIXADA_AVARIA, 0)
          - NVL(rp.QTD_RESERVADA,      0),
        0
      )
    ELSE 0
  END                              AS QTD_DISPONIVEL,
  tp.QTD_PENDENTE,
  -- Mesma quantidade de QTD_BAIXADA_AVARIA, exposta com nome semântico para o
  -- front renderizar como badge inline ("avaria interna: X kg") nas linhas A/B.
  NVL(ba.QTD_BAIXADA_AVARIA, 0)    AS QTD_AVARIA_INTERNA,
  CASE
    WHEN tp.STATUS_LINHA IN ('CLASSIFICADO', 'NAO_CLASSIFICAVEL') THEN 'S'
    ELSE 'N'
  END                              AS VENDAVEL,
  lo.NUNOTA_ORIGEM,
  lo.DTNEG_ORIGEM,
  lo.CODPARC_ORIGEM,
  par.NOMEPARC                     AS NOMEPARC_ORIGEM
FROM todas_pernas tp
LEFT JOIN baixas_venda     bv ON bv.CODPROD      = tp.CODPROD
                              AND bv.CODAGREGACAO = tp.CODAGREGACAO
LEFT JOIN baixas_avaria    ba ON ba.CODPROD      = tp.CODPROD
                              AND ba.CODAGREGACAO = tp.CODAGREGACAO
LEFT JOIN reservas_pedido  rp ON rp.CODPROD      = tp.CODPROD
                              AND rp.CODAGREGACAO = tp.CODAGREGACAO
LEFT JOIN lotes_origem     lo ON lo.CODEMP = tp.CODEMP
                              AND lo.CODAGREGACAO = tp.CODAGREGACAO
LEFT JOIN TGFPRO           pr ON pr.CODPROD = tp.CODPROD
LEFT JOIN TGFPAR           par ON par.CODPARC = lo.CODPARC_ORIGEM
;


-- =============================================================================
-- MIGRAÇÃO: renomeação de ANDRE_IRIS_SALDO_LOTE → ANDRE_IAGRO_SALDO_LOTE
-- =============================================================================
-- Histórico: a view era chamada ANDRE_IRIS_SALDO_LOTE quando o projeto se
-- chamava "Iris". Em Mai/2026 o projeto foi renomeado para "IAgro" e a view
-- segue o mesmo nome. Se você está atualizando um ambiente que tinha a view
-- antiga, escolha UMA das opções abaixo:
--
--   Opção A — RENAME (mantém os mesmos GRANTS e dependências):
--      RENAME ANDRE_IRIS_SALDO_LOTE TO ANDRE_IAGRO_SALDO_LOTE;
--
--   Opção B — DROP + CREATE (mais limpo, mas exige refazer GRANTS depois):
--      DROP VIEW SANKHYA.ANDRE_IRIS_SALDO_LOTE;
--      -- e em seguida rodar este arquivo para CREATE OR REPLACE.
--
-- Em ambiente novo (sem a view antiga) basta executar o CREATE OR REPLACE
-- acima — não há nada a renomear.
