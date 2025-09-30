-- SANKHYA.TRG_INC_UPD_TGFCAB_CERTIFIC
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFCAB_CERTIFIC
"SANKHYA".TRG_INC_UPD_TGFCAB_CERTIFIC BEFORE INSERT OR UPDATE ON TGFCAB FOR EACH ROW

DECLARE
  P_OQUE           VARCHAR2(60);
  P_QUEM           VARCHAR2(60);
  P_COM            VARCHAR2(60);
  P_ERRO           VARCHAR2(4);
  P_TIPO           TGFCER.TIPO%TYPE;
  P_SEQUENCIA      TGFCER.SEQUENCIA%TYPE;
  P_CHAVE          TGFCER.CHAVE%TYPE;
  P_CODREGRA       TGFREG.CODREGRA%TYPE;
  P_INSTPRINC      TGFREG.INSTPRINC%TYPE;
  P_INSTSEC        TGFREG.INSTSEC%TYPE;
  P_DESCRREGRA     TGFREG.DESCRREGRA%TYPE;
  P_TIPOREGRA      TGFREG.TIPO%TYPE;
  P_CODINSTPRINC   NUMBER(10,0);
  P_CODINSTSEC     NUMBER(10,0);
  P_COUNT          NUMBER(10,0);
  P_CODLOCAL       TGFLOC.CODLOCAL%TYPE;
  P_CODPROD        TGFPRO.CODPROD%TYPE;
  ERRMSG           VARCHAR2(255);
  ERROR            EXCEPTION;
  P_VALIDAR        BOOLEAN;

  CURSOR  curRegras IS
   (SELECT CER.TIPO, CER.CHAVE, CER.CODREGRA, CER.SEQUENCIA, REG.INSTPRINC, REG.INSTSEC, REG.TIPO, REG.DESCRREGRA, 0 AS CODPROD, 0 AS CODLOCAL
    FROM TGFCER CER
       , TGFREG REG
    WHERE ((CER.TIPO = 'U' AND CER.CHAVE = :NEW.CODUSU) OR
           (CER.TIPO = 'F' AND CER.CHAVE = :NEW.CODFUNC) OR
           (CER.TIPO = 'V' AND CER.CHAVE = :NEW.CODVEND) OR
           (CER.TIPO = 'E' AND CER.CHAVE = :NEW.CODEMP) OR
           (CER.TIPO = 'G'))
    AND CER.ATIVO = 'S'
    AND CER.CODREGRA = REG.CODREGRA
    AND REG.INSTPRINC NOT IN ('Local', 'Conta Bancaria', 'Conta Bancária', 'Produto', 'Grupo de Produto', 'Departamento', 'Tipo de Título p/ FastService')
    AND (REG.INSTSEC IS NULL OR REG.INSTSEC NOT IN ('Local', 'Conta Bancaria', 'Conta Bancária', 'Produto', 'Grupo de Produto', 'Departamento'))
  UNION
    SELECT CER.TIPO, CER.CHAVE, CER.CODREGRA, CER.SEQUENCIA, REG.INSTPRINC, REG.INSTSEC, REG.TIPO, REG.DESCRREGRA, ITE.CODPROD, ITE.CODLOCALORIG
    FROM TGFCER CER
       , TGFREG REG
     , TGFITE ITE 
    WHERE ITE.NUNOTA = :NEW.NUNOTA
    AND ((CER.TIPO = 'U' AND CER.CHAVE = :NEW.CODUSU) OR
           (CER.TIPO = 'V' AND CER.CHAVE = ITE.CODVEND) OR
           (CER.TIPO = 'V' AND CER.CHAVE = NVL(ITE.CODEXEC,0)) OR           
           (CER.TIPO = 'G'))
    AND CER.ATIVO = 'S'
    AND CER.CODREGRA = REG.CODREGRA
    AND ((REG.INSTPRINC IN ('Local', 'Produto', 'Grupo de Produto') AND REG.INSTSEC IS NOT NULL) OR 
       REG.INSTSEC IN ('Local', 'Produto', 'Grupo de Produto')) 
    AND REG.INSTPRINC NOT IN ('Conta Bancaria', 'Conta Bancária', 'Departamento', 'Tipo de Título p/ FastService')
    AND (REG.INSTSEC IS NULL OR REG.INSTSEC NOT IN ('Conta Bancaria', 'Conta Bancária', 'Departamento')))
    ORDER BY SEQUENCIA;
