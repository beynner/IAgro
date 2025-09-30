-- SANKHYA.TRG_DEL_TFPAVI_REQ
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DEL_TFPAVI_REQ
"SANKHYA".TRG_DEL_TFPAVI_REQ
   BEFORE DELETE
   ON TFPAVI
   FOR EACH ROW

DECLARE
   P_COUNT   INTEGER;
BEGIN
   SELECT COUNT (1)
     INTO P_COUNT
     FROM TFPREQRESC
    WHERE ID IN
             (SELECT ORIGEMID
                FROM TFPREQ
               WHERE     ORIGEMTIPO = 'R'
                     AND STATUS NOT IN (-2, 3)
                     AND CAST (
                               CAST (:OLD.CODEMP AS VARCHAR2 (20))
                            || ':'
                            || CAST (:OLD.CODFUNC AS VARCHAR2 (20)) AS VARCHAR2 (20)) =
                            CAST (
                                  CAST (CODEMP AS VARCHAR2 (20))
                               || ':'
                               || CAST (CODFUNC AS VARCHAR2 (20)) AS VARCHAR2 (20)));

   IF P_COUNT > 0
   THEN
      RAISE_APPLICATION_ERROR (
         -20101,
         'Há requisição de rescisão para registro que está sendo deletado. Reprove ou cancele a requisição e tente novamente!!!');
   END IF;
END;

/
