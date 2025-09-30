-- SANKHYA.TRG_INC_UPD_TGFREP
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFREP
"SANKHYA".TRG_INC_UPD_TGFREP
BEFORE INSERT OR UPDATE ON TGFREP FOR EACH ROW

DECLARE
    P_COUNT          INT:= 0;
    ERRMSG  VARCHAR2(255);      
BEGIN
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  IF INSERTING OR :OLD.CODCOLREST <> :NEW.CODCOLREST THEN
     IF :NEW.TIPREST = 'E' THEN
        SELECT COUNT(1) INTO  P_COUNT
          FROM TGFEMP
         WHERE CODEMP = :NEW.CODCOLREST;
        IF (P_COUNT = 0) THEN
           ERRMSG := 'Empresa '||:NEW.CODCOLREST||' não esta ativa.';
           RAISE_APPLICATION_ERROR(-20101, ERRMSG);
         END IF;
     ELSIF :NEW.TIPREST = 'G' THEN
           SELECT COUNT(1) INTO  P_COUNT
             FROM TGFGRU
            WHERE CODGRUPOPROD = :NEW.CODCOLREST;
           IF (P_COUNT = 0) THEN
              ERRMSG := 'Grupo de produto '||:NEW.CODCOLREST||' não esta ativo, não é analítico ou não existe.';
              RAISE_APPLICATION_ERROR(-20101, ERRMSG);
           END IF;
     ELSIF :NEW.TIPREST = 'A' THEN
           SELECT COUNT(1) INTO  P_COUNT
             FROM TGFPAR
            WHERE CODPARC = :NEW.CODCOLREST;
           IF (P_COUNT = 0) THEN
              ERRMSG := 'Parceiro '||:NEW.CODCOLREST||' não existe.';
              RAISE_APPLICATION_ERROR(-20101, ERRMSG);
           END IF;
     ELSIF :NEW.TIPREST = 'P' THEN
           SELECT COUNT(1) INTO  P_COUNT
             FROM TGFPRO
            WHERE CODPROD = :NEW.CODCOLREST;
           IF (P_COUNT = 0) THEN
              ERRMSG := 'Produto '||:NEW.CODCOLREST||' não existe.';
              RAISE_APPLICATION_ERROR(-20101, ERRMSG);
           END IF;
     ELSIF :NEW.TIPREST = 'T' THEN
           SELECT COUNT(1) INTO  P_COUNT
             FROM TGFTPV
            WHERE CODTIPVENDA = :NEW.CODCOLREST;
            IF (P_COUNT = 0) THEN
               ERRMSG := 'Tipo de negociação '||:NEW.CODCOLREST||' não existe';
               RAISE_APPLICATION_ERROR(-20101, ERRMSG);
            END IF;
     ELSIF :NEW.TIPREST = 'U' THEN
           SELECT COUNT(1) INTO  P_COUNT
             FROM TSIUSU
            WHERE CODUSU = :NEW.CODCOLREST;
           IF (P_COUNT = 0) THEN
              ERRMSG := 'Usuário '||:NEW.CODCOLREST||' não existe';
              RAISE_APPLICATION_ERROR(-20101,ERRMSG);
           END IF;
     ELSIF :NEW.TIPREST = 'V' THEN
           SELECT COUNT(1) INTO  P_COUNT
             FROM TGFVEN
            WHERE CODVEND = :NEW.CODCOLREST;
           IF (P_COUNT = 0) THEN
              ERRMSG := 'Vendedor '||:NEW.CODCOLREST||' não existe';
              RAISE_APPLICATION_ERROR(-20101,ERRMSG);
           END IF;
     ELSIF :NEW.TIPREST = 'L' THEN
           SELECT COUNT(1) INTO  P_COUNT
             FROM TGFTPP
            WHERE CODTIPPARC = :NEW.CODCOLREST;
           IF (P_COUNT = 0) THEN
              ERRMSG := 'Tipo de parceiro '||:NEW.CODCOLREST||' não existe';
              RAISE_APPLICATION_ERROR(-20101, ERRMSG);
           END IF;
     ELSIF :NEW.TIPREST = 'D' THEN
           SELECT COUNT(1) INTO  P_COUNT
             FROM TGFTOP
            WHERE CODTIPOPER = :NEW.CODCOLREST;
           IF (P_COUNT = 0) THEN
              ERRMSG := 'Tipo de operação '||:NEW.CODCOLREST||' não existe';
              RAISE_APPLICATION_ERROR(-20101, ERRMSG);
           END IF;
     ELSIF :NEW.TIPREST = 'N' THEN
           SELECT COUNT(1) INTO  P_COUNT
             FROM TGFNAT
            WHERE CODNAT = :NEW.CODCOLREST;
           IF (P_COUNT = 0) THEN
              ERRMSG := 'Natureza '||:NEW.CODCOLREST||' não esta ativa, não e analítica ou não existe';
              RAISE_APPLICATION_ERROR(-20101, ERRMSG);
           END IF;
     ELSIF :NEW.TIPREST = 'C' THEN
           SELECT COUNT(1) INTO  P_COUNT
             FROM TSICUS
            WHERE CODCENCUS = :NEW.CODCOLREST;
           IF (P_COUNT = 0) THEN
              ERRMSG := 'Centro de resultado '||:NEW.CODCOLREST||' não esta ativo, não é analítico ou não existe.';
              RAISE_APPLICATION_ERROR(-20101, ERRMSG);
           END IF;
     END IF;
  END IF;

END;

/
