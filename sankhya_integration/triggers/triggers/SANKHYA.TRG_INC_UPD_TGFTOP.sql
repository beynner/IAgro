-- SANKHYA.TRG_INC_UPD_TGFTOP
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFTOP
"SANKHYA".TRG_INC_UPD_TGFTOP
   BEFORE INSERT OR UPDATE
   ON TGFTOP
   FOR EACH ROW

DECLARE
   P_COUNT        INT;
   P_TIPOIMPKIT   VARCHAR2 (1);
   P_VALIDAR      BOOLEAN;
   ERRMSG         VARCHAR2 (255);
   ERROR          EXCEPTION;
   P_UTILIZA      CHAR;
BEGIN

   IF STP_GET_ATUALIZANDO
   THEN
      RETURN;
   END IF;
   
   P_VALIDAR := Fpodevalidar ('TGFTOP'); -- sincronização de dados

   -- OS 1026302 VERIFICANDO SE O CLIENTE UTILIZA ESTA FUNCIONALIDADE
   IF NVL(:OLD.TIPMOV, ' ') <> NVL(:NEW.TIPMOV, ' ') 
   THEN
      STP_VERIFICA_SE_UTILIZA (
         'TGFTOP',
         'TIPMOV IN (''8'',''N'',''1'',''2'',''3'',''4'')',
         P_UTILIZA);

      UPDATE TSIVARBD
         SET UTILIZA_TGAMOV = P_UTILIZA;
   END IF;

   IF NVL(:OLD.ATUALESTTERC, ' ') <> NVL(:NEW.ATUALESTTERC, ' ')
   THEN
      STP_VERIFICA_SE_UTILIZA (
         'TGFTOP',
         'ATUALESTTERC IS NOT NULL AND ATUALESTTERC <> ''N''',
         P_UTILIZA);

      UPDATE TSIVARBD
         SET UTILIZA_ESTTERC = P_UTILIZA;
   END IF;

   IF NVL(:OLD.ATUALACDC, ' ') <> NVL(:NEW.ATUALACDC, ' ') 
   THEN
      STP_VERIFICA_SE_UTILIZA (
         'TGFTOP',
         'ATUALACDC IS NOT NULL AND ATUALACDC <> ''N''',
         P_UTILIZA);

      UPDATE TSIVARBD
         SET UTILIZA_FLEX = P_UTILIZA;
   END IF;

   IF NVL(:OLD.ATUALINDENIZ, 0) <> NVL(:NEW.ATUALINDENIZ, 0) 
   THEN
      STP_VERIFICA_SE_UTILIZA (
         'TGFTOP',
         'ATUALINDENIZ IS NOT NULL AND ATUALINDENIZ <> 0',
         P_UTILIZA);

      UPDATE TSIVARBD
         SET UTILIZA_INDENIZ = P_UTILIZA;
   END IF;

   IF  (NVL(:OLD.ATUALULTIMACOMP, ' ') <> NVL(:NEW.ATUALULTIMACOMP, ' ')) OR 
       (NVL(:OLD.ATUALULTIMAVEND, ' ') <> NVL(:NEW.ATUALULTIMAVEND, ' '))
   THEN
      STP_VERIFICA_SE_UTILIZA (
         'TGFTOP',
         'ATUALULTIMACOMP <> ''N'' OR ATUALULTIMAVEND <> ''N''',
         P_UTILIZA);

      UPDATE TSIVARBD
         SET UTILIZA_TGFCPP = P_UTILIZA;
   END IF;

   IF NVL(:OLD.ATUALBEM, ' ') <> NVL(:NEW.ATUALBEM, ' ') 
   THEN
      STP_VERIFICA_SE_UTILIZA ('TGFTOP', 'ATUALBEM IN (''C'',''B'',''T'',''D'',''E'',''F'',''1'')', P_UTILIZA);

      UPDATE TSIVARBD
         SET UTILIZA_TCIBEM = P_UTILIZA;
   END IF;

   IF (NVL(:OLD.BASENUMERACAO, ' ') <> NVL(:NEW.BASENUMERACAO, ' ')) OR 
      (NVL(:OLD.TIPMOV, ' ') <> NVL(:NEW.TIPMOV, ' ')) 
   THEN
      STP_VERIFICA_SE_UTILIZA ('TGFTOP',
                               'TIPMOV = ''P'' AND BASENUMERACAO = ''A''',
                               P_UTILIZA);

      UPDATE TSIVARBD
         SET UTILIZA_DAV = P_UTILIZA;
   END IF;

   IF NVL(:OLD.ATUALTRANSG, 0) <> NVL(:NEW.ATUALTRANSG, 0) 
   THEN
      STP_VERIFICA_SE_UTILIZA ('TGFTOP', 'ATUALTRANSG = 1', P_UTILIZA);

      UPDATE TSIVARBD
         SET UTILIZA_TRANSG = P_UTILIZA;
   END IF;

   -- OS 1026302

   /* OS 808153 */
   IF :NEW.TIPOIMPKIT IS NULL
   THEN
      BEGIN
         SELECT CASE INTEIRO
                   WHEN 0 THEN 'K'
                   WHEN 1 THEN 'C'
                   WHEN 2 THEN 'T'
                   ELSE 'C'
                END
           INTO P_TIPOIMPKIT
           FROM TSIPAR
          WHERE CHAVE = 'IMPITENSNFE';
      EXCEPTION
         WHEN NO_DATA_FOUND
         THEN
            P_TIPOIMPKIT := 'C';
      END;

      :NEW.TIPOIMPKIT := P_TIPOIMPKIT;
   END IF;

   /* FIM OS 808153 */

   IF (   NVL (:NEW.CODENQIPIENT, 0) <> NVL (:OLD.CODENQIPIENT, 0)
       OR NVL (:NEW.CSTIPIENT, 0) <> NVL (:OLD.CSTIPIENT, 0))
   THEN
      STP_VALIDA_ENQUADRAMENTO_IPI (:NEW.CSTIPIENT, :NEW.CODENQIPIENT);
   END IF;

   IF (   NVL (:NEW.CODENQIPISAI, 0) <> NVL (:OLD.CODENQIPISAI, 0)
       OR NVL (:NEW.CSTIPISAI, 0) <> NVL (:OLD.CSTIPISAI, 0))
   THEN
      STP_VALIDA_ENQUADRAMENTO_IPI (:NEW.CSTIPISAI, :NEW.CODENQIPISAI);
   END IF;

   IF :NEW.TIPMOV = 'D'
   THEN
      SELECT COUNT (1)
        INTO P_COUNT
        FROM TSIPAR
       WHERE CHAVE = 'RETDESCDEV' AND LOGICO = 'N';

      IF P_COUNT > 0 AND :NEW.ATUALACDC <> 'N'
      THEN
         ERRMSG :=
            'Não é permitido o campo Atualizar Acréscimos/Decréscimos ser diferente que Não atualizar quando o parametro RETDESCDEV estiver desligado.';
         RAISE ERROR;
      END IF;
   END IF;

   --Validações para impacto na análise de giro
   IF    INSERTING
      OR (   (:NEW.TIPMOV <> :OLD.TIPMOV)
          OR (:NEW.ANALISEGIRO <> :OLD.ANALISEGIRO))
   THEN
      IF :NEW.TIPMOV IN ('O', 'C', 'E') AND :NEW.ANALISEGIRO <> 0
      THEN
         ERRMSG :=
            'Pedido de Compra, Compra ou Devolução de Compra não podem impactar na análise de giro.';
         RAISE ERROR;
      END IF;

      IF :NEW.TIPMOV IN ('D', 'L') AND :NEW.ANALISEGIRO = -1
      THEN
         ERRMSG :=
            'Devolução de Venda ou Devolução de Requisição não podem impactar na análise de giro como Saída.';
         RAISE ERROR;
      END IF;

      IF :NEW.TIPMOV IN ('P', 'V', 'J', 'Q', 'T') AND :NEW.ANALISEGIRO = 1
      THEN
         ERRMSG :=
            'Pedido de Venda, Venda, Pedido de Requisição, Requisição ou Transferência não podem impactar na análise de giro como Entrada.';
         RAISE ERROR;
      END IF;
   END IF;
EXCEPTION
   WHEN ERROR
   THEN
      /*
      Sincronização de dados não faz validações
      */
      IF (P_VALIDAR)
      THEN
         RAISE_APPLICATION_ERROR (-20101, ERRMSG);
      END IF;
END;

/
