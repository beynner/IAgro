-- SANKHYA.TRG_INC_UPD_TGFIMA
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFIMA
"SANKHYA".TRG_INC_UPD_TGFIMA BEFORE INSERT OR UPDATE ON TGFIMA FOR EACH ROW 

DECLARE 
    P_COUNT                INT:= 0; 
BEGIN 
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  IF (:NEW.TIPO = 'P') THEN 
    SELECT COUNT(1) INTO  P_COUNT 
    FROM TGFPAR P 
    WHERE P.CODPARC = :NEW.CODIGO 
      AND P.ATIVO   = 'S'; 
    IF (P_COUNT = 0)   THEN 
       RAISE_APPLICATION_ERROR (-20101, 'Parceiro de código: ' || :NEW.CODIGO || ', não é válido ou não está ativo.');
    END IF; 
  ELSIF (:NEW.TIPO = 'T') THEN 
    SELECT COUNT(1) INTO  P_COUNT 
    FROM TGFTOP P 
    WHERE P.CODTIPOPER = :NEW.CODIGO 
      AND P.ATIVO   = 'S'; 
    IF (P_COUNT = 0)   THEN 
       RAISE_APPLICATION_ERROR (-20101, 'TOP de código: '  || :NEW.CODIGO || ', não é válido ou não está ativa.');
    END IF; 
  ELSIF (:NEW.TIPO = 'E') THEN 
    SELECT COUNT(1) INTO  P_COUNT 
    FROM TGFEMP P 
    WHERE P.CODEMP = :NEW.CODIGO 
      AND P.ATIVO   = 'S'; 
    IF (P_COUNT = 0)   THEN 
       RAISE_APPLICATION_ERROR (-20101, 'Empresa de código: ' || :NEW.CODIGO || ', não é válido ou não está ativa.');
    END IF; 
  ELSIF (:NEW.TIPO = 'G') THEN 
    SELECT COUNT(1) INTO  P_COUNT 
    FROM TGFGRU U 
    WHERE U.CODGRUPOPROD = :NEW.CODIGO 
      AND U.ATIVO   = 'S' AND U.ANALITICO = 'S'; 
    IF (P_COUNT = 0)   THEN 
       RAISE_APPLICATION_ERROR (-20101, 'Grupo de produtos de código: ' || :NEW.CODIGO || ', não é válido, não é analítico ou não está ativo.');
    END IF; 
  ELSIF (:NEW.TIPO = 'S') THEN 
    SELECT COUNT(1) INTO  P_COUNT 
    FROM TGFPRO P 
    WHERE P.CODPROD = :NEW.CODIGO 
      AND P.USOPROD = 'S' 
      AND P.ATIVO   = 'S'; 
    IF (P_COUNT = 0)   THEN 
       RAISE_APPLICATION_ERROR (-20101, 'Serviço de código: ' || :NEW.CODIGO || ', não é válido ou não está ativo.');
    END IF; 
  ELSIF (:NEW.TIPO = 'R') THEN 
    SELECT COUNT(1) INTO  P_COUNT 
    FROM TGFPRO P 
    WHERE P.CODPROD = :NEW.CODIGO 
      AND P.USOPROD <> 'S' 
      AND P.ATIVO   = 'S'; 
    IF (P_COUNT = 0)   THEN 
       RAISE_APPLICATION_ERROR (-20101, 'Produto de código: ' || :NEW.CODIGO || ', não é válido ou não está ativo.');
    END IF; 
  END IF; 
END;

/
