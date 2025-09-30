-- SANKHYA.TRG_AUTO_DUPLICATE_CLASS
-- Trigger para duplicação automática TOP 11 → TOP 26
-- Criado em: 2025-09-30
-- Função: Quando inserir item TOP 11 com GERAPRODUCAO='S', 
--          duplica automaticamente TGFCAB e TGFITE para TOP 26

CREATE OR REPLACE TRIGGER SANKHYA.TRG_AUTO_DUPLICATE_CLASS
    AFTER INSERT ON TGFITE
    FOR EACH ROW
DECLARE
    v_nunota_26 NUMBER;
    v_exists NUMBER;
    v_codtipoper NUMBER;
    v_controle VARCHAR2(100);
    v_auto_enabled NUMBER;
    v_count_items NUMBER;
BEGIN
    -- Verificar se automação está habilitada (via parâmetro ou configuração)
    BEGIN
        SELECT 1 INTO v_auto_enabled
        FROM DUAL 
        WHERE 1=1; -- Por enquanto sempre habilitado, pode ser controlado via tabela de parâmetros
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RETURN; -- Se não encontrar configuração, não executa
    END;
    
    -- Obter CODTIPOPER do cabeçalho da nota
    SELECT c.CODTIPOPER INTO v_codtipoper
    FROM TGFCAB c 
    WHERE c.NUNOTA = :NEW.NUNOTA;
    
    -- Só processar se for TOP 11 e produto que gera produção
    IF (v_codtipoper = 11 AND NVL(:NEW.GERAPRODUCAO, 'N') = 'S') THEN
        
        v_controle := :NEW.CODAGREGACAO;
        
        -- Verificar se já existe TOP 26 para este controle
        SELECT COUNT(*) INTO v_exists
        FROM TGFITE i
        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA  
        WHERE i.CODAGREGACAO = v_controle
        AND c.CODTIPOPER = 26
        AND ROWNUM = 1;
        
        -- Se não existe TOP 26, criar
        IF v_exists = 0 THEN
            
            -- 1. Criar TGFCAB TOP 26 baseado no TOP 11
            INSERT INTO TGFCAB (
                NUNOTA, CODEMP, CODPARC, CODTIPOPER, CODNAT, CODCENCUS,
                DTNEG, DTMOV, DTENTSAI, DHTIPOPER, TIPMOV, STATUSNOTA,
                OBSERVACAO, CODVEND, CODPARCTRANSP, CODPROJ
            )
            SELECT 
                (SELECT NVL(MAX(NUNOTA), 0) + 1 FROM TGFCAB),
                c.CODEMP, c.CODPARC, 26, c.CODNAT, c.CODCENCUS,
                c.DTNEG, c.DTMOV, c.DTENTSAI, SYSDATE, 'P', 'A',
                'Auto-criado para classificação do controle ' || v_controle,
                c.CODVEND, c.CODPARCTRANSP, c.CODPROJ
            FROM TGFCAB c
            WHERE c.NUNOTA = :NEW.NUNOTA;
            
            -- Obter NUNOTA criado
            SELECT MAX(NUNOTA) INTO v_nunota_26
            FROM TGFCAB 
            WHERE CODTIPOPER = 26;
            
            -- 2. Inserir todos os itens classificáveis do mesmo controle
            INSERT INTO TGFITE (
                NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG, VLRUNIT, VLRTOT,
                CODVOL, CODLOCALORIG, CODAGREGACAO, GERAPRODUCAO, STATUSNOTA,
                OBSERVACAO
            )
            SELECT 
                v_nunota_26,
                ROW_NUMBER() OVER (ORDER BY i.SEQUENCIA),
                i.CODEMP, i.CODPROD, i.QTDNEG, i.VLRUNIT, i.VLRTOT,
                i.CODVOL, i.CODLOCALORIG, i.CODAGREGACAO, i.GERAPRODUCAO, 'A',
                'Auto-duplicado de TOP 11 NUNOTA ' || i.NUNOTA
            FROM TGFITE i
            JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
            WHERE c.CODTIPOPER = 11 
            AND i.CODAGREGACAO = v_controle
            AND NVL(i.GERAPRODUCAO, 'N') = 'S';
            
            -- Contar quantos itens foram inseridos
            SELECT COUNT(*) INTO v_count_items
            FROM TGFITE 
            WHERE NUNOTA = v_nunota_26;
            
            -- Log da operação (opcional - comentar se não houver tabela de log)
            /*
            INSERT INTO TGFLOG (DTLOG, USUARIO, EVENTO, DESCRICAO)
            VALUES (SYSDATE, USER, 'TRG_AUTO_DUPLICATE_CLASS', 
                    'Duplicado TOP 11→26: NUNOTA ' || :NEW.NUNOTA || '→' || v_nunota_26 || 
                    ', Controle: ' || v_controle || ', Itens: ' || v_count_items);
            */
            
        END IF;
    END IF;
    
EXCEPTION
    WHEN OTHERS THEN
        -- Log do erro mas não falha a transação principal
        -- Opcional - comentar se não houver tabela de log
        /*
        INSERT INTO TGFLOG (DTLOG, USUARIO, EVENTO, DESCRICAO)
        VALUES (SYSDATE, USER, 'TRG_AUTO_DUPLICATE_CLASS_ERROR', 
                'Erro: ' || SQLERRM || ' - NUNOTA: ' || :NEW.NUNOTA || 
                ', CONTROLE: ' || :NEW.CODAGREGACAO);
        COMMIT;
        */
        NULL; -- Não propagar erro para não afetar inserção original
END;
/

-- Comentários e instruções de uso:
-- 
-- 1. Este trigger é executado APÓS INSERT em TGFITE
-- 2. Só atua em itens TOP 11 com GERAPRODUCAO = 'S'
-- 3. Cria automaticamente TGFCAB e TGFITE TOP 26 para classificação
-- 4. Não duplica se já existir TOP 26 para o mesmo controle
-- 5. Em caso de erro, não afeta a inserção original (EXCEPTION NULL)
--
-- Para habilitar logs, descomente as seções INSERT INTO TGFLOG
-- e certifique-se de que a tabela TGFLOG existe com as colunas adequadas.
--
-- Para desabilitar temporariamente, execute:
-- ALTER TRIGGER SANKHYA.TRG_AUTO_DUPLICATE_CLASS DISABLE;
--
-- Para reabilitar:
-- ALTER TRIGGER SANKHYA.TRG_AUTO_DUPLICATE_CLASS ENABLE;
--
-- Para verificar status:
-- SELECT trigger_name, status FROM user_triggers WHERE trigger_name = 'TRG_AUTO_DUPLICATE_CLASS';