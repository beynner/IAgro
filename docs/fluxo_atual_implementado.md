# Fluxo Atual - Duplicação Automática Via Python

## 🔄 **Fluxo Completo Implementado**

```mermaid
graph TD
    A[👤 Usuário no Portal] --> B[📝 Salva Item]
    B --> C{🔍 Verificações Automáticas}
    
    C --> D{📋 É TOP 11?}
    D -->|❌ Não| E[✅ Item Salvo<br/>Sem Duplicação]
    
    D -->|✅ Sim| F{🏭 GERAPRODUCAO='S'?}
    F -->|❌ Não| E
    
    F -->|✅ Sim| G{⚙️ Auto Duplicate<br/>Habilitado?}
    G -->|❌ Não| E
    
    G -->|✅ Sim| H{📦 Já existe<br/>TOP 26?}
    H -->|✅ Sim| E
    
    H -->|❌ Não| I[🔄 Duplicar Automaticamente]
    
    I --> J[📊 Criar TGFCAB TOP 26]
    J --> K[📋 Copiar TGFITE TOP 26]
    K --> L[✅ Sucesso]
    
    L --> M[📱 Response JSON<br/>com Detalhes]
    M --> N[🎯 Classificação<br/>Disponível]
    
    I --> O[❌ Erro na Duplicação]
    O --> P[⚠️ Item Salvo<br/>Sem Duplicação]
    
    style A fill:#e1f5fe
    style I fill:#fff3e0
    style L fill:#e8f5e8
    style E fill:#e8f5e8
    style O fill:#ffebee
```

## 📊 **Separação de Interfaces**

```mermaid
graph LR
    subgraph "Portal (TOP 11)"
        P1[📝 Lança Items]
        P2[🔍 Filtra TOP 11]
        P3[🔄 Auto Duplica]
    end
    
    subgraph "Classificação (TOP 26)"
        C1[🎯 Lista TOP 26]
        C2[👨‍🔬 Classifica]
        C3[✅ Executa]
    end
    
    P3 -.->|Cria Automaticamente| C1
    
    style P1 fill:#e3f2fd
    style P2 fill:#e3f2fd
    style P3 fill:#fff3e0
    style C1 fill:#f3e5f5
    style C2 fill:#f3e5f5
    style C3 fill:#f3e5f5
```

## 🎯 **Estados do Sistema**

```mermaid
stateDiagram-v2
    [*] --> ItemSalvo
    ItemSalvo --> VerificaCondições
    
    VerificaCondições --> NãoClassifica : TOP ≠ 11 ou GERAPRODUCAO ≠ 'S'
    VerificaCondições --> JáExiste : TOP 26 já existe
    VerificaCondições --> PodeDuplicar : Todas condições OK
    
    PodeDuplicar --> DuplicandoTOP26 : Executando duplicação
    DuplicandoTOP26 --> SucessoDuplicação : Sucesso
    DuplicandoTOP26 --> ErroDuplicação : Falha
    
    NãoClassifica --> [*]
    JáExiste --> [*]
    SucessoDuplicação --> DisponívelClassificação
    ErroDuplicação --> [*]
    DisponívelClassificação --> [*]
```

## 📋 **Detalhamento de Cada Etapa**

### **1. Entrada do Usuário**
```
Portal → /sankhya/item/save/
POST {
    nunota: 123456,
    codprod: 863,
    qtdneg: 100,
    ...
}
```

### **2. Verificações Automáticas** (Python)
```python
# 1. Configuração habilitada?
if is_auto_duplicate_on_save_enabled():

# 2. É TOP 11?
if codtipoper == 11:

# 3. Produto classificável?
if geraproducao == 'S':

# 4. Ainda não existe TOP 26?
if not has_top26:
    # → DUPLICAR
```

### **3. Duplicação Automática**
```sql
-- Criar TGFCAB TOP 26
INSERT INTO TGFCAB (NUNOTA, CODTIPOPER=26, ...)

-- Copiar itens classificáveis  
INSERT INTO TGFITE (NUNOTA=nova, ...)
```

