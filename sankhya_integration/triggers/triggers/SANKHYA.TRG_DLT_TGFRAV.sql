-- SANKHYA.TRG_DLT_TGFRAV
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGFRAV
"SANKHYA".TRG_DLT_TGFRAV 
BEFORE DELETE ON TGFRAV FOR EACH ROW

DECLARE P_COUNT                  INT:= 0;  
        ERROR                    EXCEPTION;  
        ERRMSG                   VARCHAR2(255);  
        PRAGMA AUTONOMOUS_TRANSACTION;
BEGIN
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
  
  IF :OLD.ORIGEM = 'E' THEN
  
    SELECT COUNT(1) INTO P_COUNT  
    FROM TCBINT C  
    WHERE C.NUNICO = :OLD.NUFIN   
      AND C.ORIGEM = 'E';  
    IF P_COUNT > 0 THEN  
       ERRMSG := 'NUNOTA: ' || :OLD.NUFIN || ' já  contabilizada, não pode ser alterada.';  
       RAISE ERROR;  
    END IF;
        
    SELECT COUNT(1)  
    INTO P_COUNT  
    FROM TCBINT C  
       , TGFFIN F  
    WHERE F.NUNOTA = :OLD.NUFIN   
      AND C.NUNICO = F.NUFIN  
      AND C.ORIGEM IN ('F', 'B');  
    IF P_COUNT > 0 THEN  
      ERRMSG := 'NUNOTA: ' || :OLD.NUFIN || ' com Financeiro já  contabilizado, não pode ser alterada.';  
      RAISE ERROR;  
    END IF;  
      
  ELSIF ((:OLD.ORIGEM = 'F') OR (:OLD.ORIGEM = 'R')) AND (:OLD.NUFIN <> TGFFIN_PKG.V_NUFINRECOMPANT) THEN
    
    SELECT COUNT(1) INTO P_COUNT  
    FROM TCBINT C  
    WHERE C.NUNICO = :OLD.NUFIN   
      AND C.ORIGEM IN ('F','B');  
    IF P_COUNT > 0 THEN  
       ERRMSG := 'NUFIN: ' || :OLD.NUFIN || ' já  contabilizado, não pode ser alterado.';  
       RAISE ERROR;  
    END IF;
      
  END IF;
  
  COMMIT;  
	RETURN;
EXCEPTION WHEN ERROR THEN  
    RAISE_APPLICATION_ERROR(-20101, ERRMSG);  
END;

/
