-- SANKHYA.TRG_INC_TGFVAR
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_TGFVAR
"SANKHYA".TRG_INC_TGFVAR
BEFORE INSERT ON TGFVAR 
FOR EACH ROW

DECLARE
    P_COUNT             INT:= 0;
    P_CODPROD_O         INT;
    P_QTDRESTANTE       NUMERIC(15,6);
    P_ACEITA            CHAR(1);
    P_NUNOTAORIG        INT;
    P_SEQUENCIAORIG     INT;
    P_NUMTRANSF     TGMTRA.NUMTRANSF%TYPE;
    P_NEWNUMTRANSF  TGMTRA.NUMTRANSF%TYPE;
    P_CODMETA       TGMTRA.CODMETA%TYPE;
    P_DTREF         TGMTRA.DTREF%TYPE;
    P_CODEMP        TGMTRA.CODEMP%TYPE;
    P_CODPROD       TGMTRA.CODPROD%TYPE;
    P_CODGRUPOPROD  TGMTRA.CODGRUPOPROD%TYPE;
    P_CODLOCAL      TGMTRA.CODLOCAL%TYPE;
    P_CONTROLE      TGMTRA.CONTROLE%TYPE;
    P_MARCA         TGMTRA.MARCA%TYPE;
    P_CODPROJ       TGMTRA.CODPROJ%TYPE;
    P_CODCENCUS     TGMTRA.CODCENCUS%TYPE;
    P_CODNAT        TGMTRA.CODNAT%TYPE;
    P_CODCTACTB     TGMTRA.CODCTACTB%TYPE;
    P_CODREG        TGMTRA.CODREG%TYPE;
    P_CODGER        TGMTRA.CODGER%TYPE;
    P_CODVEND       TGMTRA.CODVEND%TYPE;
    P_CODPARC       TGMTRA.CODPARC%TYPE;
    P_CODUF         TGMTRA.CODUF%TYPE;
    P_CODCID        TGMTRA.CODCID%TYPE;
    P_CODPAIS       TGMTRA.CODPAIS%TYPE;
    P_CODTIPPARC    TGMTRA.CODTIPPARC%TYPE;
    P_VALOR         TGMTRA.VALOR%TYPE;
    P_CODUSU        TGMTRA.CODUSU%TYPE;
    P_NUFIN         TGMTRA.NUFIN%TYPE;
    P_STATUS        TGMTRA.STATUS%TYPE;
    P_CODUSULIB     TGMTRA.CODUSULIB%TYPE;
    P_GRAU          TGMTRA.GRAU%TYPE;
    P_TIPO          TGMTRA.TIPO%TYPE;
    P_SINAL         TGMTRA.SINAL%TYPE;
    P_DTNEG         TGFCAB.DTNEG%TYPE;
    P_SEQUENCIA     TGMTRA.SEQUENCIA%TYPE;
    P_NUREM    		TGFCAB.NUREM%TYPE;
    ERRMSG            VARCHAR2(255);
    ERROR             EXCEPTION;
    P_VALIDAR BOOLEAN;    
    P_ADIARATUALIZACAOORIGEM  CHAR(1);
    P_ADIARATUALIZACAOESTOQUE  CHAR(1);
    
    CURSOR CUR_TGMTRA1 IS
        SELECT TRA.NUMTRANSF,
                TRA.CODMETA,
                TRA.DTREF,
                TRA.CODEMP,
                TRA.CODPROD, 
                TRA.CODGRUPOPROD, 
                TRA.CODLOCAL, 
                TRA.CONTROLE, 
                TRA.MARCA,
                TRA.CODPROJ, 
                TRA.CODCENCUS, 
                TRA.CODNAT, 
                TRA.CODCTACTB,
                TRA.CODREG, 
                TRA.CODGER, 
                TRA.CODVEND,
                TRA.CODPARC, 
                TRA.CODUF, 
                TRA.CODCID, 
                TRA.CODPAIS, 
                TRA.CODTIPPARC,
                ROUND(TRA.VALOR_ORIG / ITE.QTDNEG * :NEW.QTDATENDIDA,2),
                TRA.CODUSU,
                TRA.NUFIN,
                TRA.STATUS, 
                TRA.CODUSULIB, 
                TRA.GRAU
          FROM TGMTRA TRA,
                 TGFITE ITE
          WHERE TRA.NUNOTA = P_NUNOTAORIG
          AND TRA.SEQUENCIAITE = P_SEQUENCIAORIG
          AND TRA.TIPO = 'C'
          AND ITE.NUNOTA = P_NUNOTAORIG
          AND ITE.SEQUENCIA = P_SEQUENCIAORIG
          AND ITE.QTDNEG <> 0;

    CURSOR CUR_TGMTRA2 IS
        SELECT TRA.NUMTRANSF,
                TRA.CODMETA,
                SNK_GET_DTREF_META(CAB.NUNOTA,TRA.CODMETA),
                TRA.CODEMP,
                TRA.CODPROD, 
                TRA.CODGRUPOPROD, 
                TRA.CODLOCAL, 
                TRA.CONTROLE, 
                TRA.MARCA,
                TRA.CODPROJ, 
                TRA.CODCENCUS, 
                TRA.CODNAT, 
                TRA.CODCTACTB,
                TRA.CODREG, 
                TRA.CODGER, 
                TRA.CODVEND,
                TRA.CODPARC, 
                TRA.CODUF, 
                TRA.CODCID, 
                TRA.CODPAIS, 
                TRA.CODTIPPARC,
                ROUND(TRA.VALOR_ORIG / ITE.QTDNEG * :NEW.QTDATENDIDA,2), 
                TRA.CODUSU, 
                TRA.NUFIN,
                TRA.STATUS, 
                TRA.CODUSULIB, 
                TRA.GRAU,
                TRA.TIPO, 
                TRA.SINAL
          FROM TGMTRA TRA,
                 TGFITE ITE,
                 TGMTME TME,
                 TGFCAB CAB
          WHERE TRA.NUNOTA = :NEW.NUNOTAORIG
          AND TRA.SEQUENCIAITE = :NEW.SEQUENCIAORIG
          AND TRA.TIPO = 'C'
          AND TRA.CODMETA = TME.CODMETA
          AND CAB.NUNOTA = :NEW.NUNOTA
          AND CAB.CODTIPOPER = TME.CODTIPOPER
          AND ITE.NUNOTA = :NEW.NUNOTAORIG
          AND ITE.SEQUENCIA = :NEW.SEQUENCIAORIG
          AND ITE.QTDNEG <> 0;
          
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
  
    /* 
    Sincronizacao de dados
    */
    P_VALIDAR := Fpodevalidar('TGFVAR'); 
    IF NOT (P_VALIDAR) THEN
        RETURN;
    END IF;
   
    P_ADIARATUALIZACAOORIGEM := NVL(VARIAVEIS_PKG.V_ADIARATUALIZACAOORIGEM, 'N');
    P_ADIARATUALIZACAOESTOQUE := NVL(VARIAVEIS_PKG.V_ADIARATUALIZACAOESTOQUE, 'N');
     
    SELECT COUNT(1) INTO P_COUNT
    FROM TGFITE
    WHERE NUNOTA = :NEW.NUNOTA
    AND SEQUENCIA = :NEW.SEQUENCIA;
    
    IF (P_COUNT = 0)  THEN
        SELECT COUNT(1) INTO P_COUNT 
        FROM TGFCAB CAB
        WHERE CAB.NUNOTA = :NEW.NUNOTA
        AND CAB.NUREM IS NULL;
        
        IF P_COUNT>0 THEN 
            ERRMSG := 'Nao existe ou nao tem referenciado.';
            RAISE ERROR;
        END IF;
    END IF;

    SELECT COUNT(1) INTO P_COUNT
    FROM TGFITE
    WHERE NUNOTA = :NEW.NUNOTAORIG
    AND SEQUENCIA = :NEW.SEQUENCIAORIG;
    
    IF (P_COUNT = 0 ) THEN
        SELECT COUNT(1) INTO P_COUNT 
        FROM TGFCAB CAB
        WHERE CAB.NUNOTA = :NEW.NUNOTAORIG
    AND CAB.NUREM IS NULL;
    
    IF P_COUNT>0 THEN 
      ERRMSG := 'Nao existe a origem referenciada.';
      RAISE ERROR;
    END IF;
  END IF;

  IF ((:NEW.NUNOTAORIG <> :NEW.NUNOTA) AND (:NEW.QTDATENDIDA IS NOT NULL)  AND (:NEW.QTDATENDIDA <> 0)) THEN
    IF P_ADIARATUALIZACAOORIGEM <> 'S' AND P_ADIARATUALIZACAOESTOQUE <> 'S' THEN
        UPDATE TGFITE
        SET QTDENTREGUE = ROUND(QTDENTREGUE + (CASE  WHEN :NEW.FIXACAO = 'S' THEN 0 ELSE :NEW.QTDATENDIDA END),9),
        QTDFIXADA = NVL(QTDFIXADA, 0) + (CASE  WHEN :NEW.FIXACAO = 'S' THEN :NEW.QTDATENDIDA ELSE 0 END)
        WHERE (NUNOTA = :NEW.NUNOTAORIG)
        AND (SEQUENCIA = :NEW.SEQUENCIAORIG);
    END IF;

    SELECT COUNT(1)
    INTO P_COUNT
    FROM TGMTRA
    WHERE NUNOTA = :NEW.NUNOTAORIG
    AND SEQUENCIAITE = :NEW.SEQUENCIAORIG
    AND TIPO = 'C';

		IF (P_COUNT > 0) THEN
			SELECT COUNT(1)
			INTO P_COUNT
			FROM TGFCAB CAB
			, TGFCAB REQ, TGMTRA TRA
			WHERE CAB.NUNOTA = :NEW.NUNOTA
			AND REQ.NUNOTA = :NEW.NUNOTAORIG
			AND TRA.NUNOTA = REQ.NUNOTA
			AND TRA.SEQUENCIAITE = :NEW.SEQUENCIAORIG
			AND TRA.TIPO = 'C'
			AND SNK_GET_DTREF_META(CAB.NUNOTA,TRA.CODMETA) <> SNK_GET_DTREF_META(REQ.NUNOTA,TRA.CODMETA);
			
			IF (P_COUNT > 0) THEN
				P_NUNOTAORIG := :NEW.NUNOTAORIG;
				P_SEQUENCIAORIG := :NEW.SEQUENCIAORIG;
			END IF;
		ELSE
			SELECT COUNT(1), MAX(COT.NUNOTAORIG), MAX(IR.SEQUENCIA)
			INTO P_COUNT, P_NUNOTAORIG, P_SEQUENCIAORIG
			FROM TGFCAB PED, TGFCOT COT, TGFCAB REQ, TGFITE IO, TGFITE IR, TGFCAB CAB, TGMTRA TRA
			WHERE PED.NUNOTA = :NEW.NUNOTAORIG
			AND COT.NUMCOTACAO = PED.NUMCOTACAO
			AND COT.NUNOTAORIG = TRA.NUNOTA
			AND TRA.TIPO = 'C'
			AND REQ.NUNOTA = COT.NUNOTAORIG
			AND IO.NUNOTA = :NEW.NUNOTAORIG
			AND IO.SEQUENCIA = :NEW.SEQUENCIAORIG
			AND IR.NUNOTA = COT.NUNOTAORIG
			AND IR.CODPROD = IO.CODPROD
			AND CAB.NUNOTA = :NEW.NUNOTA
			AND SNK_GET_DTREF_META(CAB.NUNOTA,TRA.CODMETA) <> SNK_GET_DTREF_META(REQ.NUNOTA,TRA.CODMETA);
	END IF;
    IF (P_COUNT > 0) THEN
      OPEN CUR_TGMTRA1;
      LOOP
        FETCH CUR_TGMTRA1 INTO
        P_NUMTRANSF,
        P_CODMETA,
        P_DTREF,
        P_CODEMP,
        P_CODPROD, 
        P_CODGRUPOPROD, 
        P_CODLOCAL, 
        P_CONTROLE, 
        P_MARCA,
        P_CODPROJ, 
        P_CODCENCUS, 
        P_CODNAT, 
        P_CODCTACTB,
        P_CODREG, 
        P_CODGER, 
        P_CODVEND,
        P_CODPARC, 
        P_CODUF, 
        P_CODCID, 
        P_CODPAIS, 
        P_CODTIPPARC,
        P_VALOR,
        P_CODUSU,
        P_NUFIN,
        P_STATUS, 
        P_CODUSULIB, 
        P_GRAU;
        EXIT WHEN CUR_TGMTRA1%NOTFOUND;

        P_SEQUENCIA := SNK_GET_PROX_SEQ_TGMTRA(P_NUMTRANSF, :NEW.SEQUENCIA, 1000);
	    P_NEWNUMTRANSF := SNK_VERIFICA_PK_TGMTRA(P_NUMTRANSF, P_SEQUENCIA, :NEW.SEQUENCIA);

	    IF(P_NEWNUMTRANSF = P_NUMTRANSF) THEN
		    P_SEQUENCIA := SNK_GET_PROX_SEQ_TGMTRA(P_NUMTRANSF,:NEW.SEQUENCIA, 2000);
		    P_NEWNUMTRANSF := SNK_VERIFICA_PK_TGMTRA(P_NUMTRANSF, P_SEQUENCIA, :NEW.SEQUENCIA);
	 		
		    IF(P_NEWNUMTRANSF = P_NUMTRANSF) THEN
		   		 P_SEQUENCIA := SNK_GET_PROX_SEQ_TGMTRA(P_NUMTRANSF, :NEW.SEQUENCIA, 3000);
		    	 P_NEWNUMTRANSF := SNK_VERIFICA_PK_TGMTRA(P_NUMTRANSF, P_SEQUENCIA, :NEW.SEQUENCIA);
		    END IF;
		END IF;
	
	    IF(P_NEWNUMTRANSF <> P_NUMTRANSF) THEN
	   		STP_TROCA_NUMTRANSF(P_NUMTRANSF, P_NEWNUMTRANSF, :NEW.NUNOTAORIG);	
			P_NUMTRANSF := P_NEWNUMTRANSF;	    	      
	    END IF;
	   
        P_SEQUENCIA := SNK_GET_PROX_SEQ_TGMTRA(P_NUMTRANSF, :NEW.SEQUENCIA, 1000);
        
        INSERT INTO TGMTRA (
          NUMTRANSF,
          SEQUENCIA,
          NUNOTA, 
		  SEQUENCIAITE,
          CODMETA,
          DTREF,
          CODEMP,
          CODPROD, 
          CODGRUPOPROD, 
          CODLOCAL, 
          CONTROLE, 
          MARCA,
          CODPROJ, 
          CODCENCUS, 
          CODNAT, 
          CODCTACTB,
          CODREG, 
          CODGER, 
          CODVEND,
          CODPARC, 
          CODUF, 
          CODCID, 
          CODPAIS, 
          CODTIPPARC,
          TIPO,
          SINAL,
          VALOR, 
          VALOR_ORIG,
          CODUSU, 
          DTALTER,
          NUFIN,
          STATUS, 
          CODUSULIB, 
          GRAU)
        VALUES (
          P_NUMTRANSF,
          P_SEQUENCIA,
          :NEW.NUNOTA, 
          :NEW.SEQUENCIA,
          P_CODMETA,
          P_DTREF,
          P_CODEMP,
          P_CODPROD, 
          P_CODGRUPOPROD, 
          P_CODLOCAL, 
          P_CONTROLE, 
          P_MARCA,
          P_CODPROJ, 
          P_CODCENCUS, 
          P_CODNAT, 
          P_CODCTACTB,
          P_CODREG, 
          P_CODGER, 
          P_CODVEND,
          P_CODPARC, 
          P_CODUF, 
          P_CODCID, 
          P_CODPAIS, 
          P_CODTIPPARC,
          'M',
          -1,
          P_VALOR, 
          P_VALOR,
          P_CODUSU, 
          TRUNC(SYSDATE, 'MI'),
          P_NUFIN,
          P_STATUS, 
          P_CODUSULIB, 
          P_GRAU);

        SELECT TRUNC(DTNEG, 'MONTH')
        INTO P_DTNEG
        FROM TGFCAB
        WHERE NUNOTA = :NEW.NUNOTA;

        P_SEQUENCIA := SNK_GET_PROX_SEQ_TGMTRA(P_NUMTRANSF, :NEW.SEQUENCIA, 2000);
	    P_NEWNUMTRANSF := SNK_VERIFICA_PK_TGMTRA(P_NUMTRANSF, P_SEQUENCIA, :NEW.SEQUENCIA);

	    IF(P_NEWNUMTRANSF <> P_NUMTRANSF) THEN
	   		STP_TROCA_NUMTRANSF(P_NUMTRANSF, P_NEWNUMTRANSF, :NEW.NUNOTAORIG);	
	   		P_NUMTRANSF := P_NEWNUMTRANSF;
	    	P_SEQUENCIA := SNK_GET_PROX_SEQ_TGMTRA(P_NUMTRANSF, :NEW.SEQUENCIA, 2000);
	    END IF;
        
        INSERT INTO TGMTRA (
          NUMTRANSF,
          SEQUENCIA,
          NUNOTA, 
          SEQUENCIAITE,
          CODMETA,
          DTREF,
          CODEMP,
          CODPROD, 
          CODGRUPOPROD, 
          CODLOCAL, 
          CONTROLE,
          MARCA,
          CODPROJ, 
          CODCENCUS, 
          CODNAT, 
          CODCTACTB,
          CODREG, 
          CODGER, 
          CODVEND,
          CODPARC, 
          CODUF, 
          CODCID, 
          CODPAIS, 
          CODTIPPARC,
          TIPO,
          SINAL,
          VALOR, 
          VALOR_ORIG,
          CODUSU, 
          DTALTER,
          NUFIN,
          STATUS, 
          CODUSULIB, 
          GRAU)
        VALUES (
          P_NUMTRANSF,
          P_SEQUENCIA,
          :NEW.NUNOTA, 
          :NEW.SEQUENCIA,
          P_CODMETA,
          P_DTNEG,
          P_CODEMP,
          P_CODPROD, 
          P_CODGRUPOPROD, 
          P_CODLOCAL, 
          P_CONTROLE, 
          P_MARCA,
          P_CODPROJ, 
          P_CODCENCUS, 
          P_CODNAT, 
          P_CODCTACTB,
          P_CODREG, 
          P_CODGER, 
          P_CODVEND,
          P_CODPARC, 
          P_CODUF, 
          P_CODCID, 
          P_CODPAIS, 
          P_CODTIPPARC,
          'M',
          1,
          P_VALOR, 
          P_VALOR,
          P_CODUSU, 
          TRUNC(SYSDATE, 'MI'),
          P_NUFIN,
          P_STATUS, 
          P_CODUSULIB, 
          P_GRAU);

      END LOOP;
      CLOSE CUR_TGMTRA1;
    END IF;

    /* tem compromisso na origem e a TOP da nova inclusao estao prevista na Meta/Orcamento,
    duplicaremos o compromisso p/a nova inclusao */
    SELECT COUNT(1)
    INTO P_COUNT
    FROM TGMTRA TRA
    , TGMTME TME
    , TGFCAB CAB
    WHERE TRA.NUNOTA = :NEW.NUNOTAORIG
    AND TRA.SEQUENCIAITE = :NEW.SEQUENCIAORIG
    AND TRA.TIPO = 'C'
    AND TRA.CODMETA = TME.CODMETA
    AND CAB.NUNOTA = :NEW.NUNOTA
    AND CAB.CODTIPOPER = TME.CODTIPOPER;
    
    IF (P_COUNT > 0) THEN
      OPEN CUR_TGMTRA2;
      LOOP
        FETCH CUR_TGMTRA2 INTO
          P_NUMTRANSF,
          P_CODMETA,
          P_DTNEG,
          P_CODEMP,
          P_CODPROD, 
          P_CODGRUPOPROD, 
          P_CODLOCAL, 
          P_CONTROLE, 
          P_MARCA,
          P_CODPROJ, 
          P_CODCENCUS, 
          P_CODNAT, 
          P_CODCTACTB,
          P_CODREG, 
          P_CODGER, 
          P_CODVEND,
          P_CODPARC, 
          P_CODUF, 
          P_CODCID, 
          P_CODPAIS, 
          P_CODTIPPARC,
          P_VALOR,
          P_CODUSU,
          P_NUFIN,
          P_STATUS, 
          P_CODUSULIB, 
          P_GRAU,
          P_TIPO, 
          P_SINAL;
        EXIT WHEN CUR_TGMTRA2%NOTFOUND;

        P_SEQUENCIA := SNK_GET_PROX_SEQ_TGMTRA(P_NUMTRANSF, :NEW.SEQUENCIA, 3000);
	    P_NEWNUMTRANSF := SNK_VERIFICA_PK_TGMTRA(P_NUMTRANSF, P_SEQUENCIA, :NEW.SEQUENCIA);
	    
	    IF(P_NEWNUMTRANSF <> P_NUMTRANSF) THEN
	   		STP_TROCA_NUMTRANSF(P_NUMTRANSF, P_NEWNUMTRANSF, :NEW.NUNOTAORIG);	
	    	P_NUMTRANSF := P_NEWNUMTRANSF;
	    	P_SEQUENCIA := SNK_GET_PROX_SEQ_TGMTRA(P_NUMTRANSF, :NEW.SEQUENCIA, 3000);
	    END IF;
        
        INSERT INTO TGMTRA (
          NUMTRANSF,
          SEQUENCIA,
          NUNOTA, SEQUENCIAITE,
          CODMETA,
          DTREF,
          CODEMP,
          CODPROD, 
          CODGRUPOPROD, 
          CODLOCAL, 
          CONTROLE, 
          MARCA,
          CODPROJ, 
          CODCENCUS, 
          CODNAT, 
          CODCTACTB,
          CODREG, 
          CODGER, 
          CODVEND,
          CODPARC, 
          CODUF, 
          CODCID, 
          CODPAIS, 
          CODTIPPARC,
          TIPO,
          SINAL,
          VALOR, 
          VALOR_ORIG,
          CODUSU, 
          DTALTER,
          NUFIN,
          STATUS, 
          CODUSULIB, 
          GRAU)
        VALUES (
          P_NUMTRANSF,
          P_SEQUENCIA,
          :NEW.NUNOTA, 
          :NEW.SEQUENCIA,
          P_CODMETA,
          P_DTNEG,
          P_CODEMP,
          P_CODPROD, 
          P_CODGRUPOPROD, 
          P_CODLOCAL, 
          P_CONTROLE, 
          P_MARCA,
          P_CODPROJ, 
          P_CODCENCUS, 
          P_CODNAT, 
          P_CODCTACTB,
          P_CODREG, 
          P_CODGER, 
          P_CODVEND,
          P_CODPARC, 
          P_CODUF, 
          P_CODCID, 
          P_CODPAIS, 
          P_CODTIPPARC,
          P_TIPO,
          P_SINAL,
          P_VALOR, 
          P_VALOR,
          P_CODUSU, 
          TRUNC(SYSDATE, 'MI'),
          P_NUFIN,
          P_STATUS, 
          P_CODUSULIB, 
          P_GRAU);
      END LOOP;
      CLOSE CUR_TGMTRA2;
    END IF;
  END IF;
  RETURN;
EXCEPTION
  WHEN ERROR THEN
    /* 
    Sincronizacao de dados nao faz validacoes
    */
    IF (P_VALIDAR) THEN 
      RAISE_APPLICATION_ERROR(-20101, ERRMSG);
    END IF; 
END;

/
