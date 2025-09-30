-- SANKHYA.TRG_INC_TGFTAB
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_TGFTAB
"SANKHYA".TRG_INC_TGFTAB 
BEFORE INSERT ON TGFTAB 
FOR EACH ROW

DECLARE
    ERROR                    EXCEPTION;
    ERRMSG                   VARCHAR2(255);
    P_COUNT                  INT;
    P_CODIGO                 TGFTAB.NUTAB%TYPE;
    P_ATIVO                  CHAR(1);
    P_VALIDAR                BOOLEAN;
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
  
  /* 
   Sincronização de dados
  */
  P_VALIDAR := Fpodevalidar('TGFTAB');
  IF NOT (P_VALIDAR) OR (NVL(:NEW.NUTAB,0)<>0) THEN 
    RETURN;
  END IF;

  DELETE FROM TGFTAB_INC;

  IF (:NEW.CODTAB = 0) THEN
      IF (:OLD.FORMULA IS NOT NULL) THEN
          ERRMSG := 'Tabela padrão não pode ter fórmula.';
          RAISE ERROR;
      END IF;
      IF (:NEW.PERCENTUAL <> 0) THEN
          ERRMSG := 'Tabela padrão não pode ter percentual.';
          RAISE ERROR;
      END IF;
      IF (:NEW.CODTABORIG IS NOT NULL) AND (:NEW.CODTABORIG <> 0) THEN
          ERRMSG := 'Tabela padrão não pode ter tabela de origem.';
          RAISE ERROR;
      END IF;
  ELSE
      IF (:NEW.CODTABORIG IS NULL) AND (:NEW.FORMULA IS NULL) THEN
          ERRMSG := 'A coluna FÓRMULA ou a coluna TABELA ORIGEM deve conter informaçãoo.';
          RAISE ERROR;
      END IF;
      IF UPDATING('FORMULA') AND UPDATING('CODTABORIG') AND (:NEW.FORMULA IS NOT NULL) AND (:NEW.CODTABORIG IS NOT NULL) THEN
        ERRMSG := 'A coluna FÓRMULA e a coluna TABELA ORIGEM não podem conter informações simultâneamente.';
        RAISE ERROR;
      END IF;
  END IF;
  IF (:NEW.CODREG IS NOT NULL) THEN
    SELECT COUNT(1) INTO P_COUNT
    FROM TSIREG
    WHERE CODREG = :NEW.CODREG AND ATIVA = 'S' AND ANALITICA = 'S';
    IF (P_COUNT = 0) THEN
        ERRMSG := 'Região não está ativa. ';
        RAISE ERROR;
    END IF;
  END IF;
  BEGIN
    SELECT ATIVO INTO P_ATIVO
    FROM TGFNTA
    WHERE CODTAB = :NEW.CODTAB;
  EXCEPTION WHEN NO_DATA_FOUND THEN
    ERRMSG := 'Não existe este código de tabela cadastrado na TGFNTA. Inclusão cancelada.';
    RAISE ERROR;
  END;
  IF (P_ATIVO = 'N') THEN
    ERRMSG := 'Tabela não está Ativa.(TGFNTA)';
    RAISE ERROR;
  END IF;
  --  
  BEGIN
    SELECT COUNT(1) INTO P_COUNT FROM TSIPAR WHERE CHAVE = 'SBPRODUTO';
  EXCEPTION WHEN NO_DATA_FOUND THEN
      P_COUNT := 0;  
  END;
  /* 
   Usado a mesma variavel de validação para não deixar incluir uma nova quando for sincronização OS:334442
  */ 
  IF (P_COUNT=0) AND (P_VALIDAR) AND NOT (VARIAVEIS_PKG.V_SBPRODUTO) THEN 
    SELECT SEQ_TGFTAB_NUTAB.NEXTVAL INTO P_CODIGO FROM DUAL;
    :NEW.NUTAB :=  P_CODIGO;
    INSERT INTO TGFTAB_INC (NUTAB, CODTAB, CODTABORIG, DTVIGOR) VALUES (:NEW.NUTAB, :NEW.CODTAB, :NEW.CODTABORIG, :NEW.DTVIGOR);
    /* passado para o after o código daqui, pois nao tenho o ult_nutab */
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
