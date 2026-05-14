-- =============================================================================
-- View: SANKHYA.ANDRE_IAGRO_SALDO_COMBUSTIVEL
-- Pacote/Modulo: IAgro - Controle de Combustivel
--
-- Objetivo
--   Calcular o saldo disponivel de combustivel por CODPROD a partir de TOP 10
--   (entrada) menos TOP 26 (requisicao via IAgro). Toda a leitura e derivada
--   de TGFITE + TGFCAB filtrando pelo grupo de produto COMBUSTIVEIS
--   (TGFGRU.CODGRUPOPROD = 200400).
--
-- Decisao Mai/2026 (2026-05-12): saldo de combustivel e UNICO, independe de
-- CODEMP. Combustivel e despesa operacional compartilhada entre empresas do
-- grupo (Agromil/Semear/etc) - nao faz sentido segregar estoque por CODEMP.
-- Comparavel ao WMS Rastreio que tambem agrega lotes sem filtrar CODEMP.
--
-- Hierarquia do grupo (validada em produccao Mai/2026):
--   200000 (MEF) -> 200400 (COMBUSTIVEIS) [analitico, ativo]
--   Produtos atuais: Diesel S10 (392), Diesel S500 (1373), Gasolina (391),
--   Oleo de Motor (550). CODVOL='LT' (litros).
--
-- Importante: NAO confundir com TSIGRU.CODGRUPO=11 (PACKING_FROTA), que e o
-- grupo de USUARIO usado pelo decorator @exige_grupo('combustivel').
--
-- Segregacao versus modulo Classificacao (Mai/2026)
--   - Classificacao usa TOP 26 com CODAGREGACAO IS NOT NULL e produtos do
--     grupo hortifruti (CODGRUPOPROD diferente).
--   - Combustivel usa TOP 26 com CODAGREGACAO = NULL e produtos do grupo
--     COMBUSTIVEIS (CODGRUPOPROD = 200400).
--   - O filtro pr.CODGRUPOPROD = 200400 garante segregacao total entre os
--     dois fluxos sem precisar consultar AD_REQUISICAO_COMBUSTIVEL aqui.
--
-- TOP 53 (Mai/2026 - 2026-05-13)
--   - Requisicoes internas (saida de estoque) usam TOP 53 - REQUISICAO INTERNA
--     (TIPMOV='Q'). Antes era TOP 26, mas essa TOP eh do modulo de
--     Classificacao de mercadoria (hortifruti) - nao deve ser misturada.
--
-- Abastecimento externo (Mai/2026 - 2026-05-13)
--   - Linhas com TIPO='EXTERNA_POSTO' em AD_REQUISICAO_COMBUSTIVEL representam
--     abastecimentos feitos em postos externos (Allianz/Semear/Agromil). Esses
--     lancamentos tambem geram TGFCAB TOP 53 + TGFFIN, mas NAO descontam dos
--     tanques internos. O NOT EXISTS na perna `saidas` exclui essas notas do
--     saldo.
--
-- STATUSNOTA convencao
--   Entradas (TOP 10): STATUSNOTA <> 'E'  (nao excluida; conta como estoque)
--   Saidas   (TOP 53): STATUSNOTA <> 'E'  (em aberto ja desconta - evita
--                                          estouro de saldo entre criacao da
--                                          requisicao IAgro e confirmacao
--                                          no Sankhya)
--
-- Como testar
--   Rode este arquivo UMA VEZ para criar a view (CREATE OR REPLACE).
--   Depois consulte:
--     SELECT * FROM SANKHYA.ANDRE_IAGRO_SALDO_COMBUSTIVEL
--     ORDER BY DESCRPROD;
--
-- Pre-requisitos no Sankhya
--   1. Grupo de produto TGFGRU.CODGRUPOPROD = 200400 (COMBUSTIVEIS) ja existe
--   2. Produtos de combustivel cadastrados em TGFPRO com CODGRUPOPROD = 200400
--      (Diesel S10 392, Diesel S500 1373, Gasolina 391, Oleo de Motor 550)
--   3. Notas TOP 10 lancadas com itens desses produtos
-- =============================================================================
CREATE OR REPLACE VIEW SANKHYA.ANDRE_IAGRO_SALDO_COMBUSTIVEL AS
WITH
  entradas AS (
    SELECT
      i.CODPROD,
      SUM(NVL(i.QTDNEG, 0)) AS QTD_ENTRADA
    FROM TGFITE i
    JOIN TGFCAB c  ON c.NUNOTA  = i.NUNOTA
    JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
    WHERE c.CODTIPOPER   = 10
      AND c.STATUSNOTA  <> 'E'
      AND pr.CODGRUPOPROD = 200400
    GROUP BY i.CODPROD
  ),
  saidas AS (
    SELECT
      i.CODPROD,
      SUM(NVL(i.QTDNEG, 0)) AS QTD_SAIDA
    FROM TGFITE i
    JOIN TGFCAB c  ON c.NUNOTA  = i.NUNOTA
    JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
    WHERE c.CODTIPOPER   = 53
      AND c.STATUSNOTA  <> 'E'
      AND pr.CODGRUPOPROD = 200400
      AND NOT EXISTS (
        SELECT 1
        FROM AD_REQUISICAO_COMBUSTIVEL r
        WHERE r.NUNOTA = i.NUNOTA
          AND r.TIPO   = 'EXTERNA_POSTO'
      )
    GROUP BY i.CODPROD
  )
SELECT
  COALESCE(e.CODPROD, s.CODPROD) AS CODPROD,
  pr.DESCRPROD,
  pr.CODVOL,
  NVL(e.QTD_ENTRADA, 0)                                       AS QTD_ENTRADA,
  NVL(s.QTD_SAIDA,   0)                                       AS QTD_SAIDA,
  GREATEST(NVL(e.QTD_ENTRADA, 0) - NVL(s.QTD_SAIDA, 0), 0)    AS QTD_DISPONIVEL
FROM entradas e
FULL OUTER JOIN saidas s
  ON s.CODPROD = e.CODPROD
JOIN TGFPRO pr
  ON pr.CODPROD = COALESCE(e.CODPROD, s.CODPROD);
