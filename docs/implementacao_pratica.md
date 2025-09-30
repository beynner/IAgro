# Implementação Prática - 3 Opções de Fluxo

## 🏆 OPÇÃO A - TRIGGERS AUTOMÁTICOS (Recomendada)

### 1. Trigger de Duplicação TOP 11 → TOP 26

```sql
-- Arquivo: sankhya_integration/triggers/triggers/SANKHYA.TRG_AUTO_DUPLICATE_CLASS.sql
CREATE OR REPLACE TRIGGER SANKHYA.TRG_AUTO_DUPLICATE_CLASS
    AFTER INSERT ON TGFITE
    FOR EACH ROW
DECLARE
    v_nunota_26 NUMBER;
    v_exists NUMBER;
    v_codtipoper NUMBER;
    v_controle VARCHAR2(100);
BEGIN
    -- Só processar se for TOP 11 e produto que gera produção
    SELECT c.CODTIPOPER INTO v_codtipoper
    FROM TGFCAB c 
    WHERE c.NUNOTA = :NEW.NUNOTA;
    
    -- Verificar se é TOP 11 e se produto classifica
    IF (v_codtipoper = 11 AND NVL(:NEW.GERAPRODUCAO, 'N') = 'S') THEN
        
        v_controle := :NEW.CODAGREGACAO;
        
        -- Verificar se já existe TOP 26 para este controle
        SELECT COUNT(*) INTO v_exists
        FROM TGFITE i
        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA  
        WHERE i.CODAGREGACAO = v_controle
        AND c.CODTIPOPER = 26;
        
        IF v_exists = 0 THEN
            -- 1. Criar TGFCAB TOP 26 baseado no TOP 11
            INSERT INTO TGFCAB (
                NUNOTA, CODEMP, CODPARC, CODTIPOPER, CODNAT, CODCENCUS,
                DTNEG, DTMOV, DTENTSAI, DHTIPOPER, TIPMOV, STATUSNOTA,
                OBSERVACAO
            )
            SELECT 
                SQ_TGFCAB_NUNOTA.NEXTVAL,
                c.CODEMP, c.CODPARC, 26, c.CODNAT, c.CODCENCUS,
                c.DTNEG, c.DTMOV, c.DTENTSAI, SYSDATE, 'P', 'A',
                'Auto-criado para classificação do controle ' || v_controle
            FROM TGFCAB c
            WHERE c.NUNOTA = :NEW.NUNOTA
            RETURNING NUNOTA INTO v_nunota_26;
            
            -- 2. Inserir todos os itens classificáveis do mesmo controle
            INSERT INTO TGFITE (
                NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG, VLRUNIT, VLRTOT,
                CODVOL, CODLOCALORIG, CODAGREGACAO, GERAPRODUCAO, STATUSNOTA
            )
            SELECT 
                v_nunota_26,
                ROW_NUMBER() OVER (ORDER BY i.SEQUENCIA),
                i.CODEMP, i.CODPROD, i.QTDNEG, i.VLRUNIT, i.VLRTOT,
                i.CODVOL, i.CODLOCALORIG, i.CODAGREGACAO, i.GERAPRODUCAO, 'A'
            FROM TGFITE i
            JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
            WHERE c.CODTIPOPER = 11 
            AND i.CODAGREGACAO = v_controle
            AND NVL(i.GERAPRODUCAO, 'N') = 'S';
            
        END IF;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        -- Log do erro mas não falha a transação principal
        INSERT INTO TGFLOG (DTLOG, USUARIO, EVENTO, DESCRICAO)
        VALUES (SYSDATE, USER, 'TRG_AUTO_DUPLICATE_CLASS', 
                'Erro: ' || SQLERRM || ' - NUNOTA: ' || :NEW.NUNOTA);
        COMMIT;
END;
/
```

### 2. Trigger de Vale de Compra TOP 26 → TOP 13

