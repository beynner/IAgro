-- SANKHYA.TRG_DLT_TCIMOVAJ
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TCIMOVAJ
"SANKHYA".TRG_DLT_TCIMOVAJ
   BEFORE DELETE
   ON TCIMOVAJ
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
   P_VALIDAR := Fpodevalidar ('TCIMOVAJ');

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
