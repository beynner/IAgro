-- SANKHYA.TRG_INC_UPD_TGFPEM
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFPEM
"SANKHYA".TRG_INC_UPD_TGFPEM
   BEFORE INSERT OR UPDATE
   ON TGFPEM
   FOR EACH ROW

DECLARE
   P_COUNT     INT := 0;
   P_VALIDAR   BOOLEAN;
   ERRMSG      VARCHAR2 (255);
   ERROR EXCEPTION;
BEGIN
   IF STP_GET_ATUALIZANDO
   THEN
      RETURN;
   END IF;

   /*
   sincronização de dados
   */
   P_VALIDAR := Fpodevalidar ('TGFPEM');

   IF (:NEW.TIPCONTEST IS NOT NULL AND :OLD.TIPCONTEST <> :NEW.TIPCONTEST)
   THEN
      SELECT COUNT (1)
        INTO P_COUNT
        FROM TGFFCP
       WHERE CODPROD = :NEW.CODPROD;

      IF (P_COUNT > 0)
      THEN
         ERRMSG :=
            'Produto tem Formula ou pertence a uma formula de produção ou componente e não está preparada para usar esta opção.';
         RAISE ERROR;
      END IF;

      SELECT COUNT (1)
        INTO P_COUNT
        FROM TGFICP
       WHERE CODPROD = :NEW.CODPROD OR CODMATPRIMA = :NEW.CODPROD;

      IF (P_COUNT > 0)
      THEN
         ERRMSG :=
            'Produto tem Formula ou pertence a uma formula de produção ou componente e não está preparada para usar esta opção.';
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
