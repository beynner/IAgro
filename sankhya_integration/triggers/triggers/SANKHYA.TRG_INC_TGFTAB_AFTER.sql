-- SANKHYA.TRG_INC_TGFTAB_AFTER
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_TGFTAB_AFTER
"SANKHYA".TRG_INC_TGFTAB_AFTER
  AFTER INSERT
  ON TGFTAB

DECLARE
  P_COUNT         INT;
  P_NUTAB         INT;
  P_CODTAB        INT;
  P_CODTABORIG    INT;
  P_DTVIGOR       DATE;
  ERRMSG          VARCHAR2 (255);
  ERROR           EXCEPTION;
  P_ULT_NUTAB     INT;
  P_ULT_DTVIGOR   DATE;

  CURSOR INCTAB
  IS
    SELECT NUTAB, CODTAB, CODTABORIG, DTVIGOR
      FROM TGFTAB_INC;
BEGIN
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  OPEN INCTAB;

  DELETE FROM TGFTAB_INC;

  LOOP
    FETCH INCTAB
     INTO P_NUTAB, P_CODTAB, P_CODTABORIG, P_DTVIGOR;

    EXIT WHEN INCTAB%NOTFOUND;

    SELECT COUNT (1)
      INTO P_COUNT
      FROM TGFTAB T
     WHERE T.CODTAB = P_CODTABORIG
       AND P_DTVIGOR < T.DTVIGOR;

    IF (P_COUNT <> 0) THEN
      ERRMSG := 'A tabela de origem tem data de vigor maior que a data de vigor da própria tabela.'||' CODTABORIG: '||TO_CHAR(P_CODTABORIG)||' DTVIGOR: '||TO_CHAR(P_DTVIGOR);
      RAISE ERROR;
    END IF;

    SELECT COUNT (1)
      INTO P_COUNT
      FROM TGFTAB
     WHERE CODTAB = P_CODTAB
       AND NUTAB <> P_NUTAB;

    IF (P_COUNT <> 0) THEN
      SELECT NUTAB, DTVIGOR
        INTO P_ULT_NUTAB, P_ULT_DTVIGOR
        FROM TGFTAB
       WHERE CODTAB = P_CODTAB
         AND NUTAB <> P_NUTAB
         AND DTVIGOR = (SELECT MAX (DTVIGOR)
                          FROM TGFTAB
                         WHERE CODTAB = P_CODTAB
                           AND NUTAB <> P_NUTAB);

      /* Não incluir uma tabela com data de vigor anterior a ultima venda para a tabela 0. */
      /*IF (P_CODTAB = 0) THEN*/ --Comentado por demanda da OS 524893 
        SELECT COUNT (1)
          INTO P_COUNT
          FROM TGFITE I, TGFCAB C
         WHERE I.NUTAB = P_ULT_NUTAB
           AND C.DTNEG > P_DTVIGOR
           AND C.DTNEG <= SYSDATE ()
           AND I.NUNOTA = C.NUNOTA
           AND C.TIPMOV IN ('V', 'P');

        IF (P_COUNT <> 0) THEN
          ERRMSG := '(0) Já existe venda posterior a esta data de vigor.';
          RAISE ERROR;
        END IF;
      /*ELSE  --Comentado por demanda da OS 524893
        SELECT COUNT (1)
          INTO P_COUNT
          FROM TGFITE I, TGFCAB C
         WHERE I.NUTAB = P_ULT_NUTAB
           AND C.DTNEG >= P_DTVIGOR
           AND C.DTNEG <= SYSDATE ()
           AND I.NUNOTA = C.NUNOTA
           AND C.TIPMOV IN ('V', 'P');

        IF (P_COUNT <> 0) THEN
          ERRMSG := '(1) Já existe venda posterior a esta data de vigor.';
          RAISE ERROR;
        END IF;
      END IF;*/

      IF (TRUNC(P_ULT_DTVIGOR) >= TRUNC(P_DTVIGOR)) THEN
        ERRMSG :=
             'Não pode incluir uma tabela com data VIGOR anterior ou igual a última data da tabela. (Nutab:'
          || TO_CHAR (P_ULT_NUTAB, '9999999999')
          || ' DtVigor:'
          || TO_CHAR (P_ULT_DTVIGOR, 'DD/MM/YYYY')
          || ')';
        RAISE ERROR;
      END IF;
    END IF;
  END LOOP;

  CLOSE INCTAB;
EXCEPTION
  WHEN ERROR THEN
    RAISE_APPLICATION_ERROR (-20101, ERRMSG);
END;

/
