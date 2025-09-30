-- SANKHYA.TRG_INC_UPD_TGFLIV_INTEGRIDADE
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFLIV_INTEGRIDADE
"SANKHYA".TRG_INC_UPD_TGFLIV_INTEGRIDADE
   BEFORE INSERT OR UPDATE
   ON TGFLIV
   FOR EACH ROW

DECLARE
   P_COUNT     INT;
   ERROR       EXCEPTION;
   ERRMSG      VARCHAR2 (255);
   P_VALIDAR   BOOLEAN;
BEGIN
   IF STP_GET_ATUALIZANDO
   THEN
      RETURN;
   END IF;

   P_VALIDAR := Fpodevalidar ('TGFLIV');             -- sincronização de dados

   IF :NEW.CODCFO IS NOT NULL THEN
       SELECT COUNT (1)
         INTO P_COUNT
         FROM TGFCFO
        WHERE CODCFO = :NEW.CODCFO;

       IF (P_COUNT = 0)
       THEN
          ERRMSG := 'CFO não existe.';
          RAISE ERROR;
       END IF;
   END IF;

   IF :NEW.CODCTACTB IS NOT NULL THEN
       SELECT COUNT (1)
         INTO P_COUNT
         FROM TCBPLA
        WHERE CODCTACTB = :NEW.CODCTACTB;

       IF (P_COUNT = 0)
       THEN
          ERRMSG := 'Código da conta contábil não existe.';
          RAISE ERROR;
       END IF;
   END IF;

   IF :NEW.CODEMP IS NOT NULL THEN
       SELECT COUNT (1)
         INTO P_COUNT
         FROM TGFEMP
        WHERE CODEMP = :NEW.CODEMP;

       IF (P_COUNT = 0)
       THEN
          ERRMSG := 'Código da empresa não existe.';
          RAISE ERROR;
       END IF;
   END IF;

   RETURN;
EXCEPTION
   WHEN ERROR
   THEN
      /*
      Sincronização de dados não faz validações
      */
      IF (P_VALIDAR)
      THEN
         RAISE_APPLICATION_ERROR (-20101, ERRMSG);
      END IF;
END;

/
