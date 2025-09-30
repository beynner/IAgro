-- SANKHYA.TRG_INC_UPD_TGFTIT
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFTIT
"SANKHYA".TRG_INC_UPD_TGFTIT
BEFORE UPDATE OR INSERT ON TGFTIT
FOR EACH ROW

DECLARE
    P_COUNT                  INT;
BEGIN
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;

  IF ((:NEW.CODCTACTB<>:OLD.CODCTACTB) OR INSERTING) AND (:NEW.CODCTACTB IS NOT NULL) AND (:NEW.CODCTACTB <> 0) THEN
     SELECT COUNT(1) INTO P_COUNT
       FROM TCBPLA
      WHERE CODCTACTB = :NEW.CODCTACTB
        AND ATIVA = 'S' AND ANALITICA = 'S';
     IF (P_COUNT = 0) THEN
        RAISE_APPLICATION_ERROR(-20101,ERROS_PKG.ERRO_CTACTB_ATIV_ANALI_EXIST);
     END IF;
  END IF;

  IF ((:NEW.CODCTACTB2<>:OLD.CODCTACTB2) OR INSERTING) AND (:NEW.CODCTACTB2 IS NOT NULL) AND (:NEW.CODCTACTB2 <> 0) THEN
     SELECT COUNT(1) INTO P_COUNT
       FROM TCBPLA
      WHERE CODCTACTB = :NEW.CODCTACTB2
        AND ATIVA = 'S' AND ANALITICA = 'S';
     IF (P_COUNT = 0) THEN
        RAISE_APPLICATION_ERROR(-20101,ERROS_PKG.ERRO_CTACTB_ATIV_ANALI_EXIST || ' Conta contábil2');
     END IF;
  END IF;

  IF ((:NEW.CODCTACTB3<>:OLD.CODCTACTB3) OR INSERTING) AND (:NEW.CODCTACTB3 IS NOT NULL) AND (:NEW.CODCTACTB3 <> 0) THEN
     SELECT COUNT(1) INTO P_COUNT
       FROM TCBPLA
      WHERE CODCTACTB = :NEW.CODCTACTB3
        AND ATIVA = 'S' AND ANALITICA = 'S';
     IF (P_COUNT = 0) THEN
        RAISE_APPLICATION_ERROR(-20101,ERROS_PKG.ERRO_CTACTB_ATIV_ANALI_EXIST || ' Conta contábil3');
     END IF;
  END IF;

  IF :NEW.ATIVO = 'N' THEN
    SELECT COUNT(*) INTO P_COUNT 
    FROM TGFPPG
    WHERE CODTIPTITPAD = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar um tipo de título usado em Parcelas de TIPO DE NEGOCIAÇÃO.');
     END IF;

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'CODTIPTITCHQ' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.CODTIPTITCHQ - Tipo de título para cheque');
    END IF;

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'RCBCODTIPTIT' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.RCBCODTIPTIT - Tipo de título para recebimentos');
    END IF;            

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TITBXPARCRET' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TITBXPARCRET - Tipo de título p/baixa parcial NO ret.bancário');
    END IF;            

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TITBXPARCRETPEN' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TITBXPARCRETPEN - Tipo de título p/Pend.bx.parcial NO ret.bancário');
    END IF;            

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TIPTITCREDCLI' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TIPTITCREDCLI - Tipo de título para compensação de Crédito');
    END IF;            

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TIPTITDAE' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TIPTITDAE - Tipo de Título p/ Documento de Arrecadação');
    END IF;            

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TIPTITDEBFOR' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TIPTITDEBFOR - Tipo de título para compensação de Débito');
    END IF;            

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TIPTITDINHEIRO' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TIPTITDINHEIRO - Tipo de título dinheiro');
    END IF;

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TIPTITFATCART' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TIPTITFATCART - Tipo de título para fatura DO cartão');
    END IF;            

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TIPTITGNREST' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TIPTITGNREST - Tipo de Título p/indicar GNRE p/S.T.');
    END IF;
	
	SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TIPTITGNRECTE' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TIPTITGNRECTE - Tipo de Título p/indicar GNRE p/CTe.');
    END IF;           

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TIPTITGNRESTRB' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TIPTITGNRESTRB - Tipo de Título p/reembolso de GNRE S.T.');
    END IF;            

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TIPTITJUROCART' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TIPTITJUROCART - Tipo de título para juro DO cartão');
    END IF;            

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'TIPTITMULTACART' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.TIPTITMULTACART - Tipo de título para multa DO cartão');
    END IF;            

    SELECT COUNT(*) INTO P_COUNT
    FROM TSIPAR 
    WHERE CHAVE = 'FATSERVTIT' AND INTEIRO = :NEW.CODTIPTIT;
    IF P_COUNT > 0 THEN
        RAISE_APPLICATION_ERROR(-20101,'Não pode inativar ! Está sendo usado no param.FATSERVTIT - Tipo de título padrão para faturamento de serviços');
    END IF;            
  END IF;            

END;

/