```sql
-- Arquivo: sankhya_integration/triggers/triggers/SANKHYA.TRG_AUTO_VALE_COMPRA.sql
CREATE OR REPLACE TRIGGER SANKHYA.TRG_AUTO_VALE_COMPRA
    AFTER UPDATE ON TGFCAB
    FOR EACH ROW
DECLARE
    v_nunota_13 NUMBER;
    v_nufin NUMBER;
    v_vlrtotal NUMBER;
BEGIN
    -- Processar apenas TOP 26 quando status mudar para Liquidado
    IF (:NEW.CODTIPOPER = 26 AND 
        :NEW.STATUSNOTA = 'L' AND 
        :OLD.STATUSNOTA != 'L') THEN
        
        -- Calcular valor total da classificação
        SELECT NVL(SUM(VLRTOT), 0) INTO v_vlrtotal
        FROM TGFITE 
        WHERE NUNOTA = :NEW.NUNOTA;
        
        -- 1. Criar TGFCAB TOP 13 (Vale de Compra)
        INSERT INTO TGFCAB (
            NUNOTA, CODEMP, CODPARC, CODTIPOPER, CODNAT, CODCENCUS,
            DTNEG, DTMOV, DTENTSAI, DHTIPOPER, TIPMOV, STATUSNOTA,
            VLRNOTA, OBSERVACAO
        )
        VALUES (
            SQ_TGFCAB_NUNOTA.NEXTVAL,
            :NEW.CODEMP, :NEW.CODPARC, 13, :NEW.CODNAT, :NEW.CODCENCUS,
            :NEW.DTNEG, SYSDATE, SYSDATE, SYSDATE, 'O', 'L',
            v_vlrtotal,
            'Vale de compra - Ref. Classificação NUNOTA: ' || :NEW.NUNOTA
        )
        RETURNING NUNOTA INTO v_nunota_13;
        
        -- 2. Copiar itens da classificação para o vale
        INSERT INTO TGFITE (
            NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG, VLRUNIT, VLRTOT,
            CODVOL, CODAGREGACAO, STATUSNOTA
        )
        SELECT 
            v_nunota_13,
            SEQUENCIA, CODEMP, CODPROD, QTDNEG, VLRUNIT, VLRTOT,
            CODVOL, CODAGREGACAO, 'L'
        FROM TGFITE
        WHERE NUNOTA = :NEW.NUNOTA;
        
        -- 3. Gerar título financeiro (TGFFIN)
        SELECT SQ_TGFFIN_NUFIN.NEXTVAL INTO v_nufin FROM DUAL;
        
        INSERT INTO TGFFIN (
            NUFIN, NUNOTA, CODEMP, CODPARC, CODNAT,
            DTNEG, DTMOV, DTVENC, VLRDESDOB, ORIGEM,
            PROVISAO, BAIXA, RECDESP
        )
        VALUES (
            v_nufin, v_nunota_13, :NEW.CODEMP, :NEW.CODPARC, :NEW.CODNAT,
            :NEW.DTNEG, SYSDATE, SYSDATE + 30, v_vlrtotal, 'E',
            'N', 'N', -1
        );
        
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        INSERT INTO TGFLOG (DTLOG, USUARIO, EVENTO, DESCRICAO)
        VALUES (SYSDATE, USER, 'TRG_AUTO_VALE_COMPRA', 
                'Erro: ' || SQLERRM || ' - NUNOTA: ' || :NEW.NUNOTA);
        COMMIT;
END;
/
```

### 3. Filtros nas Views Python

