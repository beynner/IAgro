-- SANKHYA.TRG_INC_UPD_TGFITE_PRODNFE
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFITE_PRODNFE
TRG_INC_UPD_TGFITE_PRODNFE
   BEFORE INSERT OR UPDATE
   ON TGFITE
   REFERENCING NEW AS NEW OLD AS OLD
   FOR EACH ROW

DECLARE
   P_EMPNFE          TGFEMP.NFE%TYPE;
   P_TOPNFE          TGFTOP.NFE%TYPE;
   P_PRODUTONFE      TGFPRO.PRODUTONFE%TYPE;
   P_REFERENCIA      TGFPRO.REFERENCIA%TYPE;
   P_TIPGTINNFE      TGFPRO.TIPGTINNFE%TYPE;
   P_TIPCONTEST      TGFPRO.TIPCONTEST%TYPE;
   P_CODBARRA        TGFEST.CODBARRA%TYPE;
   P_TIPGTINNFEVOA   TGFVOA.TIPGTINNFE%TYPE;
   P_CODBARRAVOA     TGFVOA.CODBARRA%TYPE;
   P_COUNT           NUMBER( 10 );
   ERRMSG            VARCHAR2(4000);
   ERROR EXCEPTION;
   P_VALIDAR         BOOLEAN;
   P_ORIGPROD        TGFITE.ORIGPROD%TYPE;
   P_BASENUMERACAO   CHAR( 1 );
   P_USACODVOLPARC   CHAR( 1 );
   P_CODTIPOPER      NUMBER( 10 );
   P_SERIENOTA       VARCHAR2( 3 );
   P_CODVOLPARC      VARCHAR2( 6 );
   P_CODMODDOC       NUMBER( 10 );
   P_CONTAUNTRIB     NUMBER( 5 );
   P_TOPCALCICMS TGFTOP.CALCICMS%TYPE;
   P_TIPMOV      TGFTOP.TIPMOV%TYPE;
   P_CONESTORIGPROD_EMP	NUMBER(5);
   P_CONESTORIGPROD_PRO	CHAR(1);
   P_BUSCAR_ORIG_PROD	BOOLEAN;
