-- SANKHYA.TRG_DLT_TGFMBC
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGFMBC
"SANKHYA".TRG_DLT_TGFMBC BEFORE DELETE ON TGFMBC FOR EACH ROW

DECLARE
    P_COUNT                  INT:= 0;
    P_ATUALIZOU              CHAR(1);
    CODCTABCOINTDEST         NUMBER;
    CONCILIADODEST           VARCHAR2(1);
    DHCONCILIACAODEST        DATE;
    ERRMSG            VARCHAR2(255);
    ERROR             EXCEPTION;
    P_VALIDAR BOOLEAN;
    P_DIAS_VALIDAR_DESCON    INT;
    
BEGIN

  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  /* 
  sincronização de dados
  */
  P_VALIDAR := Fpodevalidar('TGFMBC');
  
  IF :OLD.CONCILIADO = 'S' THEN

    P_DIAS_VALIDAR_DESCON := GET_TSIPAR_INTEIRO('DIASBLQDESCONBC');
    IF P_DIAS_VALIDAR_DESCON = 0 THEN
      P_DIAS_VALIDAR_DESCON := 60; --O default é 60 dias.
    END IF;
    
    IF :OLD.DHCONCILIACAO < (TRUNC(SYSDATE) - P_DIAS_VALIDAR_DESCON) THEN
      ERRMSG := 'De acordo com o parâmetro "DIASBLQDESCONBC", a exclusão só pode ser feita em lançamentos conciliados a partir de ' || TO_CHAR(TRUNC(SYSDATE) - P_DIAS_VALIDAR_DESCON, 'DD/MM/YYYY');
      RAISE ERROR;
    END IF;
  END IF;
  
  SELECT COUNT(1) INTO P_COUNT FROM TCBINT C WHERE  C.NUNICO = :OLD.NUBCO AND C.ORIGEM = 'M';
  IF P_COUNT <> 0 THEN
	 ERRMSG := 'Movimento Bancário já foi contabilizado, não pode ser excluido.';
	 RAISE ERROR;
  END IF;

  SELECT COUNT(1) INTO  P_COUNT
  FROM TGFFIN
  WHERE NUBCO = :OLD.NUBCO;
  IF P_COUNT <> 0 THEN
	 ERRMSG := 'Movimento Bancário está sendo referenciado pelo financeiro, não pode ser excluido.';
   RAISE ERROR;
  END IF;

  IF (:OLD.ORIGMOV IN ('T','A','R','D','S')) THEN
        /*Registra perna deletada para deletar a perna contrária.*/
        INSERT INTO TGFMBC_DLT(NUMTRANSF, ORIGMOV, RECDESP) VALUES(:OLD.NUMTRANSF, :OLD.ORIGMOV, :OLD.RECDESP);
  END IF;

  IF :OLD.RECDESP = 1 THEN
    SELECT COUNT(1)
    INTO P_COUNT
    FROM TGFMBS
    WHERE NUBCOREC = :OLD.NUBCO;
    IF P_COUNT <> 0 THEN
    ERRMSG := 'Lançamento em Moeda já participou de apuração de Variação Cambial, não pode ser excluido.';
    RAISE ERROR;
    END IF;
  END IF;

  Stp_Atualiza_Tgfsbc_Dlt(:OLD.RECDESP, :OLD.VLRLANC, :OLD.CONCILIADO, :OLD.DTLANC, :OLD.DHCONCILIACAO, :OLD.CODCTABCOINT, P_ATUALIZOU );
  IF (P_ATUALIZOU = 'N') THEN
   ERRMSG := 'Não existe um saldo acumulado na tabela de saldos para esta data de lançamento.';
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
