-- SANKHYA.TRG_DLT_TGFGRU
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGFGRU
"SANKHYA".TRG_DLT_TGFGRU BEFORE DELETE ON TGFGRU FOR EACH ROW

DECLARE P_COUNT INTEGER;
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
  
  EXISTSRESTRICAO('TGFGRU',:OLD.CODGRUPOPROD);
  
  IF (:OLD.CODGRUPOPROD = 0) THEN
     raise_application_error(-20101, 'Registro padr?o do sistema. N?o pode ser alterado ou excluido.');
  END IF;
  
  SELECT COUNT(1) INTO P_COUNT 
  FROM TGFICM 
  WHERE TIPRESTRICAO = 'G' 
    AND CODRESTRICAO = :OLD.CODGRUPOPROD;
  IF (P_COUNT<>0) THEN
     raise_application_error(-20101, 'Registro nao pode ser deletado. Existe uma ref.nas excessoes das aliquotas de ICMS.');
  END IF;
  
  SELECT COUNT(1) INTO P_COUNT 
  FROM TGFICM 
  WHERE TIPRESTRICAO2 = 'G' 
    AND CODRESTRICAO2 = :OLD.CODGRUPOPROD;
  IF (P_COUNT<>0) THEN
     raise_application_error(-20101, 'Registro nao pode ser deletado. Existe uma ref.nas excessoes das aliquotas de ICMS.');
  END IF;
END;

/
