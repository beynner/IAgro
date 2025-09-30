-- SANKHYA.TRG_DLT_TFPBSU
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TFPBSU
"SANKHYA".TRG_DLT_TFPBSU BEFORE DELETE ON TFPBSU 
FOR EACH ROW

BEGIN 
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  IF (:OLD.NUFIN IS NOT NULL) THEN
    RAISE_APPLICATION_ERROR(-20101, 'Este cálculo não pode ser excluído ou recalculado porque seu valor já foi gerado no '||
									'Financeiro. Exclua primeiramente o lançamento correspondente no Financeiro. '||
									'Número único do título (' || TO_CHAR(:OLD.NUFIN) || ')');  
  END IF; 
END;

/
