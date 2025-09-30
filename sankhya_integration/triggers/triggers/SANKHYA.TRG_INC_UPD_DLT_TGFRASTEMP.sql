-- SANKHYA.TRG_INC_UPD_DLT_TGFRASTEMP
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_DLT_TGFRASTEMP
"SANKHYA".TRG_INC_UPD_DLT_TGFRASTEMP
   BEFORE INSERT OR UPDATE OR DELETE
   ON TGFRASTEMP
   FOR EACH ROW

DECLARE
   P_COUNT     INT := 0;
   P_VALIDAR   BOOLEAN;
   ERRMSG      VARCHAR2 (255);
   P_CODEMP    NUMBER(10);
   ERROR EXCEPTION;
BEGIN
   IF STP_GET_ATUALIZANDO
   THEN
      RETURN;
   END IF;
   /*
   sincronização de dados
   */
   P_VALIDAR := Fpodevalidar ('TGFRASTEMP');
   IF (INSERTING OR UPDATING) AND NVL(:NEW.TIPORASTR, '*') <> NVL(:OLD.TIPORASTR, '*') AND (NOT RASTRESTOQUE_PKG.V_LIB_EXEC) AND :NEW.TIPORASTR <> null THEN 
		SELECT COUNT (1) INTO P_COUNT
        FROM TGFITE
      	WHERE CODPROD = :NEW.CODPROD
      	  AND ROWNUM = 1;
  		IF P_COUNT > 0 THEN
  			RAISE_APPLICATION_ERROR (
            -20101,
               'Existe movimentações de estoque para o produto: '
            || :NEW.CODPROD
            || CHR (13)
            || '. A ativação do rastreamento de estoque, deve ser feito pela tela de "Rastreamento de Estoques" ou "Rastrear ST pela Última compra".');
  		END IF;
   ELSIF NVL(:OLD.TIPORASTR, '*') <> '*'  AND (NOT RASTRESTOQUE_PKG.V_LIB_EXEC) THEN --TEM RASTREAMENTO ATIVO
   		SELECT COUNT (1) INTO P_COUNT
        FROM TGFITE
      	WHERE CODPROD = :OLD.CODPROD
      	  AND ROWNUM = 1;
      	IF P_COUNT > 0 THEN
   			RAISE_APPLICATION_ERROR (
            -20101,
               'O produto "'
            || :NEW.CODPROD
            || '" Está configurado para rastrear estoque.');
         END IF;
   END IF;
END;

/
