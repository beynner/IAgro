-- SANKHYA.TRG_INC_UPD_TGFVAR
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFVAR
"SANKHYA".TRG_INC_UPD_TGFVAR 
BEFORE UPDATE OR INSERT ON TGFVAR
FOR EACH ROW

DECLARE
  P_COUNT                  INT:= 0;
  P_TESTE                  INT:=0; 
  ERRMSG            VARCHAR2(255);
  ERROR             EXCEPTION;
  P_VALIDAR BOOLEAN;  
  P_CODPROD_O              INT;
  P_CODPROD                INT;
  P_TOPKITSERVICO          INT;
  P_TOPIMPUREZA            INT;
  P_TOPNOTA                INT;
  P_TIPMOV                 CHAR;
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  /* 
  Sincronização de dados
  */
    P_VALIDAR := Fpodevalidar('TGFVAR'); 
  
  IF (:NEW.NUNOTAORIG <> :NEW.NUNOTA) THEN
    SELECT TIPMOV, CODTIPOPER 
    INTO P_TIPMOV, P_TOPNOTA 
    FROM TGFCAB 
    WHERE NUNOTA = :NEW.NUNOTA;
    
    IF (P_TIPMOV = 'N') THEN  -- ENTRADAS ARMAZEM
      BEGIN
        SELECT INTEIRO INTO P_TOPIMPUREZA 
        FROM TSIPAR 
        WHERE CHAVE = 'TOPIMPUREZAE';

        IF (P_TOPIMPUREZA = 0) THEN
          ERRMSG := 'Parametro TOPIMPUREZAE nao esta configurado.';
          RAISE ERROR;
        END IF;

        IF (P_TOPNOTA = P_TOPIMPUREZA) THEN
          RETURN;  -- Nao valida os itens para nota de Impureza ( Armazens Gerais )
          -- Pois os produtos sao diferentes neste tipo de movimento.
        END IF;
      EXCEPTION WHEN NO_DATA_FOUND THEN
        ERRMSG := 'Parametro TOPIMPUREZAE n?o esta configurado.';
      END;
    END IF;
  
    IF (P_TIPMOV = '4') THEN  -- FATURAMENTO ARMAZEM
      BEGIN
        SELECT CODTIPOPER INTO P_TOPKITSERVICO 
        FROM TGFCAB 
        WHERE NUNOTA = ( SELECT INTEIRO FROM TSIPAR WHERE CHAVE = 'NOTAMODKITSERV' );
        
        IF (P_TOPKITSERVICO = 0) THEN
          ERRMSG := 'Parametro NOTAMODKITSERV n?o esta configurado.';
          RAISE ERROR;
        END IF;
      EXCEPTION WHEN NO_DATA_FOUND THEN
        ERRMSG := 'Parametro NOTAMODKITSERV n?o esta configurado.';
      END;
      
      IF (P_TOPNOTA = P_TOPKITSERVICO) THEN
        RETURN;  -- Nao valida os itens para nota de Kit de Servicos ( Armazens Gerais )
        -- Pois os produtos sao diferentes neste tipo de movimento.
      END IF;
    END IF;
      /* Garantir que sempre ser  o mesmo produto da nota e sua nota de origem */
    SELECT  CODPROD INTO P_CODPROD
    FROM  TGFITE
    WHERE NUNOTA = :NEW.NUNOTAORIG
    AND SEQUENCIA = :NEW.SEQUENCIAORIG;

    SELECT CODPROD INTO P_CODPROD_O
    FROM TGFITE
    WHERE NUNOTA = :NEW.NUNOTA
    AND SEQUENCIA = :NEW.SEQUENCIA;

		IF (P_CODPROD <> P_CODPROD_O) THEN
			SELECT COUNT(1) INTO P_COUNT
			FROM TSIPAR
			WHERE CHAVE = 'SBPRODUTO';
			
      SELECT COUNT(1) INTO P_TESTE
      FROM TSIPAR
      WHERE CHAVE = 'USABACKORDERWMS' AND LOGICO = 'S';

			IF (P_COUNT = 0) AND (P_TESTE=0) AND NOT (VARIAVEIS_PKG.V_SBPRODUTO) THEN
				SELECT COUNT(1) INTO P_COUNT
				FROM TGFPAL
				WHERE (CODPROD = P_CODPROD AND CODPRODALT = P_CODPROD_O)
				OR (CODPROD = P_CODPROD_O AND CODPRODALT = P_CODPROD);
				
				IF (P_COUNT = 0 ) THEN
					ERRMSG := 'Os produtos dos ítens da nota e sua origem são diferentes. Atualização cancelada.';
					RAISE ERROR;
				END IF;
			END IF;
		END IF;
  ELSE
    --Testar se a formula de produção esta ativa
    IF ((:NEW.NUNOTA=:NEW.NUNOTAORIG) AND (:NEW.QTDATENDIDA=0)) THEN
      SELECT COUNT(1)
      INTO P_COUNT
      FROM TGFCAB CAB
      ,TGFITE ITE
      ,TGFFCP FCP
      WHERE CAB.NUNOTA = :NEW.NUNOTAORIG
      AND CAB.NUNOTA = ITE.NUNOTA
      AND ITE.SEQUENCIA = :NEW.SEQUENCIAORIG
      AND CAB.TIPMOV = 'F'
      AND ITE.CODPROD = FCP.CODPROD
      AND (ITE.CODLOCALORIG = FCP.CODLOCAL OR FCP.CODLOCAL = 0)
      AND (ITE.CONTROLE = FCP.CONTROLE OR FCP.CONTROLE = ' ')
      AND ITE.VLRIPI = FCP.VARIACAO
      AND FCP.ATIVO = 'N';

      IF (P_COUNT<>0) THEN
        ERRMSG := 'A fórmula de produção NÃO está ativa.';
        RAISE ERROR;
      END IF;
    END IF;
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
