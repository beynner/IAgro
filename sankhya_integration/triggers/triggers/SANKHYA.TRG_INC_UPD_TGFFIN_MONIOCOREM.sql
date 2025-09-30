-- SANKHYA.TRG_INC_UPD_TGFFIN_MONIOCOREM
CREATE OR REPLACE TRIGGER SANKHYA.TRG_INC_UPD_TGFFIN_MONIOCOREM
TRG_INC_UPD_TGFFIN_MONIOCOREM
   BEFORE INSERT OR UPDATE OR DELETE
   ON TGFFIN
   FOR EACH ROW

DECLARE
   P_COUNT                   INT               := 0;
   P_TEMPERMISSAO            INT               := 0;
   P_CONTROLAPERMISSAO       INT               := 0;
   P_OCORRENCIA_ENTRADA_NEW  VARCHAR2(15 Byte) := NULL;
   P_OCORRENCIA_BAIXA        VARCHAR2(15 Byte) := NULL;
   P_OCORRENCIA_EXCLUSAO     VARCHAR2(15 Byte) := NULL;
   P_TROCANDO_CONTA          BOOLEAN           := NVL(:OLD.CODCTABCOINT, 0) <> NVL(:NEW.CODCTABCOINT, 0);
   P_DELETANDO               BOOLEAN           := NOT INSERTING AND NOT UPDATING;
   P_TITULO_MONITORADO       BOOLEAN           := :OLD.MONIOCOREM = 'S' OR :NEW.MONIOCOREM = 'S';
   P_GERANDO_REMESSA         BOOLEAN           := FALSE;
   P_IGNORE_OCORR_BAIXA      BOOLEAN           := FALSE;
   P_NUREMESSA               INT               := NULL;
   P_USA_CONTA_BAIXA        CHAR(1);
   ERRMSG                   VARCHAR2(4000);
   ERROR                    EXCEPTION;
   P_VALIDAR                BOOLEAN;
   P_TIPO_ENVIO             CHAR(1)            := 'R';
   P_DESC_CONTA             VARCHAR2(255);
   P_COD_CTA                VARCHAR2(255);
   EXIST_ITEM_RAF           INT                := 0;  
   IS_CONTA_MONITARADA      INT                := 0;
   COUNT_TIPO_API           INT                := 0;
   TIPO_ENVIO_API           CHAR(1)            := 'A';
  
