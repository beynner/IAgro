-- SANKHYA.TRG_DLT_TCIMOV
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TCIMOV
"SANKHYA".TRG_DLT_TCIMOV
   BEFORE DELETE
   ON TCIMOV
   FOR EACH ROW
   
DECLARE
   ERRMSG      VARCHAR2 (255);
   ERROR EXCEPTION;
   P_VALIDAR   BOOLEAN;
BEGIN
   IF Stp_Get_Atualizando
   THEN
      RETURN;
   END IF;

   /*
   Sincronização de dados
   */
   P_VALIDAR := Fpodevalidar ('TCIMOV');

   ERRMSG :=
         'Movimento do Imobilizado '
      || :NEW.CODBEM
      || ' não pode ser excluído por já estar contabilizado.';
   RAISE ERROR;
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
