-- SANKHYA.TRG_DLT_TGFCAB_RASTEST
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGFCAB_RASTEST
"SANKHYA".TRG_DLT_TGFCAB_RASTEST
AFTER DELETE ON TGFCAB FOR EACH ROW

DECLARE P_COUNT   NUMBER(5);
BEGIN

  IF STP_GET_ATUALIZANDO THEN 
    RETURN;
  END IF;

  -- VERIFICANDO SE O CLIENTE UTILIZA ESTA FUNCIONALIDADE
  IF VARIAVEIS_PKG.V_UTILIZA_RASTEST = 'N' THEN
    RETURN;
  END IF;

  /* QUANDO SUBSTITUINDO PRODUTO NÃO VALIDAR RASTREAMENTO */
  IF (VARIAVEIS_PKG.V_SBPRODUTO) THEN
    RETURN;
  END IF;
  
  SELECT COUNT(1) INTO P_COUNT
  FROM TSIPAR
  WHERE CHAVE = 'SBPRODUTO';
  IF (P_COUNT <> 0) THEN
    RETURN;
  END IF; 
  
  IF :OLD.STATUSNOTA = 'L' THEN   
  
    IF :OLD.TIPMOV IN ('C', 'T', 'D', 'Q') THEN
      IF :OLD.TIPMOV = 'C' THEN
        SELECT COUNT(1) INTO P_COUNT
        FROM TGFTOP TP
        WHERE TP.CODTIPOPER = :OLD.CODTIPOPER
          AND TP.DHALTER = :OLD.DHTIPOPER
          AND COMPLEMENTO = 'S'
          AND EXISTS(SELECT 1 FROM TGFVAR WHERE NUNOTA = :OLD.NUNOTA)
          AND EXISTS(SELECT 1
                     FROM TGFITE I
                        , TGFPRO P               
                     WHERE I.NUNOTA = :OLD.NUNOTA
                       AND I.ATUALESTOQUE = 1
                       AND P.CODPROD = I.CODPROD          
                       AND P.RASTRESTOQUE <> 'N'
                       AND I.QTDNEG > 0);
      ELSE
        P_COUNT := 0;
      END IF;      
      IF P_COUNT > 0 THEN -- SE FOR COMPLEMENTAR
        UPDATE TGFITS SET QTDENT = QTDENT - (SELECT I.QTDNEG
                                              FROM TGFVAR V
                                                 , TGFITE I
                                                 , TGFPRO P
                                              WHERE I.NUNOTA = :OLD.NUNOTA
                                                AND I.ATUALESTOQUE = 1
                                                AND P.CODPROD = I.CODPROD
                                                AND P.RASTRESTOQUE <> 'N' 
                                                AND V.NUNOTA = I.NUNOTA 
                                                AND V.SEQUENCIA = I.SEQUENCIA
                                                AND TGFITS.NUNOTA = V.NUNOTAORIG 
                                                AND TGFITS.SEQUENCIA = V.SEQUENCIAORIG)
        WHERE EXISTS( SELECT 1  
                      FROM TGFVAR V
                         , TGFITE I
                         , TGFPRO P
                      WHERE I.NUNOTA = :OLD.NUNOTA
                        AND I.ATUALESTOQUE = 1
                        AND P.CODPROD = I.CODPROD
                        AND P.RASTRESTOQUE <> 'N' 
                        AND V.NUNOTA = I.NUNOTA 
                        AND V.SEQUENCIA = I.SEQUENCIA
                        AND TGFITS.NUNOTA = V.NUNOTAORIG 
                        AND TGFITS.SEQUENCIA = V.SEQUENCIAORIG);
      ELSE
      	SELECT COUNT(1) INTO P_COUNT
      	FROM TGFITS
        WHERE NUNOTA = :OLD.NUNOTA;
        IF P_COUNT > 0 THEN 
	        DELETE FROM TGFITS
	        WHERE NUNOTA = :OLD.NUNOTA;
        END IF;
      END IF;
    END IF;
    
    IF :OLD.TIPMOV IN ('T', 'V', 'E', 'Q') THEN
      SELECT COUNT(1) INTO P_COUNT
	  FROM TGFVAS
	  WHERE NUNOTA = :OLD.NUNOTA;
	  IF P_COUNT > 0 THEN
	      DELETE FROM TGFVAS
	      WHERE NUNOTA = :OLD.NUNOTA;
      END IF;
    END IF;
  END IF;
END;

/
