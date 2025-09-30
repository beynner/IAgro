-- SANKHYA.TRG_INC_TCBLAN
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_TCBLAN
TRG_INC_TCBLAN BEFORE INSERT ON TCBLAN FOR EACH ROW

DECLARE
  P_COUNT              INT;
  P_ACEITARHISTZERO    TCBEMP.ACEITARHISTZERO%TYPE;
  P_PROJOBRIG          TCBPLA.PROJOBRIG%TYPE;
  P_CENCUSOBRIG        TCBPLA.CENCUSOBRIG%TYPE;
  P_VALCTA             CHAR(1);
  P_UTILCENCUS         CHAR(1);
  ERRMSG  VARCHAR2(255);  
BEGIN
  BEGIN
  
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
  
    SELECT LOGICO INTO P_VALCTA
    FROM TSIPAR 
    WHERE CHAVE = 'VALCTA';
  EXCEPTION WHEN NO_DATA_FOUND THEN
    P_VALCTA := 'N';
  END;
  
IF :NEW.VLRLANC <= 0 THEN
	RAISE_APPLICATION_ERROR(-20101,'Valor contabilizado não pode ser menor que 0,01. Lançamento: '||:NEW.NUMLANC|| ', Núm. Documento: '||NVL(:NEW.NUMDOC, 0)||'.'); 
END IF;
  
  IF (Tcblan_Pkg.V_PROCRET = 1) THEN 
    RETURN;
  END IF;

  SELECT COUNT(1) INTO P_COUNT 
  FROM TSIPAR 
  WHERE CHAVE = 'CONSOLIDANDOEMP' 
  AND INTEIRO = :NEW.CODEMP;

  IF (P_COUNT=0) THEN
    IF :NEW.CODHISTCTB = 0 THEN
      SELECT ACEITARHISTZERO INTO P_ACEITARHISTZERO
      FROM TCBEMP E
      WHERE E.CODEMP = :NEW.CODEMP;
      IF P_ACEITARHISTZERO = 'N' THEN
         RAISE_APPLICATION_ERROR (-20101, 'Histórico não pode ser zero.');
      END IF;
    END IF;

    IF (P_VALCTA = 'S') then 
        if (NVL(:NEW.CODCTACTB, 0) <> 0) THEN
           SELECT COUNT(1) INTO P_COUNT
           FROM TCBPLA P, TCBEMP E
           WHERE P.CODCTACTB = :NEW.CODCTACTB
           AND E.CODEMP = :NEW.CODEMP
           AND E.CODEMPPLACTA = P.CODEMP
           AND P.ATIVA = 'S'
           AND P.ANALITICA = 'S';
           IF (P_COUNT = 0 ) THEN
              RAISE_APPLICATION_ERROR (-20101, 'Código Contábil não valido, ou não ativo, ou não analítico. Conta: ' || :NEW.CODCTACTB || ' Empresa: ' || :NEW.CODEMP);
           END IF;
        end if;

        IF (:NEW.CODCONPAR IS NOT NULL AND :NEW.CODCONPAR <> 0) THEN
           SELECT COUNT(1) INTO P_COUNT FROM TCBPLA P, TCBEMP E
           WHERE P.CODCTACTB = :NEW.CODCONPAR
           AND E.CODEMP = :NEW.CODEMP
           AND E.CODEMPPLACTA = P.CODEMP
           AND P.ATIVA = 'S'
           AND P.ANALITICA = 'S';
           IF (P_COUNT = 0 ) THEN
             RAISE_APPLICATION_ERROR (-20101, 'Conta de Contra-Partida '||:NEW.CODCONPAR||' não Ativa ou não Cadastrada.');
           END IF;
        END IF;
            
        SELECT PROJOBRIG, CENCUSOBRIG 
        INTO P_PROJOBRIG, P_CENCUSOBRIG
        FROM TCBPLA P
        WHERE P.CODCTACTB = :NEW.CODCTACTB;
    ELSE
        P_PROJOBRIG := 'N'; 
        P_CENCUSOBRIG := 'N'; 
    
    END IF;

    IF (:NEW.CODCENCUS <> 0) THEN
       SELECT COUNT(1) INTO P_COUNT FROM  TSICUS C
       WHERE :NEW.CODCENCUS = C.CODCENCUS
       AND C.ATIVO = 'S'
       AND C.ANALITICO = 'S';
       IF (P_COUNT = 0 ) THEN
         ERRMSG := 'Centro de resultado '||:NEW.CODCENCUS||' não esta ativo, não é ANALíTICO ou não EXISTE.';
         RAISE_APPLICATION_ERROR (-20101, ERRMSG);
       END IF;
    END IF;
    
    

    IF (:NEW.CODCENCUS = 0) AND (P_CENCUSOBRIG = 'S') THEN
      
      SELECT UTILCENCUS
        INTO P_UTILCENCUS
      FROM TCBEMP
      WHERE CODEMP = :NEW.CODEMP;
      IF P_UTILCENCUS = 'S' THEN   
        RAISE_APPLICATION_ERROR (-20101, 'C.R.deve ser informado. Conta que exige o CR: '||:NEW.CODCTACTB);
      END IF;
    END IF;

    IF :NEW.CODPROJ IS NULL THEN
      :NEW.CODPROJ := 0;
    END IF;
    IF (:NEW.CODPROJ = 0) AND (P_PROJOBRIG = 'S') THEN
      RAISE_APPLICATION_ERROR (-20101, 'Projeto deve ser informado. Conta que exige o Projeto: '||:NEW.CODCTACTB);
    END IF;
  
    IF (:NEW.CODPROJ <> 0) THEN
       SELECT COUNT(1) INTO P_COUNT FROM TCSPRJ C
       WHERE :NEW.CODPROJ = C.CODPROJ
       AND C.ATIVO = 'S'
       AND C.ANALITICO = 'S';
       IF (P_COUNT = 0 ) THEN
         ERRMSG := 'Projeto '||:NEW.CODPROJ||' não esta ativo, não e ANALíTICO ou não existe.';
         RAISE_APPLICATION_ERROR (-20101, ERRMSG);
       END IF;
    END IF;

    IF (:NEW.LIBERADO = 'S') THEN
      Stp_Atualiza_Saldo_Inc (:NEW.CODEMP   , :NEW.REFERENCIA,
                              :NEW.TIPLANC  , :NEW.CODCTACTB,
                              :NEW.CODCENCUS, :NEW.CODPROJ,  
                              :NEW.VLRLANC  , :NEW.VLRLANC);
    END IF;

    IF (:NEW.LIBERADO = 'S') AND (:NEW.CODEMPORIG <> 0) AND (GET_TSIPAR_LOGICO('CTBUTISALEMPORG') = 'S') THEN 
          STP_ATUALIZA_SALDO_POR_EMP_INC (:NEW.CODEMPORIG, :NEW.REFERENCIA,
                                  :NEW.TIPLANC  , :NEW.CODCTACTB,
                                  :NEW.CODCENCUS, :NEW.CODPROJ,
                                  :NEW.VLRLANC  , :NEW.VLRLANC);
    END IF;
  END IF;
END;

/
