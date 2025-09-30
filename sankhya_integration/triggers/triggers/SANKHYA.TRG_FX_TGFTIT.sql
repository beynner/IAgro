-- SANKHYA.TRG_FX_TGFTIT
CREATE OR REPLACE TRIGGER SANKHYA.TRG_FX_TGFTIT
"SANKHYA".TRG_FX_TGFTIT
	BEFORE INSERT OR UPDATE OR DELETE
	ON TGFTIT
	FOR EACH ROW

DECLARE
	P_CONT_TFXBPA		NUMBER (19);
	P_CONT_TGFTIT_OLD	NUMBER (19);
	P_TEM_CHECKOUT 		BOOLEAN;
  
	PRAGMA AUTONOMOUS_TRANSACTION;
BEGIN			
 
 P_TEM_CHECKOUT := FCheckout_Utiliza;
	
   IF (NOT P_TEM_CHECKOUT) THEN
	  RETURN;
   END IF;	
	-- caso insercao
	IF INSERTING THEN
			IF(:NEW.SUBTIPOVENDA IN (7, 8, 9) 
				AND NVL(:NEW.FISCAL, ' ') <> ' '
				AND :NEW.FASTUSA = 'S') THEN
				SELECT COUNT (1)
				  INTO P_CONT_TFXBPA
				  FROM TFXBPA
				 WHERE SUBTIPOVENDA = :NEW.SUBTIPOVENDA
				   AND FISCAL = :NEW.FISCAL
				   AND EHPOS = :NEW.UTILIZAPOS;
				IF (NVL(P_CONT_TFXBPA, 0) = 0) THEN
					INSERT INTO TFXBPA 
					 (FISCAL, 
					  SUBTIPOVENDA, 
					  CODPARCTEF, 
					  EHPOS)
					VALUES (
					    :NEW.FISCAL, 
						:NEW.SUBTIPOVENDA, 
						:NEW.CODPARCTEF, 
						:NEW.UTILIZAPOS);
				END IF;
			END IF;
		COMMIT;
	END IF;
	-- caso atualizacao
	IF UPDATING THEN
		IF(:NEW.SUBTIPOVENDA IN (7, 8, 9) 
			AND NVL(:NEW.FISCAL, ' ') <> ' '
			AND :NEW.FASTUSA = 'S') THEN 
			SELECT COUNT (1)
			  INTO P_CONT_TFXBPA
			  FROM TFXBPA
			 WHERE SUBTIPOVENDA = :NEW.SUBTIPOVENDA
			   AND FISCAL = :NEW.FISCAL
			   AND EHPOS = :NEW.UTILIZAPOS;	
			   
			IF (NVL(P_CONT_TFXBPA, 0) > 0) THEN
				-- verificando se existe TIT com informacoes antigas
				-- para preservar os dependentes relacionados
				SELECT COUNT (1)
				  INTO P_CONT_TGFTIT_OLD
				  FROM TGFTIT
				  WHERE SUBTIPOVENDA = :OLD.SUBTIPOVENDA
					AND FISCAL = :OLD.FISCAL
					AND UTILIZAPOS = :OLD.UTILIZAPOS;
				IF (NVL(P_CONT_TGFTIT_OLD, 0) <= 1) THEN
						DELETE FROM TFXBPA
							  WHERE SUBTIPOVENDA = :OLD.SUBTIPOVENDA
								AND FISCAL = :OLD.FISCAL
								AND EHPOS = :OLD.UTILIZAPOS;
				END IF;
				-- para evitar diversas verificacoes nos valores alterados
				-- sera deletado o objeto existente e criado um novo
				DELETE FROM TFXBPA
					  WHERE SUBTIPOVENDA = :NEW.SUBTIPOVENDA
					    AND FISCAL = :NEW.FISCAL
					    AND EHPOS = :NEW.UTILIZAPOS;
				-- inserindo nova linha
				INSERT INTO TFXBPA 
					(FISCAL, 
					 SUBTIPOVENDA, 
					 CODPARCTEF, 
					 EHPOS)
				VALUES (
					:NEW.FISCAL,
					:NEW.SUBTIPOVENDA,
					:NEW.CODPARCTEF,
					:NEW.UTILIZAPOS);
			ELSE
				-- inserindo novos elementos caso nao existam
				INSERT INTO TFXBPA 
					(FISCAL, 
					 SUBTIPOVENDA, 
					 CODPARCTEF, 
					 EHPOS)
				VALUES (
					:NEW.FISCAL,
					:NEW.SUBTIPOVENDA,
					:NEW.CODPARCTEF,
					:NEW.UTILIZAPOS);
			END IF;
		-- caso o titulo nao mais cumpra com os requisitos
		-- sera verificado se ainda existe algum pai na tabela TIT
		-- e caso nao exista sera excluido os remanescentes na BPA
    ELSE
			SELECT COUNT (1)
			  INTO P_CONT_TGFTIT_OLD
			  FROM TGFTIT
			 WHERE SUBTIPOVENDA = :OLD.SUBTIPOVENDA
			   AND FISCAL = :OLD.FISCAL
			   AND UTILIZAPOS = :OLD.UTILIZAPOS
			   AND SUBTIPOVENDA IN (7,8,9)
			   AND NVL(FISCAL, ' ') <> ' '
			   AND FASTUSA = 'S';
			IF (NVL (P_CONT_TGFTIT_OLD, 0) <= 1) THEN
				DELETE FROM TFXBPA
				 WHERE SUBTIPOVENDA = :OLD.SUBTIPOVENDA 
				   AND FISCAL = :OLD.FISCAL
				   AND EHPOS = :OLD.UTILIZAPOS;
			END IF;
		END IF;
	  COMMIT;
	END IF;
	-- caso exclusao
	IF DELETING THEN	
		IF(:OLD.SUBTIPOVENDA IN (7, 8, 9)  
			AND :OLD.FASTUSA = 'S') THEN
			SELECT COUNT (1)
			  INTO P_CONT_TGFTIT_OLD
			  FROM TGFTIT
            WHERE SUBTIPOVENDA = :OLD.SUBTIPOVENDA
			  AND FISCAL = :OLD.FISCAL
			  AND UTILIZAPOS = :OLD.UTILIZAPOS;
                IF (NVL (P_CONT_TGFTIT_OLD, 0) <= 1) THEN
                    DELETE FROM TFXBPA
                     WHERE SUBTIPOVENDA = :OLD.SUBTIPOVENDA 
                       AND FISCAL = :OLD.FISCAL
                       AND EHPOS = :OLD.UTILIZAPOS;
                END IF;
		END IF;
      COMMIT;
	END IF;
END;

/
