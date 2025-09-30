-- SANKHYA.TRG_INC_UPD_DLT_TGFPRO_SUBST
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_DLT_TGFPRO_SUBST
"SANKHYA".TRG_INC_UPD_DLT_TGFPRO_SUBST
  AFTER INSERT OR UPDATE OR DELETE
  ON TGFPRO FOR EACH ROW

DECLARE
  P_COUNT     NUMBER(10);
  ERRMSG      VARCHAR2(500);
  ERROR       EXCEPTION;
  P_VALIDAR   BOOLEAN;  
  
  PRAGMA AUTONOMOUS_TRANSACTION;
  
  
            
BEGIN

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'PERCADPRODSUBST';
    IF P_COUNT = 0 THEN
        RETURN;
    ELSE
        P_COUNT := 0;
        SELECT COUNT(*) INTO P_COUNT
        FROM TSIPAR
        WHERE CHAVE = 'PERCADPRODSUBST'
          AND LOGICO = 'S';
        IF P_COUNT = 0 THEN
            RETURN;
        END IF;
    END IF;
     
    

    IF STP_GET_ATUALIZANDO THEN
    RETURN;
    END IF;
    
    --sincronizacão de dados
    P_VALIDAR := Fpodevalidar('TGFPRO');  
    --Sincronizacão de dados não faz validacães
    IF NOT P_VALIDAR THEN
      RETURN;
    END IF;
    
    --Um produto não pode ser substituto de si mesmo
    IF :NEW.CODPRODSUBST = :NEW.CODPROD THEN
      RAISE_APPLICATION_ERROR(-20101, 'Um produto não pode ser substituto de si mesmo.');
    END IF;
    
    --Não existe inclusão de produto com substituto ja definido!
    IF INSERTING AND (:NEW.CODPRODSUBST IS NOT NULL) THEN
       RAISE_APPLICATION_ERROR(-20101, 'Um produto que esta sendo criado não deve possuir um substituto.');
    END IF;
    
    --Não existe inclusão de produto com data de substituicão ja definida!
    IF INSERTING AND (:NEW.DTSUBST IS NOT NULL) THEN
       RAISE_APPLICATION_ERROR(-20101, 'Um produto que esta sendo criado não deve possuir data de substituicão.');
    END IF;
        
    --Um produto que não existe não pode ser inserido como substituto de outro
    IF UPDATING('CODPRODSUBST') AND :NEW.CODPRODSUBST IS NOT NULL THEN
       SELECT COUNT(1) INTO P_COUNT
              FROM TGFPRO
              WHERE CODPROD = :NEW.CODPRODSUBST;
       IF (P_COUNT = 0) THEN
          RAISE_APPLICATION_ERROR(-20101, 'O produto que esta sendo colocado como substituto não existe.');
       END IF;
     END IF;
     
    --Se colocar um SUBSTITUTO deve colocar a DTSUBST e vice versa
    IF (:NEW.CODPRODSUBST IS NOT NULL AND :NEW.DTSUBST IS NULL) OR (:NEW.DTSUBST IS NOT NULL AND :NEW.CODPRODSUBST IS NULL) THEN
       RAISE_APPLICATION_ERROR(-20101, 'Se existe um produto Substituto e necessaria uma Data de Substituicão e vice versa.');
    END IF;
    
    --DELETE REGISTROS DA TGFPAL QUE PERDERAM A LIGACãO
    IF UPDATING AND NVL(:NEW.CODPRODSUBST, 0) <> NVL(:OLD.CODPRODSUBST, 0) THEN
       DELETE FROM TGFPAL WHERE CODPROD = :NEW.CODPROD AND CODPRODALT <> :NEW.CODPRODSUBST;
    END IF;
    
    --DELETE REGISTROS DA TGFPAL QUANDO APAGA PRODUTO SUBSTITUTO NA TGFPRO
    IF UPDATING AND :OLD.CODPRODSUBST IS NOT NULL AND :NEW.CODPRODSUBST IS NULL THEN
       DELETE FROM TGFPAL WHERE CODPROD = :NEW.CODPROD;
    END IF;
    
    --Chama a procedure para executar a substituicão recursiva
    IF NVL(:NEW.CODPRODSUBST, 0) <> 0 AND (NVL(:OLD.CODPRODSUBST, 0) <> NVL(:NEW.CODPRODSUBST, 0) OR  NVL(:OLD.DTSUBST, '01/01/1900') <> NVL(:NEW.DTSUBST, '01/01/1900')) THEN 
        STP_PRODALTERNATIVO(:NEW.CODPROD, :NEW.CODPRODSUBST, :OLD.CODPRODSUBST, :NEW.DTSUBST);
    END IF;
    
  COMMIT;
  
  RETURN;
EXCEPTION
  WHEN ERROR THEN
  /* 
  Sincronizacão de dados não faz validacões
  */
  IF (P_VALIDAR) THEN 
    RAISE_APPLICATION_ERROR(-20101, ERRMSG);
  END IF;
END;

/