```python
# sankhya_integration/services/oracle_conn.py
def listar_lotes_portal(date_start=None, date_end=None, **filters):
    """Lista lotes apenas para Portal (TOP 11)"""
    params = get_params()
    TOP_ENTRADA = params['TOP_ENTRADA']  # 11
    
    sql = """
        SELECT DISTINCT i.CODAGREGACAO as controle,
               c.CODPARC, p.RAZAOSOCIAL,
               c.DTNEG, COUNT(*) as itens
        FROM TGFITE i
        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
        LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC
        WHERE c.CODTIPOPER = :top_entrada
        AND (:date_start IS NULL OR c.DTNEG >= TO_DATE(:date_start, 'YYYY-MM-DD'))
        AND (:date_end IS NULL OR c.DTNEG <= TO_DATE(:date_end, 'YYYY-MM-DD'))
        GROUP BY i.CODAGREGACAO, c.CODPARC, p.RAZAOSOCIAL, c.DTNEG
        ORDER BY c.DTNEG DESC
    """
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, {
            'top_entrada': TOP_ENTRADA,
            'date_start': date_start,
            'date_end': date_end
        })
        return cur.fetchall()

def listar_lotes_classificacao(date_start=None, date_end=None, **filters):
    """Lista lotes apenas para Classificação (TOP 26)"""
    params = get_params()
    TOP_CLASS = params['TOP_CLASS']  # 26
    
    sql = """
        SELECT DISTINCT i.CODAGREGACAO as controle,
               c.NUNOTA, c.CODPARC, p.RAZAOSOCIAL,
               c.DTNEG, c.STATUSNOTA, COUNT(*) as itens
        FROM TGFITE i
        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
        LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC
        WHERE c.CODTIPOPER = :top_class
        AND (:date_start IS NULL OR c.DTNEG >= TO_DATE(:date_start, 'YYYY-MM-DD'))
        AND (:date_end IS NULL OR c.DTNEG <= TO_DATE(:date_end, 'YYYY-MM-DD'))
        GROUP BY i.CODAGREGACAO, c.NUNOTA, c.CODPARC, p.RAZAOSOCIAL, c.DTNEG, c.STATUSNOTA
        ORDER BY c.DTNEG DESC
    """
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, {
            'top_class': TOP_CLASS,
            'date_start': date_start,
            'date_end': date_end
        })
        return cur.fetchall()
```

### 4. Modificações nas Views Django

```python
# sankhya_integration/views.py
@ensure_csrf_cookie
def compras_portal(request: HttpRequest) -> HttpResponse:
    """Portal - Mostra apenas TOP 11 (Pedidos de Compra)"""
    # ... parâmetros atuais ...
    
    # MODIFICAÇÃO: Usar nova função filtrada
    try:
        controles = listar_lotes_portal(
            date_start=params['date_start'],
            date_end=params['date_end'],
            codparc=params['codparc'],
            codprod=params['codprod']
        )
    except Exception:
        controles = []
    
    # ... resto do código igual ...

@ensure_csrf_cookie  
def compras_classificacao(request: HttpRequest) -> HttpResponse:
    """Classificação - Mostra apenas TOP 26 (Classificação)"""
    # ... parâmetros atuais ...
    
    # MODIFICAÇÃO: Usar nova função filtrada
    try:
        controles = listar_lotes_classificacao(
            date_start=params['date_start'],
            date_end=params['date_end'],
            codparc=params['codparc'],
            codprod=params['codprod']
        )
    except Exception:
        controles = []
    
    # ... resto do código igual ...
```

---

## 📋 OPÇÃO B - CONTROLE POR APLICAÇÃO

### 1. Serviços de Duplicação

