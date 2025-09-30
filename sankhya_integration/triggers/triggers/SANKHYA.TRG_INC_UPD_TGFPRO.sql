-- SANKHYA.TRG_INC_UPD_TGFPRO
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFPRO
"SANKHYA".TRG_INC_UPD_TGFPRO
   BEFORE UPDATE OR INSERT
   ON TGFPRO
   FOR EACH ROW

DECLARE
   P_COUNT               INT;
   P_VALCTA              CHAR (1);
   P_PARCIMPFICI         INT;
   P_AGENDAR_INDEXACAO   VARCHAR2 (1);
   P_DHALTER             DATE;
   P_NOMEUSU             VARCHAR2(40); 
BEGIN
   IF STP_GET_ATUALIZANDO
   THEN
      RETURN;
   END IF;

   -- OS 1162243

   IF (:NEW.USOPROD = 'S' AND NVL (:NEW.FLEX, 'N') = 'N')
   THEN
      :NEW.FLEX := 'N';
   END IF;

   -- FIM DA OS 1162243

   IF (NVL (:NEW.TIPCONTEST, 0) <> NVL (:OLD.TIPCONTEST, 0)
       AND (Tsiusu_Log_Pkg.V_CODUSULOG <> 0))
   THEN
      BEGIN
         SELECT COUNT ( * )
           INTO P_COUNT
           FROM TGFEST
          WHERE CODPROD = :NEW.CODPROD AND ESTOQUE <> 0;
      EXCEPTION
         WHEN NO_DATA_FOUND
         THEN
            P_COUNT := 0;
      END;

      IF (P_COUNT > 0)
      THEN
        BEGIN
          SELECT NOMEUSU INTO P_NOMEUSU
          FROM TSIUSU
          WHERE CODUSU = 0;
        EXCEPTION
         WHEN NO_DATA_FOUND
         THEN
            P_NOMEUSU := 'SUP';
        END;
        RAISE_APPLICATION_ERROR (-20101,'Produto possui estoque. Alteração do Tipo de Controle Adicional poderá inviabilizar movimentação. Ação só permitida para usuário '||P_NOMEUSU||'.');
      END IF;
   END IF;

   IF (NVL (:NEW.CODENQIPIENT, 0) <> NVL (:OLD.CODENQIPIENT, 0)
       OR NVL (:NEW.CSTIPIENT, 0) <> NVL (:OLD.CSTIPIENT, 0))
   THEN
      STP_VALIDA_ENQUADRAMENTO_IPI (:NEW.CSTIPIENT, :NEW.CODENQIPIENT);
   END IF;

   IF (NVL (:NEW.CODENQIPISAI, 0) <> NVL (:OLD.CODENQIPISAI, 0)
       OR NVL (:NEW.CSTIPISAI, 0) <> NVL (:OLD.CSTIPISAI, 0))
   THEN
      STP_VALIDA_ENQUADRAMENTO_IPI (:NEW.CSTIPISAI, :NEW.CODENQIPISAI);
   END IF;

   BEGIN
      SELECT LOGICO
        INTO P_VALCTA
        FROM TSIPAR
       WHERE CHAVE = 'VALCTA';
   EXCEPTION
      WHEN NO_DATA_FOUND
      THEN
         P_VALCTA := 'N';
   END;

   IF (UPDATING ('CODGRUPOPROD') OR INSERTING)
   THEN
      SELECT COUNT (1)
        INTO P_COUNT
        FROM TGFGRU
       WHERE     CODGRUPOPROD = :NEW.CODGRUPOPROD
             AND ATIVO = 'S'
             AND ANALITICO = 'S';

      IF (P_COUNT = 0)
      THEN
         RAISE_APPLICATION_ERROR (-20101,
                                  Erros_Pkg.ERRO_GRUPO_ATIV_ANALI_EXIST);
      END IF;
   END IF;

   IF (P_VALCTA = 'S')
   THEN
      IF     (UPDATING ('CODCTACTB') OR INSERTING)
         AND (:NEW.CODCTACTB IS NOT NULL)
         AND (:NEW.CODCTACTB <> 0)
      THEN
         SELECT COUNT (1)
           INTO P_COUNT
           FROM TCBPLA
          WHERE     CODCTACTB = :NEW.CODCTACTB
                AND ATIVA = 'S'
                AND ANALITICA = 'S';

         IF (P_COUNT = 0)
         THEN
            RAISE_APPLICATION_ERROR (-20101,
                                     Erros_Pkg.ERRO_CTACTB_ATIV_ANALI_EXIST);
         END IF;
      END IF;

      IF     (UPDATING ('CODCTACTB2') OR INSERTING)
         AND (:NEW.CODCTACTB2 IS NOT NULL)
         AND (:NEW.CODCTACTB2 <> 0)
      THEN
         SELECT COUNT (1)
           INTO P_COUNT
           FROM TCBPLA
          WHERE     CODCTACTB = :NEW.CODCTACTB2
                AND ATIVA = 'S'
                AND ANALITICA = 'S';

         IF (P_COUNT = 0)
         THEN
            RAISE_APPLICATION_ERROR (
               -20101,
               Erros_Pkg.ERRO_CTACTB_ATIV_ANALI_EXIST || ' Conta contábil2');
         END IF;
      END IF;

      IF     (UPDATING ('CODCTACTB3') OR INSERTING)
         AND (:NEW.CODCTACTB3 IS NOT NULL)
         AND (:NEW.CODCTACTB3 <> 0)
      THEN
         SELECT COUNT (1)
           INTO P_COUNT
           FROM TCBPLA
          WHERE     CODCTACTB = :NEW.CODCTACTB3
                AND ATIVA = 'S'
                AND ANALITICA = 'S';

         IF (P_COUNT = 0)
         THEN
            RAISE_APPLICATION_ERROR (
               -20101,
               Erros_Pkg.ERRO_CTACTB_ATIV_ANALI_EXIST || ' Conta contábil3');
         END IF;
      END IF;

      IF     (UPDATING ('CODCTACTB4') OR INSERTING)
         AND (:NEW.CODCTACTB4 IS NOT NULL)
         AND (:NEW.CODCTACTB4 <> 0)
      THEN
         SELECT COUNT (1)
           INTO P_COUNT
           FROM TCBPLA
          WHERE     CODCTACTB = :NEW.CODCTACTB4
                AND ATIVA = 'S'
                AND ANALITICA = 'S';

         IF (P_COUNT = 0)
         THEN
            RAISE_APPLICATION_ERROR (
               -20101,
               Erros_Pkg.ERRO_CTACTB_ATIV_ANALI_EXIST || ' Conta contábil4');
         END IF;
      END IF;
   END IF;

   IF (UPDATING ('CODGAR') OR INSERTING) AND (:NEW.CODGAR IS NOT NULL)
   THEN
      SELECT COUNT (1)
        INTO P_COUNT
        FROM TGFGAR
       WHERE CODGAR = :NEW.CODGAR;

      IF P_COUNT = 0
      THEN
         RAISE_APPLICATION_ERROR (
            -20101,
            'Código de garantia não cadastrado: ' || TO_CHAR (:NEW.CODGAR));
      END IF;
   END IF;

   IF (:NEW.CODFCI IS NOT NULL)
   THEN
      IF :NEW.ORIGPROD NOT IN ('3', '5', '8')
      THEN
         RAISE_APPLICATION_ERROR (
            -20101,
            'Para definir o Código da FCI a origem do produto(ORIGPROD) deve ser definida entre 3, 5 ou 8. Produto: '
            || TO_CHAR (:NEW.CODPROD));
      END IF;

      IF (UPPER (:NEW.CODFCI) <> 'PENDENTE') AND (LENGTH (:NEW.CODFCI) <> 36)
      THEN
         RAISE_APPLICATION_ERROR (
            -20101,
            'O Código da FCI deve ser PENDENTE ou ter trinta e seis dígitos. Produto: '
            || TO_CHAR (:NEW.CODPROD));
      END IF;
   END IF;

   IF NVL (:NEW.VLRPARCIMPEXT, 0) > 0
   THEN
      P_PARCIMPFICI := GET_TSIPAR_INTEIRO ('PARCIMPFICI');

      IF P_PARCIMPFICI < 0
      THEN
         RAISE_APPLICATION_ERROR (
            -20101,
            'Para informar o Vlr. da parcela de importação o parâmetro PARCIMPFICI deve ter valor maior ou igual a zero.');
      END IF;

      IF NVL (:NEW.VLRCOMERC, 0) = 0
      THEN
         RAISE_APPLICATION_ERROR (
            -20101,
            'Para informar o Vlr. da parcela de importação o Vlr. comercializado deve ser informado.');
      END IF;

      IF ( (:NEW.VLRPARCIMPEXT / :NEW.VLRCOMERC) * 100) < P_PARCIMPFICI
      THEN
         RAISE_APPLICATION_ERROR (
            -20101,
               'Parcela Importada deverá ser maior ou igual a '
            || TO_CHAR (P_PARCIMPFICI)
            || ' %');
      END IF;
   END IF;

   IF SNK_TGFTOKCFG
   THEN
      BEGIN
         P_AGENDAR_INDEXACAO := 'N';

         DECLARE
            CURSOR curCamposTok
            IS
               SELECT C.CAMPO
                 FROM TGFTOKCAM C
                WHERE C.CODCFG = 0 AND C.TABELA = 'TGFPRO';
         BEGIN
            FOR registro IN curCamposTok
            LOOP
               IF ( (UPDATING (registro.CAMPO) OR INSERTING)
                   AND P_AGENDAR_INDEXACAO = 'N')
               THEN
                  P_AGENDAR_INDEXACAO := 'S';
               END IF;
            END LOOP;
         END;

         IF P_AGENDAR_INDEXACAO = 'S'
         THEN
            BEGIN
               P_DHALTER := SYSDATE;

               INSERT INTO TGFATUTOK (CODPROD, DHALTER)
                  SELECT :NEW.CODPROD, P_DHALTER
                    FROM DUAL
                   WHERE NOT EXISTS
                            (SELECT 1
                               FROM TGFATUTOK
                              WHERE CODPROD = :NEW.CODPROD
                                    AND DHALTER = P_DHALTER);
            END;
         END IF;
      END;
   END IF;
END;

/
