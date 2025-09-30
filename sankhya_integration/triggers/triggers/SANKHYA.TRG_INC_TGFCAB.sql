-- SANKHYA.TRG_INC_TGFCAB
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_TGFCAB
TRG_INC_TGFCAB 
BEFORE INSERT ON TGFCAB FOR EACH ROW

DECLARE
       P_TIPRES            CHAR;
       P_UTILIZALOCAL      CHAR;
       P_TIPMOV            CHAR;
       P_CODPARC           NUMBER(10);
       P_CODTIPOPER        NUMBER(5);
       P_CODTIPVENDA       NUMBER(5);
       P_DHTIPVENDA        DATE;
       P_SOLICITANTE       VARCHAR2(30);
       P_COUNT             NUMBER(10) := 0;
       P_ATIVO             CHAR(1);
       P_MOTORISTA         CHAR(1);
       ERRMSG              VARCHAR2(500);
       ERROR               EXCEPTION;
       P_VALIDAR           BOOLEAN;
       P_PRODUETLOC        CHAR(1);
       P_TOP_ATIVO         CHAR(1);
       P_INDPRESNFCE       CHAR(1);
       P_INTERMED          VARCHAR2(1);
       P_CODINTERM         NUMBER(10);
       P_APELIDO           TGFVEN.APELIDO%TYPE;
       
      CURSOR CUR_TIPRES IS
      SELECT REP.TIPREST
       FROM TGFREP REP
      WHERE REP.CODTIPOPER = :NEW.CODTIPOPER AND REP.RESTRICAO = 'N'
        AND ((REP.TIPREST = 'E' AND REP.CODCOLREST = :NEW.CODEMP)
             OR (REP.TIPREST = 'A' AND REP.CODCOLREST = :NEW.CODPARC)
             OR (REP.TIPREST = 'V' AND REP.CODCOLREST = :NEW.CODVEND)
             OR (REP.TIPREST = 'T' AND REP.CODCOLREST = :NEW.CODTIPVENDA)
             OR (REP.TIPREST = 'N' AND REP.CODCOLREST = :NEW.CODNAT)
             OR (REP.TIPREST = 'C' AND REP.CODCOLREST = :NEW.CODCENCUS)
             OR (REP.TIPREST = 'S' AND REP.SERIE = :NEW.SERIENOTA) );
  BEGIN
  
  IF STP_GET_ATUALIZANDO THEN
    RETURN;
  END IF;
  /* 
  Sincronização de dados
  */    
    P_VALIDAR := Fpodevalidar('TGFCAB');
  
    IF (:NEW.TIPMOV <> 'Z') AND (:NEW.CODTIPOPER = 0) THEN
       ERRMSG := 'Campo TOP obrigatório para a nota de Nro Único:'||:NEW.NUNOTA||'';
     RAISE ERROR;
    END IF;

    IF (:NEW.CODTIPVENDA <> 0) AND (:NEW.TIPMOV IN ('T','R')) THEN
       ERRMSG := 'Campo Tipo de negociação deve ser 0 para a nota de Nro Único:'||:NEW.NUNOTA||'.';
       RAISE ERROR;
    END IF;

    IF (:NEW.CODTIPVENDA = 0) AND (:NEW.TIPMOV IN ('P','V','D')) THEN
       ERRMSG := 'Campo Tipo de negociação obrigatório para a nota de Nro Único:'||:NEW.NUNOTA||'.';
       RAISE ERROR;
    END IF;
    
    SELECT COUNT(1) INTO P_COUNT
    FROM TGFEMP E
    WHERE E.CODEMP = NVL(:NEW.CODEMP, 1)
      AND E.ATIVO = 'S';
    IF P_COUNT = 0 THEN
       ERRMSG := 'Empresa '||:NEW.CODEMP||' não está ativa para a nota de Nro Único:'||:NEW.NUNOTA||'.';
       RAISE ERROR;
    END IF;

    SELECT COUNT(1) INTO P_COUNT
    FROM TSICUS C
    WHERE C.CODCENCUS  = NVL(:NEW.CODCENCUS, 0)
      AND C.ATIVO = 'S' AND C.ANALITICO = 'S';
    IF P_COUNT = 0 THEN
      ERRMSG := 'Centro de Resultado '||:NEW.CODCENCUS||' não está ativa ou não é analítico. Nota de Nro Único: '||:NEW.NUNOTA||'.';
      RAISE ERROR;    
    END IF;

    SELECT COUNT(1) INTO P_COUNT
    FROM TGFEMP E
    WHERE E.CODEMP = NVL(:NEW.CODEMPNEGOC, 1)
      AND E.ATIVO = 'S';
    IF P_COUNT = 0 THEN
       ERRMSG := 'Empresa ' ||  TO_CHAR(:NEW.CODEMPNEGOC) || ' de negociação não está ativa para a nota de Nro Único:'||:NEW.NUNOTA||'.';
     RAISE ERROR;
    END IF;

     IF :NEW.CODVEICULO IS NOT NULL THEN
       Stp_Valida_Veiculo(:NEW.CODVEICULO);
     END IF;

    SELECT COUNT(1) INTO P_COUNT
    FROM TGFPAR P
    WHERE P.CODPARC = :NEW.CODPARC
      AND P.ATIVO = 'S';
    IF P_COUNT = 0 THEN
      ERRMSG := 'Parceiro: '|| TO_CHAR(:NEW.CODPARC) ||' não esta ativo. Nota de Nro Único:'||:NEW.NUNOTA;
     RAISE ERROR;
    END IF;

    SELECT COUNT(1) INTO P_COUNT
    FROM TGFPAR P
    WHERE P.CODPARC = :NEW.CODPARCTRANSP
      AND P.ATIVO = 'S';
    IF P_COUNT = 0 THEN
       ERRMSG := 'Transportadora ' || TO_CHAR(:NEW.CODPARCTRANSP) ||' não está ativa para a nota de Nro Único:'||:NEW.NUNOTA||'. ';
     RAISE ERROR;
    END IF;
    
    BEGIN
        SELECT COUNT(1) INTO P_COUNT
        FROM TGFVEN V
        WHERE V.CODVEND = :NEW.CODVEND
          AND V.ATIVO = 'S';
    EXCEPTION
          WHEN no_data_found 
          THEN
           ERRMSG := 'Vendedor: '|| :NEW.CODVEND || ' não existe no cadastro de vendedores, Nota de Nro Único:'|| :NEW.NUNOTA;
          RAISE ERROR;
    END;
      
    IF P_COUNT = 0 THEN
       SELECT APELIDO INTO P_APELIDO FROM TGFVEN WHERE CODVEND = :NEW.CODVEND;
       ERRMSG := 'Vendedor: '|| :NEW.CODVEND || ' - ' || P_APELIDO || ' não esta ativo, Nota de Nro Único:'|| :NEW.NUNOTA;
       RAISE ERROR;
    END IF;

    SELECT COUNT(1) INTO P_COUNT
    FROM TGFNAT N
    WHERE N.CODNAT = NVL(:NEW.CODNAT, 0)
      AND N.ATIVA = 'S' AND ANALITICA = 'S';
    IF P_COUNT = 0 THEN
      ERRMSG := 'Natureza '||:NEW.CODNAT||' não está ativa ou não é analítico. Nota de Nro Único:'|| :NEW.NUNOTA ||'.';
      RAISE ERROR;      
    END IF;
  
    IF :NEW.NUMCONTRATO <> 0 THEN
      SELECT COUNT(1) INTO P_COUNT
      FROM TCSCON C
      WHERE C.NUMCONTRATO = NVL(:NEW.NUMCONTRATO, 0)
        AND C.ATIVO = 'S';
      IF  P_COUNT = 0 THEN
        ERRMSG := 'Contrato'|| TO_CHAR(:NEW.NUMCONTRATO) ||' não esta ativo. Nota de Nro Único:'||:NEW.NUNOTA;
       RAISE ERROR;
      END IF;
  END IF;

    SELECT COUNT(1) INTO P_COUNT
    FROM TCSPRJ
    WHERE CODPROJ = :NEW.CODPROJ
      AND ATIVO = 'S' AND ANALITICO = 'S';
    IF P_COUNT = 0 THEN
      ERRMSG := 'Projeto '||:NEW.CODPROJ||' não esta ativo, não e analítico ou não existe.';
      RAISE_APPLICATION_ERROR (-20101, ERRMSG);
    END IF;

    SELECT ATIVO, TIPMOV, PRODUETLOC, INDPRESNFCE, INTERMED, CODINTERM
    INTO P_TOP_ATIVO, P_TIPMOV, P_PRODUETLOC, P_INDPRESNFCE, P_INTERMED, P_CODINTERM
    FROM TGFTOP
    WHERE CODTIPOPER = :NEW.CODTIPOPER
      AND DHALTER  = :NEW.DHTIPOPER;
    
    IF :NEW.INDPRESNFCE IS NULL THEN 
     :NEW.INDPRESNFCE := P_INDPRESNFCE;
    END IF;
    
    IF :NEW.INTERMED IS NULL THEN 
     :NEW.INTERMED := P_INTERMED;
    END IF;
    
    IF :NEW.CODINTERM IS NULL THEN 
     :NEW.CODINTERM := P_CODINTERM;
    END IF;
          
    IF (P_TOP_ATIVO <> 'S') THEN
       ERRMSG := 'Tipo de Operação '  || TO_CHAR(:NEW.CODTIPOPER) || ' não está ativo para a nota de Nro Único:'||:NEW.NUNOTA||'.' ;
       RAISE ERROR;
    END IF;
          
    IF (:NEW.TIPMOV <> 'Z') AND (P_TIPMOV <> :NEW.TIPMOV) THEN
        ERRMSG := 'Esta TOP '  || TO_CHAR(:NEW.CODTIPOPER) ||' não pode ser lançada nesta opção para a nota de Nro Único:'||:NEW.NUNOTA||'.' ;
        RAISE ERROR;
    END IF;


    IF (:NEW.CODCONTATO IS NOT NULL )THEN
       SELECT COUNT(1) INTO P_COUNT
       FROM TGFCTT
       WHERE CODPARC = :NEW.CODPARC
         AND CODCONTATO = :NEW.CODCONTATO
         AND ATIVO = 'S';
       IF  (P_COUNT = 0) THEN
           ERRMSG := 'Contato '||:NEW.CODCONTATO||' não está ativo para a nota de Nro Único:'||:NEW.NUNOTA||'.';
           RAISE ERROR;
       END IF;
    END IF;
    
        IF (:NEW.CODCONTATOENTREGA IS NOT NULL )THEN
       SELECT COUNT(1) INTO P_COUNT
       FROM TGFCTT
       WHERE CODPARC = :NEW.CODPARC
         AND CODCONTATO = :NEW.CODCONTATOENTREGA
         AND ATIVO = 'S';
       IF  (P_COUNT = 0) THEN
           ERRMSG := 'Contato '||:NEW.CODCONTATOENTREGA||' não está ativo para a nota de Nro Único:'||:NEW.NUNOTA||'.';
           RAISE ERROR;
       END IF;
    END IF;

    SELECT COUNT(1) INTO P_COUNT
    FROM TGFTPV
    WHERE :NEW.CODTIPVENDA = CODTIPVENDA
      AND :NEW.DHTIPVENDA = DHALTER
      AND ATIVO = 'S';
    IF (P_COUNT = 0) THEN
       ERRMSG := 'Verifique se o TIPO DE NEGOCIAÇÂO '  || TO_CHAR(:NEW.CODTIPVENDA)|| ' está ativo ou se sua data de alteração é menor ou igual a data de lançamento da nota de Nro Único:'||:NEW.NUNOTA||'.';
       RAISE ERROR;
    END IF;

    /* TESTA SE O ANO DIGITADO É VÁLIDO*/
    SELECT NVL(P.INTEIRO,0) INTO P_COUNT
    FROM TSIPAR P
    WHERE P.CHAVE = 'LIMSUPANO';
    
    IF P_COUNT > 100 THEN
      P_COUNT := 100;
    END IF;     
    
    IF  (P_COUNT <> 0)
                AND ( ( ( :NEW.DTMOV <> NULL )
                AND ( :NEW.DTMOV > ADD_MONTHS(SYSDATE, 12 * P_COUNT) ) )
                OR  ( ( :NEW.DTENTSAI <> NULL )
                AND ( :NEW.DTENTSAI > ADD_MONTHS(SYSDATE, 12 * P_COUNT) ) )
                OR  ( :NEW.DTNEG > ADD_MONTHS(SYSDATE, 12 * P_COUNT) ) 
      ) THEN
       ERRMSG := 'Ano superior ao limite permitido, na nota de Nro Único:'||:NEW.NUNOTA||', veja o parâmetro de limite superior para ano. ';
       RAISE ERROR;
    END IF;

    SELECT NVL(P.INTEIRO,0) INTO P_COUNT
    FROM TSIPAR P
    WHERE P.CHAVE = 'LIMINFANO';
    
    IF P_COUNT > 100 THEN
      P_COUNT := 100;
    END IF; 
    
    IF ( P_COUNT <> 0 )
                AND ( ( ( :NEW.DTMOV <> NULL )
                AND ( :NEW.DTMOV < ADD_MONTHS(SYSDATE, 12 * -P_COUNT) ) )
                OR  ( ( :NEW.DTENTSAI <> NULL )
                AND ( :NEW.DTENTSAI < ADD_MONTHS(SYSDATE, 12 * -P_COUNT) ) )
                OR  ( :NEW.DTNEG < ADD_MONTHS(SYSDATE, 12 * -P_COUNT) )  
      ) THEN
       ERRMSG := 'O ano é inferior ao limite permitido na nota de Nro. Único: '||:NEW.NUNOTA||'. Por favor, consulte o parâmetro LIMINFANO.';
       RAISE ERROR;
    END IF;

    IF :NEW.TIPMOV IN ('P','V') THEN
       SELECT COUNT(1) INTO P_COUNT
       FROM TGFPAR P,
            TGFTPV T
       WHERE P.CODPARC = :NEW.CODPARC
         AND T.CODTIPVENDA = :NEW.CODTIPVENDA
         AND T.DHALTER = :NEW.DHTIPVENDA
         AND P.PRAZOPAG = 0
         AND T.SUBTIPOVENDA <> '1'
         AND T.SUBTIPOVENDA <> '6'
         AND T.SUBTIPOVENDA <> '7'
         AND T.SUBTIPOVENDA <> '8'
         AND T.VALPRAZOCLIENTE = 'S';
      IF P_COUNT <> 0 THEN
        ERRMSG := 'PRAZO BLOQUEADO.';
        RAISE ERROR;
      END IF;

      SELECT COUNT(1) INTO P_COUNT
      FROM TGFPAR C,
      TGFTPV T
      WHERE :NEW.CODPARC = C.CODPARC
        AND :NEW.CODTIPVENDA = T.CODTIPVENDA
        AND :NEW.DHTIPVENDA = T.DHALTER
        AND C.BLOQUEAR = 'S'
        AND T.SUBTIPOVENDA <> '1'
        AND T.SUBTIPOVENDA <> '6'
        AND T.SUBTIPOVENDA <> '7'
        AND T.SUBTIPOVENDA <> '8';
      IF P_COUNT <> 0 THEN
        ERRMSG := 'Venda a prazo bloqueada para o parceiro ' || TO_CHAR(:NEW.CODPARC) || ' na nota de Nro Único:' ||:NEW.NUNOTA||'.';
        RAISE ERROR;
      END IF;

    /* valida se o parceiro da nota faz parte do grupo de alteração da Top */
      SELECT COUNT(1)  INTO P_COUNT
      FROM TGFTPV T, TGFPAR P
      WHERE :NEW.CODPARC = P.CODPARC 
      AND :NEW.CODTIPVENDA = T.CODTIPVENDA
      AND :NEW.DHTIPVENDA = T.DHALTER 
      AND T.GRUPOAUTOR > ''
      AND NOT (P.GRUPOAUTOR LIKE '%' || T.GRUPOAUTOR || '%');
      IF P_COUNT <> 0 THEN
        ERRMSG := 'Tipo de negociação ' || TO_CHAR(:NEW.CODTIPVENDA) || ' não autorizado para o cliente ' || TO_CHAR(:NEW.CODPARC) || '! Ver Grupo autorização.
        Nota de Nro. Único: ' ||TO_CHAR(:NEW.NUNOTA)||'.';
        RAISE ERROR;
      END IF;
    END IF;

    IF :NEW.CODPARC = 0 AND :NEW.TIPMOV IN ('O', 'C', 'E', 'P', 'V', 'D', 'S', 'M','1', '2', '3', '8', 'N') THEN
      SELECT COUNT(1) INTO P_COUNT
      FROM TGFPAR P
      WHERE P.CODPARC = :NEW.CODPARC;
      IF (P_COUNT <> 0) THEN
          ERRMSG := 'O parceiro deve ser diferente de zero na nota de Nro Único:'||:NEW.NUNOTA||'.';
          RAISE ERROR;
      END IF;
    END IF;
    
    IF :NEW.TIPMOV IN ('O', 'C', 'E') THEN 
      SELECT COUNT(1) INTO P_COUNT
      FROM TGFPAR P
      WHERE P.CODPARC = :NEW.CODPARC
      AND P.FORNECEDOR <> 'S';
      IF P_COUNT <> 0 THEN
        ERRMSG := 'O parceiro ' || TO_CHAR(:NEW.CODPARC) || ' deve ser um fornecedor na nota de Nro Único:'||:NEW.NUNOTA||'.';
        RAISE ERROR;
      END IF;  
    END IF;  
  
    IF :NEW.TIPMOV IN ('P', 'V', 'D','1', '2', '3', '8', 'N') THEN 
      SELECT COUNT(1) INTO P_COUNT
      FROM TGFPAR P
      WHERE P.CODPARC = :NEW.CODPARC
      AND P.CLIENTE <> 'S';
       IF P_COUNT <> 0 THEN
        ERRMSG := 'O parceiro ' || TO_CHAR(:NEW.CODPARC) || ' deve ser um cliente na nota de Nro Único:'||:NEW.NUNOTA||'.';
        RAISE ERROR;
      END IF;  
    END IF;  

    P_COUNT := 0;
   /*Validacao das restricoes do Tipo de Operacao (TGFRep) --*/
    OPEN CUR_TIPRES;
    LOOP
      FETCH CUR_TIPRES INTO
        P_TIPRES;
        EXIT WHEN CUR_TIPRES%NOTFOUND;

          IF (P_TIPRES = 'E') THEN
              ERRMSG := ERRMSG || 'Na nota de Nro Unico:'||:NEW.NUNOTA||', esta empresa ' || TO_CHAR(:NEW.CODEMP) || ' não pode ser usada com esta TOP.'  || TO_CHAR(:NEW.CODTIPOPER);
          ELSIF (P_TIPRES = 'A') THEN
              ERRMSG := ERRMSG || 'Na nota de Nro Unico:'||:NEW.NUNOTA||', este parceiro ' || TO_CHAR(:NEW.CODPARC) || ' não pode ser usado com esta TOP.' || TO_CHAR(:NEW.CODTIPOPER);
          ELSIF (P_TIPRES = 'V') THEN
              ERRMSG := ERRMSG || 'Nanota de Nro Unico:'||:NEW.NUNOTA||', este vendedor ' || TO_CHAR(:NEW.CODVEND) || ' não pode ser usado com esta TOP.' || TO_CHAR(:NEW.CODTIPOPER);
          ELSIF (P_TIPRES = 'T') THEN
              ERRMSG := ERRMSG || 'Na nota de Nro Unico:'||:NEW.NUNOTA||', este tipo de negociação ' || TO_CHAR(:NEW.CODTIPVENDA) || ' não pode ser usado com esta TOP.' || TO_CHAR(:NEW.CODTIPOPER);
          ELSIF (P_TIPRES = 'N') THEN
              ERRMSG := ERRMSG || 'Na nota de Nro Unico:'||:NEW.NUNOTA||', esta natureza ' || :NEW.CODNAT || ' não pode ser usada com esta TOP.' || TO_CHAR(:NEW.CODTIPOPER);
          ELSIF (P_TIPRES = 'C') THEN
              ERRMSG := ERRMSG || 'Na nota de Nro Unico:'||:NEW.NUNOTA||', este centro de resultado ' || :NEW.CODCENCUS || ' não pode ser usado com esta TOP.' || TO_CHAR(:NEW.CODTIPOPER);
          ELSIF (P_TIPRES = 'S') THEN
              ERRMSG := ERRMSG || 'Na nota de Nro Unico:'||:NEW.NUNOTA||', esta serie ' || :NEW.SERIENOTA ||' não pode ser usada com esta TOP.' || TO_CHAR(:NEW.CODTIPOPER);
              
          END IF;

          P_COUNT := P_COUNT + 1;

          ERRMSG := ERRMSG || '<br/><br/>';
    END LOOP;
    CLOSE CUR_TIPRES;
    
    IF P_COUNT > 0 THEN 
      RAISE ERROR;
    END IF;

    IF (:NEW.TIPMOV = 'T') AND (:NEW.CODEMP = :NEW.CODEMPNEGOC) THEN
       SELECT P.LOGICO INTO P_UTILIZALOCAL
         FROM TSIPAR P
        WHERE P.CHAVE = 'UTILIZALOCAL';
       IF (P_UTILIZALOCAL = 'N') THEN
        ERRMSG := 'Na nota de Nro Único:'||:NEW.NUNOTA||', empresa de destino ' || TO_CHAR(:NEW.CODEMPNEGOC) || ' deve ser diferente da empresa de origem.'  || TO_CHAR(:NEW.CODEMP);
      RAISE ERROR;
       END IF;
    END IF;

    IF (:NEW.CODMOTORISTA <> 0) THEN
       SELECT MOTORISTA, ATIVO INTO P_MOTORISTA, P_ATIVO
         FROM TGFPAR
        WHERE CODPARC = :NEW.CODMOTORISTA;
       IF (P_MOTORISTA <> 'S') THEN
           ERRMSG := 'Parceiro ' || TO_CHAR(:NEW.CODMOTORISTA) || ' não está marcado como Motorista na nota de Nro Único:'||:NEW.NUNOTA||'.';
           RAISE ERROR;
       END IF;

       IF (P_ATIVO <> 'S') THEN
           ERRMSG := 'Motorista ' || TO_CHAR(:NEW.CODMOTORISTA) || ' não está ativo na nota de Nro Único:'||:NEW.NUNOTA||'.';
           RAISE ERROR;
       END IF;
    END IF;
    
  IF NVL(:NEW.CODPARCDEST, 0) <> 0 AND NVL(:NEW.CODPARCREMETENTE, 0) <> 0 AND NVL(:NEW.CODCONTATOENTREGA, 0) <> 0 AND
    :NEW.TIPMOV IN ('V', 'C') AND GET_TSIPAR_LOGICO('USAPARREMDESCPA') = 'S' THEN
    ERRMSG := 'Contato de entrega não pode ser em venda ordem (Parceiro remetente e destinatário preenchidos).';
    RAISE ERROR;
  END IF; 

   :NEW.CODUSUINC := :NEW.CODUSU;
   
   IF (:NEW.TIPMOV = 'F') THEN    
    IF P_PRODUETLOC = 'S' THEN
      :NEW.PRODUETLOC := 'S';
    ELSE 
      :NEW.PRODUETLOC := 'N';
    END IF;
    ELSE
    :NEW.PRODUETLOC := 'N';
    END IF;
  
  :NEW.DTENTSAI := NVL(:NEW.DTENTSAI, :NEW.DTNEG);
   
   --LIMPANDO OS CAMPOS DA DUPLICAÇÃO DE NOTA E FATURAMENTO
   IF :NEW.STATUSNOTA <> 'L' THEN
      :NEW.CODCIDORIGEM := NULL;
      :NEW.CODCIDDESTINO := NULL;
      :NEW.CODCIDENTREGA  := NULL;
      :NEW.CODUFORIGEM := NULL;
      :NEW.CODUFDESTINO := NULL;
      :NEW.CODUFENTREGA  := NULL;
      :NEW.CLASSIFICMS := NULL;
   END IF;
   
      
   IF GET_TSIPAR_LOGICO('VALEMISNFEFORN') = 'S' THEN
   
    SELECT COUNT(1) INTO P_COUNT
    FROM TGFPAR
    WHERE CODPARC = :NEW.CODPARC
      AND DTEMISNFEFORN IS NOT NULL
      AND :NEW.DTNEG >= DTEMISNFEFORN
      AND :NEW.TIPMOV = 'C'  
      AND (NVL(:NEW.CODMODDOCNOTA, 0) = 55 OR 
           EXISTS(SELECT 1
                  FROM TGFTOP T
                  WHERE T.CODTIPOPER = :NEW.CODTIPOPER
                    AND T.DHALTER = :NEW.DHTIPOPER
                    AND T.CODMODDOC = 55
                    AND T.NFE = 'T'))
      AND NOT EXISTS(SELECT 1
                     FROM TGFIXN
                     WHERE NUNOTA = :NEW.NUNOTA);
 
      IF P_COUNT > 0 THEN
        ERRMSG := 'Fornecedor emissor de NF-e não pode ter a nota de compra digitada. Favor obter o XML da nota de compra e importa-lo no portal de importação de XML.';
        RAISE ERROR;
      END IF;      
   END IF;
   
   RETURN ;
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
