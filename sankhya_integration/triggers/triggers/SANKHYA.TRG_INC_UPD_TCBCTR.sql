-- SANKHYA.TRG_INC_UPD_TCBCTR
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TCBCTR
"SANKHYA".TRG_INC_UPD_TCBCTR 
BEFORE INSERT OR UPDATE ON TCBCTR FOR EACH ROW

DECLARE 
  P_COUNT INT:= 0; 
  ERROR       EXCEPTION; 
  ERRMSG      VARCHAR2(255); 
  P_NATUREZA  VARCHAR2(2);
  P_CODGRUPOCTA  VARCHAR2(2);
BEGIN 

  IF Stp_Get_Atualizando THEN 
    RETURN; 
  END IF; 
  
  BEGIN
    SELECT NATUREZA 
    INTO P_NATUREZA
    FROM TCBPLR 
    WHERE TIPO = :NEW.TIPO 
    AND CODCTAREF = :NEW.CODCTAREF; 
  EXCEPTION WHEN NO_DATA_FOUND THEN
    ERRMSG := 'Conta Referencial não existe no Plano de Contas da ECF ou ' || CHR(13) || 
              'Plano de Contas da ECF não importado ou ' || CHR(13) ||
              'Código da Instituição Responsável pelo Plano de Contas Referência incorreta (Preferências) !'; 
    RAISE ERROR; 
  END;
  
  BEGIN
    SELECT CODGRUPOCTA
    INTO P_CODGRUPOCTA
    FROM TCBPLA
    WHERE CODCTACTB = :NEW.CODCTACTB;
  EXCEPTION WHEN NO_DATA_FOUND THEN
    P_CODGRUPOCTA := 'ZZ';
  END;
  
  IF P_NATUREZA <> P_CODGRUPOCTA THEN 
    ERRMSG := 'Natureza da Conta Referencial do Plano de Contas da ECF diferente do Grupo de Conta'; 
    RAISE ERROR; 
  END IF;
   
EXCEPTION 
WHEN ERROR THEN 
    RAISE_APPLICATION_ERROR(-20101, ERRMSG); 
END;

/
