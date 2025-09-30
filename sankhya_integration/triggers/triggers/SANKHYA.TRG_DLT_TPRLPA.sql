-- SANKHYA.TRG_DLT_TPRLPA
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TPRLPA
"SANKHYA".TRG_DLT_TPRLPA 
  BEFORE DELETE ON TPRLPA 
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
      WHERE  LMP.CODPRODMP = :OLD.CODPRODPA 
             -- AND (LMP.CONTROLEMP IS NULL OR LMP.CONTROLEMP = '') 
             AND NOT EXISTS (SELECT 1 
                             FROM   TPRLPA LPA 
                             WHERE  LPA.IDPROC <> :OLD.IDPROC 
                                    AND LPA.CODPRODPA = :OLD.CODPRODPA 
                                    AND ( NVL(LPA.CONTROLEPA, ' ') = ' ' 
                                           OR NVL(LPA.CONTROLEPA, ' ') = 
                                              NVL(:OLD.CONTROLEPA, ' ') )); 
    V_IDPROC     INT; 
    V_CODPRODPA  INT; 
    V_CONTROLEPA TPRLPA.CONTROLEPA%TYPE; 
    V_CODPRODMP  INT; 
    V_CONTROLEMP TPRLPA.CONTROLEPA%TYPE; 
    PRAGMA AUTONOMOUS_TRANSACTION; 
BEGIN 
    OPEN PA; 

    LOOP 
        FETCH PA INTO V_IDPROC, V_CODPRODPA, V_CONTROLEPA, V_CODPRODMP, 
        V_CONTROLEMP 
        ; 

        EXIT WHEN PA%NOTFOUND; 

        DELETE FROM TPRLPI LPI 
        WHERE  LPI.IDPROC = V_IDPROC 
               AND LPI.CODPRODPA = V_CODPRODPA 
               AND LPI.CONTROLEPA = NVL(V_CONTROLEPA, ' ') 
               AND LPI.CODPRODPI = V_CODPRODMP 
               AND LPI.CONTROLEPI = NVL(V_CONTROLEMP, ' '); 
    END LOOP; 

    COMMIT; 

    CLOSE PA; 
END; 

/
