-- SANKHYA.TRG_DLT_TGFFIN
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGFFIN
TRG_DLT_TGFFIN
   BEFORE DELETE
   ON TGFFIN
   FOR EACH ROW

DECLARE
   P_COUNT         INTEGER;
   P_NUNOTAORIG    INTEGER;
   P_CODVEND       INTEGER;
   P_VLRCOM        FLOAT;
   P_TOTAL         FLOAT;
   P_TIPO          TGFCOM.TIPO%TYPE;
   P_NUMOSORIG     TGFCOM.NUMOSORIG%TYPE;
   P_NUMITEMORIG   TGFCOM.NUMITEMORIG%TYPE;
   ERRMSG          VARCHAR2 (4000);
   ERROR EXCEPTION;
   P_VALIDAR       BOOLEAN;
   P_SUMVALOR      TGFMCX.VALOR%TYPE;
   P_NUFIN         NUMBER (10);
   P_CODFUNC       NUMBER (10);
   P_COUNT_D       INTEGER;


   CURSOR CURCOM
   IS                                   /* notas que dariam chave duplicada */
          SELECT NUNOTAORIG,
                 CODVEND,
                 VLRCOM,
                 TIPO,
                 NUMOSORIG,
                 NUMITEMORIG
            FROM TGFCOM C1
           WHERE NUFIN IN (:OLD.NUFIN, (:OLD.NUFIN * -1))
      FOR UPDATE ;
