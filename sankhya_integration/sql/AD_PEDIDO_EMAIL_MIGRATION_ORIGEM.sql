-- =============================================================================
-- MIGRATION: adicionar ORIGEM em AD_PEDIDO_EMAIL_RECEBIDO
-- Data:      Maio/2026
-- Motivo:    Permitir importação de pré-pedidos por outras fontes além do
--            IMAP (paste manual de WhatsApp/SMS/copiar-colar; futuro
--            WhatsApp Business API). Coluna fica como discriminador na
--            origem do registro.
--
-- Valores possíveis:
--   'IMAP'         -> e-mail recebido pelo worker IMAP (default; comportamento atual)
--   'TEXTO_LIVRE'  -> operador colou texto direto na tela (WhatsApp, SMS, etc.)
--   'WHATSAPP_API' -> reservado para integração futura via WhatsApp Business
--
-- Como aplicar
--   1. Conectar como dono da tabela (SANKHYA) em SQL*Plus / SQL Developer.
--   2. Executar este arquivo inteiro.
--   3. Conferir com a query no final.
--
-- Idempotência: ALTER TABLE ADD lança ORA-01430 se a coluna já existir —
-- nesse caso o script já foi aplicado, ignorar erro.
--
-- ROLLBACK (manual, se precisar reverter):
--   ALTER TABLE AD_PEDIDO_EMAIL_RECEBIDO DROP COLUMN ORIGEM;
-- =============================================================================

-- 1. Adicionar coluna ORIGEM com default 'IMAP'. Linhas existentes ficam
--    como 'IMAP' automaticamente (comportamento legado preservado).
ALTER TABLE AD_PEDIDO_EMAIL_RECEBIDO
    ADD ORIGEM VARCHAR2(20) DEFAULT 'IMAP' NOT NULL;

-- 2. Comentário descritivo (útil em SQL Developer / BI)
COMMENT ON COLUMN AD_PEDIDO_EMAIL_RECEBIDO.ORIGEM
    IS 'Origem do registro: IMAP (worker e-mail), TEXTO_LIVRE (paste manual), WHATSAPP_API (futuro)';

-- =============================================================================
-- Verificação após aplicação
-- =============================================================================
-- SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE, DATA_DEFAULT
--   FROM USER_TAB_COLUMNS
--  WHERE TABLE_NAME = 'AD_PEDIDO_EMAIL_RECEBIDO'
--    AND COLUMN_NAME = 'ORIGEM';
-- Resultado esperado:
--   ORIGEM  VARCHAR2  20  N  'IMAP'
--
-- SELECT ORIGEM, COUNT(*) FROM AD_PEDIDO_EMAIL_RECEBIDO GROUP BY ORIGEM;
-- Após migração, todos registros antigos = 'IMAP'.
