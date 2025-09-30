-- SANKHYA.TRG_DLT_TSICID
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TSICID
"SANKHYA".TRG_DLT_TSICID BEFORE DELETE ON TSICID FOR EACH ROW

DECLARE
	P_COUNT                  INT:= 0;
BEGIN
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  IF (:OLD.CODCID = 0) THEN
     raise_application_error(-20101, 'Registro padrão do sistema. Não pode ser alterado ou excluído.');
  END IF;

  SELECT COUNT(1) INTO P_COUNT
  FROM TGFICM
  WHERE (TIPRESTRICAO = 'C' OR TIPRESTRICAO = 'D')
  AND CODRESTRICAO = :OLD.CODCID;
  IF (P_COUNT<>0) THEN
    raise_application_error(-20101, 'Registro nao pode ser deletado. Existe uma ref.nas exceções das alíquotas de ICMS.');
  END IF;


  SELECT COUNT(1)  INTO P_COUNT
  FROM TGFICM
  WHERE (TIPRESTRICAO2 = 'C' OR TIPRESTRICAO2 = 'D')
  AND CODRESTRICAO2 = :OLD.CODCID;
  IF (P_COUNT<>0) THEN
    raise_application_error(-20101, 'Registro nao pode ser deletado. Existe uma ref.nas exceções das alíquotas de ICMS.');
  END IF;
END;


/
