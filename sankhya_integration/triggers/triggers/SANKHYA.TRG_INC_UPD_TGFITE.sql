-- SANKHYA.TRG_INC_UPD_TGFITE
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFITE
"SANKHYA".TRG_INC_UPD_TGFITE
BEFORE INSERT OR UPDATE ON TGFITE
FOR EACH ROW

DECLARE
  P_COUNT   NUMBER(5);
  P_VALIDAR BOOLEAN;
  P_NUPLAN  NUMBER(10);    
BEGIN


  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  P_VALIDAR := Fpodevalidar('TGFITE');
  IF (NOT P_VALIDAR) THEN
    RETURN;
  END IF;
  
  IF :OLD.CODVOL IS NULL OR :OLD.CODVOL <> :NEW.CODVOL THEN
    SELECT COUNT(1) INTO P_COUNT
    FROM TGFPRO
    WHERE CODPROD = :NEW.CODPROD
      AND CODVOL <> :NEW.CODVOL
      AND USOPROD <> 'S'
      AND NOT EXISTS(SELECT 1
                     FROM TGFVOA
                     WHERE CODPROD = :NEW.CODPROD
                       AND CODVOL  = :NEW.CODVOL);
             
    IF P_COUNT > 0 THEN
      RAISE_APPLICATION_ERROR(-20101, 'Volume: '||:NEW.CODVOL||' não cadastrado para o produto: '||TO_CHAR(:NEW.CODPROD));  
    END IF;  
  END IF;
  
  IF :OLD.STATUSNOTA = 'L' AND (NVL(:OLD.QTDNEG, 0) <> NVL(:NEW.QTDNEG, 0)) THEN
    SELECT COUNT(1) INTO P_COUNT
    FROM TGFCAB
    WHERE NUNOTA = :NEW.NUNOTA
      AND NVL(MODENTREGA, 'N') IN ('P', 'M', 'F')
      AND TIPMOV = 'P'
      AND EXISTS(SELECT 1
                 FROM TGFPLAN P
                 WHERE P.NUNOTAORIG = :NEW.NUNOTA
                   AND SITUACAO = 'A');
    IF P_COUNT > 0 THEN    
      SELECT P.NUPLAN INTO P_NUPLAN
      FROM TGFPLAN P
      WHERE P.NUNOTAORIG = :NEW.NUNOTA;
      Raise_Application_Error(-20101,'O pedido ' || :NEW.NUNOTA || ' não pode ser alterado pois está relacionado ao planejamento ' || P_NUPLAN ||' que possui distribuição de itens.');    
    END IF;  
  END IF;  
END;

/
