-- SANKHYA.TRG_DLT_TGFCOM
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGFCOM
"SANKHYA".TRG_DLT_TGFCOM BEFORE DELETE ON TGFCOM  
FOR EACH ROW  

BEGIN  

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  IF (:OLD.VLRCOM <> 0) AND (:OLD.TIPO <> 'D') THEN
     IF (:OLD.NUFIN > 0) THEN  
         raise_application_error(-20101, 'Exclusão proibida, valor de comissão com referência no financeiro.');  
     END IF;
     IF (:OLD.REFERENCIA IS NOT NULL) THEN  
        raise_application_error(-20101, 'Exclusão proibida, valor de comissão com referência na folha de pagamento.');  
     END IF; 
   END IF;
END;

/
