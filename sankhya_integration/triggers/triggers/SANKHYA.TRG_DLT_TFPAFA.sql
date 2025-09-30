-- SANKHYA.TRG_DLT_TFPAFA
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TFPAFA
"SANKHYA".TRG_DLT_TFPAFA BEFORE DELETE ON TFPAFA FOR EACH ROW

DECLARE P_COUNT INT;
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  IF (:OLD.CODAFAST = 0) THEN
     raise_application_error(-20101, 'Registro padrão do sistema. Não pode ser excluído.');
  END IF;
  SELECT 
    COUNT(1) INTO P_COUNT 
  FROM 
   TFPTPR TPR 
  WHERE ((TPR.CODAFASTCAGED = :OLD.CODAFAST) OR
  	 (TPR.CODAFASTFGTS = :OLD.CODAFAST) OR
	 (TPR.CODAFASTRAIS = :OLD.CODAFAST) );
		   
  IF (P_COUNT<>0) THEN
     raise_application_error(-20101, 'Existe ligação com o cadastro de tipos de rescisões. Não pode ser excluído. (TFPTPR)');
  END IF;		
END;


/