### **4. Response JSON**
```json
{
    "ok": true,
    "executed": true,
    "nunota": 123456,
    "auto_duplicated": true,        ✅
    "nunota_26": 123457,          ✅
    "items_duplicated": 3,        ✅
    "duplicate_message": "Classificação criada automaticamente"
}
```

## 🔧 **Configurações de Controle**

### **settings.py**
```python
SANKHYA_CONFIG = {
    'AUTO_FLOWS': {
        'DUPLICATE_ON_SAVE': True,     # 🔄 Duplicar ao salvar
        'DUPLICATE_METHOD': 'python',  # 🐍 Via Python
        'SEPARATE_INTERFACES': True,   # 📱 Interfaces separadas
    }
}
```

### **oracle_conn.py**
```python
DEFAULT_PARAMS = {
    'AUTO_DUPLICATE_ON_SAVE': True,   # 🔄 Flag principal
    'TOP_ENTRADA': 11,                # 📋 Portal
    'TOP_CLASS': 26,                  # 🎯 Classificação
}
```

## 📊 **Tabelas Envolvidas**

```mermaid
erDiagram
    TGFCAB_11 ||--o{ TGFITE_11 : "1:N"
    TGFCAB_26 ||--o{ TGFITE_26 : "1:N (Auto-criado)"
    
    TGFCAB_11 {
        NUMBER NUNOTA "123456"
        NUMBER CODTIPOPER "11"
        VARCHAR CODAGREGACAO "LOTE001"
    }
    
    TGFCAB_26 {
        NUMBER NUNOTA "123457 (Auto)"
        NUMBER CODTIPOPER "26"
        VARCHAR CODAGREGACAO "LOTE001 (Mesmo)"
    }
    
    TGFITE_11 {
        NUMBER NUNOTA "123456"
        VARCHAR GERAPRODUCAO "S"
        NUMBER CODPROD "863"
    }
    
    TGFITE_26 {
        NUMBER NUNOTA "123457 (Auto)"
        VARCHAR GERAPRODUCAO "S (Copiado)"
        NUMBER CODPROD "863 (Mesmo)"
    }
```

## 🎯 **Endpoints Disponíveis**

| Endpoint | Método | Função |
|----------|--------|---------|
| `/sankhya/item/save/` | POST | 💾 Salva + Auto Duplica |
| `/sankhya/auto/config/` | GET | ⚙️ Status configurações |
| `/sankhya/duplicate/status/` | GET | 📊 Status duplicação |
| `/sankhya/duplicate/classification/` | POST | 🔄 Duplicação manual |

## ⚡ **Exemplo Prático de Uso**

### **1. Salvar Item (Automático)**
```bash
curl -X POST /sankhya/item/save/ \
-H "Content-Type: application/json" \
-d '{
    "nunota": 123456,
    "codprod": 863,
    "qtdneg": 100
}'

# Response:
{
    "ok": true,
    "auto_duplicated": true,  ← Duplicou automaticamente!
    "nunota_26": 123457      ← Nova nota criada
}
```

### **2. Verificar Configurações**
```bash
curl /sankhya/auto/config/

# Response:
{
    "auto_duplicate_on_save": true,
    "duplicate_method": "python",
    "write_enabled": true
}
```

### **3. Status de Duplicação**
```bash
curl /sankhya/duplicate/status/?nunota_11=123456

# Response:
{
    "has_top26": true,
    "nunota_26": 123457,
    "classificable_items": 3
}
```

## 🛡️ **Características de Segurança**

- ✅ **Não altera estrutura** do banco
- ✅ **Não quebra** se duplicação falhar
- ✅ **Pode ser desabilitada** facilmente
- ✅ **Logs completos** no Python
- ✅ **Transações isoladas** (não afeta salvamento original)
- ✅ **Verificações múltiplas** antes de duplicar

**O fluxo está 100% funcional e seguro para produção! 🚀**