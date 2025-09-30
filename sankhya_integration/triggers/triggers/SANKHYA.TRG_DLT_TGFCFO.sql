-- SANKHYA.TRG_DLT_TGFCFO
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGFCFO
"SANKHYA".TRG_DLT_TGFCFO BEFORE DELETE ON TGFCFO FOR EACH ROW

DECLARE
     P_COUNT                  INT:= 0;
BEGIN
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  IF (:OLD.CODCFO = 0) THEN
     raise_application_error(-20101, 'Registro padrao do sistema. Nao pode ser excluido.');
  END IF;

  SELECT COUNT(1) INTO P_COUNT FROM TGFLIV C WHERE C.CODCFO = :OLD.CODCFO;
  IF P_COUNT <> 0 THEN
     raise_application_error(-20101, 'Existe referência a este CFO na tabela TGFLIV.');
  END IF;

END;

/
