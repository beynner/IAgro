-- SANKHYA.TRG_INC_UPD_TGFICP
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFICP
"SANKHYA".TRG_INC_UPD_TGFICP
BEFORE INSERT OR UPDATE ON TGFICP FOR EACH ROW

DECLARE
  P_COUNT                  INT := 0;
  P_VALIDAR                  BOOLEAN;
  ERRMSG                     VARCHAR2(255);
  ERROR                      EXCEPTION;
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
  
  /* 
  sincronização de dados
  */
  P_VALIDAR := Fpodevalidar('TGFICP');

  SELECT COUNT(1) INTO P_COUNT
  FROM TGFPEM PEM
  WHERE PEM.CODPROD = :NEW.CODMATPRIMA
    AND PEM.TIPCONTEST IS NOT NULL;
  
  IF (P_COUNT > 0) THEN
    ERRMSG := 'Produto tem controle de estoque definido por empresa e não está preparada para usar esta opção.';
    RAISE ERROR;
  END IF;  

  RETURN;
   
EXCEPTION

  WHEN ERROR THEN
    /* 
    Sincronização de dados não faz validações
    */
    IF (P_VALIDAR) THEN 
      RAISE_APPLICATION_ERROR(-20101, ERRMSG);
    END IF; 

END;

/
