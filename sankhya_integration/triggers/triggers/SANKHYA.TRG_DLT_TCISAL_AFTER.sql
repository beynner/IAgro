-- SANKHYA.TRG_DLT_TCISAL_AFTER
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TCISAL_AFTER
"SANKHYA".TRG_DLT_TCISAL_AFTER
AFTER DELETE ON TCISAL

DECLARE 
	P_COUNT_DELETE				NUMBER(10);
    P_COUNT_UPDATE				NUMBER(10);
BEGIN
	SELECT COUNT(1)
	INTO P_COUNT_DELETE
	FROM TCISAL_ATUAL
	WHERE DELETADO = 'S'
    AND NOT EXISTS (SELECT 1
                    FROM TCISAL
                    WHERE CODPROD = TCISAL_ATUAL.CODPROD
                        AND CODBEM = TCISAL_ATUAL.CODBEM
                        AND REFERENCIA < TCISAL_ATUAL.REFERENCIA);

    IF P_COUNT_DELETE > 0 THEN
        DELETE FROM TCISAL_ATUAL 
        WHERE DELETADO = 'S'
            AND NOT EXISTS (SELECT 1
                            FROM TCISAL
                            WHERE CODPROD = TCISAL_ATUAL.CODPROD
                                AND CODBEM = TCISAL_ATUAL.CODBEM
                                AND REFERENCIA < TCISAL_ATUAL.REFERENCIA);
    END IF;

    
	SELECT COUNT(1)
	INTO P_COUNT_UPDATE
	FROM TCISAL_ATUAL
	WHERE DELETADO = 'S'
        AND EXISTS (SELECT 1
                    FROM TCISAL
                    WHERE CODPROD = TCISAL_ATUAL.CODPROD
                        AND CODBEM = TCISAL_ATUAL.CODBEM
                        AND REFERENCIA = (SELECT MAX(REFERENCIA)
                                          FROM TCISAL
                                          WHERE CODPROD = TCISAL_ATUAL.CODPROD
                                              AND CODBEM = TCISAL_ATUAL.CODBEM
                                              AND REFERENCIA < TCISAL_ATUAL.REFERENCIA));

	IF P_COUNT_UPDATE > 0 THEN
        UPDATE TCISAL_ATUAL
        SET REFERENCIA = (SELECT MAX(REFERENCIA)
                          FROM TCISAL
                          WHERE CODPROD = TCISAL_ATUAL.CODPROD
                              AND CODBEM = TCISAL_ATUAL.CODBEM
                              AND REFERENCIA < TCISAL_ATUAL.REFERENCIA)
          , SALDO = (SELECT MAX(SALDO)
                     FROM TCISAL
                     WHERE CODPROD = TCISAL_ATUAL.CODPROD
                         AND CODBEM = TCISAL_ATUAL.CODBEM
                         AND REFERENCIA = (SELECT MAX(REFERENCIA)
                                           FROM TCISAL
                                           WHERE CODPROD = TCISAL_ATUAL.CODPROD
                                               AND CODBEM = TCISAL_ATUAL.CODBEM
                                               AND REFERENCIA < TCISAL_ATUAL.REFERENCIA))
          , TOTALDEP = (SELECT MAX(TOTALDEP)
                        FROM TCISAL
                        WHERE CODPROD = TCISAL_ATUAL.CODPROD
                            AND CODBEM = TCISAL_ATUAL.CODBEM
                            AND REFERENCIA = (SELECT MAX(REFERENCIA)
                                              FROM TCISAL
                                              WHERE CODPROD = TCISAL_ATUAL.CODPROD
                                                  AND CODBEM = TCISAL_ATUAL.CODBEM
                                                  AND REFERENCIA < TCISAL_ATUAL.REFERENCIA))
          , DELETADO = 'N' --NORMALIZANDO O CAMPO
        WHERE DELETADO = 'S'
            AND EXISTS (SELECT 1
                        FROM TCISAL
                        WHERE CODPROD = TCISAL_ATUAL.CODPROD
                            AND CODBEM = TCISAL_ATUAL.CODBEM
                            AND REFERENCIA = (SELECT MAX(REFERENCIA)
                                              FROM TCISAL
                                              WHERE CODPROD = TCISAL_ATUAL.CODPROD
                                                  AND CODBEM = TCISAL_ATUAL.CODBEM
                                                  AND REFERENCIA < TCISAL_ATUAL.REFERENCIA));
    END IF;
END;

/
