-- SANKHYA.TRG_INC_UPD_DLT_TGFITE_RASTST
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_DLT_TGFITE_RASTST
"SANKHYA".TRG_INC_UPD_DLT_TGFITE_RASTST
   BEFORE INSERT OR UPDATE OR DELETE
   ON TGFITE
   FOR EACH ROW

DECLARE
   P_COUNT                NUMBER(10);
   P_CODEMP                NUMBER(5);
   P_CODEMPNEGOC        NUMBER(5);
   P_CODTIPOPER            NUMBER(10);
   P_DHTIPOPER            DATE;
   P_TIPMOV                CHAR(1);
   P_NUNOTAENTRADA        NUMBER(10);
   P_SEQUENCIAENTRADA    NUMBER(5);
   P_DIGITADO            VARCHAR2(1);
   P_NUNOTAAMPARO        NUMBER(10);
   P_SEQUENCIAAMPARO    NUMBER(5);
   P_VLRICMSANT            FLOAT;
   P_BASESUBSTITANT        FLOAT;
   P_VLRSUBSTANT        FLOAT;
   P_ALIQSTFCPSTANT        FLOAT;
   P_BASESTFCPINTANT    FLOAT;
   P_VLRSTFCPINTANT        FLOAT;
   P_PERCSTFCPINTANT    FLOAT;
   P_MSG                VARCHAR2(4000);
   P_TEMRASTEMPDEST        CHAR(1);
