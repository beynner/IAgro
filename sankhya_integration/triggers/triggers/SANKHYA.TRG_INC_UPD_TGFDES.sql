-- SANKHYA.TRG_INC_UPD_TGFDES
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFDES
"SANKHYA".TRG_INC_UPD_TGFDES 
BEFORE INSERT OR UPDATE ON TGFDES
FOR EACH ROW

DECLARE
   P_COUNT          INT:= 0;
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
  
   IF (TRIM(:NEW.GRUPODESCPARC) IS NULL) AND (:NEW.CODPARC = 0) THEN
      RAISE_APPLICATION_ERROR (-20101, 'Grupo de desconto de parceiros ou código do parceiro deve ser informado');
   END IF;
   IF (TRIM(:NEW.GRUPODESCPARC) IS NOT NULL) AND (:NEW.GRUPODESCPARC <> '***************') AND (:NEW.CODPARC <> 0) THEN
      RAISE_APPLICATION_ERROR (-20101, 'Quando grupo de desconto de parceiros for informado, código do parceiro deve ser = 0');
   END IF;
   IF (TRIM(:NEW.GRUPODESCVEND) IS NOT NULL) AND (:NEW.GRUPODESCVEND <> '***************') AND (:NEW.CODVEND <> 0) THEN
      RAISE_APPLICATION_ERROR (-20101, 'Quando grupo de desconto de vendedor for informado, código do vendedor deve ser = 0');
   END IF;
 
   IF (TRIM(:NEW.GRUPODESCPARC) IS NOT NULL) THEN
     IF (:NEW.GRUPODESCPARC <> '***************') THEN
        SELECT COUNT(1) INTO P_COUNT FROM TGFCPL T WHERE T.GRUPODESCPARC = :NEW.GRUPODESCPARC;
        IF (P_COUNT = 0) THEN
           RAISE_APPLICATION_ERROR (-20101,'Grupo de desconto de parceiro não existe');
        END IF;
     END IF;		
   ELSE 
        SELECT COUNT(1) INTO P_COUNT FROM TGFPAR P WHERE P.CODPARC = :NEW.CODPARC;
        IF (P_COUNT = 0) THEN
           RAISE_APPLICATION_ERROR (-20101,'Código do parceiro não existe ');
        END IF;
   END IF;

   IF (TRIM(:NEW.GRUPODESCPROD) IS NULL) AND (:NEW.CODPROD = 0) THEN
      RAISE_APPLICATION_ERROR (-20101, 'Grupo de desconto de produto ou código do produto deve ser informado');
   END IF;

   IF (TRIM(:NEW.GRUPODESCPROD) IS NOT NULL) AND (:NEW.GRUPODESCPROD <> '***************') AND (:NEW.CODPROD <> 0) THEN
      RAISE_APPLICATION_ERROR (-20101, 'Quando grupo de desconto de produto for informado o código do produto deve ser = 0');
   END IF;

   IF (TRIM(:NEW.GRUPODESCPROD) IS NOT NULL ) THEN
     IF (:NEW.GRUPODESCPROD <> '***************') THEN
	      SELECT COUNT(1) INTO P_COUNT FROM TGFPRO P WHERE P.GRUPODESCPROD = :NEW.GRUPODESCPROD;
	      IF (P_COUNT = 0) THEN
	         RAISE_APPLICATION_ERROR (-20101,'Grupo de desconto de produto não existe');
	      END IF;
	 END IF;
   ELSE
      SELECT COUNT(1) INTO P_COUNT FROM TGFPRO P WHERE P.CODPROD = :NEW.CODPROD;
      IF (P_COUNT = 0) THEN
        RAISE_APPLICATION_ERROR (-20101,'Código do produto não existe');
      END IF;
   END IF;
   
   IF (:NEW.CODEMP <> 0) THEN
     SELECT COUNT(1) INTO P_COUNT FROM TGFEMP E WHERE E.CODEMP = :NEW.CODEMP;
     IF (P_COUNT = 0) THEN
         RAISE_APPLICATION_ERROR (-20101,'Código da empresa não existe');
     END IF;
   END IF;

   IF (TRIM(:NEW.GRUPODESCVEND) IS NOT NULL) AND (:NEW.GRUPODESCVEND <> '***************') AND (:NEW.CODVEND <> 0) THEN
      RAISE_APPLICATION_ERROR (-20101, 'Quando grupo de desconto de vendedor for informado o código do vendedor deve ser = 0');
   END IF;

   IF (TRIM(:NEW.GRUPODESCVEND) IS NOT NULL ) THEN
     IF (:NEW.GRUPODESCVEND <> '***************') THEN
	      SELECT COUNT(1) INTO P_COUNT FROM TGFVEN V WHERE V.GRUPODESCVEND = :NEW.GRUPODESCVEND;
	      IF (P_COUNT = 0) THEN
	         RAISE_APPLICATION_ERROR (-20101,'Grupo de desconto de vendedor não existe');
	      END IF;
	 END IF;
   ELSE
      SELECT COUNT(1) INTO P_COUNT FROM TGFVEN V WHERE V.CODVEND = :NEW.CODVEND;
      IF (P_COUNT = 0) THEN
        RAISE_APPLICATION_ERROR (-20101,'Código do vendedor não existe');
      END IF;
   END IF;
END;

/