BEGIN

	IF NOT( STP_GET_CHECKOUT_CALC_IMPOSTO) AND STP_GET_ATUALIZANDO THEN
      RETURN;
	END IF;

   /*
   Sincronizacao de dados
   */
   P_VALIDAR := FPODEVALIDAR( 'TGFITE' );

   IF NOT ( P_VALIDAR ) THEN
      RETURN;
   END IF;
      
   /* QDO SUBSTITUINDO PRODUTO, NÃO VALIDAR ESTOQUE */
   IF (VARIAVEIS_PKG.V_SBPRODUTO) THEN
     RETURN;
   END IF;
   
   SELECT COUNT( 1 )
   INTO   P_COUNT
   FROM   TSIPAR
   WHERE  CHAVE = 'SBPRODUTO';

   IF ( P_COUNT <> 0 ) THEN
      RETURN;
   END IF;
   
   SELECT TPO.NFE, TPO.CALCICMS , TPO.TIPMOV
    INTO P_TOPNFE, P_TOPCALCICMS, P_TIPMOV
    FROM TGFTOP TPO 
    INNER JOIN TGFCAB CAB ON CAB.CODTIPOPER = TPO.CODTIPOPER AND CAB.DHTIPOPER = TPO.DHALTER 
    WHERE CAB.NUNOTA = :NEW.NUNOTA; 
    
   IF P_TOPNFE = 'E' AND P_TOPCALCICMS = 'B' THEN 
    RETURN; --NFE de Emissão Própria importada deve possuir os mesmos valores do XML, portanto, não devemos calcular nenhum campo da TGFITE. 
    END IF;
   
   IF UPDATING AND (:NEW.PENDENTE <> :OLD.PENDENTE OR :NEW.QTDENTREGUE <> :OLD.QTDENTREGUE OR :NEW.QTDCONFERIDA <> :OLD.QTDCONFERIDA) THEN 
      RETURN; 
   END IF; 

    IF UPDATING AND NVL(:OLD.STATUSNOTA, 'P') = 'L' THEN
        SELECT COUNT(1) INTO P_COUNT
        FROM TGFCAB
        WHERE NUNOTA = :OLD.NUNOTA
          AND (NVL(STATUSNFE, ' ') IN ('A','T') OR NVL(STATUSNFSE, ' ') = 'A' OR (TIPMOV IN ('C', 'D') AND P_TOPNFE = 'T'));

        IF P_COUNT > 0 THEN
	/* OS: 5886373 - Atualiza PRODUTONFE caso CODPROD seja alterado em UPDATE e movimento 'C'  */
         IF UPDATING AND P_TIPMOV = 'C' AND :OLD.CODPROD <> :NEW.CODPROD THEN 
            BEGIN
               SELECT PRODUTONFE, REFERENCIA
                 INTO P_PRODUTONFE, P_REFERENCIA
                 FROM TGFPRO
                WHERE CODPROD = :NEW.CODPROD;
               IF (P_PRODUTONFE = 1)
                  AND TRIM(P_REFERENCIA) IS NOT NULL THEN
                  :NEW.PRODUTONFE := P_REFERENCIA;
               ELSE
                  :NEW.PRODUTONFE := :NEW.CODPROD;
               END IF;
            EXCEPTION
               WHEN NO_DATA_FOUND THEN
                  :NEW.PRODUTONFE := :NEW.CODPROD;
            END;
         END IF;
            RETURN;
        END IF;
    END IF;

	P_BUSCAR_ORIG_PROD := TRUE;

    SELECT CONESTORIGPROD INTO P_CONESTORIGPROD_EMP
    FROM TGFEMP
    WHERE CODEMP = :NEW.CODEMP;

	IF P_CONESTORIGPROD_EMP IS NOT NULL THEN 
		IF P_CONESTORIGPROD_EMP = 0 THEN 
			P_BUSCAR_ORIG_PROD := FALSE;

		ELSIF P_CONESTORIGPROD_EMP = 1 THEN 
			SELECT CONESTORIGPROD INTO P_CONESTORIGPROD_PRO
			FROM TGFPRO
			WHERE CODPROD = :NEW.CODPROD;

			IF NVL(P_CONESTORIGPROD_PRO, 'N') = 'S' THEN 
				P_BUSCAR_ORIG_PROD := FALSE;
			END IF;
		END IF;
	END IF;

	IF P_BUSCAR_ORIG_PROD OR :NEW.ORIGPROD IS NULL THEN
	   /*
	   OS: 574625
	   */

		/*
		OS: 1168307
	   */
		SELECT COUNT(1) INTO P_COUNT
		FROM TSIPAR
		WHERE CHAVE = 'ORIGPRODDEV'
		AND LOGICO = 'S';

		IF (P_COUNT = 0 
			OR :NEW.ORIGPROD IS NULL
			OR (UPDATING AND :OLD.CODPROD <> :NEW.CODPROD) 
			OR (P_TIPMOV NOT IN ('D', 'E'))) THEN

			   -- OS 927107
		   :NEW.ORIGPROD := SNK_GET_ORIGEM_PRODUTO_ITE( :NEW.CODPROD
														, :NEW.CODEMP
														, :NEW.CODLOCALORIG
														, :NEW.CONTROLE );    
		END IF;
	END IF;

   SELECT PRODUTONFE, REFERENCIA, TIPGTINNFE, TIPCONTEST
   INTO   P_PRODUTONFE, P_REFERENCIA, P_TIPGTINNFE, P_TIPCONTEST
   FROM   TGFPRO
   WHERE  CODPROD = :NEW.CODPROD;

   IF ( P_PRODUTONFE = 1 ) AND TRIM( P_REFERENCIA ) IS NOT NULL THEN
      :NEW.PRODUTONFE := P_REFERENCIA;
   ELSE
      :NEW.PRODUTONFE := :NEW.CODPROD;
   END IF;


   -- ATUALIZA CAMPO CODVOLPARC, UTILIZANDO A TABELA TGFUNP
   IF VARIAVEIS_PKG.V_USACODVOLPARC = 'S' THEN
      BEGIN
         SELECT CODVOLPARC
         INTO   P_CODVOLPARC
         FROM   TGFUNP P, 
                TGFCAB C
         WHERE (P.CODPARC = C.CODPARC OR P.CODPARC = 0)
         AND C.NUNOTA = :NEW.NUNOTA 
         AND :NEW.CODVOL = P.CODVOL
         AND ROWNUM = 1
         ORDER BY P.CODPARC DESC;
      EXCEPTION
         WHEN NO_DATA_FOUND THEN
            P_CODVOLPARC := NULL;
      END;

      IF NVL( :NEW.CODVOLPARC, ' ' ) <> NVL( P_CODVOLPARC, ' ' ) THEN
         :NEW.CODVOLPARC := P_CODVOLPARC;
      END IF;
   END IF;

   IF ( P_TIPGTINNFE = 0 ) THEN
      :NEW.GTINNFE := NULL;
   ELSIF ( P_TIPGTINNFE = 1 ) THEN
      :NEW.GTINNFE := :NEW.CODPROD;
   ELSIF ( P_TIPGTINNFE = 3 ) THEN
      BEGIN
         SELECT CODBARRA
         INTO   P_CODBARRA
         FROM   TGFEST
         WHERE  CODEMP = :NEW.CODEMP
         AND    CODPROD = :NEW.CODPROD
         AND    CODLOCAL = :NEW.CODLOCALORIG
         AND    CONTROLE = :NEW.CONTROLE
         AND    CODPARC = 0;
         
         IF (NVL(LTRIM(RTRIM(P_CODBARRA)), '*') = '*' AND GET_TSIPAR_LOGICO('VALEANGTINPROD') = 'S') THEN
            RAISE_APPLICATION_ERROR(-20101, 'O EAN/GTIN Produto para NF-e está configurado como Código de Barras Estoque, porém o campo Código de Barras Estoque deste produto está vazio. Para prosseguir é necessário ajustar a configuração. ');
         ELSE
            :NEW.GTINNFE := SUBSTR( P_CODBARRA, 1, 14 );
         END IF;
      EXCEPTION
         WHEN NO_DATA_FOUND THEN
            :NEW.GTINNFE := NULL;
      END;
      
   ELSIF ( P_TIPGTINNFE = 4 ) THEN
      BEGIN
         IF ( P_TIPCONTEST = 'I' OR P_TIPCONTEST = 'S') THEN --CONTROLE LIVRE OU POR LISTA
             SELECT CODBARRA
             INTO   P_CODBARRAVOA
             FROM (
               SELECT CODBARRA
               FROM   TGFVOA
               WHERE  CODPROD = :NEW.CODPROD
               AND    CODVOL = :NEW.CODVOL
               AND    (CONTROLE = :NEW.CONTROLE OR CONTROLE = ' ')
               ORDER BY CONTROLE DESC
             )
             WHERE ROWNUM = 1; 
         ELSE
             SELECT CODBARRA
             INTO   P_CODBARRAVOA
             FROM   TGFVOA
             WHERE  CODPROD = :NEW.CODPROD
             AND    CODVOL = :NEW.CODVOL;
         END IF;
         
         IF (NVL(LTRIM(RTRIM(P_CODBARRAVOA)), '*') = '*' AND GET_TSIPAR_LOGICO('VALEANGTINPROD') = 'S') THEN
             RAISE_APPLICATION_ERROR(-20101, 'O EAN/GTIN Produto p/ NF-e está configurado como Cód. Barras da Unid. Alternativa ou a Referência, porém o campo Cód. Barras da Unid. Alternativa ou a Referência deste produto está vazio. Para prosseguir é necessário ajustar a configuração. ');
         ELSIF ( P_CODBARRAVOA IS NULL )
            OR( P_CODBARRAVOA = '' ) THEN          
         IF (NVL(LTRIM(RTRIM(P_REFERENCIA)), '*') = '*' AND GET_TSIPAR_LOGICO('VALEANGTINPROD') = 'S') THEN
             RAISE_APPLICATION_ERROR(-20101, 'O EAN/GTIN Produto p/ NF-e está configurado como Cód.Barras da Unid.Alternativa ou a Referência, porém o campo Cód.Barras da Unid.Alternativa ou a Referência deste produto está vazio. Para prosseguir é necessário ajustar a configuração. ');  
         ELSE
            :NEW.GTINNFE := SUBSTR( P_REFERENCIA, 1, 14 );
         END IF;
         ELSE
            :NEW.GTINNFE := SUBSTR( P_CODBARRAVOA, 1, 14 );
         END IF;
      EXCEPTION
         WHEN NO_DATA_FOUND THEN
         IF (NVL(LTRIM(RTRIM(P_REFERENCIA)), '*') = '*' AND GET_TSIPAR_LOGICO('VALEANGTINPROD') = 'S') THEN
             RAISE_APPLICATION_ERROR(-20101, 'O EAN/GTIN Produto p/ NF-e eEstá configurado como Cód.Barras da Unid.Alternativa ou a Referência, porém o campo Cód.Barras da Unid.Alternativa ou a Referência deste produto está vazio. Para prosseguir é necessário ajustar a configuração. ');  
         ELSE
            :NEW.GTINNFE := SUBSTR( P_REFERENCIA, 1, 14 );
         END IF;
      END;
   ELSE
      IF (NVL(LTRIM(RTRIM(P_REFERENCIA)), '*') = '*' AND GET_TSIPAR_LOGICO('VALEANGTINPROD') = 'S') THEN
          RAISE_APPLICATION_ERROR(-20101, 'O EAN/GTIN Produto p/ NF-e está configurado como Referência, porém o campo Referência deste produto está vazio. Para prosseguir é necessário ajustar a configuração. ');  
      ELSE
        :NEW.GTINNFE := SUBSTR( P_REFERENCIA, 1, 14 );
      END IF;
   END IF;

   BEGIN
      SELECT MIN(TIPGTINNFE), MIN(CODBARRA), COUNT(UNIDTRIB)
      INTO   P_TIPGTINNFEVOA, P_CODBARRAVOA, P_CONTAUNTRIB
      FROM   TGFVOA
      WHERE  CODPROD = :NEW.CODPROD
      AND    UNIDTRIB = 'S';

      IF P_CONTAUNTRIB > 1 THEN
        RAISE_APPLICATION_ERROR(-20101, 'Há mais de uma unidade alternativa marcada como unidade de tributação para o produto ' || TO_CHAR(:NEW.CODPROD));  
      END IF;

      IF (P_CONTAUNTRIB = 0) THEN
         :NEW.GTINTRIBNFE := :NEW.GTINNFE;
      ELSIF ( P_TIPGTINNFEVOA = 0 ) THEN
         :NEW.GTINTRIBNFE := NULL;
      ELSIF ( P_TIPGTINNFEVOA = 1 ) THEN
         :NEW.GTINTRIBNFE := :NEW.CODPROD;
      ELSIF ( P_TIPGTINNFEVOA = 2 ) THEN
         :NEW.GTINTRIBNFE := SUBSTR( P_REFERENCIA, 1, 14 );
      ELSE
         :NEW.GTINTRIBNFE := SUBSTR( P_CODBARRAVOA, 1, 14 );
      END IF;
   EXCEPTION
      WHEN NO_DATA_FOUND THEN
         :NEW.GTINTRIBNFE := :NEW.GTINNFE;
   END;

   RETURN;
EXCEPTION
   WHEN OTHERS THEN
      /*
      Sincroniza¿¿o de dados não faz validacões
      */
     IF (P_VALIDAR) THEN
       IF SQLCODE <> 1 THEN
         ERRMSG := ERRMSG || '  ' || SQLERRM;
       END IF;
       RAISE_APPLICATION_ERROR(-20101, ERRMSG);       
     END IF;
END;

/
