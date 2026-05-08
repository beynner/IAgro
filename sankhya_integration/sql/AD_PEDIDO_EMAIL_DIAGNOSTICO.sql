-- ============================================================
-- DIAGNÓSTICO — Tabelas auxiliares do módulo Importação por E-mail
-- Use para verificar o estado dos pré-pedidos no banco.
-- ============================================================

-- 1) Estado geral da fila (contagem por STATUS)
SELECT STATUS, COUNT(*) AS QTD
  FROM AD_PEDIDO_EMAIL_RECEBIDO
 GROUP BY STATUS
 ORDER BY QTD DESC;

-- 2) Últimos 30 e-mails recebidos (cabeçalho)
SELECT R.ID,
       R.SUB_ID,
       R.MESSAGE_ID,
       R.REMETENTE,
       R.ASSUNTO,
       R.RECEBIDO_EM,
       R.PROCESSADO_EM,
       R.STATUS,
       R.LLM_MODELO,                 -- 'regex_consinco_v1' (Etapa 0) ou 'qwen2.5:14b-instruct' (LLM)
       R.LLM_CONFIANCA_GERAL,
       R.CODPARC_SUGERIDO,
       R.CODEMP_SUGERIDO,
       R.CODTIPVENDA_SUGERIDO,
       R.DTNEG_SUGERIDA,
       R.OBSERVACAO_EXTRAIDA,
       R.MOTIVO_DESCARTE,
       R.NUNOTA_GERADO,              -- preenchido só após CONFIRMADO
       R.CONFIRMADO_POR,
       R.CONFIRMADO_EM,
       R.ORIGEM,                     -- IMAP / TEXTO_LIVRE / WHATSAPP_API
       R.PDF_PATH,
       R.CRIADO_EM
  FROM AD_PEDIDO_EMAIL_RECEBIDO R
 ORDER BY R.RECEBIDO_EM DESC, R.SUB_ID ASC
 FETCH FIRST 30 ROWS ONLY;

-- 3) Pré-pedidos PENDENTE_REVISAO com nome canônico do parceiro sugerido
--    (mesma query que a tela de revisão usa)
SELECT R.ID,
       R.SUB_ID,
       R.RECEBIDO_EM,
       R.REMETENTE,
       R.ASSUNTO,
       R.LLM_CONFIANCA_GERAL                          AS CONFIANCA,
       R.LLM_MODELO,
       R.CODPARC_SUGERIDO,
       P.NOMEPARC                                     AS PARCEIRO_SUGERIDO,
       (SELECT COUNT(*) FROM AD_PEDIDO_EMAIL_ITEM I
         WHERE I.RECEBIDO_ID = R.ID)                   AS QTD_ITENS
  FROM AD_PEDIDO_EMAIL_RECEBIDO R
  LEFT JOIN TGFPAR P ON P.CODPARC = R.CODPARC_SUGERIDO
 WHERE R.STATUS = 'PENDENTE_REVISAO'
 ORDER BY R.RECEBIDO_EM DESC, R.SUB_ID ASC;

-- 4) Itens de um pré-pedido específico (troque <ID>)
SELECT I.ID,
       I.SEQUENCIA,
       I.DESCRICAO_PDF,
       I.COD_CLIENTE,                                 -- coluna nova; só populada em PDFs Consinco
       I.CODPROD_SUGERIDO,
       PR.DESCRPROD                                   AS PRODUTO_SUGERIDO,
       I.CODPROD_CONFIANCA,                           -- 1.00 = alias/cod_cliente; 0.75-0.99 = fuzzy
       I.CODPROD_FINAL,                               -- preenchido só quando operador edita
       I.QTD,
       I.CODVOL,
       I.PRECO_UNIT,
       I.OBSERVACAO,
       I.CRIADO_EM
  FROM AD_PEDIDO_EMAIL_ITEM I
  LEFT JOIN TGFPRO PR ON PR.CODPROD = I.CODPROD_SUGERIDO
 WHERE I.RECEBIDO_ID = &RECEBIDO_ID
 ORDER BY I.SEQUENCIA;

-- 5) Itens com matching automatico por código do cliente (Etapa 0)
--    Confiança = 1.00 + COD_CLIENTE preenchido = veio direto da
--    AD_CLIENTE_PRODUTO_COD (pedidos seguintes do mesmo cliente).
SELECT R.ID            AS RECEBIDO_ID,
       R.RECEBIDO_EM,
       P.NOMEPARC      AS CLIENTE,
       I.SEQUENCIA,
       I.COD_CLIENTE,
       I.DESCRICAO_PDF,
       PR.DESCRPROD    AS NOSSO_PRODUTO,
       I.CODPROD_SUGERIDO,
       I.CODPROD_CONFIANCA
  FROM AD_PEDIDO_EMAIL_RECEBIDO R
  JOIN AD_PEDIDO_EMAIL_ITEM I ON I.RECEBIDO_ID = R.ID
  LEFT JOIN TGFPAR P  ON P.CODPARC  = R.CODPARC_SUGERIDO
  LEFT JOIN TGFPRO PR ON PR.CODPROD = I.CODPROD_SUGERIDO
 WHERE I.COD_CLIENTE IS NOT NULL
   AND I.CODPROD_CONFIANCA = 1.00
 ORDER BY R.RECEBIDO_EM DESC, I.SEQUENCIA;

