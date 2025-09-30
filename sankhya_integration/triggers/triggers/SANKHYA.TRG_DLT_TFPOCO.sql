-- SANKHYA.TRG_DLT_TFPOCO
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TFPOCO
"SANKHYA".TRG_DLT_TFPOCO
   BEFORE DELETE
   ON TFPOCO
   FOR EACH ROW

DECLARE
   P_COUNT   INTEGER;
BEGIN
   IF STP_GET_ATUALIZANDO
   THEN
      RETURN;
   END IF;

   SELECT COUNT (1)
     INTO P_COUNT
     FROM TFPAFDT
    WHERE NUOCOR = :OLD.NUOCOR AND FECHADO = 'S';

   IF P_COUNT > 0
   THEN
      RAISE_APPLICATION_ERROR (
         -20101,
         'Impossivel excluir. Existe registro fechado na tabela TFPAFDT(Ponto), ligado a esta ocorrência!');
   END IF;

   SELECT COUNT (1)
     INTO P_COUNT
     FROM TFPAFDT
    WHERE NUOCOR = :OLD.NUOCOR AND TIPREGISTRO IN ('I', 'P');

   IF P_COUNT > 0
   THEN
      DELETE FROM TFPAFDT
            WHERE NUOCOR = :OLD.NUOCOR;
   ELSE
      SELECT COUNT (1)
        INTO P_COUNT
        FROM TFPAFDT
       WHERE NUOCOR = :OLD.NUOCOR AND TIPREGISTRO = 'O';

      IF P_COUNT > 0
      THEN
         UPDATE TFPAFDT
            SET NUOCOR = NULL,
                TIPMARCACAO = NULL,
                SEQTIPMARCACAO = NULL,
                DIGITADO = 'N'
          WHERE NUOCOR = :OLD.NUOCOR;
      END IF;
   END IF;

   IF (:OLD.NUFALTA IS NOT NULL)
   THEN
      SELECT COUNT (1)
        INTO P_COUNT
        FROM TFPFAL
       WHERE   NUFALTA = :OLD.NUFALTA
             AND CODEMP = :OLD.CODEMP
             AND CODFUNC = :OLD.CODFUNC;

      IF P_COUNT > 0
      THEN
         RAISE_APPLICATION_ERROR (
            -20101,
            'Impossível excluir. Movimento esta sendo referenciado pela falta/restituição de falta ('
            || :OLD.NUFALTA
            || ') na TFPFAL !');
      END IF;
   END IF;
END;

/