BEGIN
    IF (INSERTING OR UPDATING) AND NVL(:NEW.STATUSNOTA, 'A') = 'L' THEN
        BEGIN
            SELECT CODEMP, NVL(CODEMPNEGOC, 0), CODTIPOPER, DHTIPOPER, TIPMOV
                INTO P_CODEMP, P_CODEMPNEGOC, P_CODTIPOPER, P_DHTIPOPER, P_TIPMOV
            FROM TGFCAB
            WHERE NUNOTA = :NEW.NUNOTA;
        EXCEPTION WHEN NO_DATA_FOUND THEN
            P_MSG := 'Não foi localizado o cabeçalho da nora de nro único '||:NEW.NUNOTA||' para realizar o rastreamento de st.';
            RAISE_APPLICATION_ERROR(-20101, P_MSG);
        END;

        IF P_TIPMOV = 'T' THEN
            P_TEMRASTEMPDEST := NVL(GET_TEM_RASTSTULTENTRADA(P_CODEMPNEGOC, :NEW.CODPROD, P_CODTIPOPER, P_DHTIPOPER), 'S');
        ELSE 
            P_TEMRASTEMPDEST := 'N';
        END IF;

        -- A TRANSFERÊNCIA ENTRA AQUI TAMBÉM PARA PREENCHER OS VALORES DE STRETIDO ANTERIORMENTE NA PRÓPRIA TRANSFERÊNCIA E 
        -- PARA ATUALIZAR A ÚLTIMA ENTRADA NA EMPRESA DE DESTINO
        IF P_TEMRASTEMPDEST = 'S' OR GET_TEM_RASTSTULTENTRADA(P_CODEMP, :NEW.CODPROD, P_CODTIPOPER, P_DHTIPOPER) = 'S' THEN
            IF (NVL(:OLD.STATUSNOTA, 'A') <> NVL(:NEW.STATUSNOTA, 'A') OR NVL(:OLD.QTDNEG, 0) <> :NEW.QTDNEG OR NVL(:OLD.CODPROD, 0) <> :NEW.CODPROD) THEN
                IF UPDATING AND :OLD.CODPROD <> :NEW.CODPROD AND (P_TIPMOV IN ('V', 'E') OR (P_TIPMOV = 'T' AND :NEW.ATUALESTOQUE = -1)) THEN
                    SELECT COUNT(1) INTO P_COUNT
                    FROM TGFNOI
                    WHERE NUNOTA = :OLD.NUNOTA
                      AND SEQUENCIA = :OLD.SEQUENCIA;
                    IF P_COUNT > 0 THEN
                        DELETE FROM TGFNOI
                        WHERE NUNOTA = :OLD.NUNOTA
                          AND SEQUENCIA = :OLD.SEQUENCIA;
                    END IF;    
                END IF;

                IF P_TIPMOV IN ('V', 'E', 'T') THEN
                    BEGIN
                        SELECT NUNOTAENTRADA, SEQUENCIAENTRADA, VLRICMSUNIT, BASESUBSTUNIT, VLRSUBSTUNIT, PERCSUBST, BASESTFCPINTANTUNIT, VLRSTFCPINTANTUNIT, PERCSTFCPINTANTUNIT, NUNOTAAMPARO, SEQUENCIAAMPARO, DIGITADO
                            INTO P_NUNOTAENTRADA, P_SEQUENCIAENTRADA, P_VLRICMSANT, P_BASESUBSTITANT, P_VLRSUBSTANT, P_ALIQSTFCPSTANT, P_BASESTFCPINTANT, P_VLRSTFCPINTANT, P_PERCSTFCPINTANT, P_NUNOTAAMPARO, P_SEQUENCIAAMPARO, P_DIGITADO
                        FROM TGFCST
                        WHERE CODEMP = P_CODEMP --Se for transferência pega os valores da empresa de origem
                          AND CODPROD = :NEW.CODPROD;
                    EXCEPTION WHEN NO_DATA_FOUND THEN
                        P_BASESUBSTITANT := 0;
                    END;

                    IF NVL(P_BASESUBSTITANT, 0) <> 0 THEN
                        IF P_TIPMOV IN ('V', 'E')  OR (P_TIPMOV = 'T' AND :NEW.ATUALESTOQUE = -1) THEN
                            :NEW.VLRICMSANT := ROUND(P_VLRICMSANT * :NEW.QTDNEG, 2);
                            :NEW.BASESUBSTITANT := ROUND(P_BASESUBSTITANT * :NEW.QTDNEG, 2);
                            :NEW.VLRSUBSTANT := ROUND(P_VLRSUBSTANT * :NEW.QTDNEG, 2);
                            :NEW.ALIQSTFCPSTANT := P_ALIQSTFCPSTANT;
                            :NEW.BASESTFCPINTANT := ROUND(P_BASESTFCPINTANT * :NEW.QTDNEG, 2);
                            :NEW.VLRSTFCPINTANT := ROUND(P_VLRSTFCPINTANT * :NEW.QTDNEG, 2);
                            :NEW.PERCSTFCPINTANT := P_PERCSTFCPINTANT;

                            SELECT COUNT(1) INTO P_COUNT
                            FROM TGFNOI
                            WHERE NUNOTA = :NEW.NUNOTA
                              AND SEQUENCIA = :NEW.SEQUENCIA;

                            IF P_COUNT > 0 THEN
                                UPDATE TGFNOI SET NUNOTAENTRADA = P_NUNOTAENTRADA
                                                , SEQUENCIAENTRADA = P_SEQUENCIAENTRADA
                                                , DIGITADO = P_DIGITADO
                                                , NUNOTAAMPARO = P_NUNOTAAMPARO
                                                , SEQUENCIAAMPARO = P_SEQUENCIAAMPARO
                                WHERE NUNOTA = :NEW.NUNOTA
                                  AND SEQUENCIA = :NEW.SEQUENCIA;
                            ELSE
                                INSERT INTO TGFNOI (NUNOTA, SEQUENCIA, NUNOTAENTRADA, SEQUENCIAENTRADA, DIGITADO, NUNOTAAMPARO, SEQUENCIAAMPARO)
                                            VALUES(:NEW.NUNOTA, :NEW.SEQUENCIA, P_NUNOTAENTRADA, P_SEQUENCIAENTRADA, P_DIGITADO, P_NUNOTAAMPARO, P_SEQUENCIAAMPARO);
                            END IF;
                        END IF;
                    ELSE
                        P_MSG := 'O produto "'||:NEW.CODPROD||'", da nota de nro único "'||:NEW.NUNOTA||'" e empresa '||P_CODEMP||', não tem as informações de ICMS ST retido anteriormente, necessárias para revenda/transferência deste.';
                        RAISE_APPLICATION_ERROR(-20101, P_MSG);
                    END IF;
                ELSIF P_TIPMOV = 'C' THEN

                    GET_IMPOSTOS_RASTSTULTENTRADA (:NEW.NUNOTA, 
                                                  :NEW.SEQUENCIA,
                                                  1, --QTDDISP
                                                  P_VLRICMSANT,
                                                  P_BASESUBSTITANT,
                                                  P_VLRSUBSTANT,
                                                  P_BASESTFCPINTANT,
                                                  P_VLRSTFCPINTANT,
                                                  P_PERCSTFCPINTANT,
                                                  P_ALIQSTFCPSTANT);

                    IF NVL(P_BASESUBSTITANT, 0) > 0 THEN
                        SELECT COUNT(1) INTO P_COUNT
                        FROM TGFCST
                        WHERE CODEMP = P_CODEMP
                          AND CODPROD = :NEW.CODPROD;

                        IF P_COUNT > 0 THEN
                            UPDATE TGFCST SET NUNOTAENTRADA = :NEW.NUNOTA
                                            , SEQUENCIAENTRADA = :NEW.SEQUENCIA
                                            , DIGITADO = 'N'
                                            , NUNOTAAMPARO = NULL
                                            , SEQUENCIAAMPARO = NULL
                                            , VLRICMSUNIT = P_VLRICMSANT
                                            , BASESUBSTUNIT = P_BASESUBSTITANT
                                            , VLRSUBSTUNIT = P_VLRSUBSTANT
                                            , PERCSUBST = P_ALIQSTFCPSTANT
                                            , BASESTFCPINTANTUNIT = P_BASESTFCPINTANT
                                            , VLRSTFCPINTANTUNIT = P_VLRSTFCPINTANT
                                            , PERCSTFCPINTANTUNIT = P_PERCSTFCPINTANT
                            WHERE CODEMP = P_CODEMP
                                AND CODPROD = :NEW.CODPROD;
                        ELSE
                            INSERT INTO TGFCST(CODEMP, CODPROD, NUNOTAENTRADA, SEQUENCIAENTRADA, VLRICMSUNIT, BASESUBSTUNIT, VLRSUBSTUNIT, PERCSUBST, BASESTFCPINTANTUNIT, VLRSTFCPINTANTUNIT, PERCSTFCPINTANTUNIT, DIGITADO)
                                        VALUES(P_CODEMP, :NEW.CODPROD, :NEW.NUNOTA, :NEW.SEQUENCIA, P_VLRICMSANT, P_BASESUBSTITANT, P_VLRSUBSTANT, P_ALIQSTFCPSTANT, P_BASESTFCPINTANT, P_VLRSTFCPINTANT, P_PERCSTFCPINTANT, 'N');
                        END IF;
                    ELSE
                        P_MSG := 'O produto "'||:NEW.CODPROD||'" da nota de nro único "'||:NEW.NUNOTA||'" e empresa "'||P_CODEMP||'", não tem as informações de ICMS ST retido anteriormente, necessárias para revenda deste.';
                        RAISE_APPLICATION_ERROR(-20101, P_MSG);
                    END IF;
                END IF;
            END IF;
        END IF;
    ELSIF NVL(:OLD.STATUSNOTA, 'A') = 'L' THEN -- SE ESTIVER DELETANDO
        SELECT COUNT(1) INTO P_COUNT
        FROM TGFNOI
        WHERE NUNOTA = :OLD.NUNOTA
          AND SEQUENCIA = :OLD.SEQUENCIA;
        IF P_COUNT > 0 THEN
            DELETE FROM TGFNOI
            WHERE NUNOTA = :OLD.NUNOTA
              AND SEQUENCIA = :OLD.SEQUENCIA;
        END IF;
    END IF;
END;

/
