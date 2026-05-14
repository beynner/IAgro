-- =============================================================================
-- Migration: AD_REQUISICAO_COMBUSTIVEL — suporte a "abastecimento externo (posto)"
-- Pacote/Modulo: IAgro - Controle de Combustivel (Mai/2026)
--
-- O QUE
--   Adiciona 3 colunas e ajusta CHECKs para discriminar:
--     - CATEGORIA: 'COMBUSTIVEL' (default) | 'MANUTENCAO' (preparado pra futuro)
--     - CODPARC:   parceiro do abastecimento externo (posto Allianz, Semear, Agromil)
--     - NUFIN_GERADO: NUFIN da despesa gerada (TGFFIN) — audit
--
--   Amplia o CHECK do TIPO para aceitar 'EXTERNA_POSTO' (alem dos 3 ja existentes).
--   Adiciona constraint condicional: se TIPO='EXTERNA_POSTO', CODPARC OBRIGATORIO.
--
-- POR QUE
--   - Abastecimento externo (no meio da viagem) NAO desconta do tanque interno,
--     mas precisa ser registrado para:
--       (1) fechar a curva de consumo km/L do veiculo (sem lacuna)
--       (2) gerar TGFFIN (despesa contra o posto)
--   - Tabela unificada para todas as despesas do veiculo simplifica o relatorio.
--   - CATEGORIA prepara o terreno para o futuro modulo de Manutencao
--     (pneu, oficina, eletrica) sem refactor.
--
-- O QUE AFETA
--   - 5 linhas existentes em producao ganham CATEGORIA='COMBUSTIVEL' (default),
--     CODPARC=NULL, NUFIN_GERADO=NULL. Sem quebra.
--   - View ANDRE_IAGRO_SALDO_COMBUSTIVEL (atualizada em script separado)
--     ignora linhas com TIPO='EXTERNA_POSTO' na perna de saida.
--   - Funcoes Python: criar_requisicao_combustivel_banco (mantida),
--     criar_abastecimento_externo_banco (nova), editar/excluir adaptadas.
--
-- IDEMPOTENCIA
--   Script seguro de rodar 2x: cada ALTER eh envolto em DECLARE-EXCEPTION que
--   ignora "ORA-01430 - column already exists" e "ORA-02260 - check constraint
--   already exists".
-- =============================================================================

-- 1) ADD COLUMN CATEGORIA (default COMBUSTIVEL para nao quebrar linhas antigas)
DECLARE
    coluna_existe NUMBER;
BEGIN
    SELECT COUNT(*) INTO coluna_existe FROM USER_TAB_COLUMNS
    WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL' AND COLUMN_NAME = 'CATEGORIA';
    IF coluna_existe = 0 THEN
        EXECUTE IMMEDIATE q'[
            ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
            ADD CATEGORIA VARCHAR2(20) DEFAULT 'COMBUSTIVEL' NOT NULL
        ]';
    END IF;
END;
/

-- 2) ADD COLUMN CODPARC (nullable; obrigatorio so quando TIPO='EXTERNA_POSTO')
DECLARE
    coluna_existe NUMBER;
BEGIN
    SELECT COUNT(*) INTO coluna_existe FROM USER_TAB_COLUMNS
    WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL' AND COLUMN_NAME = 'CODPARC';
    IF coluna_existe = 0 THEN
        EXECUTE IMMEDIATE q'[
            ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
            ADD CODPARC NUMBER NULL
        ]';
    END IF;
END;
/

-- 3) ADD COLUMN NUFIN_GERADO (nullable; audit do TGFFIN criado)
DECLARE
    coluna_existe NUMBER;
BEGIN
    SELECT COUNT(*) INTO coluna_existe FROM USER_TAB_COLUMNS
    WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL' AND COLUMN_NAME = 'NUFIN_GERADO';
    IF coluna_existe = 0 THEN
        EXECUTE IMMEDIATE q'[
            ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
            ADD NUFIN_GERADO NUMBER NULL
        ]';
    END IF;
END;
/

-- 4) AMPLIAR CHECK do TIPO para aceitar 'EXTERNA_POSTO'
--    Drop and recreate (Oracle nao permite MODIFY de check inline).
DECLARE
    constraint_existe NUMBER;
BEGIN
    SELECT COUNT(*) INTO constraint_existe FROM USER_CONSTRAINTS
    WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
      AND CONSTRAINT_NAME = 'CK_AD_REQ_COMBUST_TIPO';
    IF constraint_existe > 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE AD_REQUISICAO_COMBUSTIVEL DROP CONSTRAINT CK_AD_REQ_COMBUST_TIPO';
    END IF;
END;
/

ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
ADD CONSTRAINT CK_AD_REQ_COMBUST_TIPO
CHECK (TIPO IN ('INTERNA_FROTA','INTERNA_MAQUINARIO','EXTERNA_FRETE','EXTERNA_POSTO'));
/

-- 5) CHECK condicional: EXTERNA_POSTO exige CODPARC
DECLARE
    constraint_existe NUMBER;
BEGIN
    SELECT COUNT(*) INTO constraint_existe FROM USER_CONSTRAINTS
    WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
      AND CONSTRAINT_NAME = 'CK_AD_REQ_COMBUST_EXTPOSTO';
    IF constraint_existe = 0 THEN
        EXECUTE IMMEDIATE q'[
            ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
            ADD CONSTRAINT CK_AD_REQ_COMBUST_EXTPOSTO
            CHECK (TIPO <> 'EXTERNA_POSTO' OR CODPARC IS NOT NULL)
        ]';
    END IF;
END;
/

-- 6) CHECK CATEGORIA (extensivel pra MANUTENCAO no futuro)
DECLARE
    constraint_existe NUMBER;
BEGIN
    SELECT COUNT(*) INTO constraint_existe FROM USER_CONSTRAINTS
    WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
      AND CONSTRAINT_NAME = 'CK_AD_REQ_COMBUST_CATEG';
    IF constraint_existe = 0 THEN
        EXECUTE IMMEDIATE q'[
            ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
            ADD CONSTRAINT CK_AD_REQ_COMBUST_CATEG
            CHECK (CATEGORIA IN ('COMBUSTIVEL','MANUTENCAO'))
        ]';
    END IF;
END;
/

-- Conferencia rapida (informativa - nao bloqueia execucao):
-- SELECT COLUMN_NAME, DATA_TYPE, NULLABLE, DATA_DEFAULT
-- FROM USER_TAB_COLUMNS WHERE TABLE_NAME='AD_REQUISICAO_COMBUSTIVEL'
-- ORDER BY COLUMN_ID;
--
-- SELECT CONSTRAINT_NAME, SEARCH_CONDITION
-- FROM USER_CONSTRAINTS
-- WHERE TABLE_NAME='AD_REQUISICAO_COMBUSTIVEL' AND CONSTRAINT_TYPE='C';
