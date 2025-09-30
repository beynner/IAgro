```mermaid
flowchart TD
    A[👤 Usuário no Portal] --> B[📝 Lança Item]
    B --> C{🔍 Produto Classifica?<br/>GERAPRODUCAO='S'}
    
    C -->|❌ Não| D[📋 Apenas TOP 11<br/>Processo Normal]
    C -->|✅ Sim| E[🔄 Trigger Automático]
    
    E --> F[📊 Duplica TGFCAB<br/>TOP 11 → TOP 26]
    F --> G[📦 Duplica TGFITE<br/>Itens Classificáveis]
    
    G --> H[📱 Interface Classificação<br/>Mostra TOP 26]
    H --> I[👨‍🔬 Usuário Classifica<br/>Produtos]
    
    I --> J{📈 Classificação<br/>Completa?}
    J -->|❌ Não| K[⏳ Aguarda Mais<br/>Classificações]
    J -->|✅ Sim| L[🔄 Trigger TOP 13]
    
    K --> I
    
    L --> M[🧾 Cria TGFCAB<br/>TOP 13 - Vale Compra]
    M --> N[📋 Cria TGFITE<br/>TOP 13]
    N --> O[💰 Gera TGFFIN<br/>Financeiro]
    
    O --> P[✅ Processo Completo]
    
    D --> Q[✅ Item TOP 11<br/>Finalizado]
    
    style A fill:#e1f5fe
    style E fill:#fff3e0
    style L fill:#fff3e0
    style P fill:#e8f5e8
    style Q fill:#e8f5e8
    
    classDef userAction fill:#bbdefb,stroke:#1976d2,stroke-width:2px
    classDef systemAction fill:#ffe0b2,stroke:#f57c00,stroke-width:2px
    classDef decision fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef success fill:#c8e6c9,stroke:#388e3c,stroke-width:2px
    
    class A,B,H,I userAction
    class E,F,G,L,M,N,O systemAction  
    class C,J decision
    class P,Q success
```

## Comparação das 3 Opções

### 🏆 Opção A - Triggers Automáticos
```mermaid
graph LR
    A1[Portal<br/>TOP 11] -->|Trigger| B1[Auto TOP 26]
    B1 -->|Classificação| C1[Auto TOP 13]
    C1 --> D1[Auto TGFFIN]
    
    style A1 fill:#e3f2fd
    style B1 fill:#fff3e0  
    style C1 fill:#fff3e0
    style D1 fill:#e8f5e8
```

**Prós**: Totalmente automático, consistente, rápido
**Contras**: Menos flexível, debugging mais difícil

### 📋 Opção B - Controle por Aplicação
```mermaid
graph LR
    A2[Portal<br/>TOP 11] -->|Botão| B2[Criar TOP 26]
    B2 -->|Botão| C2[Criar TOP 13] 
    C2 -->|Botão| D2[Gerar TGFFIN]
    
    style A2 fill:#e3f2fd
    style B2 fill:#f3e5f5
    style C2 fill:#f3e5f5
    style D2 fill:#f3e5f5
```

**Prós**: Flexível, fácil debug, controle total
**Contras**: Manual, pode esquecer etapas, inconsistente

### 🔧 Opção C - Híbrida
```mermaid
graph LR
    A3[Portal<br/>TOP 11] -->|Trigger| B3[Auto TOP 26]
    B3 -->|Botão| C3[Criar TOP 13]
    C3 -->|Trigger| D3[Auto TGFFIN]
    
    style A3 fill:#e3f2fd
    style B3 fill:#fff3e0
    style C3 fill:#f3e5f5  
    style D3 fill:#fff3e0
```

**Prós**: Balanceada, automação + controle
**Contras**: Complexidade média

## Estados das Interfaces

### Portal (TOP 11)
```mermaid
stateDiagram-v2
    [*] --> Novo_Lote
    Novo_Lote --> Item_Lancado : Lança Item
    Item_Lancado --> Item_Classificavel : Se GERAPRODUCAO='S'  
    Item_Classificavel --> TOP26_Criado : Trigger Auto
    Item_Lancado --> Finalizado : Se não classifica
    TOP26_Criado --> Disponivel_Classificacao
```

### Classificação (TOP 26)
```mermaid
stateDiagram-v2
    [*] --> Aguarda_TOP26
    Aguarda_TOP26 --> Lote_Disponivel : TOP 26 criado
    Lote_Disponivel --> Classificando : Usuário inicia
    Classificando --> Parcial : Salva produtos
    Parcial --> Classificando : Continua
    Parcial --> Completo : 100% classificado
    Completo --> TOP13_Criado : Trigger auto
```

## Tabelas Envolvidas

```mermaid
erDiagram
    TGFCAB_11 ||--o{ TGFITE_11 : "1:N"
    TGFCAB_26 ||--o{ TGFITE_26 : "1:N"  
    TGFCAB_13 ||--o{ TGFITE_13 : "1:N"
    TGFCAB_13 ||--o{ TGFFIN : "1:N"
    
    TGFCAB_11 {
        NUMBER NUNOTA
        NUMBER CODTIPOPER "= 11"
        VARCHAR2 CODAGREGACAO
    }
    
    TGFCAB_26 {
        NUMBER NUNOTA  
        NUMBER CODTIPOPER "= 26"
        VARCHAR2 CODAGREGACAO "Same as TOP 11"
    }
    
    TGFCAB_13 {
        NUMBER NUNOTA
        NUMBER CODTIPOPER "= 13" 
        VARCHAR2 CODAGREGACAO "Same as TOP 11/26"
    }
    
    TGFITE_11 {
        NUMBER NUNOTA
        NUMBER CODPROD
        VARCHAR2 GERAPRODUCAO
        VARCHAR2 CODAGREGACAO
    }
    
    TGFITE_26 {
        NUMBER NUNOTA
        NUMBER CODPROD "Classified products"
        VARCHAR2 CODAGREGACAO "Same lote"
    }
    
    TGFITE_13 {
        NUMBER NUNOTA
        NUMBER CODPROD "Same as 26"
        VARCHAR2 CODAGREGACAO "Same lote"
    }
    
    TGFFIN {
        NUMBER NUNOTA "References TOP 13"
        NUMBER NUFIN
        DATE DTVENC
        NUMBER VLRDESDOB
    }
```