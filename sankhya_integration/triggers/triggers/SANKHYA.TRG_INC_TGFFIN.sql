-- SANKHYA.TRG_INC_TGFFIN
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_TGFFIN
TRG_INC_TGFFIN
BEFORE INSERT ON TGFFIN FOR EACH ROW

DECLARE
    P_COUNT          INT:= 0;
    P_VLRBAIXAZERO   VARCHAR2(1);
    P_VLRJURO        FLOAT;
    P_VLRMULTA       FLOAT;
    P_VLRISS         FLOAT;
    P_VLRIRF         FLOAT;
    P_VLRINSS        FLOAT;
    P_OUTROSIMPOSTOS FLOAT;
    P_ORIGEM         VARCHAR2(1);
    ERRMSG           VARCHAR2(4000);
    ERROR            EXCEPTION;
    P_VALIDAR        BOOLEAN;
    P_ATIVO          CHAR(1);
    P_TPAGNFCE       VARCHAR(2);    
	P_DESCRTPAGNFCE	 VARCHAR2(60);
    P_APELIDO        TGFVEN.APELIDO%TYPE;       
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  IF Tgffin_Pkg.V_BAIXAPARCIAL = 'S' THEN /* PARA NÃO FAZER VALIDAÇÕES QUANDO BAIXANDO PARCIAL */
    RETURN;
  END IF;
  /* 
  sincronização de dados
  */  
  P_VALIDAR := Fpodevalidar('TGFFIN');
  
  IF :NEW.ORIGEM <> 'E' AND NVL(:NEW.NUNOTA, 0) <> 0 THEN
    ERRMSG := 'Só é permitido preencher o NUNOTA para financeiros com origem igual a ''E''. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
    RAISE ERROR;
  END IF; 
  
  IF :NEW.CODCTABCOINT IS NOT NULL THEN
     SELECT COUNT(1) INTO  P_COUNT
     FROM TSICTA
     WHERE CODCTABCOINT = :NEW.CODCTABCOINT
     AND ATIVA = 'S';
     IF  (P_COUNT = 0) THEN
     ERRMSG := 'Conta bancária ' || TO_CHAR(:NEW.CODCTABCOINT) || ' não está ativa. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
     RAISE ERROR;
     END IF;
  END IF;

  IF :NEW.NUDEV IS NULL AND :NEW.NURENEG IS NULL THEN -- DEVOLUÇÃO DE CHEQUES não deve validar se está ativo.

    SELECT COUNT(1) INTO  P_COUNT
    FROM TCSCON
    WHERE NUMCONTRATO = :NEW.NUMCONTRATO
    AND ATIVO = 'S';
    IF  (P_COUNT = 0) THEN
     ERRMSG := 'Contrato' || :NEW.NUMCONTRATO || 'não esta ativo. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
     RAISE ERROR;
    END IF;
  
    IF :NEW.CODPROJ IS NOT NULL THEN
       SELECT COUNT(1) INTO  P_COUNT
       FROM TCSPRJ
       WHERE CODPROJ = :NEW.CODPROJ
       AND ATIVO = 'S'
       AND ANALITICO = 'S';
       IF  (P_COUNT = 0) THEN
            ERRMSG := 'Projeto '||:NEW.CODPROJ||' não esta ativo, não e analítico ou não existe.';
            RAISE_APPLICATION_ERROR (-20101, ERRMSG);
       END IF;
    END IF;
  
    SELECT COUNT(1) INTO  P_COUNT
    FROM TGFEMP
    WHERE CODEMP = :NEW.CODEMP
    AND ATIVO = 'S';
    IF  (P_COUNT = 0) THEN
     ERRMSG := 'Empresa '|| TO_CHAR(:NEW.CODEMP) ||' não está ativa. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
     RAISE ERROR;
    END IF;
  
    IF (:NEW.CODEMPBAIXA IS NOT NULL) AND (:NEW.CODEMP <> :NEW.CODEMPBAIXA) THEN
      SELECT COUNT(1) INTO  P_COUNT
      FROM TGFEMP
      WHERE CODEMP = :NEW.CODEMPBAIXA
      AND ATIVO = 'S';
      IF   (P_COUNT = 0) THEN
     ERRMSG := 'Empresa '|| TO_CHAR(:NEW.CODEMPBAIXA) ||' da baixa não está ativa. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
     RAISE ERROR;
      END IF;
    END IF;
  
    IF :NEW.CODVEICULO IS NOT NULL THEN
       Stp_Valida_Veiculo(:NEW.CODVEICULO);
    END IF;
  
    SELECT COUNT(1) INTO  P_COUNT
    FROM TGFPAR
    WHERE CODPARC = :NEW.CODPARC
    AND ATIVO = 'S';
    IF  (P_COUNT = 0) THEN
     ERRMSG := 'Parceiro: '|| :NEW.CODPARC ||' não esta ativo. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
     RAISE ERROR;
    END IF;
  
    SELECT COUNT(1) INTO P_COUNT
    FROM TSICUS
    WHERE CODCENCUS = :NEW.CODCENCUS
      AND ATIVO = 'S'
      AND ANALITICO = 'S';
    IF  (P_COUNT = 0) THEN
            ERRMSG := 'Centro de Resultado '||:NEW.CODCENCUS||' não está ativa ou não é analítico. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
            RAISE ERROR;
    END IF;
  
	SELECT COUNT(1) INTO P_COUNT
	  FROM TGFVEN
	 WHERE CODVEND = :NEW.CODVEND
	   AND ATIVO = 'S';
	IF (P_COUNT = 0) THEN
	  SELECT COUNT(1) INTO P_COUNT
	    FROM TGFVEN
	   WHERE CODVEND = :NEW.CODVEND;
			IF (P_COUNT = 0) THEN
				ERRMSG := 'Vendedor: '|| :NEW.CODVEND || ' não existe, Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
			ELSE
				SELECT APELIDO INTO P_APELIDO FROM TGFVEN WHERE CODVEND = :NEW.CODVEND;
				ERRMSG := 'Vendedor: '|| :NEW.CODVEND || ' - ' || P_APELIDO || ' não esta ativo, Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
			END IF;
		RAISE ERROR;
	END IF;

  END IF;

  SELECT COUNT(1) INTO  P_COUNT
  FROM TGFNAT
  WHERE CODNAT = :NEW.CODNAT
  AND ATIVA = 'S'
  AND ANALITICA = 'S';
  IF (P_COUNT = 0) THEN
        ERRMSG := 'Natureza '||:NEW.CODNAT||' não está ativa ou não é analítico. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
        RAISE ERROR;
  END IF;

  SELECT COUNT(1) INTO  P_COUNT
  FROM TGFTOP
  WHERE CODTIPOPER = :NEW.CODTIPOPER
  AND DHALTER = :NEW.DHTIPOPER
  AND ATIVO = 'S';
  IF   (P_COUNT = 0) THEN
    ERRMSG := 'Tipo de Operação ' || :NEW.CODTIPOPER || ' não está ativa. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
  RAISE ERROR;
  END IF;

  IF :NEW.CODTIPOPERBAIXA IS NOT NULL THEN
     SELECT COUNT(1) INTO  P_COUNT
     FROM TGFTOP
     WHERE CODTIPOPER = :NEW.CODTIPOPERBAIXA
     AND  DHALTER = :NEW.DHTIPOPERBAIXA
     AND ATIVO = 'S';
     IF  (P_COUNT = 0) THEN
      ERRMSG := 'Tipo de Operação de baixa '|| TO_CHAR(:NEW.CODTIPOPERBAIXA) ||' não está ativo. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
    RAISE ERROR;
     END IF;
  END IF;

    IF (:NEW.CODTIPTIT IS NOT NULL) THEN
    BEGIN
     SELECT ATIVO, TPAGNFCE, DESCRTPAGNFCE
       INTO P_ATIVO, P_TPAGNFCE, P_DESCRTPAGNFCE
     FROM TGFTIT
     WHERE CODTIPTIT = :NEW.CODTIPTIT;
     IF  (P_ATIVO <> 'S') THEN
      ERRMSG := 'Tipo de Título '|| TO_CHAR(:NEW.CODTIPTIT) ||' não está ativo. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
      RAISE ERROR;
     END IF;
     :NEW.TPAGNFCE := P_TPAGNFCE;
	 :NEW.DESCRTPAGNFCE := P_DESCRTPAGNFCE;
     EXCEPTION
     WHEN NO_DATA_FOUND THEN
      BEGIN
        ERRMSG := 'Tipo de Título '|| TO_CHAR(:NEW.CODTIPTIT) ||' não existe. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
        RAISE ERROR;
      END;
    END;
  END IF;

  IF :NEW.DHBAIXA IS NOT NULL THEN
    :NEW.DHBAIXA := TRUNC(:NEW.DHBAIXA);
  END IF;
  
  /* testa se o ano digitadOo é válido */
  SELECT NVL(INTEIRO,0) INTO P_COUNT
    FROM TSIPAR
    WHERE CHAVE = 'LIMSUPANO';

  IF P_COUNT > 100 THEN
    P_COUNT := 100;
  END IF; 

  IF (P_COUNT <> 0)  
              AND ( ( ( :NEW.DTVENC <> NULL )
              AND ( :NEW.DTVENC > ADD_MONTHS(SYSDATE, 12 * P_COUNT) ) ) )
              OR  ( :NEW.DTNEG > ADD_MONTHS(SYSDATE, 12 * P_COUNT) )
              OR  ( :NEW.DHMOV > ADD_MONTHS(SYSDATE, 12 * P_COUNT) )
              OR  ( ( :NEW.DHBAIXA <> NULL )
              AND ( :NEW.DHBAIXA > ADD_MONTHS(SYSDATE, 12 * P_COUNT) ) 
        ) THEN
        ERRMSG := 'Ano superior ao limite permitido, veja o parâmetro de Limite Superior para Ano . Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
        RAISE ERROR;
  END IF;

  SELECT NVL(INTEIRO,0) INTO P_COUNT
  FROM TSIPAR
  WHERE CHAVE = 'LIMINFANO';
  
  IF P_COUNT > 100 THEN
    P_COUNT := 100;
  END IF; 
  
  IF ( P_COUNT <> 0 )
              AND ( ( ( :NEW.DTVENC <> NULL )
              AND ( :NEW.DTVENC < ADD_MONTHS(SYSDATE, 12 * -P_COUNT) ) ) )
              OR  ( :NEW.DTNEG < ADD_MONTHS(SYSDATE, 12 * -P_COUNT) )
              OR  ( :NEW.DHMOV < ADD_MONTHS(SYSDATE, 12 * -P_COUNT) )
              OR  ( ( :NEW.DHBAIXA <> NULL )
              AND ( :NEW.DHBAIXA < ADD_MONTHS(SYSDATE, 12 * -P_COUNT) ) 
      ) THEN
      ERRMSG := 'Ano inferior ao limite permitido, veja o parâmetro de Limite Inferior para Ano. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
      RAISE ERROR;
  END IF;

  /* O NUBCO deve existir na TGFMbc, não é feito via chave estrangeira porque a deleção é cascade  */
  IF (:NEW.NUBCO IS NOT NULL) THEN
    SELECT COUNT(1) INTO P_COUNT
    FROM TGFMBC
    WHERE NUBCO = :NEW.NUBCO;
    IF (P_COUNT = 0) THEN
        ERRMSG := 'Número Único do banco não estácadastrado na tabela TGFMbc. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
        RAISE ERROR;
    END IF;
  END IF;

