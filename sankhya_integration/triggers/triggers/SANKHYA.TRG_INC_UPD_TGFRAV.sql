-- SANKHYA.TRG_INC_UPD_TGFRAV
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFRAV
"SANKHYA".TRG_INC_UPD_TGFRAV 
BEFORE INSERT OR UPDATE ON TGFRAV
FOR EACH ROW

DECLARE P_COUNT                  INT:= 0;
        ERROR                    EXCEPTION;
        ERRMSG                   VARCHAR2(255);
        P_VALCTA         CHAR(1);
BEGIN

  IF STP_GET_ATUALIZANDO THEN 
    RETURN;
  END IF;

  BEGIN
    SELECT LOGICO INTO P_VALCTA
    FROM TSIPAR 
    WHERE CHAVE = 'VALCTA';
  EXCEPTION WHEN NO_DATA_FOUND THEN
    P_VALCTA := 'N';
  END;

  IF (P_VALCTA = 'S') THEN
    IF (NVL(:NEW.CODCTACTB,0) <> 0) AND (INSERTING OR (:NEW.CODCTACTB <> :OLD.CODCTACTB)) THEN
       SELECT COUNT(1) INTO P_COUNT
       FROM  TCBPLA
       WHERE CODCTACTB = :NEW.CODCTACTB
       AND ATIVA = 'S'
       AND ANALITICA = 'S';
       IF (P_COUNT = 0) THEN
          ERRMSG := 'Código contábil '||:NEW.CODCTACTB||' não esta ativo, não analítico ou não existe.';
          RAISE_APPLICATION_ERROR(-20101, ERRMSG);
       END IF;
    END IF;
  END IF;

  IF (NVL(:NEW.CODCENCUS,0) <> 0) AND (INSERTING OR (:NEW.CODCENCUS <> :OLD.CODCENCUS)) THEN
     SELECT COUNT(1) INTO P_COUNT
     FROM  TSICUS
     WHERE CODCENCUS = :NEW.CODCENCUS
     AND ATIVO = 'S'
     AND ANALITICO = 'S';
     IF ( P_COUNT = 0) THEN
        ERRMSG := 'Centro de resultado '||:NEW.CODCENCUS||' não esta ativo, não é analítico ou não existe.';
        RAISE_APPLICATION_ERROR(-20101, ERRMSG);
     END IF;
  END IF;

  IF (NVL(:NEW.CODNAT,0) <> 0) AND (INSERTING OR (:NEW.CODNAT <> :OLD.CODNAT)) THEN
     SELECT COUNT(1) INTO P_COUNT
     FROM  TGFNAT
     WHERE CODNAT = :NEW.CODNAT
     AND ATIVA = 'S'
     AND ANALITICA = 'S';
     IF (P_COUNT = 0) THEN
        ERRMSG := 'Natureza '||:NEW.CODNAT||' não esta ativa, não e analítica ou não existe';
        RAISE_APPLICATION_ERROR(-20101, ERRMSG);
     END IF;
  END IF;

  IF (NVL(:NEW.NUMCONTRATO,0) <> 0) AND (INSERTING OR (:NEW.NUMCONTRATO <> :OLD.NUMCONTRATO)) THEN
     SELECT COUNT(1) INTO P_COUNT
     FROM  TCSCON
     WHERE NUMCONTRATO = :NEW.NUMCONTRATO 
     AND ATIVO = 'S';
     IF ( P_COUNT = 0) THEN
        ERRMSG := 'Contrato '||:NEW.NUMCONTRATO||' não esta ativo.';
        RAISE_APPLICATION_ERROR(-20101,ERRMSG);
     END IF;
  END IF;

  IF (NVL(:NEW.CODPROJ,0) <> 0) AND (INSERTING OR (:NEW.CODPROJ <> :OLD.CODPROJ)) THEN
     SELECT COUNT(1) INTO P_COUNT
     FROM  TCSPRJ
     WHERE CODPROJ = :NEW.CODPROJ
     AND ATIVO = 'S' AND ANALITICO = 'S';
     IF  ( P_COUNT = 0) THEN
       ERRMSG := 'Projeto '||:NEW.CODPROJ||' não esta ativo, não e analítico ou não existe.';
       RAISE_APPLICATION_ERROR(-20101, ERRMSG);
     END IF;
  END IF;

  IF INSERTING THEN
    IF:NEW.ORIGEM = 'E' THEN
      SELECT COUNT(1) INTO P_COUNT
      FROM TGFCAB
      WHERE NUNOTA = :NEW.NUFIN;
      IF (P_COUNT = 0) THEN
        ERRMSG := 'Nota não cadastrada no sistema.';
        RAISE ERROR;
      END IF;
    ELSIF ((:NEW.ORIGEM = 'F') OR (:NEW.ORIGEM = 'R')) THEN
      SELECT COUNT(1) INTO P_COUNT
      FROM TGFFIN
      WHERE NUFIN = :NEW.NUFIN;
      IF (P_COUNT = 0) THEN
         ERRMSG := 'Número único financeiro não cadastrado no sistema.';
         RAISE ERROR;
      END IF;
    END IF;
  END IF;

  IF :NEW.ORIGEM = 'E' THEN
      SELECT COUNT(1) INTO P_COUNT
      FROM TCBINT C
      WHERE C.NUNICO = :NEW.NUFIN
    AND C.ORIGEM = 'E';
      IF P_COUNT > 0 THEN
         ERRMSG := 'Rateio-NUNOTA: ' || :NEW.NUFIN || ' já  contabilizada, não pode ser alterada.';
         RAISE ERROR;
      END IF;
      SELECT COUNT(1)
      INTO P_COUNT
      FROM TCBINT C
      , TGFFIN F
      WHERE F.NUNOTA = :NEW.NUFIN
      AND C.NUNICO = F.NUFIN
      AND C.ORIGEM IN ('F', 'B');
      IF P_COUNT > 0 THEN
        ERRMSG := 'Rateio-NUNOTA: ' || :NEW.NUFIN || ' com Financeiro já  contabilizado, não pode ser alterada.';
        RAISE ERROR;
      END IF;
  ELSIF ((:NEW.ORIGEM = 'F') OR (:NEW.ORIGEM = 'R')) AND (:NEW.NUFIN <> Tgffin_Pkg.V_NUFINRECOMP) THEN 
      SELECT COUNT(1) INTO P_COUNT
      FROM TCBINT C
      WHERE C.NUNICO = :NEW.NUFIN
    AND C.ORIGEM IN ('F','B');
      IF P_COUNT > 0 THEN
         ERRMSG := 'Rateio-NUFIN: ' || :NEW.NUFIN || ' já  contabilizado, não pode ser alterado.';
         RAISE ERROR;
      END IF;
  END IF;
  RETURN;
EXCEPTION
    WHEN ERROR THEN
    RAISE_APPLICATION_ERROR(-20101, ERRMSG);
END;

/
