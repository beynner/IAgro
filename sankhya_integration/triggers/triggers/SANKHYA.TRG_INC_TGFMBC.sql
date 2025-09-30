-- SANKHYA.TRG_INC_TGFMBC
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_TGFMBC
"SANKHYA".TRG_INC_TGFMBC BEFORE INSERT ON TGFMBC FOR EACH ROW

DECLARE
    P_COUNT                  INT := 0;
    P_LOGICO                 CHAR;
    P_ATUALIZOU              CHAR(1);
    P_ANOINVALIDO            CHAR(1);
    L_REFERENCIA             DATE;
    ERRMSG                   VARCHAR2(255);
    ERROR                    EXCEPTION;
    P_VALIDAR                BOOLEAN;
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  /* 
  sincronização de dados
  */
  P_VALIDAR := Fpodevalidar('TGFMBC');
  IF (:NEW.CODTIPOPER = 0) THEN
     ERRMSG := 'O Código da operação não pode ser zero.';
     RAISE ERROR;
  END IF;
  SELECT COUNT(1) INTO  P_COUNT
  FROM TGFTOP
  WHERE CODTIPOPER = :NEW.CODTIPOPER
  AND DHALTER = :NEW.DHTIPOPER
  AND ATIVO = 'S';
  IF (P_COUNT = 0) THEN
      Stp_Popula_Msg('TGFTOP');
  END IF;

  SELECT COUNT(1) INTO  P_COUNT
  FROM TSICTA
  WHERE CODCTABCOINT =:NEW.CODCTABCOINT
    AND ATIVA = 'S';
  IF  (P_COUNT = 0) THEN
      Stp_Popula_Msg('TSICTA');
  END IF;

  IF :NEW.RECDESP = 1 THEN
    :NEW.SALDO := :NEW.VLRLANC;
  END IF;
  IF :NEW.SALDO < 0 THEN 
     ERRMSG := 'Saldo deve ser maior ou igual a zero. Valor informado: '||TO_CHAR(:NEW.SALDO);
     RAISE ERROR;
  END IF;

  Stp_Valida_Ano(:NEW.DTLANC, P_ANOINVALIDO);

  SELECT COUNT(1), MIN(REFERENCIA) INTO P_COUNT, L_REFERENCIA
    FROM TGFSBC
   WHERE CODCTABCOINT = :NEW.CODCTABCOINT;
   
  IF (P_COUNT = 0) OR (L_REFERENCIA > :NEW.DTLANC) THEN
     ERRMSG := 'Lançamento inválido, pois e anterior a data de partida do controle de saldos da conta '|| TO_CHAR(:NEW.CODCTABCOINT) ||', inserção cancelada.';
     RAISE ERROR;
  END IF;
  
  Stp_Atualiza_Tgfsbc_Inc( :NEW.RECDESP, :NEW.VLRLANC, :NEW.CONCILIADO, :NEW.DTLANC, :NEW.DHCONCILIACAO, :NEW.CODCTABCOINT, P_ATUALIZOU);
  IF P_ATUALIZOU = 'N' THEN
     ERRMSG := 'Não existe um saldo acumulado na tabela de saldo para esta data de lançamento.';
     RAISE ERROR;
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
