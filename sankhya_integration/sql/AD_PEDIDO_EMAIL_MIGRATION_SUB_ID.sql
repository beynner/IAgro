-- =============================================================================
-- MIGRATION: adicionar SUB_ID em AD_PEDIDO_EMAIL_RECEBIDO
-- Data:      Maio/2026
-- Motivo:    1 e-mail pode trazer N pedidos no mesmo PDF (ex: rede com várias
--            lojas). Antes: 1 e-mail = 1 pré-pedido. Agora: 1 e-mail = N linhas
--            (mesmo MESSAGE_ID, SUB_ID 1..N).
--
-- Como aplicar
--   1. Conectar como dono da tabela (SANKHYA) no SQL*Plus, SQL Developer ou similar.
--   2. Executar este arquivo inteiro.
--   3. Conferir o resultado com a query no final do arquivo.
--
-- Este script é IDEMPOTENTE em parte (ALTER TABLE ADD falha se a coluna já existe).
-- Se rodar 2x e a coluna SUB_ID já existir, o segundo ALTER lança ORA-01430 — OK,
-- significa que já foi aplicado.
--
-- ROLLBACK (manual, se precisar reverter):
--   ALTER TABLE AD_PEDIDO_EMAIL_RECEBIDO DROP CONSTRAINT UK_AD_PEDIDO_EMAIL_MSGID;
--   ALTER TABLE AD_PEDIDO_EMAIL_RECEBIDO DROP COLUMN SUB_ID;
--   ALTER TABLE AD_PEDIDO_EMAIL_RECEBIDO
--     ADD CONSTRAINT UK_AD_PEDIDO_EMAIL_MSGID UNIQUE (MESSAGE_ID);
-- =============================================================================

-- 1. Adicionar coluna SUB_ID com default 1. Linhas existentes ficam com SUB_ID=1.
ALTER TABLE AD_PEDIDO_EMAIL_RECEBIDO
    ADD SUB_ID NUMBER DEFAULT 1 NOT NULL;

-- 2. Remover constraint UNIQUE antiga (somente em MESSAGE_ID)
ALTER TABLE AD_PEDIDO_EMAIL_RECEBIDO
    DROP CONSTRAINT UK_AD_PEDIDO_EMAIL_MSGID;

-- 3. Recriar constraint UNIQUE composta (MESSAGE_ID, SUB_ID)
--    Mantém o mesmo nome para minimizar diff em código que faça referência.
ALTER TABLE AD_PEDIDO_EMAIL_RECEBIDO
    ADD CONSTRAINT UK_AD_PEDIDO_EMAIL_MSGID UNIQUE (MESSAGE_ID, SUB_ID);

-- 4. Comentário descritivo na nova coluna (útil em SQL Developer / BI)
COMMENT ON COLUMN AD_PEDIDO_EMAIL_RECEBIDO.SUB_ID
    IS 'Sequencial (1,2,3,...) quando 1 PDF traz N pedidos. PDF de 1 pedido = SUB_ID=1';

-- =============================================================================
-- Verificação após aplicação (execute manualmente para conferir)
-- =============================================================================
-- SELECT COLUMN_NAME, DATA_TYPE, NULLABLE, DATA_DEFAULT
--   FROM USER_TAB_COLUMNS
--  WHERE TABLE_NAME = 'AD_PEDIDO_EMAIL_RECEBIDO'
--    AND COLUMN_NAME = 'SUB_ID';
-- Resultado esperado:
--   SUB_ID  NUMBER  N  1
--
-- SELECT c.CONSTRAINT_NAME, cc.COLUMN_NAME, cc.POSITION
--   FROM USER_CONSTRAINTS c
--   JOIN USER_CONS_COLUMNS cc ON c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
--  WHERE c.TABLE_NAME = 'AD_PEDIDO_EMAIL_RECEBIDO'
--    AND c.CONSTRAINT_TYPE = 'U';
-- Resultado esperado: 2 linhas
--   UK_AD_PEDIDO_EMAIL_MSGID  MESSAGE_ID  1
--   UK_AD_PEDIDO_EMAIL_MSGID  SUB_ID      2
