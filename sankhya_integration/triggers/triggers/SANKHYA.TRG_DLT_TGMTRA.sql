-- SANKHYA.TRG_DLT_TGMTRA
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGMTRA
"SANKHYA".TRG_DLT_TGMTRA 
BEFORE DELETE ON TGMTRA 
FOR EACH ROW

DECLARE
	P_COUNT INTEGER;
   PRAGMA Autonomous_Transaction; --Por causa da tgfvar que desfaz as linhas anteriores e recria. 
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
	SELECT COUNT(*)
	INTO P_COUNT
	FROM TGFFIN FIN
	WHERE FIN.NUNOTA = :OLD.NUNOTA
	AND FIN.DHBAIXA IS NOT NULL;
	
	IF (P_COUNT > 0) THEN
	   RAISE_APPLICATION_ERROR(-20101, 'Financeiro baixado, Liberações do Pedido/Nota não podem ser eliminadas.');
	END IF;
  
	SELECT COUNT(*)
	INTO P_COUNT
	FROM TGFVAR	
	WHERE NUNOTAORIG = :OLD.NUNOTA;
	
	IF (P_COUNT > 0) THEN
	   RAISE_APPLICATION_ERROR(-20101, 'Pedido ou Nota já foram faturados/devolvidos, não podem ter a liberação apagada.');
	END IF;
	
	RETURN;
END;

/
