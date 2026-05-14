"""Aplica AD_REQUISICAO_COMBUSTIVEL_MIGRATION_EXTERNO.sql no Oracle.

Smoke idempotente — checa USER_TAB_COLUMNS/USER_CONSTRAINTS antes de cada ALTER.
Pode ser rodado N vezes sem erro.

Usage: python apply_migration_externo.py
"""
import os

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'IAgro.settings')
django.setup()

from sankhya_integration.services.oracle_conn import obter_conexao_oracle


def main():
    print("=" * 70)
    print("Aplicando migration: AD_REQUISICAO_COMBUSTIVEL — EXTERNO")
    print("=" * 70)

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()

        # 1) ADD COLUMN CATEGORIA
        cur.execute("""
            SELECT COUNT(*) FROM USER_TAB_COLUMNS
            WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
              AND COLUMN_NAME = 'CATEGORIA'
        """)
        if cur.fetchone()[0] == 0:
            print("[1/6] ADD COLUMN CATEGORIA ...")
            cur.execute("""
                ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
                ADD CATEGORIA VARCHAR2(20) DEFAULT 'COMBUSTIVEL' NOT NULL
            """)
            print("       OK")
        else:
            print("[1/6] CATEGORIA ja existe — skip")

        # 2) ADD COLUMN CODPARC
        cur.execute("""
            SELECT COUNT(*) FROM USER_TAB_COLUMNS
            WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
              AND COLUMN_NAME = 'CODPARC'
        """)
        if cur.fetchone()[0] == 0:
            print("[2/6] ADD COLUMN CODPARC ...")
            cur.execute("""
                ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
                ADD CODPARC NUMBER NULL
            """)
            print("       OK")
        else:
            print("[2/6] CODPARC ja existe — skip")

        # 3) ADD COLUMN NUFIN_GERADO
        cur.execute("""
            SELECT COUNT(*) FROM USER_TAB_COLUMNS
            WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
              AND COLUMN_NAME = 'NUFIN_GERADO'
        """)
        if cur.fetchone()[0] == 0:
            print("[3/6] ADD COLUMN NUFIN_GERADO ...")
            cur.execute("""
                ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
                ADD NUFIN_GERADO NUMBER NULL
            """)
            print("       OK")
        else:
            print("[3/6] NUFIN_GERADO ja existe — skip")

        # 4) DROP CHECK TIPO antigo + CREATE com EXTERNA_POSTO
        cur.execute("""
            SELECT COUNT(*) FROM USER_CONSTRAINTS
            WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
              AND CONSTRAINT_NAME = 'CK_AD_REQ_COMBUST_TIPO'
        """)
        if cur.fetchone()[0] > 0:
            print("[4/6] DROP CONSTRAINT CK_AD_REQ_COMBUST_TIPO ...")
            cur.execute("""
                ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
                DROP CONSTRAINT CK_AD_REQ_COMBUST_TIPO
            """)
            print("       OK")
        print("[4/6] ADD CONSTRAINT CK_AD_REQ_COMBUST_TIPO (com EXTERNA_POSTO) ...")
        cur.execute("""
            ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
            ADD CONSTRAINT CK_AD_REQ_COMBUST_TIPO
            CHECK (TIPO IN ('INTERNA_FROTA','INTERNA_MAQUINARIO','EXTERNA_FRETE','EXTERNA_POSTO'))
        """)
        print("       OK")

        # 5) CHECK condicional EXTERNA_POSTO -> CODPARC obrigatorio
        cur.execute("""
            SELECT COUNT(*) FROM USER_CONSTRAINTS
            WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
              AND CONSTRAINT_NAME = 'CK_AD_REQ_COMBUST_EXTPOSTO'
        """)
        if cur.fetchone()[0] == 0:
            print("[5/6] ADD CONSTRAINT CK_AD_REQ_COMBUST_EXTPOSTO ...")
            cur.execute("""
                ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
                ADD CONSTRAINT CK_AD_REQ_COMBUST_EXTPOSTO
                CHECK (TIPO <> 'EXTERNA_POSTO' OR CODPARC IS NOT NULL)
            """)
            print("       OK")
        else:
            print("[5/6] CK_AD_REQ_COMBUST_EXTPOSTO ja existe — skip")

        # 6) CHECK CATEGORIA
        cur.execute("""
            SELECT COUNT(*) FROM USER_CONSTRAINTS
            WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
              AND CONSTRAINT_NAME = 'CK_AD_REQ_COMBUST_CATEG'
        """)
        if cur.fetchone()[0] == 0:
            print("[6/6] ADD CONSTRAINT CK_AD_REQ_COMBUST_CATEG ...")
            cur.execute("""
                ALTER TABLE AD_REQUISICAO_COMBUSTIVEL
                ADD CONSTRAINT CK_AD_REQ_COMBUST_CATEG
                CHECK (CATEGORIA IN ('COMBUSTIVEL','MANUTENCAO'))
            """)
            print("       OK")
        else:
            print("[6/6] CK_AD_REQ_COMBUST_CATEG ja existe — skip")

        conn.commit()

        print()
        print("Estrutura final:")
        cur.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE
            FROM USER_TAB_COLUMNS
            WHERE TABLE_NAME = 'AD_REQUISICAO_COMBUSTIVEL'
            ORDER BY COLUMN_ID
        """)
        for row in cur.fetchall():
            print(f"  {row[0]:30s} {row[1]:15s} ({row[2]}) NULL={row[3]}")

        print()
        print("Constraints CHECK:")
        cur.execute("""
            SELECT CONSTRAINT_NAME, SEARCH_CONDITION
            FROM USER_CONSTRAINTS
            WHERE TABLE_NAME='AD_REQUISICAO_COMBUSTIVEL'
              AND CONSTRAINT_TYPE='C'
            ORDER BY CONSTRAINT_NAME
        """)
        for row in cur.fetchall():
            print(f"  {row[0]}")
            print(f"    {row[1]}")

    print()
    print("Migration aplicada com sucesso.")


if __name__ == '__main__':
    main()
