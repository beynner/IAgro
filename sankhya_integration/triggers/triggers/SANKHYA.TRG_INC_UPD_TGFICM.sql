-- SANKHYA.TRG_INC_UPD_TGFICM
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFICM
"SANKHYA".TRG_INC_UPD_TGFICM 
BEFORE INSERT OR UPDATE ON TGFICM
FOR EACH ROW

DECLARE
  ERRMSG        VARCHAR2(255);
  ERROR         EXCEPTION;
  P_VALIDAR     BOOLEAN;
BEGIN
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  /* sincronização de dados */
  P_VALIDAR := Fpodevalidar('TGFICM');
  
  IF (:OLD.STCAT137SP IS NULL AND :NEW.STCAT137SP <> 'N') THEN
    ERRMSG := 'O banco de dados já está na versão que desativou o campo ''Calcular ST p/ Medicamentos - CAT-SP'', você não pode usar versões anteriores para marcar esse campo.';
    RAISE ERROR;      
  END IF; 
 
  IF (:OLD.STCAT137SP IS NOT NULL AND (:OLD.STCAT137SP <> :NEW.STCAT137SP)) THEN
    ERRMSG := 'O banco de dados já está na versão que desativou o campo ''Calcular ST p/ Medicamentos - CAT-SP'', você não pode usar versões anteriores para alterar a marcação desse campo.';
    RAISE ERROR;      
  END IF; 
 
  IF (:OLD.CALCSTDIFALIQ IS NULL AND :NEW.CALCSTDIFALIQ <> 'N') THEN
    ERRMSG := 'O banco de dados já está na versão que desativou o campo ''Calcular ST para Diferencial de Alíquota (por dentro)'', você não pode usar versões anteriores para marcar esse campo.';
    RAISE ERROR;      
  END IF; 
 
  IF (:OLD.CALCSTDIFALIQ IS NOT NULL AND (:OLD.CALCSTDIFALIQ <> :NEW.CALCSTDIFALIQ)) THEN
    ERRMSG := 'O banco de dados já está na versão que desativou o campo ''Calcular ST para Diferencial de Alíquota (por dentro)'', você não pode usar versões anteriores para alterar a marcação desse campo.';
    RAISE ERROR;      
  END IF; 
  
  IF ((:OLD.UFORIG IS NULL) AND (:NEW.CALCSTSEMDEDICMS IS NULL)) THEN
    :NEW.CALCSTSEMDEDICMS := 'N';
  END IF;
			
  IF ((:OLD.UFORIG IS NULL) AND (:NEW.CALCSTSEMDEDICMS <> 'N')) THEN
    ERRMSG := 'O banco de dados já está na versão que desativou o campo ''Calcular ST sem dedução do ICMS Próprio'', você não pode usar versões anteriores para marcar esse campo.';
	RAISE ERROR;
  END IF;
				
  IF ((:OLD.UFORIG IS NOT NULL) AND (NVL(:NEW.CALCSTSEMDEDICMS,'N') <> NVL(:OLD.CALCSTSEMDEDICMS,'N'))) THEN
    ERRMSG := 'O banco de dados já está na versão que desativou o campo ''Calcular ST sem dedução do ICMS Próprio'', você não pode usar versões anteriores para alterar a marcação desse campo.';
    RAISE ERROR;
  END IF;
 
  RETURN;

EXCEPTION
  WHEN ERROR THEN
    IF (P_VALIDAR) THEN
      RAISE_APPLICATION_ERROR(-20101, ERRMSG);
    END IF;

END;

/
