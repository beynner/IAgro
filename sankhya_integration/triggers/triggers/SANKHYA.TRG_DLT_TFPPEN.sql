-- SANKHYA.TRG_DLT_TFPPEN
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TFPPEN
"SANKHYA".TRG_DLT_TFPPEN
BEFORE DELETE ON TFPPEN
FOR EACH ROW

BEGIN

  IF (:OLD.NUFIN IS NOT NULL) THEN
    RAISE_APPLICATION_ERROR(-20101, 'Cálculo de pensionista não pode ser excluído ou recalculado porque seu valor já foi gerado no Financeiro. Exclua primeiramente o lançamento correspondente no Financeiro. Número único do título (' || :OLD.NUFIN || ')');  
  END IF;
 
END;

/