BEGIN
   IF STP_GET_ATUALIZANDO
   THEN
      RETURN;
   END IF;

   /*
   sincronização de dados
   */
   P_VALIDAR := Fpodevalidar ('TGFFIN');

   IF (:OLD.NUBCO IS NOT NULL)
   THEN
      ERRMSG :=
         'Título já baixado, estorne-o primeiro. Financeiro de Nro Único: '
         || TO_CHAR (:OLD.NUFIN)
         || '.';
      RAISE ERROR;
   END IF;

   -- OS 864848
   SELECT COUNT (1)
     INTO P_COUNT
     FROM TGFRCI RCI
    WHERE RCI.NUFIN = :OLD.NUFIN;

   IF (P_COUNT > 0)
   THEN
      ERRMSG :=
         'O título de número Único ' || TO_CHAR (:OLD.NUFIN)
         || ' possui ligação com remessa. Para continuar com a exclusão do título será necessário desvinculá-lo da remessa, pela tela Movimentação Financeira.';
      RAISE ERROR;
   END IF;

   -- Fim OS 864848

   IF (    (:OLD.ORIGEM = 'F')
       AND (:OLD.NUMNOTA = :OLD.NUFIN)
       AND (:OLD.PROVISAO = 'N'))
   THEN
      IF (:OLD.RECDESP = 1)
      THEN
         SELECT COUNT (1)
           INTO P_COUNT
           FROM TGFFRP FRP
          WHERE FRP.NUFINREC = :OLD.NUFIN;
      ELSIF (:OLD.RECDESP = -1)
      THEN
         SELECT COUNT (1)
           INTO P_COUNT
           FROM TGFFRP FRP
          WHERE FRP.NUFINDESP = :OLD.NUFIN;
      END IF;

      IF (P_COUNT <> 0)
      THEN
         ERRMSG :=
            'Financeiro ligado a um Rateio de Holding, não pode ser excluído. Financeiro de Nro Único: '
            || TO_CHAR (:OLD.NUFIN)
            || '.';
         RAISE ERROR;
      END IF;
   END IF;

   IF ( (:OLD.PROVISAO = 'N') AND (:OLD.DHBAIXA IS NOT NULL))
   THEN
      ERRMSG :=
         'Impossível excluir. O título já foi baixado. Financeiro de Nro Único: '
         || TO_CHAR (:OLD.NUFIN)
         || '.';
      RAISE ERROR;
   END IF;

   SELECT COUNT (1)
     INTO P_COUNT_D
     FROM TCBINT C
    WHERE C.NUNICO = :OLD.NUFIN AND C.ORIGEM = 'F' AND C.VLRLANC = 0;

   IF (P_COUNT_D <> 0)
   THEN
      DELETE FROM TCBINT C
            WHERE C.NUNICO = :OLD.NUFIN AND C.ORIGEM = 'F' AND C.VLRLANC = 0;
   END IF;

   SELECT COUNT (1)
     INTO P_COUNT
     FROM TCBINT C
    WHERE C.NUNICO = :OLD.NUFIN AND C.ORIGEM IN ('B', 'F');

   IF (P_COUNT <> 0)
   THEN
      ERRMSG :=
         'Título já foi contabilizado, não pode ser excluído. Financeiro de Nro Único: '
         || TO_CHAR (:OLD.NUFIN)
         || '.';
      RAISE ERROR;
   END IF;

   IF ( (:OLD.ORIGEM = 'F' OR (:OLD.ORIGEM = 'E' AND :OLD.DESDOBDUPL = 'F'))
       AND (:OLD.CODTIPOPER <> 0))
   THEN
      SELECT COUNT (1)
        INTO P_COUNT
        FROM TGFLIV LIV
       WHERE LIV.NUNOTA = :OLD.NUFIN AND LIV.ORIGEM = ('F');

      IF (P_COUNT <> 0)
      THEN
         ERRMSG :=
            'Financeiro já foi gerado nos Livros Fiscais, não pode ser excluído. Financeiro de Nro Único: '
            || TO_CHAR (:OLD.NUFIN)
            || '.';
         RAISE ERROR;
      END IF;
   END IF;

   IF ( (:OLD.RECDESP = -1) AND (:OLD.ORIGEM = 'F'))
   THEN
      SELECT COUNT (1)
        INTO P_COUNT_D
        FROM TGMTRA
       WHERE NUFIN = :OLD.NUFIN;

      IF (P_COUNT_D <> 0)
      THEN
         DELETE FROM TGMTRA
               WHERE NUFIN = :OLD.NUFIN;
      END IF;
   END IF;

   SELECT COUNT (1)
     INTO P_COUNT_D
     FROM TGFRAT
    WHERE NUFIN = :OLD.NUFIN AND ORIGEM IN ('F', 'R');

   IF (P_COUNT_D <> 0)
   THEN
      DELETE FROM TGFRAT
            WHERE NUFIN = :OLD.NUFIN AND ORIGEM IN ('F', 'R');
   END IF;

   SELECT COUNT (1)
     INTO P_COUNT_D
     FROM TSILIB
    WHERE NUCHAVE = :OLD.NUFIN AND TABELA = 'TGFFIN';

   IF (P_COUNT_D <> 0)
   THEN
      DELETE FROM TSILIB
            WHERE NUCHAVE = :OLD.NUFIN AND TABELA = 'TGFFIN';
   END IF;

   IF (:OLD.NUNOTA IS NULL)
   THEN
      SELECT COUNT (1)
        INTO P_COUNT_D
        FROM TCSFAT
       WHERE NUFINREAL = :OLD.NUFIN OR NUFINPROVISAO = :OLD.NUFIN;

      IF (P_COUNT_D <> 0)
      THEN
         DELETE FROM TCSFAT
               WHERE NUFINREAL = :OLD.NUFIN OR NUFINPROVISAO = :OLD.NUFIN;
      END IF;
   END IF;

   SELECT COUNT (1)
     INTO P_COUNT
     FROM TGFCOM
    WHERE NUFINORIG = :OLD.NUFIN;

   IF (P_COUNT > 0)
   THEN
      SELECT NVL (MAX (NUFIN), 0), NVL (MAX (CODFUNC), 0)
        INTO P_NUFIN, P_CODFUNC
        FROM TGFCOM
       WHERE NUFINORIG = :OLD.NUFIN;

      IF ( (P_NUFIN <> 0) OR (P_CODFUNC <> 0))
      THEN
         ERRMSG :=
            'Essa comissão já foi paga. Exclusão proibida. Financeiro de Nro Único: '
            || TO_CHAR (:OLD.NUFIN)
            || '.';
         RAISE ERROR;
      ELSE
         SELECT COUNT (1)
           INTO P_COUNT_D
           FROM TGFCOM
          WHERE NUFINORIG = :OLD.NUFIN;

         IF (P_COUNT_D <> 0)
         THEN
            DELETE FROM TGFCOM
                  WHERE NUFINORIG = :OLD.NUFIN;
         END IF;
      END IF;
   END IF;

   IF VARIAVEIS_PKG.V_IGNORE_VALID_EST_MOV = 'N'
   THEN
      SELECT SUM (MCX.VALOR * MCX.RECDESP)
        INTO P_SUMVALOR
        FROM TGFMCX MCX
       WHERE MCX.NROUNICO = :OLD.NUFIN AND MCX.ORIGEM = 'F';

      IF ( (P_SUMVALOR IS NOT NULL) AND (P_SUMVALOR <> 0))
      THEN
         ERRMSG :=
            'Título nro. Único: ' || :OLD.NUFIN
            || ' possui baixa no movimento de caixa e não possui o estorno no movimento de caixa.';
         RAISE ERROR;
      END IF;
   END IF;

   SELECT COUNT (1)
     INTO P_COUNT
     FROM TGMTRA
    WHERE NUFIN = :OLD.NUFIN AND STATUS = 'A';

   IF (P_COUNT <> 0)
   THEN
      ERRMSG :=
         'Já existe aprovação de orçamento, não pode ser excluído. Financeiro de Nro Único: '
         || TO_CHAR (:OLD.NUFIN)
         || '.';
      RAISE ERROR;
   END IF;

   IF ( (:OLD.ORIGEM = 'F') AND (:OLD.PROVISAO = 'N'))
   THEN
      SELECT COUNT (1)
        INTO P_COUNT_D
        FROM TGFCOM
       WHERE NUFIN = :OLD.NUFIN AND (VLRCOM = 0 OR TIPO = 'D');

      IF P_COUNT_D <> 0
      THEN
         DELETE FROM TGFCOM
               WHERE NUFIN = :OLD.NUFIN AND (VLRCOM = 0 OR TIPO = 'D');
      END IF;

      SELECT COUNT (1)
        INTO P_COUNT_D
        FROM TGFCOM
       WHERE NUFIN = (:OLD.NUFIN * -1);

      IF P_COUNT_D <> 0
      THEN
         DELETE FROM TGFCOM
               WHERE NUFIN = (:OLD.NUFIN * -1); /* tem que apagar todas que tenham nufin negativo*/
      END IF;

      OPEN CURCOM;

      FETCH CURCOM
      INTO P_NUNOTAORIG,
           P_CODVEND,
           P_TOTAL,
           P_TIPO,
           P_NUMOSORIG,
           P_NUMITEMORIG;

      WHILE CURCOM%FOUND
      LOOP
         SELECT COUNT (1)
           INTO P_COUNT
           FROM TGFCOM
          WHERE     NUNOTAORIG = P_NUNOTAORIG
                AND CODVEND = P_CODVEND
                AND NUFIN = 0
                AND NUFINORIG = 0
                AND CODFUNC IS NULL
                AND TIPO = P_TIPO
                AND NUMOSORIG = P_NUMOSORIG
                AND NUMITEMORIG = P_NUMITEMORIG;

         IF (P_COUNT > 0)
         THEN
            UPDATE TGFCOM
               SET VLRCOM = VLRCOM + P_TOTAL
             WHERE     NUNOTAORIG = P_NUNOTAORIG
                   AND CODVEND = P_CODVEND
                   AND NUFIN = 0
                   AND NUFINORIG = 0
                   AND CODFUNC IS NULL
                   AND TIPO = P_TIPO
                   AND NUMOSORIG = P_NUMOSORIG
                   AND NUMITEMORIG = P_NUMITEMORIG;

            UPDATE TGFCOM
               SET VLRCOM = 0
             WHERE CURRENT OF CURCOM;

            DELETE FROM TGFCOM
                  WHERE CURRENT OF CURCOM;
         ELSE
            UPDATE TGFCOM
               SET NUFIN = 0,
                   NUFINORIG = DECODE (NUNOTAORIG, 0, NUFINORIG, 0),
                   REFERENCIA = NULL
             WHERE CURRENT OF CURCOM;
         END IF;

         FETCH CURCOM
         INTO P_NUNOTAORIG,
              P_CODVEND,
              P_TOTAL,
              P_TIPO,
              P_NUMOSORIG,
              P_NUMITEMORIG;
      END LOOP;

      CLOSE CURCOM;
   END IF;

   IF :OLD.DESDOBDUPL = 'ZZ'
   THEN
      Tgffin_Pkg.V_CONTADOR := Tgffin_Pkg.V_CONTADOR + 1;
      Tgffin_Pkg.V_NUMDUPL (Tgffin_Pkg.V_CONTADOR) := :OLD.NUMDUPL;
   END IF;

   SELECT COUNT (1)
     INTO P_COUNT
     FROM TGFIXN
    WHERE NUFIN = :OLD.NUFIN;

   IF (P_COUNT > 0)
   THEN
      SELECT COUNT (1)
        INTO P_COUNT
        FROM TSIPAR
       WHERE CHAVE = 'MANTERIXNDELFIN' AND CODUSU = 0 AND LOGICO = 'S';

      IF (P_COUNT > 0)
      THEN
         UPDATE TGFIXN
            SET STATUS = 0,
                CODUSUPROC = NULL,
                DHPROCESS = NULL,
                NUFIN = NULL
          WHERE NUFIN = :OLD.NUFIN;
      ELSE
         DELETE FROM TGFIXN
               WHERE NUFIN = :OLD.NUFIN;
      END IF;
   END IF;

   RETURN;
EXCEPTION
   WHEN OTHERS
   THEN
      /*
      Sincronização de dados não faz validações
      */
      IF (P_VALIDAR)
      THEN
         IF SQLCODE <> 1
         THEN
            ERRMSG := ERRMSG || '  ' || SQLERRM;
         END IF;

         RAISE_APPLICATION_ERROR (-20101, ERRMSG);
      END IF;
END;

/
