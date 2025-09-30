-- SANKHYA.TRG_DDL_SCHEMA_LOG
CREATE OR REPLACE TRIGGER SANKHYA.TRG_DDL_SCHEMA_LOG
"SANKHYA".TRG_DDL_SCHEMA_LOG
    BEFORE DROP
    ON SCHEMA

DECLARE
    oper VARCHAR2(100);
    TIP  VARCHAR2(100);
	tab  VARCHAR2(100);
BEGIN
    SELECT ora_sysevent INTO oper FROM DUAL;
    select ora_dict_obj_type into TIP from dual;
	SELECT ora_dict_obj_name INTO tab FROM DUAL;
	
	
    IF     oper = 'DROP' 
	   AND TIP = 'TABLE' 
       AND TAB IN ('TGFEMP', 'TSIEMP', 'TFPEMP', 'TCBEMP',
					'TGFPAR', 'TGFCTT', 'TSIUSU',
					'TGFPRO', 'TGFGRU',
					'TGFTOP', 'TGFTIT',
					'TGFCAB', 'TGFITE', 'TGFNFE', 'TGFNFSE', 'TGFNCTE', 'TGFVAR',
					'TGFFIN', 'TGFMBC', 
					'TFPFUN', 'TFPHFU',  
					'TGFRAT', 'TGFEST', 
					'TCBLAN', 'TCBINT',
					'TGFLIV', 'TGFLIS',
					'TGWSEP', 'TGWREC', 'TGWEST',
					'TSIPAR', 'TSICFG')
	THEN
        RAISE_APPLICATION_ERROR(-20101,'FORBIDEN_12022024');
    END IF;
END;
/
