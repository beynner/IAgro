-- SANKHYA.TRG_DLT_TGFCAB_LIB41
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGFCAB_LIB41
"SANKHYA".TRG_DLT_TGFCAB_LIB41 BEFORE DELETE ON TGFCAB FOR EACH ROW

DECLARE 
  P_COUNT INT; 
  ERRMSG            VARCHAR2(255);
  ERROR             EXCEPTION;
  P_VALIDAR BOOLEAN;
BEGIN 

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

    /* 
    Sincronização de dados
    */
    P_VALIDAR := FPODEVALIDAR('TGFCAB');
    SELECT COUNT(*) 
    INTO P_COUNT 
    FROM TSILIB 
    WHERE EVENTO = 41 
    AND TABELA = 'TGFCAB' 
    AND (DHLIB IS NOT NULL OR REPROVADO = 'S') 
    AND NUCHAVE = :OLD.NUNOTA; 
    IF P_COUNT > 0 THEN 
      ERRMSG := 'Pedido/Nota com Liberação por Análise dos Itens não pode ser Excluída. Nota de Nro único: '|| TO_CHAR(:NEW.NUNOTA) ||'.';
    RAISE ERROR;
    END IF;
  
    RETURN;
     
EXCEPTION
  WHEN ERROR THEN
    /* 
    Sincronização de dados não faz validações
    */
    IF (P_VALIDAR) THEN 
      RAISE_APPLICATION_ERROR(-20101, ERRMSG);
    END IF; 
   
END;

/
