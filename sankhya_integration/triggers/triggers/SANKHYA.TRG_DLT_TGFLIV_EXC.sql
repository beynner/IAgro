-- SANKHYA.TRG_DLT_TGFLIV_EXC
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DLT_TGFLIV_EXC
"SANKHYA".TRG_DLT_TGFLIV_EXC 
AFTER DELETE ON TGFLIV FOR EACH ROW

DECLARE
  P_SOLICITANTE           VARCHAR2(255);
  P_NTUSERNAME            VARCHAR2(255);
  P_PROGRAMNAME           VARCHAR2(80);
BEGIN
  SELECT  SUBSTR(OSUSER,1,30), SUBSTR(MACHINE,1,64), PROGRAM  
  INTO P_NTUSERNAME, P_SOLICITANTE, P_PROGRAMNAME
  FROM V$SESSION
  WHERE AUDSID = USERENV('SESSIONID')
    AND ROWNUM = 1;

  INSERT INTO TGFLIV_EXC
  (
    NUNOTA               ,
    ORIGEM               ,
    SEQUENCIA            ,
    CODEMP               ,
    NUMNOTA              ,
    SERIENOTA            ,
    DTDOC                ,
    DHMOV                ,
    EMPPARC              ,
    CODPARC              ,
    CODCFO               ,
    NUMLANC              ,
    ESPDOC               ,
    CODTRIB              ,
    TIPICMS              ,
    BASEICMS             ,
    ALIQICMS             ,
    VLRICMS              ,
    ISENTASICMS          ,
    OUTRASICMS           ,
    BASERETENCAO         ,
    ICMSRETENCAO         ,
    TIPIPI               ,
    BASEIPI              ,
    ALIQIPI              ,
    VLRIPI               ,
    ISENTASIPI           ,
    OUTRASIPI            ,
    VLRCTB               ,
    CODCTACTB            ,
    DIGITADO             ,
    ENTSAI               ,
    DIFICMS              ,
    UFORIGEM             ,
    UFDESTINO            ,
    NUMNOTA2             ,
    GTOTECF              ,
    DTFILT               ,
    CODEMPORIG           ,
    CODMODDOC            ,
    DTEXCLUSAO           ,
    NT_USERNAME          ,
    HOSTNAME             ,
    PROGRAMA             ,
    CODUSU               ,
    DHALTER
 )
    VALUES
 (
    :OLD.NUNOTA               ,
    :OLD.ORIGEM               ,
    :OLD.SEQUENCIA            ,
    :OLD.CODEMP               ,
    :OLD.NUMNOTA              ,
    :OLD.SERIENOTA            ,
    :OLD.DTDOC                ,
    :OLD.DHMOV                ,
    :OLD.EMPPARC              ,
    :OLD.CODPARC              ,
    :OLD.CODCFO               ,
    :OLD.NUMLANC              ,
    :OLD.ESPDOC               ,
    :OLD.CODTRIB              ,
    :OLD.TIPICMS              ,
    :OLD.BASEICMS             ,
    :OLD.ALIQICMS             ,
    :OLD.VLRICMS              ,
    :OLD.ISENTASICMS          ,
    :OLD.OUTRASICMS           ,
    :OLD.BASERETENCAO         ,
    :OLD.ICMSRETENCAO         ,
    :OLD.TIPIPI               ,
    :OLD.BASEIPI              ,
    :OLD.ALIQIPI              ,
    :OLD.VLRIPI               ,
    :OLD.ISENTASIPI           ,
    :OLD.OUTRASIPI            ,
    :OLD.VLRCTB               ,
    :OLD.CODCTACTB            ,
    :OLD.DIGITADO             ,
    :OLD.ENTSAI               ,
    :OLD.DIFICMS              ,
    :OLD.UFORIGEM             ,
    :OLD.UFDESTINO            ,
    :OLD.NUMNOTA2             ,
    :OLD.GTOTECF              ,
    :OLD.DTFILT               ,
    :OLD.CODEMPORIG           ,
    :OLD.CODMODDOC            ,
    SYSDATE                   ,
    P_NTUSERNAME              ,
    P_SOLICITANTE             ,
    P_PROGRAMNAME             ,
    Tsiusu_Log_Pkg.V_CODUSULOG,
    SYSDATE                   
 );
    DELETE FROM TGFLTARE WHERE NUNOTA = :OLD.NUNOTA ;

END;

/
