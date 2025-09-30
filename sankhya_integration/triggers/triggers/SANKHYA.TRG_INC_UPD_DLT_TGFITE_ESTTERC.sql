-- SANKHYA.TRG_INC_UPD_DLT_TGFITE_ESTTERC
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_DLT_TGFITE_ESTTERC
TRG_INC_UPD_DLT_TGFITE_ESTTERC 
BEFORE INSERT OR UPDATE OR DELETE ON TGFITE 
FOR EACH ROW

DECLARE
  P_CODPARC            TGFEST.CODPARC%TYPE;
  P_CODPARCDEST        TGFCAB.CODPARCDEST%TYPE;
  P_USOPROD            TGFPRO.USOPROD%TYPE;  
  P_SINAL              NUMBER(5);
  P_COUNT              NUMBER(5);
  P_TIPO               CHAR(1);
  P_TIPMOV             CHAR(1);
  ERROR                EXCEPTION;
  ERRMSG               VARCHAR2(4000);
  P_VALIDAR            BOOLEAN;
  P_DTVAL              DATE;
  P_DTFABRICACAO       DATE;
  P_CODLOCAL_NEW       NUMBER(10);
  P_CODLOCAL_OLD       NUMBER(10);
  P_CODCFOENTRADA      NUMBER(10);
  P_CODCFOENTRADA_FORA NUMBER(10);
  P_CODPARCCONSIG      NUMBER(10);
  P_TOPDENEGADA        CHAR(1);
  P_CODLOCAL_ORIGEM NUMBER(10);
  P_IGNORAVALID	       CHAR(1);
  P_VALIDAESTTERC	   CHAR(1);
	
BEGIN

  -- VERIFICANDO SE O CLIENTE UTILIZA ESTA FUNCIONALIDADE
  SELECT COUNT(*) INTO P_COUNT
  FROM TSIVARBD
  WHERE UTILIZA_ESTTERC = 'N';
  IF P_COUNT > 0 THEN 
    RETURN;
  END IF;

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  /* QDO SUBSTITUINDO PRODUTO, NÃO VALIDAR ESTOQUE */
  IF (VARIAVEIS_PKG.V_SBPRODUTO) THEN
    RETURN;
  END IF;
  
  SELECT COUNT (1) INTO P_COUNT
  FROM TSIPAR
  WHERE CHAVE = 'SBPRODUTO';

  IF (P_COUNT > 0) THEN
    RETURN;
  END IF;

