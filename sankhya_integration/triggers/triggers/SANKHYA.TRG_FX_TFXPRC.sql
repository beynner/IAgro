-- SANKHYA.TRG_FX_TFXPRC
CREATE OR REPLACE TRIGGER SANKHYA.TRG_FX_TFXPRC
"SANKHYA".TRG_FX_TFXPRC
   BEFORE INSERT OR UPDATE OR DELETE 
   ON TFXPRC
   FOR EACH ROW

DECLARE
   P_CONTADOR   NUMBER (19);
   P_CODTAB     NUMBER (10);
   ERRMSG       VARCHAR2(255);
BEGIN
    IF INSERTING OR UPDATING THEN    	 
		IF(:NEW.VLRVENDA >= 0.01 AND :NEW.VLRVENDA <= 99999999) THEN
        	IF (NVL(:NEW.DATAVIGOR, TRUNC(SYSDATE)) <> NVL(:OLD.DATAVIGOR, TRUNC(SYSDATE)))
			OR (NVL(:NEW.CODPROD, -1) <> NVL(:OLD.CODPROD, -1))
            OR (NVL(:NEW.NUTAB, -1) <> NVL(:OLD.NUTAB, -1))
            OR (NVL(:NEW.CODTAB, -1) <> NVL(:OLD.CODTAB, -1))
            OR (NVL(:NEW.VLRVENDA, -1) <> NVL(:OLD.VLRVENDA, -1))
	    OR (NVL(:NEW.NUVERSAO, 0) = 0) THEN 
		    		IF(NVL(:NEW.CODTAB, -1) = -1) THEN 
            			SELECT CODTAB INTO P_CODTAB from TGFTAB WHERE NUTAB = :NEW.NUTAB;                          
                    	:NEW.CODTAB := P_CODTAB;
                    END IF;
                            
            		SELECT SEQ_GLOBALFOX.NEXTVAL INTO P_CONTADOR FROM DUAL;
            		:NEW.NUVERSAO := P_CONTADOR;
            END IF;
    	END IF;
    END IF;
    IF DELETING THEN
        INSERT INTO TFXADE (NOMETAB, STRPK) VALUES (  'TPRECO', ' CODPRODUTO = '  || TO_CHAR (:OLD.CODPROD) 
	                                                                ||' AND NUTAB =  '|| TO_CHAR (:OLD.NUTAB) 
	                                                                ||' AND NUVERSAO = ' || TO_CHAR (:OLD.NUVERSAO) );
    END IF;
END;

/