-- 6) Pré-pedidos JÁ CONFIRMADOS (viraram TGFCAB) — link reverso
SELECT R.ID                AS RECEBIDO_ID,
       R.SUB_ID,
       R.RECEBIDO_EM,
       R.NUNOTA_GERADO,
       C.NUMNOTA,
       C.CODTIPOPER        AS TOP_NOTA,
       C.STATUSNOTA,
       C.VLRNOTA,
       C.CODPARC,
       P.NOMEPARC,
       R.CONFIRMADO_POR,
       U.NOMEUSU           AS CONFIRMADO_POR_NOME,
       R.CONFIRMADO_EM
  FROM AD_PEDIDO_EMAIL_RECEBIDO R
  JOIN TGFCAB C ON C.NUNOTA = R.NUNOTA_GERADO
  LEFT JOIN TGFPAR P ON P.CODPARC = C.CODPARC
  LEFT JOIN TSIUSU U ON U.CODUSU  = R.CONFIRMADO_POR
 WHERE R.STATUS = 'CONFIRMADO'
 ORDER BY R.CONFIRMADO_EM DESC
 FETCH FIRST 20 ROWS ONLY;

-- 7) Pré-pedidos com ERRO (parser falhou ou PDF ilegível)
SELECT ID, SUB_ID, RECEBIDO_EM, REMETENTE, ASSUNTO, STATUS,
       MOTIVO_DESCARTE, PDF_PATH
  FROM AD_PEDIDO_EMAIL_RECEBIDO
 WHERE STATUS IN ('ERRO_PARSER', 'ERRO_PDF', 'DESCARTADO')
 ORDER BY RECEBIDO_EM DESC;

-- 8) Tabelas de aprendizado — quanto cada alias já economizou trabalho
SELECT 'AD_PARCEIRO_ALIAS' AS TABELA,
       COUNT(*)            AS LINHAS,
       NVL(SUM(COUNT_USADO), 0) AS USOS_TOTAIS
  FROM AD_PARCEIRO_ALIAS
UNION ALL
SELECT 'AD_PRODUTO_ALIAS',
       COUNT(*), NVL(SUM(COUNT_USADO), 0)
  FROM AD_PRODUTO_ALIAS
UNION ALL
SELECT 'AD_CLIENTE_PRODUTO_COD',
       COUNT(*), NVL(SUM(COUNT_USADO), 0)
  FROM AD_CLIENTE_PRODUTO_COD;

-- 9) Top 20 vinculações cliente→produto mais usadas
SELECT V.CODPARC,
       P.NOMEPARC,
       V.COD_CLIENTE,
       V.CODPROD,
       PR.DESCRPROD,
       V.COUNT_USADO,
       V.ULTIMO_USO,
       V.CRIADO_EM
  FROM AD_CLIENTE_PRODUTO_COD V
  LEFT JOIN TGFPAR P  ON P.CODPARC  = V.CODPARC
  LEFT JOIN TGFPRO PR ON PR.CODPROD = V.CODPROD
 ORDER BY V.COUNT_USADO DESC, V.ULTIMO_USO DESC
 FETCH FIRST 20 ROWS ONLY;

-- 10) Distribuição Etapa 0/1 (regex) vs Etapa 2 (LLM) nas últimas semanas
--     Útil pra medir o ganho da Etapa 0 em produção.
SELECT TRUNC(RECEBIDO_EM)   AS DIA,
       LLM_MODELO,
       COUNT(*)              AS QTD
  FROM AD_PEDIDO_EMAIL_RECEBIDO
 WHERE RECEBIDO_EM >= TRUNC(SYSDATE) - 14
   AND STATUS NOT IN ('ERRO_PDF')
 GROUP BY TRUNC(RECEBIDO_EM), LLM_MODELO
 ORDER BY DIA DESC, LLM_MODELO;

-- 11) Schema das duas tabelas principais (para conferência rápida)
SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE, DATA_DEFAULT
  FROM USER_TAB_COLUMNS
 WHERE TABLE_NAME = 'AD_PEDIDO_EMAIL_RECEBIDO'
 ORDER BY COLUMN_ID;

SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE, DATA_DEFAULT
  FROM USER_TAB_COLUMNS
 WHERE TABLE_NAME = 'AD_PEDIDO_EMAIL_ITEM'
 ORDER BY COLUMN_ID;

-- 12) Constraint UNIQUE composta (MESSAGE_ID, SUB_ID) — anti-duplicação
SELECT C.CONSTRAINT_NAME, C.CONSTRAINT_TYPE, CC.COLUMN_NAME, CC.POSITION
  FROM USER_CONSTRAINTS C
  JOIN USER_CONS_COLUMNS CC ON CC.CONSTRAINT_NAME = C.CONSTRAINT_NAME
 WHERE C.TABLE_NAME = 'AD_PEDIDO_EMAIL_RECEBIDO'
   AND C.CONSTRAINT_TYPE IN ('U', 'P')
 ORDER BY C.CONSTRAINT_NAME, CC.POSITION;
