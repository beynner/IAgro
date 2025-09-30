-- SANKHYA.TRG_DLT_TSIBAI
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TSIBAI
"SANKHYA".TRG_DLT_TSIBAI BEFORE DELETE ON TSIBAI 
FOR EACH ROW

DECLARE
     P_COUNT                  INT:= 0;
     ERROR                    EXCEPTION;
     ERRMSG                   VARCHAR2(255);
 BEGIN
   IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
   IF (:OLD.CODBAI = 0) THEN
      ERRMSG := 'Registro padr?o do sistema. N?o pode ser excluido.';
      RAISE ERROR;
   END IF;
   EXCEPTION
     WHEN ERROR THEN
     raise_application_error(-20101, ERRMSG);
END;

/
