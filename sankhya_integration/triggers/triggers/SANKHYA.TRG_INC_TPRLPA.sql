-- SANKHYA.TRG_INC_TPRLPA
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_TPRLPA
"SANKHYA".TRG_INC_TPRLPA 
  BEFORE INSERT ON TPRLPA 
  FOR EACH ROW 

DECLARE 
    CURSOR PA IS 
      SELECT PRC.IDPROC, 
             LMP.CODPRODPA, 
             LMP.CONTROLEPA, 
             LMP.CODPRODMP, 
             LMP.CONTROLEMP 
      FROM   TPRLMP LMP 
             INNER JOIN TPREFX EFX 
                     ON ( LMP.IDEFX = EFX.IDEFX ) 
             INNER JOIN TPRPRC PRC 
                     ON ( EFX.IDPROC = PRC.IDPROC ) 
      WHERE  LMP.CODPRODMP = :NEW.CODPRODPA 
             AND LMP.CONTROLEMP = :NEW.CONTROLEPA
             AND PRC.IDPROC = :NEW.IDPROC
             AND NOT EXISTS (SELECT 1 
                             FROM   TPRLPI 
                             WHERE  CODPRODPA = LMP.CODPRODPA 
                                    AND ( NVL(CONTROLEPA, ' ') = ' ' 
                                           OR NVL(CONTROLEPA, ' ') = 
                                              NVL(LMP.CONTROLEPA, ' ') 
                                        ) 
                                    AND IDPROC = PRC.IDPROC 
                                    AND CODPRODPI = LMP.CODPRODMP 
                                    AND NVL(CONTROLEPI, ' ') = 
                                        NVL(LMP.CONTROLEMP, ' ' 
                                        )); 
    V_IDPROC     INT; 
    V_CODPRODPA  INT; 
    V_CONTROLEPA TPRLPA.CONTROLEPA%TYPE; 
    V_CODPRODMP  INT; 
    V_CONTROLEMP TPRLPA.CONTROLEPA%TYPE; 
BEGIN 
    OPEN PA; 

    LOOP 
        FETCH PA INTO V_IDPROC, V_CODPRODPA, V_CONTROLEPA, V_CODPRODMP, 
        V_CONTROLEMP 
        ; 

        EXIT WHEN PA%NOTFOUND; 

        BEGIN 
            INSERT INTO TPRLPI 
                        (IDPROC, 
                         CODPRODPA, 
                         CONTROLEPA, 
                         CODPRODPI, 
                         CONTROLEPI) 
            VALUES      (V_IDPROC, 
                         V_CODPRODPA, 
                         NVL(V_CONTROLEPA, ' '), 
                         V_CODPRODMP, 
                         NVL(V_CONTROLEMP, ' ')); 
        EXCEPTION 
            WHEN DUP_VAL_ON_INDEX THEN 
              RETURN; 
        END; 
    END LOOP; 

    CLOSE PA; 
END; 

/
