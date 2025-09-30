-- SANKHYA.TRG_DLT_TCIIBE_AFTER
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TCIIBE_AFTER
"SANKHYA".TRG_DLT_TCIIBE_AFTER
   AFTER DELETE
   ON TCIIBE

DECLARE
   P_COUNT             INT;
   P_CODPROD           INT;
   P_CODBEM            VARCHAR2 (30);
   P_NUNOTA            INT;
   P_NUNOTADEV         INT;
   P_NUMCONTRATO_BEM   INT;
   P_NUNOTADEVVENDA    INT;
   P_ATUALBEM          VARCHAR2 (1);
   P_NUMNOTABAIXA      INT;
   P_DTBAIXA           DATE;
   P_ULT_NUNOTA        INT;
   P_CODEMP            INT;

   CURSOR ITENS
   IS
      SELECT CODPROD,
             CODBEM,
             NUMCONTRATO_BEM,
             NUNOTA,
             NUNOTADEV,
             NUNOTADEVVENDA,
             ATUALBEM
        FROM TCIIBE_DLT;
BEGIN
   IF STP_GET_ATUALIZANDO
   THEN
      RETURN;
   END IF;

   OPEN ITENS;

   DELETE FROM TCIIBE_DLT;

   LOOP
      FETCH ITENS
      INTO P_CODPROD,
           P_CODBEM,
           P_NUMCONTRATO_BEM,
           P_NUNOTA,
           P_NUNOTADEV,
           P_NUNOTADEVVENDA,
           P_ATUALBEM;

      EXIT WHEN ITENS%NOTFOUND;

      IF (P_ATUALBEM = 'C')
      THEN
         SELECT COUNT(*) INTO P_COUNT  FROM TCIMOV WHERE CODBEM = P_CODBEM AND CODPROD = P_CODPROD;
         IF (P_COUNT  > 0) THEN
            RAISE_APPLICATION_ERROR(-20111, 'O Bem "'||TO_CHAR(P_CODBEM)|| '" possui cálculo da depreciação mensal');
         END IF;

         SELECT COUNT(*) INTO P_COUNT  FROM TCIMOVAJ WHERE CODBEM = P_CODBEM AND CODPROD = P_CODPROD;
         IF (P_COUNT  > 0) THEN
            RAISE_APPLICATION_ERROR(-20111, 'O Bem "'||TO_CHAR(P_CODBEM)|| '" possui cálculo da depreciação mensal p/ Ajuste Lei 11.638');
         END IF;

         SELECT COUNT(*) INTO P_COUNT  FROM TCISAL WHERE CODBEM = P_CODBEM AND CODPROD = P_CODPROD;
         IF (P_COUNT  > 0) THEN
            RAISE_APPLICATION_ERROR(-20111, 'O Bem "'||TO_CHAR(P_CODBEM)|| '" possui saldo de cálculo da depreciação mensal');
         END IF;

         SELECT COUNT(*) INTO P_COUNT  FROM TCISALAJ WHERE CODBEM = P_CODBEM AND CODPROD = P_CODPROD;
         IF (P_COUNT  > 0) THEN
            RAISE_APPLICATION_ERROR(-20111, 'O Bem "'||TO_CHAR(P_CODBEM)|| '" possui saldo de cálculo da depreciação mensal p/ Ajuste Lei 11.638');
         END IF;

         UPDATE TCIBEM
         SET NUNOTA = 0
         WHERE CODBEM = P_CODBEM AND CODPROD = P_CODPROD;

         SELECT COUNT(*) INTO P_COUNT  FROM TCICEX WHERE CODBEM = P_CODBEM AND CODPROD = P_CODPROD;
         IF (P_COUNT  > 0) THEN
            DELETE FROM TCICEX WHERE CODBEM = P_CODBEM AND CODPROD = P_CODPROD;
         END IF;

         SELECT COUNT(*) INTO P_COUNT  FROM TCICTA WHERE CODBEM = P_CODBEM AND CODPROD = P_CODPROD;
         IF (P_COUNT  > 0) THEN
            DELETE FROM TCICTA WHERE CODBEM = P_CODBEM AND CODPROD = P_CODPROD;
         END IF;

         SELECT COUNT(*) INTO P_COUNT  FROM TCITAX WHERE CODBEM = P_CODBEM AND CODPROD = P_CODPROD;
         IF (P_COUNT  > 0) THEN
            DELETE FROM TCITAX WHERE CODBEM = P_CODBEM AND CODPROD = P_CODPROD;
         END IF;

         DELETE FROM TCIBEM
         WHERE CODPROD = P_CODPROD AND CODBEM = P_CODBEM;

      ELSIF (P_ATUALBEM = 'T')
      THEN
         BEGIN
            SELECT NVL (MAX (IBE.NUNOTA), 0)
              INTO P_ULT_NUNOTA
              FROM TCIIBE IBE, TGFCAB CAB, TGFTOP TP
             WHERE     IBE.CODPROD = P_CODPROD
                   AND IBE.CODBEM = P_CODBEM
                   AND IBE.NUNOTA <> P_NUNOTA
                   AND IBE.NUNOTA <> P_NUNOTADEV
                   AND CAB.NUNOTA = IBE.NUNOTA
                   AND TP.CODTIPOPER = CAB.CODTIPOPER
                   AND TP.DHALTER = CAB.DHTIPOPER
                   AND TP.ATUALBEM <> 'F';
         EXCEPTION
            WHEN NO_DATA_FOUND
            THEN
               P_ULT_NUNOTA := 0;
         END;

         P_NUMCONTRATO_BEM := 0;

         IF (P_ULT_NUNOTA = 0)
         THEN
            IF P_NUNOTA = 0
            THEN
               P_CODEMP := 1;
            ELSE
               SELECT CODEMP
                 INTO P_CODEMP
                 FROM TGFCAB
                WHERE NUNOTA = P_NUNOTA;
            END IF;
         ELSIF (P_ULT_NUNOTA < P_NUNOTADEV)
         THEN
            SELECT CODEMP
              INTO P_CODEMP
              FROM TGFCAB
             WHERE NUNOTA = P_NUNOTADEV;
         ELSE
            SELECT NUMCONTRATO, CASE WHEN TIPMOV = 'T' THEN CODEMPNEGOC ELSE CODEMP END
              INTO P_NUMCONTRATO_BEM, P_CODEMP
              FROM TGFCAB
             WHERE NUNOTA = P_ULT_NUNOTA;
         END IF;

         UPDATE TCIBEM
            SET NUMCONTRATO = P_NUMCONTRATO_BEM,
                NUNOTASAIDA = P_ULT_NUNOTA,
                CODEMP = P_CODEMP
          WHERE CODPROD = P_CODPROD AND CODBEM = P_CODBEM;
      ELSIF (P_ATUALBEM = 'E')
      THEN
         BEGIN
            SELECT NVL (MAX (NUNOTA), 0)
              INTO P_ULT_NUNOTA
              FROM TCIIBE
             WHERE     CODPROD = P_CODPROD
                   AND CODBEM = P_CODBEM
                   AND NUNOTA <> P_NUNOTA
                   AND NUNOTA <> P_NUNOTADEV
                   AND NUNOTA <> P_NUNOTADEVVENDA;
         EXCEPTION
            WHEN NO_DATA_FOUND
            THEN
               P_ULT_NUNOTA := 0;
         END;

         IF (P_ULT_NUNOTA = 0)
         THEN
            P_ULT_NUNOTA := NULL;
            P_DTBAIXA := NULL;
            P_NUMNOTABAIXA := NULL;
         ELSE
            SELECT DTNEG, NUMNOTA
              INTO P_DTBAIXA, P_NUMNOTABAIXA
              FROM TGFCAB
             WHERE NUNOTA = P_ULT_NUNOTA;
         END IF;

         UPDATE TCIBEM
            SET NUNOTABAIXA = P_ULT_NUNOTA,
                NUMNOTABAIXA = P_NUMNOTABAIXA,
                DTBAIXA = P_DTBAIXA,
                NUNOTADEVVENDA = NULL
          WHERE CODPROD = P_CODPROD AND CODBEM = P_CODBEM;
      END IF;
   END LOOP;

   CLOSE ITENS;
END;

/