/*
 mudando veio da cab, estou colocando o delete cascade pela fk, para o implementacao da
 Uni funcionar.
*/
  /* O NUNOTA deve existir na Cab, não é feito via chave estrangeira porque a deleção é cascade
IF (:NEW.NUNOTA IS NOT NULL) THEN
    SELECT NVL(COUNT(1),0) INTO P_COUNT
    FROM TGFCAB
    WHERE NUNOTA = :NEW.NUNOTA;
    IF (P_COUNT = 0 ) THEN
        ERRMSG := 'Número da Nota não cadastrado na tabela de notas.';
        RAISE ERROR;
    END IF;
  END IF;
*/

 IF (:NEW.TIPJURO = '1') THEN
    P_VLRJURO := NVL(:NEW.VLRJURO,0);
  ELSE P_VLRJURO := 0;
  END IF;
  IF (:NEW.TIPMULTA = '1') THEN
    P_VLRMULTA := NVL(:NEW.VLRMULTA,0);
  ELSE P_VLRMULTA := 0;
  END IF;
  IF (:NEW.ISSRETIDO = 'S') THEN
    P_VLRISS := NVL(:NEW.VLRISS,0);
  ELSE P_VLRISS := 0;
  END IF;
  IF (:NEW.IRFRETIDO = 'S') THEN
    P_VLRIRF := NVL(:NEW.VLRIRF,0);
  ELSE P_VLRIRF := 0;
  END IF;
  IF (:NEW.INSSRETIDO = 'S') THEN
    P_VLRINSS := NVL(:NEW.VLRINSS,0);
  ELSE P_VLRINSS := 0;
  END IF;
  BEGIN
    SELECT NVL(SUM(VALOR * TIPIMP),0) INTO P_OUTROSIMPOSTOS
    FROM TGFIMF
    WHERE NUFIN = :NEW.NUFIN;
  EXCEPTION
    WHEN NO_DATA_FOUND THEN P_OUTROSIMPOSTOS := 0;
  END;

 IF (:NEW.DHBAIXA IS NOT NULL) AND
    (:NEW.PROVISAO = 'N') AND
    ((  :NEW.VLRDESDOB 
      + :NEW.VLRVENDOR 
      + :NEW.DESPCART 
      + NVL(:NEW.VLRVARCAMBIAL, 0) 
      - :NEW.VLRDESC 
      - P_VLRIRF 
      - P_VLRINSS 
      - :NEW.CARTAODESC 
      + P_VLRJURO 
      + P_VLRMULTA 
      - P_VLRISS 
      + P_OUTROSIMPOSTOS 
      + NVL(:NEW.VLRMULTANEGOC,0) 
      + NVL(:NEW.VLRJURONEGOC,0) 
      - NVL(:NEW.VLRMULTALIB,0) 
      - NVL(:NEW.VLRJUROLIB,0)) <> :NEW.VLRBAIXA) THEN
      ERRMSG := 'Valor da baixa diferente de (VLRDESDOB + VLRVENDOR + VLRJURO + VLRMULTA + DESPCART + VLRVARCAMBIAL - VLRDESC - VLRISS - VLRIRRF - VLRINSS - CARTAODESC + OUTROS IMPOSTOS+ VLRMULTANEGOC + VLRJURONEGOC - VLRMULTALIB - VLRJUROLIB. Financeiro de Nro Único: ' || TO_CHAR(:NEW.NUFIN, '99999999');
      RAISE ERROR;
 END IF;

  /* OU TUDO 0 OU NADA 0 */
  IF (:NEW.NUDEV IS NULL) AND (:NEW.PROVISAO <> 'S') AND
     (((:NEW.CODTIPOPERBAIXA = 0) AND (:NEW.VLRBAIXA <> 0) ) OR
      ((:NEW.CODTIPOPERBAIXA <> 0) AND (:NEW.VLRBAIXA = 0))) THEN
    SELECT COUNT(1), MIN(LOGICO) INTO P_COUNT, P_VLRBAIXAZERO FROM TSIPAR WHERE CHAVE = 'VLRBAIXAZERO';
    IF ((P_COUNT = 0) OR (P_VLRBAIXAZERO <> 'S')) THEN
        ERRMSG := 'Informe o valor da baixa e Código de operação de baixa simultaneamente ou deixe os dois campos em branco ou iguais a zero. Ou seja: quando um dos dois campos for preenchido o outra também deve ser. Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
        RAISE ERROR;
    END IF;
  END IF;
  
  IF :NEW.DHBAIXA IS NOT NULL AND :NEW.NUCCR IS NOT NULL THEN
    ERRMSG := 'Título de autorização de venda de cartão de crédito não pode ser baixado! Financeiro de Nro Único: '|| TO_CHAR(:NEW.NUFIN) ||'.';
    RAISE ERROR;
  END IF;
  
  RETURN;
   
EXCEPTION
  WHEN OTHERS THEN
    /* 
    Sincronização de dados não faz validações
    */
     IF (P_VALIDAR) THEN
       IF SQLCODE <> 1 THEN
         ERRMSG := ERRMSG || '  ' || SQLERRM;
       END IF;
       RAISE_APPLICATION_ERROR(-20101, ERRMSG);       
     END IF;
END;

/
