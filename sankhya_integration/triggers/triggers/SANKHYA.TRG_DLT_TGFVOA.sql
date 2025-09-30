-- SANKHYA.TRG_DLT_TGFVOA
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGFVOA
TRG_DLT_TGFVOA 
  BEFORE DELETE ON TGFVOA 
  FOR EACH ROW

DECLARE 
    P_COUNT       NUMBER(10); 
    P_CODVOLIGUAL NUMBER(10); 
    
    PRAGMA AUTONOMOUS_TRANSACTION;
BEGIN 
    /* QUANDO SUBSTITUINDO PRODUTO N¿O VALIDAR RASTREAMENTO */ 
    IF (VARIAVEIS_PKG.V_SBPRODUTO) THEN
      RETURN;
    END IF;
  
    SELECT COUNT(1) 
    INTO   P_COUNT 
    FROM   TSIPAR 
    WHERE  CHAVE = 'SBPRODUTO'; 

    IF ( P_COUNT <> 0 ) THEN 
      RETURN; 
    END IF; 

    SELECT COUNT(1) 
    INTO   P_CODVOLIGUAL 
    FROM   TGFPRO PRO 
    WHERE  PRO.CODPROD = :OLD.CODPROD 
           AND PRO.CODVOL = :OLD.CODVOL; 
    
    IF P_CODVOLIGUAL > 0 THEN 
      RETURN; 
    END IF; 

    IF STP_GET_ATUALIZANDO THEN 
      RETURN; 
    END IF; 

    SELECT COUNT(1) 
    INTO   P_COUNT 
    FROM   TGFITE ITE 
    WHERE  TRIM(ITE.CODVOL) = TRIM(:OLD.CODVOL) 
           AND ITE.CODPROD = :OLD.CODPROD; 

    IF ( P_COUNT <> 0 ) THEN 
      Raise_application_error(-20101, 
      'Este Volume foi usado em Pedidos/Notas, n?o pode ser excluido.'); 
    END IF; 

    SELECT COUNT(1) 
    INTO   P_COUNT 
    FROM   TGFITC ITC
    WHERE  TRIM(ITC.CODVOL) = TRIM(:OLD.CODVOL) 
      AND ITC.CODPROD = :OLD.CODPROD; 

    IF ( P_COUNT <> 0 ) THEN 
      Raise_application_error(-20101, 
      'Este Volume foi usado em Cotac?es n?o pode ser excluido.'); 
    END IF; 
    
END;

/
