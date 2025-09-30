-- SANKHYA.TRG_INC_UPD_TGFFIN_DTNEG
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFFIN_DTNEG
"SANKHYA".TRG_INC_UPD_TGFFIN_DTNEG
BEFORE INSERT OR UPDATE ON TGFFIN
FOR EACH ROW

DECLARE
  P_VALIDAR                 BOOLEAN;
  ERRMSG                    VARCHAR2(4000);
  ERROR                      EXCEPTION;
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
  
  /*   sincronização de dados  */
  P_VALIDAR := Fpodevalidar('TGFFIN');
  
  IF NVL(:OLD.DTNEG, TO_DATE('01/01/1899', 'DD/MM/YYYY')) <> NVL(:NEW.DTNEG, TO_DATE('01/01/1899', 'DD/MM/YYYY')) AND :NEW.DTNEG <> TRUNC(:NEW.DTNEG) THEN
    RAISE_APPLICATION_ERROR(-20101, 'Data de negociação com Hora, entre em contato com Help Desk. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.');
  END IF;

  RETURN;
   
EXCEPTION

  WHEN OTHERS THEN
    /*    Sincronização de dados não faz validações    */
     IF (P_VALIDAR) THEN
       IF SQLCODE <> 1 THEN
         ERRMSG := ERRMSG || '  ' || SQLERRM;
       END IF;
       RAISE_APPLICATION_ERROR(-20101, ERRMSG);       
     END IF;
END;

/
