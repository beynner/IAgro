-- SANKHYA.TRG_DLT_TGFTPV_AFTER
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGFTPV_AFTER
"SANKHYA".TRG_DLT_TGFTPV_AFTER
AFTER DELETE ON TGFTPV

DECLARE
  CURSOR DELETADAS IS SELECT CODTIPVENDA FROM TGFTPV_DLT;
  P_CODTIPVENDA        SMALLINT;
  P_COUNT              SMALLINT;
BEGIN
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
  
  OPEN DELETADAS;
  DELETE FROM TGFTPV_DLT;
  LOOP
     FETCH DELETADAS INTO P_CODTIPVENDA;
     EXIT WHEN DELETADAS%NOTFOUND;

     SELECT COUNT(1) INTO P_COUNT
     FROM TGFTPV
     WHERE CODTIPVENDA = P_CODTIPVENDA;
     IF P_COUNT = 0 THEN
        
        EXISTSRESTRICAO('TGFTPV',P_CODTIPVENDA);
            
        SELECT COUNT(1) INTO P_COUNT
        FROM TCSCON
        WHERE CODTIPVENDA = P_CODTIPVENDA;
        IF P_COUNT <> 0 THEN
           RAISE_APPLICATION_ERROR(-20101, 'Existe referência no cadastro de contratos !');
        END IF;

        SELECT COUNT(1) INTO P_COUNT
        FROM TGFIAC
        WHERE CODTIPVENDA = P_CODTIPVENDA;
        IF P_COUNT <> 0 THEN
           RAISE_APPLICATION_ERROR(-20101, 'Existe referência nos Itens dos Acordos p/Pedido Eletrônico !');
        END IF;

        SELECT COUNT(1) INTO P_COUNT
        FROM TGFCPL
        WHERE SUGTIPNEGENTR = P_CODTIPVENDA;
        IF (P_COUNT<>0) THEN
           RAISE_APPLICATION_ERROR(-20101, 'Registro não pode ser excluído, existe uma referencia no complemento de parceiros, para sugestão do tipo de negociação em compras.');
        END IF;

        SELECT COUNT(1) INTO P_COUNT
        FROM TGFCPL
        WHERE SUGTIPNEGSAID = P_CODTIPVENDA;
        IF (P_COUNT<>0) THEN
           RAISE_APPLICATION_ERROR(-20101, 'Registro não pode ser excluído, existe uma referencia no complemento de parceiros, para sugestão do tipo de negociação em saídas.');
        END IF;
    
        SELECT COUNT(1) INTO P_COUNT
        FROM TGAINS
        WHERE CODTIPVENDA = P_CODTIPVENDA;
        IF P_COUNT <> 0 THEN
           RAISE_APPLICATION_ERROR(-20101, 'Existe referência na TGAINS !');
        END IF;
    
     END IF;
  END LOOP;
  CLOSE DELETADAS;

  /* deleção em cascata para as parcelas de pagamento se não existe mais nenhuma
  TPV com o número deletado */
  DELETE FROM TGFPPG WHERE NOT EXISTS (SELECT DISTINCT CODTIPVENDA FROM TGFTPV WHERE CODTIPVENDA = TGFPPG.CODTIPVENDA);
END;

/