/* 
 sincronização de dados
 */
  P_VALIDAR := Fpodevalidar('TGFITE');

    -- OS 1079897 Não permitir mudar o local entre a devolução e a nota de venda
   BEGIN
    SELECT TIPMOV
    INTO P_TIPMOV
    FROM TGFCAB
    WHERE NUNOTA = :NEW.NUNOTA;
   EXCEPTION
    WHEN NO_DATA_FOUND THEN
        P_TIPMOV := '';
   END;

   P_IGNORAVALID := Get_Tsipar_Logico('IGVALBXESTTERC');
   
   IF (UPDATING AND  (:NEW.TERCEIROS = 'S' AND :NEW.ATUALESTTERC <> 'N') AND (P_TIPMOV = 'D') AND (P_IGNORAVALID = 'N')) THEN
        P_CODLOCAL_ORIGEM := GET_LOCAL_ORIGEM(:NEW.NUNOTA, :NEW.SEQUENCIA);
        IF (P_CODLOCAL_ORIGEM > -1) AND  (:NEW.CODLOCALORIG <> P_CODLOCAL_ORIGEM) THEN
             ERRMSG :=  'Não é permitido alterar o Código de Local na Devolução.';
             RAISE ERROR;
        END IF;
   END IF;
    -- FIM OS 1079897 Não permitir mudar o local entre a devolução e a nota de venda

  IF (INSERTING OR UPDATING) THEN
      BEGIN 
        SELECT CASE WHEN C.STATUSNFE = 'D' THEN 'S' ELSE 'N' END
        INTO P_TOPDENEGADA
        FROM TGFCAB C
        WHERE C.NUNOTA = :NEW.NUNOTA;
      EXCEPTION WHEN NO_DATA_FOUND THEN      
        P_TOPDENEGADA := 'N'; --Não é denegada
      END;
  END IF;

  IF P_VALIDAR AND (INSERTING OR UPDATING) AND ( P_TOPDENEGADA = 'N' )THEN
    BEGIN
      SELECT C.TIPMOV, C.CODPARC
      INTO P_TIPMOV, P_CODPARC
      FROM TGFCAB C
      WHERE C.NUNOTA = :NEW.NUNOTA;
    EXCEPTION WHEN NO_DATA_FOUND THEN
      P_TIPMOV := '';
      P_CODPARC := 0;
    END;

    BEGIN
      SELECT CODPARCCONSIG
      INTO P_CODPARCCONSIG
      FROM TGFPRO
      WHERE CODPROD = :NEW.CODPROD;
    EXCEPTION WHEN NO_DATA_FOUND THEN
      P_CODPARCCONSIG := 0;
      P_USOPROD := 'S'; --Não valida
    END;

    P_USOPROD := :NEW.USOPROD;  -- OS 941793

    ERRMSG := NULL;
    IF :NEW.ATUALESTTERC = 'P' AND :NEW.ATUALESTOQUE = 1 THEN
      ERRMSG := 'Para somar o estoque com terceiros, não pode entrar estoque próprio.';
    END IF;
    IF :NEW.ATUALESTTERC = 'R' AND :NEW.ATUALESTOQUE = -1 THEN
      ERRMSG := 'Para subtrair o estoque com terceiros, não pode baixar estoque próprio.';
    END IF;
    IF :NEW.ATUALESTTERC = 'T' AND :NEW.ATUALESTOQUE = -1 AND NOT :NEW.CODCFO IN (5116, 5922, 6116, 6922) THEN
      ERRMSG := 'Para somar o estoque de terceiros, não pode baixar estoque próprio.';
    END IF;
    IF :NEW.ATUALESTTERC = 'D' AND :NEW.ATUALESTOQUE = 1 THEN
      ERRMSG := 'Para subtrair o estoque de terceiros, não pode entrar estoque próprio.';
    END IF;
    IF P_USOPROD <> 'S' THEN -- NÃO VALIDA ESTOQUE EM SERVIÇO
      IF P_CODPARCCONSIG > 0 THEN 
        IF P_TIPMOV IN ('O', 'C', 'E') AND P_CODPARCCONSIG <> P_CODPARC THEN
          ERRMSG := 'Produto consignado, o parceiro dever ser o mesmo que esta configurado no cadastro do produto.';
        END IF;
        IF P_TIPMOV IN ('O', 'C') AND (:NEW.ATUALESTTERC <> 'T' OR :NEW.ATUALESTOQUE <> 1) THEN
          IF NOT (:NEW.ATUALESTTERC = 'D' AND :NEW.ATUALESTOQUE = 0) THEN  -- Compra simbolica movimenta apenas estoque de terceiro.
            ERRMSG := 'Produto consignado, deve dar entrada no estoque proprio e de terceiros.'||CHR(13)||
                      'Ou baixar estoque de terceiro e não movimentar estoque próprio';
          END IF;
        END IF;
        IF P_TIPMOV = 'E' AND (:NEW.ATUALESTTERC <> 'D' OR :NEW.ATUALESTOQUE <> -1)  AND :NEW.CODCFO <> 0 AND :NEW.CODCFO NOT IN (5919, 6919) THEN
          ERRMSG := 'Produto consignado, deve dar saí­da no estoque próprio e de terceiros.';
        END IF;
        IF P_TIPMOV IN ('P', 'V', 'D') AND :NEW.ATUALESTTERC IN ('T','D') THEN 
          SELECT COUNT(1)INTO P_COUNT
            FROM TGFEMP E,
			   TGFCAB MO,
			   TGFCAB C 
          WHERE C.NUNOTA = :NEW.NUNOTA   
		    AND C.CODEMP = E.CODEMP 
		    AND MO.NUNOTA = E.NOTASAIAJUSTESTCONS
		    AND C.CODTIPOPER = MO.CODTIPOPER;
          IF P_COUNT = 0 THEN --Em ajustes de estoque, permitimos que uma venda altere o estoque de terceiros de produtos consignados
            ERRMSG := 'Venda não pode atualizar estoque de terceiros.'; 
          END IF;
        END IF;
        IF :NEW.ATUALESTTERC IN ('P', 'R') THEN
          ERRMSG := 'Produto consignado, não pode atualizar estoque próprio em poder de terceiros.';
        END IF;
      ELSIF P_USOPROD <> 'T' AND :NEW.CODCFO NOT IN (5116, 6116, 5922, 6922) THEN
        IF (:NEW.ATUALESTTERC IN ('T', 'D') AND :NEW.ATUALESTOQUE <> 0) THEN
          ERRMSG := 'Produto não é consignado, não pode atualizar estoque de terceiros e próprio simultâneamente.';
        END IF;
      END IF;
    END IF;
    IF ERRMSG IS NOT NULL THEN 
      RAISE ERROR;
    END IF;
  END IF;

  IF :NEW.TERCEIROS = 'S' AND :NEW.ATUALESTTERC <> 'N' AND
     (NVL(:NEW.CODLOCALTERC,0) = 0 OR
      (UPDATING AND (NVL(:OLD.CODEMP,0) <> NVL(:NEW.CODEMP,0) OR 
                    NVL(:NEW.CODLOCALORIG,0) <> NVL(:OLD.CODLOCALORIG, 0)))) THEN

      SELECT CASE WHEN NVL(CODLOCALTERC,0) = 0 THEN :NEW.CODLOCALORIG ELSE CODLOCALTERC END 
      INTO P_CODLOCAL_NEW      FROM TGFEMP
      WHERE CODEMP = :NEW.CODEMP;

    :NEW.CODLOCALTERC := P_CODLOCAL_NEW;          
  ELSE
    P_CODLOCAL_NEW := :NEW.CODLOCALTERC;
  END IF;

    P_CODLOCAL_OLD := NVL(:OLD.CODLOCALTERC,:OLD.CODLOCALORIG);    


   /* Pega deleção e update*/
     
  IF NOT INSERTING AND :OLD.TERCEIROS = 'S' AND :OLD.ATUALESTTERC <> 'N' THEN
    IF DELETING OR (:OLD.ATUALESTTERC <> :NEW.ATUALESTTERC) OR 
                    (:OLD.QTDNEG <> :NEW.QTDNEG) OR 
                    (:OLD.TERCEIROS <> :NEW.TERCEIROS) OR 
                    (P_CODLOCAL_OLD <> P_CODLOCAL_NEW) OR 
                    (:OLD.CONTROLE <> :NEW.CONTROLE) OR 
                    (:OLD.CODPROD <> :NEW.CODPROD) OR 
                    (:OLD.CODEMP <> :NEW.CODEMP) THEN
      BEGIN         
        SELECT C.CODPARC, NVL(C.CODPARCDEST,0), NVL(T.CODCFO_ENTRADA,0), NVL(T.CODCFO_ENTRADA_FORA,0) 
          INTO P_CODPARC, P_CODPARCDEST       , P_CODCFOENTRADA        , P_CODCFOENTRADA_FORA 
        FROM TGFCAB C
           , TGFTOP T
        WHERE C.NUNOTA = :OLD.NUNOTA
          AND C.CODTIPOPER = T.CODTIPOPER
          AND C.DHTIPOPER = T.DHALTER;          
      EXCEPTION WHEN NO_DATA_FOUND THEN 
        SELECT C.CODPARC, NVL(C.CODPARCDEST,0), NVL(T.CODCFO_ENTRADA,0), NVL(T.CODCFO_ENTRADA_FORA,0)
          INTO P_CODPARC, P_CODPARCDEST       , P_CODCFOENTRADA        , P_CODCFOENTRADA_FORA
        FROM TGFCAB_DLT C        
           , TGFTOP T
        WHERE C.NUNOTA = :OLD.NUNOTA
          AND C.CODTIPOPER = T.CODTIPOPER
          AND C.DHTIPOPER = T.DHALTER;          
      END;

      IF ((P_CODCFOENTRADA IN (1122,2122,1924,2924) OR 
          P_CODCFOENTRADA_FORA IN (1122,2122,1924,2924)) AND
      (:OLD.ATUALESTTERC IN ('P', 'T'))) THEN
       P_CODPARC := P_CODPARCDEST;
      END IF;

      IF(P_CODPARC =0) THEN
        ERRMSG := 'Parceiro 0 é inválido para controle de estoque com terceiros.';
        RAISE ERROR;
      END IF;

      IF (:OLD.ATUALESTTERC IN ('P', 'T')) THEN
        P_SINAL := CASE WHEN :OLD.SEQUENCIA > 0 THEN   1 ELSE -1 END;
      ELSE
        P_SINAL := CASE WHEN :OLD.SEQUENCIA > 0 THEN  -1 ELSE  1 END;
      END IF;

      IF (:OLD.ATUALESTTERC IN ('P', 'R')) THEN
        P_TIPO := 'P';
      ELSE
        P_TIPO := 'T';
      END IF;

      SELECT COUNT(1)
      INTO P_COUNT
      FROM TGFEST
      WHERE CODEMP = :OLD.CODEMP
      AND CODLOCAL = P_CODLOCAL_OLD
      AND CODPROD = :OLD.CODPROD
      AND CONTROLE = :OLD.CONTROLE
      AND CODPARC = P_CODPARC
      AND TIPO = P_TIPO;

      IF(P_COUNT = 0) OR (P_COUNT IS NULL) THEN
          SELECT MIN(DTVAL), MIN(DTFABRICACAO) 
          INTO P_DTVAL, P_DTFABRICACAO 
        FROM TGFEST 
        WHERE CODPARC = 0 
          AND CODPROD = :OLD.CODPROD 
          AND CONTROLE = :OLD.CONTROLE;
        INSERT INTO TGFEST(CODEMP, CODLOCAL, CODPROD, CONTROLE, ESTOQUE, RESERVADO, CODPARC, TIPO, DTVAL, DTFABRICACAO, STATUSLOTE)
        VALUES (:OLD.CODEMP, P_CODLOCAL_OLD, :OLD.CODPROD, :OLD.CONTROLE, :OLD.QTDNEG * P_SINAL, 0, P_CODPARC, P_TIPO, P_DTVAL, P_DTFABRICACAO, :OLD.STATUSLOTE);
      ELSE
        UPDATE TGFEST SET
          ESTOQUE = ESTOQUE - (:OLD.QTDNEG * P_SINAL)
        WHERE CODEMP = :OLD.CODEMP
        AND CODLOCAL = P_CODLOCAL_OLD
        AND CODPROD = :OLD.CODPROD
        AND CONTROLE = :OLD.CONTROLE
        AND CODPARC = P_CODPARC
        AND TIPO = P_TIPO;
      END IF;
    END IF;
  END IF;

   /* Pega inserção ou update*/
  IF NOT DELETING AND :NEW.TERCEIROS = 'S' AND :NEW.ATUALESTTERC <> 'N' THEN
    IF INSERTING OR 
       (:OLD.ATUALESTTERC <> :NEW.ATUALESTTERC) OR 
       (:OLD.QTDNEG <> :NEW.QTDNEG) OR 
       (:OLD.TERCEIROS <> :NEW.TERCEIROS) OR 
       (P_CODLOCAL_OLD <> P_CODLOCAL_NEW) OR 
       (:OLD.CONTROLE <> :NEW.CONTROLE) OR 
       (:OLD.CODPROD <> :NEW.CODPROD) OR 
       (:OLD.CODEMP <> :NEW.CODEMP) THEN

      SELECT C.CODPARC, NVL(C.CODPARCDEST,0), NVL(T.CODCFO_ENTRADA,0), NVL(T.CODCFO_ENTRADA_FORA,0) 
        INTO P_CODPARC, P_CODPARCDEST       , P_CODCFOENTRADA        , P_CODCFOENTRADA_FORA 
      FROM TGFCAB C
         , TGFTOP T
      WHERE C.NUNOTA = :NEW.NUNOTA
        AND C.CODTIPOPER = T.CODTIPOPER
        AND C.DHTIPOPER = T.DHALTER;

      IF ((P_CODCFOENTRADA IN (1122,2122,1924,2924) OR 
           (P_CODCFOENTRADA_FORA IN (1122,2122,1924,2924)) AND
         (:NEW.ATUALESTTERC IN ('P', 'T')))) THEN
          P_CODPARC := P_CODPARCDEST;
      END IF;          

      IF(P_CODPARC = 0) THEN
        ERRMSG := 'Parceiro 0 é inválido para controle de estoque com terceiros.';
        RAISE ERROR;
      END IF;

      IF (:NEW.ATUALESTTERC IN ('P', 'T')) THEN
        P_SINAL := CASE WHEN :NEW.SEQUENCIA > 0 THEN   1 ELSE -1 END;
      ELSE
        P_SINAL := CASE WHEN :NEW.SEQUENCIA>0 THEN  -1 ELSE  1 END;
      END IF;

      IF (:NEW.ATUALESTTERC IN ('P', 'R')) THEN
        P_TIPO := 'P';
      ELSE
        P_TIPO := 'T';
      END IF;

      SELECT COUNT(1)
      INTO P_COUNT
      FROM TGFEST
      WHERE CODEMP = :NEW.CODEMP
      AND CODLOCAL = P_CODLOCAL_NEW
      AND CODPROD = :NEW.CODPROD
      AND CONTROLE = :NEW.CONTROLE
      AND CODPARC = P_CODPARC
      AND TIPO = P_TIPO;
      IF (P_COUNT = 0) OR (P_COUNT IS NULL) THEN
          SELECT MIN(DTVAL), MIN(DTFABRICACAO) 
          INTO P_DTVAL, P_DTFABRICACAO
        FROM TGFEST
        WHERE CODPARC = 0 
          AND CODPROD = :NEW.CODPROD 
          AND CONTROLE = :NEW.CONTROLE;
          
        P_VALIDAESTTERC := Get_Tsipar_Logico('VALESTINCESTTER');  
		IF ((P_VALIDAESTTERC = 'S') AND (:NEW.QTDNEG * P_SINAL) < 0) AND (P_CODPARC <> 0) THEN 
			 ERRMSG := 'Estoque com/de Terceiros não pode ficar negativo. Produto: ' || TO_CHAR(:NEW.CODPROD);
			 RAISE ERROR;
		END IF;
		
        INSERT INTO TGFEST(CODEMP, CODLOCAL, CODPROD, CONTROLE, ESTOQUE, RESERVADO, CODPARC, TIPO, DTVAL, DTFABRICACAO, STATUSLOTE)
        VALUES (:NEW.CODEMP, P_CODLOCAL_NEW, :NEW.CODPROD, :NEW.CONTROLE, :NEW.QTDNEG * P_SINAL, 0, P_CODPARC, P_TIPO, P_DTVAL, P_DTFABRICACAO, :NEW.STATUSLOTE);
      ELSE 
        UPDATE TGFEST SET
        ESTOQUE = ESTOQUE + (:NEW.QTDNEG * P_SINAL)
        WHERE CODEMP = :NEW.CODEMP
        AND CODLOCAL =  P_CODLOCAL_NEW
        AND CODPROD = :NEW.CODPROD
        AND CONTROLE = :NEW.CONTROLE
        AND CODPARC = P_CODPARC
        AND TIPO = P_TIPO;

        /*
         Apaga a linha da tgfest se ficar linha com estoque zero, 
         Foi comentado porque ao apgar essa linha, não sei porque a aplicação muda o tipo do campo atualestterc e terceiro para não, dessa forma não funciona mais.
        SELECT COUNT(1) 
        INTO 
        P_COUNT
        FROM TGFEST
        WHERE CODEMP = :NEW.CODEMP
        AND CODLOCAL = P_CODLOCAL_NEW
        AND CODPROD = :NEW.CODPROD
        AND CONTROLE = :NEW.CONTROLE
        AND CODPARC = P_CODPARC
        AND ESTOQUE = 0 
        AND RESERVADO = 0
        AND ESTMIN = 0 
        AND ESTMAX = 0 
        AND TRIM(CODBARRA) IS NULL
        AND DTVAL IS NULL
        AND TIPO = P_TIPO;
        IF (P_COUNT>0) THEN 
          DELETE FROM TGFEST
          WHERE CODEMP = :NEW.CODEMP
          AND CODLOCAL = P_CODLOCAL_NEW
          AND CODPROD = :NEW.CODPROD
          AND CONTROLE = :NEW.CONTROLE
          AND CODPARC = P_CODPARC
          AND TIPO = P_TIPO;
        END IF;
        */
      END IF;
    END IF;
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
        RAISE_APPLICATION_ERROR(-20101, NVL(ERRMSG, SQLERRM));       
     END IF;
END;

/