```python
# sankhya_integration/services/oracle_conn.py
def duplicate_to_classification(nunota_11: int, dry_run: bool = True) -> dict:
    """Duplica nota TOP 11 para TOP 26 com produtos classificáveis"""
    res = {'ok': False, 'nunota_26': None, 'errors': [], 'warnings': []}
    
    try:
        params = get_params()
        TOP_CLASS = params['TOP_CLASS']
        
        with get_connection() as conn:
            cur = conn.cursor()
            
            # 1. Verificar se TOP 11 existe
            cur.execute("SELECT COUNT(*) FROM TGFCAB WHERE NUNOTA = :n AND CODTIPOPER = 11", n=nunota_11)
            if cur.fetchone()[0] == 0:
                res['errors'].append('NUNOTA TOP 11 não encontrada')
                return res
            
            # 2. Verificar se já existe TOP 26 para este controle
            cur.execute("""
                SELECT DISTINCT i.CODAGREGACAO 
                FROM TGFITE i 
                WHERE i.NUNOTA = :n
            """, n=nunota_11)
            controle = cur.fetchone()
            if not controle:
                res['errors'].append('Nenhum item encontrado na nota')
                return res
            
            controle = controle[0]
            
            cur.execute("""
                SELECT COUNT(*) FROM TGFITE i
                JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                WHERE i.CODAGREGACAO = :ctrl AND c.CODTIPOPER = :top
            """, ctrl=controle, top=TOP_CLASS)
            
            if cur.fetchone()[0] > 0:
                res['warnings'].append('TOP 26 já existe para este controle')
                return res
            
            if dry_run:
                res['ok'] = True
                res['warnings'].append('Modo simulação - não executado')
                return res
            
            # 3. Duplicar TGFCAB
            cur.execute("""
                INSERT INTO TGFCAB (
                    NUNOTA, CODEMP, CODPARC, CODTIPOPER, CODNAT, CODCENCUS,
                    DTNEG, DTMOV, DTENTSAI, DHTIPOPER, TIPMOV, STATUSNOTA
                )
                SELECT 
                    SQ_TGFCAB_NUNOTA.NEXTVAL, CODEMP, CODPARC, :top_class, CODNAT, CODCENCUS,
                    DTNEG, DTMOV, DTENTSAI, SYSDATE, 'P', 'A'
                FROM TGFCAB 
                WHERE NUNOTA = :nunota_orig
                RETURNING NUNOTA INTO :nunota_new
            """, {
                'top_class': TOP_CLASS,
                'nunota_orig': nunota_11,
                'nunota_new': cur.var(cx_Oracle.NUMBER)
            })
            
            nunota_26 = int(cur.getvalue(cur.lastrowid))
            res['nunota_26'] = nunota_26
            
            # 4. Duplicar itens classificáveis
            cur.execute("""
                INSERT INTO TGFITE (
                    NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG, VLRUNIT, VLRTOT,
                    CODVOL, CODLOCALORIG, CODAGREGACAO, GERAPRODUCAO, STATUSNOTA
                )
                SELECT 
                    :nunota_26, ROW_NUMBER() OVER (ORDER BY SEQUENCIA),
                    CODEMP, CODPROD, QTDNEG, VLRUNIT, VLRTOT,
                    CODVOL, CODLOCALORIG, CODAGREGACAO, GERAPRODUCAO, 'A'
                FROM TGFITE
                WHERE NUNOTA = :nunota_11 AND NVL(GERAPRODUCAO, 'N') = 'S'
            """, {'nunota_26': nunota_26, 'nunota_11': nunota_11})
            
            conn.commit()
            res['ok'] = True
            
    except Exception as e:
        res['errors'].append(str(e))
        
    return res

def create_vale_compra(nunota_26: int, dry_run: bool = True) -> dict:
    """Cria vale de compra TOP 13 a partir da classificação TOP 26"""
    res = {'ok': False, 'nunota_13': None, 'nufin': None, 'errors': [], 'warnings': []}
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # 1. Verificar se TOP 26 está liquidada
            cur.execute("""
                SELECT STATUSNOTA, VLRNOTA FROM TGFCAB 
                WHERE NUNOTA = :n AND CODTIPOPER = 26
            """, n=nunota_26)
            
            row = cur.fetchone()
            if not row:
                res['errors'].append('NUNOTA TOP 26 não encontrada')
                return res
                
            status, vlrnota = row
            if status != 'L':
                res['errors'].append('TOP 26 deve estar liquidada para gerar vale')
                return res
            
            if dry_run:
                res['ok'] = True
                res['warnings'].append('Modo simulação - não executado')
                return res
            
            # 2. Criar TGFCAB TOP 13
            cur.execute("""
                INSERT INTO TGFCAB (
                    NUNOTA, CODEMP, CODPARC, CODTIPOPER, CODNAT, CODCENCUS,
                    DTNEG, DTMOV, DTENTSAI, DHTIPOPER, TIPMOV, STATUSNOTA, VLRNOTA
                )
                SELECT 
                    SQ_TGFCAB_NUNOTA.NEXTVAL, CODEMP, CODPARC, 13, CODNAT, CODCENCUS,
                    DTNEG, SYSDATE, SYSDATE, SYSDATE, 'O', 'L', :vlrnota
                FROM TGFCAB 
                WHERE NUNOTA = :nunota_26
                RETURNING NUNOTA INTO :nunota_new
            """, {
                'vlrnota': vlrnota,
                'nunota_26': nunota_26,
                'nunota_new': cur.var(cx_Oracle.NUMBER)
            })
            
            nunota_13 = int(cur.getvalue(cur.lastrowid))
            res['nunota_13'] = nunota_13
            
            # 3. Copiar itens
            cur.execute("""
                INSERT INTO TGFITE (
                    NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG, VLRUNIT, VLRTOT,
                    CODVOL, CODAGREGACAO, STATUSNOTA
                )
                SELECT 
                    :nunota_13, SEQUENCIA, CODEMP, CODPROD, QTDNEG, VLRUNIT, VLRTOT,
                    CODVOL, CODAGREGACAO, 'L'
                FROM TGFITE
                WHERE NUNOTA = :nunota_26
            """, {'nunota_13': nunota_13, 'nunota_26': nunota_26})
            
            # 4. Gerar TGFFIN
            cur.execute("SELECT SQ_TGFFIN_NUFIN.NEXTVAL FROM DUAL")
            nufin = cur.fetchone()[0]
            
            cur.execute("""
                INSERT INTO TGFFIN (
                    NUFIN, NUNOTA, CODEMP, CODPARC, CODNAT,
                    DTNEG, DTMOV, DTVENC, VLRDESDOB, ORIGEM, PROVISAO, BAIXA, RECDESP
                )
                SELECT 
                    :nufin, :nunota_13, CODEMP, CODPARC, CODNAT,
                    DTNEG, SYSDATE, SYSDATE + 30, :vlrnota, 'E', 'N', 'N', -1
                FROM TGFCAB
                WHERE NUNOTA = :nunota_26
            """, {'nufin': nufin, 'nunota_13': nunota_13, 'vlrnota': vlrnota, 'nunota_26': nunota_26})
            
            conn.commit()
            res['nufin'] = nufin
            res['ok'] = True
            
    except Exception as e:
        res['errors'].append(str(e))
        
    return res
```