BEGIN

  -- VERIFICANDO SE O CLIENTE UTILIZA ESTA FUNCIONALIDADE
  SELECT COUNT(*) INTO P_COUNT
  FROM TSIVARBD
  WHERE UTILIZA_CERTIFIC = 'N';
  IF P_COUNT > 0 THEN 
    RETURN;
  END IF;

  IF Stp_Get_Atualizando THEN
    RETURN;
  END IF;

  /* 
  Sincronizacão de dados
  */
  P_VALIDAR := Fpodevalidar('TGFCAB');
  IF INSERTING OR
     :OLD.CODUSU      <> :NEW.CODUSU      OR
     :OLD.CODEMP      <> :NEW.CODEMP      OR
     :OLD.CODVEND     <> :NEW.CODVEND     OR
     :OLD.CODFUNC     <> :NEW.CODFUNC     OR
     :OLD.CODCENCUS   <> :NEW.CODCENCUS   OR
     :OLD.CODNAT      <> :NEW.CODNAT      OR
     :OLD.CODPROJ     <> :NEW.CODPROJ     OR
     :OLD.CODTIPOPER  <> :NEW.CODTIPOPER  OR
     :OLD.CODTIPVENDA <> :NEW.CODTIPVENDA OR
     :OLD.CODPARC     <> :NEW.CODPARC THEN
    OPEN curRegras;
    LOOP
      FETCH curRegras INTO
         P_TIPO, P_CHAVE, P_CODREGRA, P_SEQUENCIA, P_INSTPRINC, P_INSTSEC, P_TIPOREGRA, P_DESCRREGRA, P_CODPROD, P_CODLOCAL;
      EXIT WHEN curRegras%NOTFOUND;

