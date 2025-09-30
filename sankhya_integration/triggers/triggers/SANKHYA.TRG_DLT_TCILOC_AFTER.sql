-- SANKHYA.TRG_DLT_TCILOC_AFTER
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TCILOC_AFTER
"SANKHYA".TRG_DLT_TCILOC_AFTER
AFTER DELETE ON TCILOC

DECLARE 
	P_COUNT_DELETE				NUMBER(5);
    P_COUNT_UPDATE				NUMBER(5);
BEGIN
	SELECT COUNT(1)
	INTO P_COUNT_DELETE
	FROM TCILOC_ATUAL
	WHERE DELETADO = 'S'
    AND NOT EXISTS (SELECT 1
                    FROM TCILOC
                    WHERE CODPROD = TCILOC_ATUAL.CODPROD
                        AND CODBEM = TCILOC_ATUAL.CODBEM
                        AND DTENTRADA < TCILOC_ATUAL.DTENTRADA);

	IF P_COUNT_DELETE > 0 THEN
        DELETE FROM TCILOC_ATUAL 
        WHERE DELETADO = 'S'
            AND NOT EXISTS (SELECT 1
                            FROM TCILOC
                            WHERE CODPROD = TCILOC_ATUAL.CODPROD
                                AND CODBEM = TCILOC_ATUAL.CODBEM
                                AND DTENTRADA < TCILOC_ATUAL.DTENTRADA);
    END IF;

	SELECT COUNT(1)
	INTO P_COUNT_UPDATE
	FROM TCILOC_ATUAL
	WHERE DELETADO = 'S'
        AND EXISTS (SELECT 1
                    FROM TCILOC
                    WHERE CODPROD = TCILOC_ATUAL.CODPROD
                        AND CODBEM = TCILOC_ATUAL.CODBEM
                        AND DTENTRADA = (SELECT MAX(DTENTRADA)
                                          FROM TCILOC
                                          WHERE CODPROD = TCILOC_ATUAL.CODPROD
                                              AND CODBEM = TCILOC_ATUAL.CODBEM
                                              AND DTENTRADA < TCILOC_ATUAL.DTENTRADA));

    IF P_COUNT_UPDATE > 0 THEN
        UPDATE TCILOC_ATUAL
        SET DTENTRADA = (SELECT MAX(DTENTRADA)
                         FROM TCILOC
                         WHERE CODPROD = TCILOC_ATUAL.CODPROD
                             AND CODBEM = TCILOC_ATUAL.CODBEM
                             AND DTENTRADA < TCILOC_ATUAL.DTENTRADA)
          , CODUSU = (SELECT MAX(CODUSU)
                      FROM TCILOC
                      WHERE CODPROD = TCILOC_ATUAL.CODPROD
                          AND CODBEM = TCILOC_ATUAL.CODBEM
                          AND DTENTRADA = (SELECT MAX(DTENTRADA)
                                           FROM TCILOC
                                           WHERE CODPROD = TCILOC_ATUAL.CODPROD
                                               AND CODBEM = TCILOC_ATUAL.CODBEM
                                               AND DTENTRADA < TCILOC_ATUAL.DTENTRADA))
          , CODEMP = (SELECT MAX(CODEMP)
                      FROM TCILOC
                      WHERE CODPROD = TCILOC_ATUAL.CODPROD
                          AND CODBEM = TCILOC_ATUAL.CODBEM
                          AND DTENTRADA = (SELECT MAX(DTENTRADA)
                                           FROM TCILOC
                                           WHERE CODPROD = TCILOC_ATUAL.CODPROD
                                               AND CODBEM = TCILOC_ATUAL.CODBEM
                                               AND DTENTRADA < TCILOC_ATUAL.DTENTRADA))
          , CODDEPTO = (SELECT MAX(CODDEPTO)
                        FROM TCILOC
                        WHERE CODPROD = TCILOC_ATUAL.CODPROD
                            AND CODBEM = TCILOC_ATUAL.CODBEM
                            AND DTENTRADA = (SELECT MAX(DTENTRADA)
                                             FROM TCILOC
                                             WHERE CODPROD = TCILOC_ATUAL.CODPROD
                                                 AND CODBEM = TCILOC_ATUAL.CODBEM
                                                 AND DTENTRADA < TCILOC_ATUAL.DTENTRADA))
          , NUNOTA = (SELECT MAX(NUNOTA)
                      FROM TCILOC
                      WHERE CODPROD = TCILOC_ATUAL.CODPROD
                          AND CODBEM = TCILOC_ATUAL.CODBEM
                          AND DTENTRADA = (SELECT MAX(DTENTRADA)
                                           FROM TCILOC
                                           WHERE CODPROD = TCILOC_ATUAL.CODPROD
                                               AND CODBEM = TCILOC_ATUAL.CODBEM
                                               AND DTENTRADA < TCILOC_ATUAL.DTENTRADA))
          , SEQUENCIA = (SELECT MAX(SEQUENCIA)
                         FROM TCILOC
                         WHERE CODPROD = TCILOC_ATUAL.CODPROD
                             AND CODBEM = TCILOC_ATUAL.CODBEM
                             AND DTENTRADA = (SELECT MAX(DTENTRADA)
                                              FROM TCILOC
                                              WHERE CODPROD = TCILOC_ATUAL.CODPROD
                                                  AND CODBEM = TCILOC_ATUAL.CODBEM
                                                  AND DTENTRADA < TCILOC_ATUAL.DTENTRADA))
          , DELETADO = 'N' --NORMALIZANDO O CAMPO
        WHERE DELETADO = 'S'
            AND EXISTS (SELECT 1
                        FROM TCILOC
                        WHERE CODPROD = TCILOC_ATUAL.CODPROD
                            AND CODBEM = TCILOC_ATUAL.CODBEM
                            AND DTENTRADA = (SELECT MAX(DTENTRADA)
                                             FROM TCILOC
                                             WHERE CODPROD = TCILOC_ATUAL.CODPROD
                                                 AND CODBEM = TCILOC_ATUAL.CODBEM
                                                 AND DTENTRADA < TCILOC_ATUAL.DTENTRADA));
    END IF;
END;

/
