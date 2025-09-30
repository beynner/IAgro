-- SANKHYA.TRG_INC_UPD_TGFVEN_CERTIFIC
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFVEN_CERTIFIC
"SANKHYA".TRG_INC_UPD_TGFVEN_CERTIFIC   
BEFORE INSERT OR UPDATE OR DELETE  
ON TGFVEN   
FOR EACH ROW

DECLARE
   P_SEQUENCIA      TGFCER.SEQUENCIA%TYPE;
   P_CODREGRA       TGFREG.CODREGRA%TYPE;
   P_INSTPRINC      TGFREG.INSTPRINC%TYPE;
   P_DESCRREGRA     TGFREG.DESCRREGRA%TYPE;
   P_TIPOREGRA      TGFREG.TIPO%TYPE;
   P_CODINSTPRINC   NUMBER (10, 0);
   P_COUNT          NUMBER (10, 0);
   P_ERRO           VARCHAR2 (4);
   ERRMSG           VARCHAR2 (255);
   ERROR EXCEPTION;

   CURSOR curRegras
   IS
        SELECT
               CER.CODREGRA,
               CER.SEQUENCIA,
               REG.INSTPRINC,
               REG.TIPO,
               REG.DESCRREGRA
         FROM
               TGFREG REG
               INNER JOIN TGFCER CER ON  CER.CODREGRA = REG.CODREGRA
         WHERE 
               REG.INSTPRINC = 'Empresa'
               AND REG.INSTSEC IS NULL
               AND CER.TIPO = 'U'
               AND CER.CHAVE = STP_GET_CODUSULOGADO
               AND CER.ATIVO = 'S'
      ORDER BY
               CER.SEQUENCIA;
BEGIN
  
   IF STP_GET_ATUALIZANDO  THEN
      RETURN;
   END IF;
   
   IF NVL(:OLD.CODEMP, :NEW.CODEMP) IS NULL THEN
       RETURN;
   END IF;
   
   OPEN curRegras;

   LOOP
      FETCH curRegras
      INTO 
           P_CODREGRA,
           P_SEQUENCIA,
           P_INSTPRINC,
           P_TIPOREGRA,
           P_DESCRREGRA;

   EXIT WHEN curRegras%NOTFOUND;
      IF (INSERTING OR UPDATING) AND :NEW.CODEMP IS NOT NULL THEN  
             P_CODINSTPRINC := :NEW.CODEMP;
              SELECT
                   COUNT ( * )
              INTO
                   P_COUNT
              FROM
                   TGFITR ITR
              WHERE
                   ITR.CODREGRA = P_CODREGRA
                   AND ITR.CODINSTPRINC <= P_CODINSTPRINC
                   AND NVL (ITR.CODINSTPRINCFIN, ITR.CODINSTPRINC) >=  P_CODINSTPRINC
                   AND ITR.ATIVO = 'S';
              
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
                     ERRMSG :=
                       'Você não tem permissão para alterar vendedores de ' || P_INSTPRINC
                       || ' '   
                       || P_CODINSTPRINC
                       ||'. Veja detalhes na Central de certificação regra "'
                       || P_DESCRREGRA
                       || '" sequência '
                       || P_SEQUENCIA
                       || '.';
                    RAISE ERROR;
                
              END IF;
       END IF;
       
       IF (:NEW.CODVEND IS NULL OR UPDATING) AND :OLD.CODEMP IS NOT NULL THEN
          P_CODINSTPRINC := :OLD.CODEMP;
          SELECT
                   COUNT ( * )
              INTO
                   P_COUNT
              FROM
                   TGFITR ITR
              WHERE
                   ITR.CODREGRA = P_CODREGRA
                   AND ITR.CODINSTPRINC <= P_CODINSTPRINC
                   AND NVL (ITR.CODINSTPRINCFIN, ITR.CODINSTPRINC) >=  P_CODINSTPRINC
                   AND ITR.ATIVO = 'S';
              
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
                     ERRMSG :=
                       'Você não tem permissão para alterar vendedores de ' || P_INSTPRINC
                       || ' '   
                       || P_CODINSTPRINC
                       ||'. Veja detalhes na Central de certificação regra "'
                       || P_DESCRREGRA
                       || '" sequência '
                       || P_SEQUENCIA
                       || '.';
                    RAISE ERROR;
                
              END IF; 
       END IF;
   END LOOP;

   CLOSE curRegras;

   RETURN;
EXCEPTION
   WHEN ERROR
   THEN
      RAISE_APPLICATION_ERROR (-20101, ERRMSG);
END;

/