/*     IF P_INSTPRINC IN ('Centro de Resultado', 'Natureza', 'Projeto') THEN
        IF P_RATEIO is null THEN
            SELECT COUNT(*)
            INTO P_RATEIO
            FROM TGFRAT
            WHERE ORIGEM = 'E'
            AND NUFIN = :NEW.NUNOTA;
        END IF;
        IF P_RATEIO > 0 THEN
          close curRegras;
          RAISE_APPLICATION_ERROR(-20101, 'Nota rateada, regra "' || P_DESCRREGRA || '" não pode ser validada.');
        END IF;
      END IF;
*/
      IF P_INSTPRINC = 'Centro de Resultado' THEN
        P_CODINSTPRINC := :NEW.CODCENCUS;
      ELSIF P_INSTPRINC = 'Natureza' THEN
        P_CODINSTPRINC := :NEW.CODNAT;
      ELSIF P_INSTPRINC = 'Projeto' THEN
        P_CODINSTPRINC := :NEW.CODPROJ;
      ELSIF P_INSTPRINC = 'TOP' THEN
        P_CODINSTPRINC := :NEW.CODTIPOPER;
      ELSIF P_INSTPRINC = 'Local' THEN
        P_CODINSTPRINC := P_CODLOCAL;
      ELSIF P_INSTPRINC = 'Produto' THEN
        P_CODINSTPRINC := P_CODPROD;
      ELSIF P_INSTPRINC = 'Grupo de Produto' THEN
        SELECT CODGRUPOPROD INTO P_CODINSTPRINC 
        FROM TGFPRO 
        WHERE CODPROD = P_CODPROD;
      ELSIF P_INSTPRINC = 'Tipo de Negociação' THEN
        P_CODINSTPRINC := :NEW.CODTIPVENDA;
      ELSIF P_INSTPRINC = 'Parceiro' THEN
        P_CODINSTPRINC := :NEW.CODPARC;
      ELSIF P_INSTPRINC = 'Empresa' THEN
        P_CODINSTPRINC := :NEW.CODEMP;
      ELSE
        CLOSE curRegras;
      ERRMSG := 'Instrução principal "'|| P_INSTPRINC ||'" da regra "' || P_DESCRREGRA || '" não definida.';
      RAISE ERROR;
      END IF;

      IF P_INSTSEC = 'Centro de Resultado' THEN
        P_CODINSTSEC := :NEW.CODCENCUS;
      ELSIF P_INSTSEC = 'Natureza' THEN
        P_CODINSTSEC := :NEW.CODNAT;
      ELSIF P_INSTSEC = 'Projeto' THEN
        P_CODINSTSEC := :NEW.CODPROJ;
      ELSIF P_INSTSEC = 'TOP' THEN
        P_CODINSTSEC := :NEW.CODTIPOPER;
      ELSIF P_INSTSEC = 'Local' THEN
        P_CODINSTSEC := P_CODLOCAL;
      ELSIF P_INSTSEC = 'Produto' THEN
        P_CODINSTSEC := P_CODPROD;
      ELSIF P_INSTSEC = 'Grupo de Produto' THEN
        SELECT CODGRUPOPROD INTO P_CODINSTSEC 
    FROM TGFPRO 
    WHERE CODPROD = P_CODPROD;
      ELSIF P_INSTSEC = 'Tipo de Negociação' THEN
        P_CODINSTSEC := :NEW.CODTIPVENDA;
      ELSIF P_INSTSEC = 'Parceiro' THEN
        P_CODINSTSEC := :NEW.CODPARC;
      ELSIF P_INSTSEC = 'Empresa' THEN
        P_CODINSTSEC := :NEW.CODEMP;
      ELSIF P_INSTSEC IS NOT NULL AND P_INSTSEC <> '' THEN
        CLOSE curRegras;
      ERRMSG := 'Instrução secundária "'|| P_INSTSEC ||'" da regra "' || P_DESCRREGRA || '" não definida.';
      RAISE ERROR;
      ELSE
        P_CODINSTSEC := 0;
      END IF;

      IF TRIM(P_INSTSEC) IS NULL THEN -- Apenas uma dimensão
        SELECT COUNT(*)
        INTO P_COUNT
        FROM TGFITR ITR
        WHERE ITR.CODREGRA = P_CODREGRA
          AND ITR.CODINSTPRINC <= P_CODINSTPRINC
          AND NVL(ITR.CODINSTPRINCFIN, ITR.CODINSTPRINC) >= P_CODINSTPRINC
          AND ITR.ATIVO = 'S';
      ELSE
        SELECT COUNT(*)
        INTO P_COUNT
        FROM TGFITR ITR
        WHERE ITR.CODREGRA = P_CODREGRA
          AND ITR.CODINSTPRINC <= P_CODINSTPRINC
          AND NVL(ITR.CODINSTPRINCFIN, ITR.CODINSTPRINC) >= P_CODINSTPRINC
          AND ITR.CODINSTSECINI <= P_CODINSTSEC  
          AND ITR.CODINSTSECFIN >= P_CODINSTSEC  
          AND ITR.ATIVO = 'S';
      END IF;
      P_ERRO := '';
      IF P_TIPOREGRA = 'R' THEN
        IF P_COUNT > 0 THEN
          P_ERRO := 'ERRO';
        END IF;
      ELSE
        IF P_COUNT = 0 THEN
          P_ERRO := 'ERRO';
        END IF;
      END IF;
      IF P_ERRO = 'ERRO' THEN
        CLOSE curRegras;
        Stp_Msg_Certific_Tipo(P_TIPO, P_CHAVE, P_QUEM);
        Stp_Msg_Certific_Codinst(P_INSTPRINC, P_CODINSTPRINC, P_OQUE);
        IF TRIM(P_OQUE) IS NULL OR TRIM(P_OQUE) = '0' THEN
        ERRMSG := 'Existe uma regra de certificação para o código '|| P_CODINSTPRINC ||' , mas não existe nenhum '|| P_INSTPRINC ||' com este código.';
        RAISE ERROR;
        END IF;
        IF TRIM(P_INSTSEC) IS NULL THEN
        ERRMSG := P_QUEM ||' não pode usar "'|| P_OQUE ||'" da regra "'||P_DESCRREGRA||'"\'||P_SEQUENCIA||'.';
        RAISE ERROR;
        ELSE
          Stp_Msg_Certific_Codinst(P_INSTSEC, P_CODINSTSEC, P_COM);
        ERRMSG := P_QUEM ||' não pode usar "'|| P_OQUE ||'" com "'|| P_COM ||'" da regra "'||P_DESCRREGRA||'"\'||P_SEQUENCIA||'.';
        RAISE ERROR;
        END IF;   
      END IF;
    END LOOP;
    CLOSE curRegras;
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