BEGIN

   IF STP_GET_ATUALIZANDO
   THEN
      RETURN;
   END IF;
   
   P_VALIDAR := Fpodevalidar('TGFFIN'); -- sincronização de dados
   
   P_USA_CONTA_BAIXA := VARIAVEIS_PKG.V_USA_CONTA_BAIXA;
    
    --NAO MONITORAR DESPESAS
    IF NVL(:NEW.RECDESP,0) = -1 OR NVL(:OLD.RECDESP,0) = -1 OR (NVL(:NEW.RECDESP,-99) = 0 AND :NEW.PROVISAO = 'N' AND :NEW.NURENEG IS NULL) THEN
       RETURN;
    END IF;
    
   P_GERANDO_REMESSA := VARIAVEIS_PKG.V_GERANDO_REMESSA;
   P_IGNORE_OCORR_BAIXA := VARIAVEIS_PKG.V_IGNORE_OCORR_BAIXA;
  
   BEGIN
	  SELECT COUNT(1) INTO EXIST_ITEM_RAF FROM TGFRAF R WHERE R.NUFIN = :NEW.NUFIN;
   END;
 
   BEGIN
	  SELECT COUNT(1) INTO IS_CONTA_MONITARADA FROM TSICTA CTA WHERE CTA.CODCTABCOINT = :OLD.CODCTABCOINT AND CTA.IDAPIBANCO IS NOT NULL AND CTA.STATUSAPI='S';
   END;

    --BUSCA OCORRENCIA DE ENTRADA
   BEGIN
      SELECT C.OCORRENCIA_ENTRADA, C.OCORRENCIA_BAIXA INTO P_OCORRENCIA_ENTRADA_NEW, P_OCORRENCIA_BAIXA
      FROM TGFCRAF C 
      WHERE C.CODCTABCOINT = :NEW.CODCTABCOINT;
      EXCEPTION 
      WHEN NO_DATA_FOUND THEN
      P_OCORRENCIA_ENTRADA_NEW := NULL;
      P_OCORRENCIA_BAIXA := NULL;
   END;
   
 
   BEGIN
      SELECT C.OCORRENCIA_EXCLUSAO INTO P_OCORRENCIA_EXCLUSAO
      FROM TGFCRAF C 
      WHERE C.CODCTABCOINT = :OLD.CODCTABCOINT;
      EXCEPTION 
      WHEN NO_DATA_FOUND THEN
      P_OCORRENCIA_EXCLUSAO := NULL;
   END;
  
   BEGIN
	   IF(IS_CONTA_MONITARADA > 0) THEN
		    SELECT
				NVL( CTA.TIPOAPIBOLETO, 'R' ) AS TIPOENVIO,
				CTA.CODCTABCO,
				CTA.DESCRICAO INTO P_TIPO_ENVIO,P_COD_CTA,P_DESC_CONTA 
			FROM
				TSICTA CTA
			WHERE
				CTA.CODCTABCOINT = :OLD.CODCTABCOINT AND CTA.IDAPIBANCO IS NOT NULL AND CTA.STATUSAPI='S';
		END IF;
   END;

    IF((P_DELETANDO OR P_TROCANDO_CONTA OR (UPDATING('PROVISAO') AND :OLD.PROVISAO = 'N' AND :NEW.PROVISAO = 'S')) AND P_TITULO_MONITORADO) THEN

        SELECT
            COUNT(1) INTO P_COUNT
        FROM
            TGFRAF R
        WHERE
            R.NUFIN = :OLD.NUFIN
            AND EXISTS(SELECT 1 FROM TGFCRAF C WHERE C.CODCTABCOINT = :OLD.CODCTABCOINT AND C.OCORRENCIA_ENTRADA = R.OCORRENCIA)
            AND NUREMESSA IS NOT NULL
            AND TIPO='E'
            AND SEQUENCIA=(SELECT MAX(SEQUENCIA) 
                           FROM TGFRAF 
                           WHERE NUFIN=:OLD.NUFIN AND
                                 TIPO='E');
            
        IF(P_COUNT > 0) THEN
            IF(P_DELETANDO) THEN
                IF P_OCORRENCIA_EXCLUSAO IS NOT NULL THEN
                  UPDATE TGFRAF SET STATUS='X' WHERE NUFIN=:OLD.NUFIN AND ((TIPO='A' AND NUREMESSA IS NULL) OR TIPO='E');
                  
                  INSERT INTO 
                            TGFRAF (NUFIN,SEQUENCIA,NUREMESSA,CODUSU,DTALTER,CAMPO,STATUS,OCORRENCIA,TIPO,TIPOENVIO)
                        VALUES 
                            (:OLD.NUFIN, (SELECT NVL(MAX(SEQUENCIA),0)+1 FROM TGFRAF WHERE NUFIN=:OLD.NUFIN), NULL, STP_GET_CODUSULOGADO, SYSDATE, ' ', 'A', P_OCORRENCIA_EXCLUSAO, 'X', P_TIPO_ENVIO);
                  RETURN; --APOS INSERIR TGFRAF DE EXCLUSAO TENHO QUE SAIR DA TRIGGER 
                ELSE
                    ERRMSG := '<br><br><b>O título ' || :NEW.NUFIN ||' está em cobrança registrada e não pode ser excluído. Para excluir, registrar a exclusão do título pela tela "Registro de Alteração Financeiro"</b><br>';
                    RAISE ERROR;
                END IF;
            ELSE IF(P_TROCANDO_CONTA) THEN
                            IF (NVL(P_USA_CONTA_BAIXA, 'N') = 'N' AND NOT(P_TIPO_ENVIO = 'B')) THEN
                                ERRMSG := '<br><br><b>O título ' ||:NEW.NUFIN ||' está em cobrança registrada e a Conta não pode ser alterada. Caso haja necessidade este título deve ser renegociado.</b><br>';
                                RAISE ERROR;
                            END IF;
                    ELSE 
                            ERRMSG := '<br><br><b>O título ' ||:NEW.NUFIN ||' está em cobrança registrada, portanto não pode ser transformado em provisão.</b><br>';
                            RAISE ERROR; 
                END IF;
            END IF;
        ELSE 
            DELETE FROM TGFRAF WHERE NUFIN = :OLD.NUFIN;
   			EXIST_ITEM_RAF := 0  ;
            IF(P_DELETANDO) THEN 
                --ACABA POR AQUI NO CASO DELETE
                RETURN;
            ELSE
                :NEW.MONIOCOREM := 'N';
            END IF;
        END IF;  
    END IF;   
             
   --INSERT ou TROCA DE CONTA ou DESMARCANDO PROVISAO ou 'TROCANDO RECDESP DE 0 PRA 1 E NAO É DESFAZIMENTO DE RENEGOCIACOES'
     IF(:NEW.PROVISAO = 'N' AND :NEW.RECDESP = 1
     AND  (INSERTING 
      	OR P_TROCANDO_CONTA 
      	OR (UPDATING('PROVISAO') AND :OLD.PROVISAO = 'S') 
      	OR (UPDATING('RECDESP') AND :OLD.RECDESP = 0 AND NOT (:OLD.NURENEG IS NOT NULL AND (:NEW.NURENEG IS NULL OR (:NEW.NURENEG IS NOT NULL AND :OLD.NURENEG <> :NEW.NURENEG)))))) --ESTE TRECHO EVITA ENTRAR AQUI QUANDO ESTOU DESFAZENDO RENEGOCIACAO, EXISTE UM TRECHO SO PRA ISSO MAIS ADIANTE. 
     THEN
        IF(P_OCORRENCIA_ENTRADA_NEW IS NOT NULL) THEN
            :NEW.MONIOCOREM := 'S';
            
            IF(P_GERANDO_REMESSA) THEN
                P_NUREMESSA := :NEW.NUMREMESSA;
            END IF;
           
            IF (EXIST_ITEM_RAF = 0) THEN
			  	TIPO_ENVIO_API := 'A';
            	SELECT COUNT(1) INTO COUNT_TIPO_API FROM TSICTA WHERE CODCTABCOINT = :NEW.CODCTABCOINT AND STATUSAPI = 'S';
            	
            	IF(COUNT_TIPO_API = 0) THEN
                	TIPO_ENVIO_API := 'E';
            	END IF;			

	            INSERT INTO 
	                TGFRAF (NUFIN,SEQUENCIA,NUREMESSA,CODUSU,DTALTER,CAMPO,STATUS,OCORRENCIA,TIPO,TIPOENVIO)
	            VALUES 
	                (:NEW.NUFIN,1,P_NUREMESSA,STP_GET_CODUSULOGADO,SYSDATE,' ','A', P_OCORRENCIA_ENTRADA_NEW,'E',TIPO_ENVIO_API);
           END IF;    
        END IF;
        RETURN; 
    END IF;

    -- SE O TITULO TEM O REGISTRO DE ENTRADA ENVIADO (NUREMESSA PREENCHIDO) E NAO TEM REGISTRO DE BAIXA NEM DE EXCLUSAO, PRECISO INSERIR MONITORAMENTOS E VALIDAR PERMISSOES DE ALTERACAO
    SELECT
        COUNT(1) INTO P_COUNT
    FROM
        TGFRAF
    WHERE
        NUFIN=:NEW.NUFIN
        AND NUREMESSA IS NOT NULL
        AND CAMPO = ' '
        AND OCORRENCIA=P_OCORRENCIA_ENTRADA_NEW
        AND TIPO='E'
        AND SEQUENCIA = (SELECT MAX(SEQUENCIA) 
                         FROM TGFRAF 
                         WHERE NUFIN=:NEW.NUFIN AND 
                               TIPO='E')
        AND NOT EXISTS (SELECT 1 
                            FROM TGFRAF 
                            WHERE NUFIN = :NEW.NUFIN
                              AND TIPO IN ('B','X')
                              AND SEQUENCIA > (SELECT MAX(SEQUENCIA) 
                                               FROM TGFRAF 
                                               WHERE NUFIN=:NEW.NUFIN AND 
                                                     TIPO='E'));

    IF(P_COUNT > 0 
       AND :NEW.DHBAIXA IS NULL AND :OLD.DHBAIXA IS NULL
       AND NOT (:OLD.RECDESP <> 0 AND :NEW.RECDESP = 0 AND -- NAO (NOT) RENEGOCIANDO
               ((:OLD.NURENEG IS NULL AND :NEW.NURENEG IS NOT NULL) 
                 OR
                (:OLD.NURENEG <> :NEW.NURENEG)))) THEN
        --PARA CADA CAMPO QUE EU MONITORO, VERIFICO SE EXISTE CONFIGURACAO DE PERMISSAO, SE NAO EXISTIR QUALQUER PESSOA PODE ALTERAR
        --SE EXISTIR VERIFICO SE O USUARIO TEM PERMISSAO, SE NAO TIVER BARRO A EDICAO.
        --QUANDO PERMITO EDITAR É REGISTRADO OU ATUALIZADO UM LOG NA TGFRAF
       DECLARE
          CURSOR curCampos IS
             SELECT
                O.NOMECAMPO,
                O.OCORRENCIA
             FROM
                TGFCRAF C
                INNER JOIN TGFOAF O ON O.NUCRAF = C.NUCRAF
             WHERE
                C.CODCTABCOINT = :NEW.CODCTABCOINT
             ORDER BY 
                O.NOMECAMPO DESC;
          registro curCampos%ROWTYPE;
       BEGIN
	      OPEN curCampos;
          LOOP
             FETCH curCampos INTO registro;
             EXIT WHEN curCampos%NOTFOUND;
            
             IF (UPDATING (registro.NOMECAMPO)) THEN
                SELECT
                    COUNT(1) INTO P_CONTROLAPERMISSAO
                FROM
                    TGFCRAF C
                    INNER JOIN TGFOAF O ON O.NUCRAF = C.NUCRAF
                    INNER JOIN TGFPPO P ON P.NUCRAF = C.NUCRAF AND P.SEQUENCIA = O.SEQUENCIA
                WHERE
                    C.CODCTABCOINT = :NEW.CODCTABCOINT
                    AND O.NOMECAMPO = registro.NOMECAMPO;

                IF (P_CONTROLAPERMISSAO > 0) THEN
                    SELECT
                        COUNT(1) INTO P_TEMPERMISSAO
                    FROM
                        TGFCRAF C
                        INNER JOIN TGFOAF O ON O.NUCRAF = C.NUCRAF
                        INNER JOIN TGFPPO P  ON P.NUCRAF = C.NUCRAF AND P.SEQUENCIA = O.SEQUENCIA
                    WHERE
                        C.CODCTABCOINT = :NEW.CODCTABCOINT
                        AND O.NOMECAMPO = registro.NOMECAMPO
                        AND P.CODUSU = STP_GET_CODUSULOGADO;

                    IF (P_TEMPERMISSAO = 0) THEN
                        ERRMSG := '<br><br><b>Alteração não permitida para esse usuário pois o titulo é de cobrança registrada.</b><br>';
                        RAISE ERROR;
                    END IF;
                END IF;
                    
                SELECT 
                    COUNT(1) INTO P_COUNT
                FROM
                    TGFRAF 
                WHERE
                    NUFIN=:NEW.NUFIN
                    AND CAMPO = registro.NOMECAMPO
                    AND OCORRENCIA=registro.OCORRENCIA
                    AND STATUS = 'A'
                    AND TIPO = 'A'
                    AND SEQUENCIA = (SELECT MAX(SEQUENCIA) 
                                     FROM TGFRAF 
                                     WHERE NUFIN=:NEW.NUFIN AND 
                                           TIPO='A' AND 
                                           CAMPO = registro.NOMECAMPO);
                    
                IF(P_COUNT > 0) THEN --SE JA EXISTIR A LINHA FACO UPDATE
                    UPDATE
                        TGFRAF
                    SET 
                        DTALTER=SYSDATE,
                        CODUSU=STP_GET_CODUSULOGADO
                    WHERE
                        NUFIN=:NEW.NUFIN 
                        AND CAMPO = registro.NOMECAMPO 
                        AND OCORRENCIA=registro.OCORRENCIA
                        AND SEQUENCIA = (SELECT MAX(SEQUENCIA) 
                                     FROM TGFRAF 
                                     WHERE NUFIN=:NEW.NUFIN AND 
                                           TIPO='A' AND 
                                           CAMPO = registro.NOMECAMPO);
                            
                ELSE --SE NAO EXISTIR A LINHA EU A CRIO
                    INSERT INTO 
                        TGFRAF (NUFIN,SEQUENCIA,NUREMESSA,CODUSU,DTALTER,CAMPO,STATUS,OCORRENCIA,TIPO,TIPOENVIO)
                    VALUES
                        (:NEW.NUFIN, (SELECT NVL(MAX(SEQUENCIA),0)+1 FROM TGFRAF WHERE NUFIN=:NEW.NUFIN), NULL, STP_GET_CODUSULOGADO, SYSDATE, registro.NOMECAMPO, 'A', registro.OCORRENCIA, 'A', P_TIPO_ENVIO);
                END IF;
             END IF;
          END LOOP;
          CLOSE curCampos;
       END;  
    ELSE IF ((:OLD.DHBAIXA IS NULL AND :NEW.DHBAIXA IS NOT NULL) --BAIXANDO
            OR
             (:OLD.RECDESP <> 0 AND :NEW.RECDESP = 0 AND --RENEGOCIAÇÃO
             ((:OLD.NURENEG IS NULL AND :NEW.NURENEG IS NOT NULL) --PRIMEIRA RENEGOCIAÇÃO
               OR
             (:OLD.NURENEG <> :NEW.NURENEG)))) --RENEGOCIAÇÃO DE TITULOS JA RENEGOCIADOS
         THEN 
                UPDATE TGFRAF 
                SET STATUS=(CASE WHEN NVL(:NEW.NURENEG, 0) <> 0 THEN 'R' ELSE 'B' END)
                WHERE NUFIN=:NEW.NUFIN AND
                    ((TIPO='A' AND NUREMESSA IS NULL) OR
                     (TIPO='E' AND SEQUENCIA=(SELECT MAX(SEQUENCIA) 
                                            FROM TGFRAF 
                                            WHERE NUFIN=:NEW.NUFIN AND 
                                                  TIPO='E'))
                    );
                          
              P_COUNT := 0;
              
              SELECT COUNT(1) INTO P_COUNT
                      FROM TGFRAF
                      WHERE NUFIN = :NEW.NUFIN
                        AND NUREMESSA IS NOT NULL
                        AND CAMPO = ' '
                        AND OCORRENCIA = P_OCORRENCIA_ENTRADA_NEW 
                        AND TIPO='E'
                        AND SEQUENCIA=(SELECT MAX(SEQUENCIA) 
                                       FROM TGFRAF 
                                       WHERE NUFIN=:NEW.NUFIN AND 
                                             TIPO='E');
                        
                IF(P_COUNT > 0 AND NOT(P_IGNORE_OCORR_BAIXA)) THEN
                  INSERT INTO 
                        TGFRAF (NUFIN,SEQUENCIA,NUREMESSA,CODUSU,DTALTER,CAMPO,STATUS,OCORRENCIA,TIPO,TIPOENVIO)
                  VALUES 
                        (:NEW.NUFIN, (SELECT NVL(MAX(SEQUENCIA),0)+1 FROM TGFRAF WHERE NUFIN=:NEW.NUFIN), NULL, STP_GET_CODUSULOGADO, SYSDATE, ' ', 'A', P_OCORRENCIA_BAIXA, 'B', P_TIPO_ENVIO);
                END IF;
         ELSE
            IF (:OLD.DHBAIXA IS NOT NULL AND :NEW.DHBAIXA IS NULL)--ESTORNO
              OR
               (:OLD.NURENEG IS NOT NULL AND 
               (:NEW.NURENEG IS NULL OR (:NEW.NURENEG IS NOT NULL AND :OLD.NURENEG <> :NEW.NURENEG)) AND 
                :OLD.RECDESP = 0 AND :NEW.RECDESP = 1) -- DESFAZENDO RENEGOCIACAO  
            THEN 
                P_COUNT := 0;
                
                SELECT COUNT(1) INTO P_COUNT 
                FROM TGFRAF 
                WHERE NUFIN = :NEW.NUFIN 
                  AND TIPO IN ('B')
                  AND NUREMESSA IS NOT NULL
                  AND SEQUENCIA=(SELECT MAX(SEQUENCIA) 
                                 FROM TGFRAF 
                                 WHERE NUFIN=:NEW.NUFIN);
                                 
                IF P_COUNT > 0 THEN
                   INSERT INTO 
                      TGFRAF (NUFIN,SEQUENCIA,NUREMESSA,CODUSU,DTALTER,CAMPO,STATUS,OCORRENCIA,TIPO,TIPOENVIO)
                   VALUES 
                     (:NEW.NUFIN,(SELECT NVL(MAX(SEQUENCIA),0)+1 FROM TGFRAF WHERE NUFIN=:NEW.NUFIN),NULL,STP_GET_CODUSULOGADO(),SYSDATE,' ','A', P_OCORRENCIA_ENTRADA_NEW,'E', P_TIPO_ENVIO);

                   :NEW.NUMREMESSA := NULL;
                ELSE
                
                  UPDATE TGFRAF 
                  SET STATUS='A'
                  WHERE NUFIN=:NEW.NUFIN AND
                  ((TIPO='A' AND NUREMESSA IS NULL) OR
                   (TIPO='E' AND SEQUENCIA=(SELECT MAX(SEQUENCIA) 
                                            FROM TGFRAF 
                                            WHERE NUFIN=:NEW.NUFIN AND 
                                                  TIPO='E'))
                  );
                  
                  DELETE TGFRAF 
                  WHERE NUFIN=:NEW.NUFIN AND
                        TIPO='B' AND
                        NUREMESSA IS NULL;
              
              END IF;  
            END IF;
            
         END IF;
    END IF;
EXCEPTION
  WHEN OTHERS THEN
    /*    Sincronização de dados não faz validações    */
     IF (P_VALIDAR) THEN
       IF SQLCODE <> 1 THEN
         ERRMSG := ERRMSG || '  ' || SQLERRM;
       END IF;
       RAISE_APPLICATION_ERROR(-20101, ERRMSG);       
     END IF;
END;

/