### 2. Endpoints para Controle Manual

```python
# sankhya_integration/views.py
def duplicate_classification(request: HttpRequest) -> JsonResponse:
    """POST /sankhya/duplicate/classification/"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Use POST'}, status=405)
    
    try:
        payload = json.loads(request.body.decode('utf-8'))
        nunota_11 = int(payload.get('nunota_11'))
        dry_run = payload.get('dry_run', True)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Parâmetros inválidos'}, status=400)
    
    result = duplicate_to_classification(nunota_11, dry_run=dry_run)
    return JsonResponse(result)

def create_vale_endpoint(request: HttpRequest) -> JsonResponse:
    """POST /sankhya/create/vale/"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Use POST'}, status=405)
    
    try:
        payload = json.loads(request.body.decode('utf-8'))
        nunota_26 = int(payload.get('nunota_26'))
        dry_run = payload.get('dry_run', True)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Parâmetros inválidos'}, status=400)
    
    result = create_vale_compra(nunota_26, dry_run=dry_run)
    return JsonResponse(result)
```

---

## 🔧 OPÇÃO C - HÍBRIDA

```python
# Combina trigger para duplicação + controle manual para vale
# Trigger: SANKHYA.TRG_AUTO_DUPLICATE_CLASS (da Opção A)
# Serviço: create_vale_compra (da Opção B)
# Interface: Botão "Gerar Vale de Compra" na tela de classificação

def auto_create_classification_if_needed(nunota_11: int) -> dict:
    """Verifica se precisa criar TOP 26 e cria se necessário (fallback para trigger)"""
    # Se trigger falhar ou estiver desabilitado, criar manualmente
    pass
```

## Resumo de Implementação

| Aspecto | Opção A | Opção B | Opção C |
|---------|---------|---------|---------|
| **Duplicação TOP 11→26** | Trigger automático | Botão manual | Trigger + fallback |
| **Vale TOP 26→13** | Trigger automático | Botão manual | Botão manual |  
| **Financeiro TGFFIN** | Trigger automático | Botão manual | Trigger automático |
| **Complexidade** | Baixa | Média | Alta |
| **Flexibilidade** | Baixa | Alta | Média |
| **Consistência** | Alta | Média | Alta |
| **Debug** | Difícil | Fácil | Médio |

## Recomendação Final

**Implementar Opção A com Opção B como fallback**:
1. Triggers principais para automação
2. Serviços manuais para casos especiais
3. Flags de configuração para habilitar/desabilitar
4. Logs detalhados para monitoramento