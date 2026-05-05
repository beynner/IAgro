-- =============================================================================
-- Arquivo de testes — view SANKHYA.ANDRE_IAGRO_SALDO_LOTE
--
-- IMPORTANTE: rode primeiro o ANDRE_IAGRO_SALDO_LOTE.sql para criar a view.
-- Depois rode este aqui para conferir lotes específicos.
--
-- Este arquivo é seguro de ser executado várias vezes — só consulta a view,
-- não cria/altera nada no banco.
-- =============================================================================

-- =============================================================================
-- LOTE A CONFERIR — TROQUE AQUI (UMA ÚNICA VEZ POR EXECUÇÃO)
-- =============================================================================
SET DEFINE ON;
SET VERIFY OFF;
DEFINE p_lote = 'COLE_AQUI_UM_LOTE_REAL';


-- =============================================================================
-- 1) TESTE PRINCIPAL — todas as linhas (todas as pernas) do lote alvo
-- =============================================================================
SELECT *
  FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE
 WHERE CODAGREGACAO = '&p_lote'
 ORDER BY STATUS_LINHA, CODPROD;


-- =============================================================================
-- 2) Sanity check — quantas linhas por status NO LOTE alvo
-- =============================================================================
SELECT STATUS_LINHA, COUNT(*) AS QTD_LINHAS
  FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE
 WHERE CODAGREGACAO = '&p_lote'
 GROUP BY STATUS_LINHA;


-- =============================================================================
-- 3) Disjunção — para o lote alvo, cada (CODEMP, CODPROD) só pode ter UM
--    STATUS_LINHA nas pernas vendáveis (A e B). Esta query DEVE retornar ZERO.
-- =============================================================================
SELECT CODEMP, CODPROD, CODAGREGACAO, COUNT(DISTINCT STATUS_LINHA) AS STATUSES
  FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE
 WHERE CODAGREGACAO = '&p_lote'
   AND STATUS_LINHA IN ('CLASSIFICADO', 'NAO_CLASSIFICAVEL')
 GROUP BY CODEMP, CODPROD, CODAGREGACAO
HAVING COUNT(DISTINCT STATUS_LINHA) > 1;


-- =============================================================================
-- 4) Total disponível por produto NO LOTE alvo (só vendáveis)
-- =============================================================================
SELECT CODPROD, DESCRPROD, STATUS_LINHA,
       SUM(QTD_ENTRADA)        AS TOT_ENTRADA,
       SUM(QTD_BAIXADA_VENDA)  AS TOT_BAIXADA,
       SUM(QTD_BAIXADA_AVARIA) AS TOT_AVARIA,
       SUM(QTD_RESERVADA)      AS TOT_RESERV,
       SUM(QTD_DISPONIVEL)     AS TOT_DISP
  FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE
 WHERE CODAGREGACAO = '&p_lote'
   AND VENDAVEL = 'S'
 GROUP BY CODPROD, DESCRPROD, STATUS_LINHA
 ORDER BY DESCRPROD;


-- =============================================================================
-- 5) Sanity check GLOBAL — sem filtro de lote, para visão macro
-- =============================================================================
SELECT STATUS_LINHA, COUNT(*) AS QTD_LINHAS
  FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE
 GROUP BY STATUS_LINHA;
