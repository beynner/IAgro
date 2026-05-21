# Tabela de Preços do Sankhya — Levantamento e Plano

> **Status**: ✅ **Cat A implementada e em produção** (Mai/2026 — 2026-05-20). Cat B (popular `TGFITE.NUTAB` no INSERT/UPDATE) ainda pendente.

## 1. Resumo executivo

O Sankhya da Agromil resolve **preço de venda automático** via 3 tabelas:

- **`TGFPAR.CODTAB`** — seletor por cliente
- **`TGFTAB`** (NUTAB, CODTAB, DTVIGOR) — versão ativa de cada tabela
- **`TGFEXC`** (NUTAB, CODPROD, VLRVENDA, TIPO='V') — armazena os preços

Não há tabela `TGFPRH` (a convenção Sankhya). Na Agromil tudo vive em **TGFEXC** ("exceções de preço"). Validado contra pedidos reais (113098 → NUTAB=131 → preços batem 100%).

## 2. Schema

### TGFPAR (cadastro de cliente — fonte da regra)

| Coluna | Função |
|---|---|
| `CODTAB` | Aponta pra qual **tabela base** o cliente usa. **NULL = cliente sem tabela** (default geral). |
| `CODTABST` | Tabela de substituição tributária — fora do escopo deste documento |

### TGFTPV (tipo de venda) — **NÃO PARTICIPA**

Coluna `CODTAB` existe mas é **NULL em todos os 20 tipos ativos**. Tipo de venda não define tabela na Agromil.

### TGFPRO (produto) — **NÃO PARTICIPA**

Coluna `CODTAB` existe mas é **NULL em todos os produtos amostrados** (3 testados: 21, 26, 358). Produto não define tabela próprio. Também **não tem `PRECOBASE`** (coluna inexistente).

### TGFNTA (mestre — 1 linha por tabela, descoberta Mai/2026 — 2026-05-21)

Cadastro **nominal** das tabelas. Visível na tela Sankhya "Tabelas de Preços".

| Coluna | Função |
|---|---|
| `CODTAB` | PK |
| **`NOMETAB`** | **Nome humano** (ex: `ASSAI`, `ECONOMART`, `EXAL`, `JC`, `VERDI`...) |
| `OBS` | Observação |
| `DECVENDA` | Casas decimais |
| `CODTIPPARC` | Tipo de parceiro |
| `CODREG` | Região (FK TSIREG) |
| `CODMOEDA` | Moeda |
| `ATIVO` | S/N |

A view `VGFTAB` faz `INNER JOIN TGFNTA n ON n.CODTAB = t.CODTAB` + filtra a versão mais recente em `TGFTAB`. IAgro lê **direto de `TGFNTA`** pra pegar nomes (mais leve que a view).

### TGFTAB (cadastro de tabelas — versões por DTVIGOR)

16 linhas. Estrutura:

| Coluna | Função |
|---|---|
| `NUTAB` | PK — número único da versão da tabela |
| `CODTAB` | Código da tabela base (0, 2, 4, 5, 6, 10, 15, 17, 18) |
| `DTVIGOR` | Data inicial de vigência |
| `DTALTER` | Data limite (não validado se é usada como teto) |
| `CODTABORIG` | NUTAB de origem (versionamento) |

**Mapa CODTAB → NUTAB ativa** (mais recente com `DTVIGOR <= SYSDATE`):

| CODTAB | NUTAB ativa | DTVIGOR | Quem usa |
|---|---|---|---|
| **0** | **77** | 2013-06-24 | **Fallback geral** (clientes sem CODTAB próprio) |
| 2 | 138 | 2023-08-17 | — |
| 4 | 149 | 2023-09-15 | — |
| **5** | **131** | 2023-06-07 | **Assaí** (CODPARC 4, 6, 244 confirmados) |
| 6 | 157 | 2024-08-20 | — |
| 10 | 136 | 2023-06-08 | — |
| 15 | 139 | 2023-09-14 | — |
| 17 | 159 | 2026-01-05 | — |
| 18 | 158 | 2026-01-05 | — |

### TGFEXC (preço operacional — onde a regra "termina")

12 colunas. Os 5 campos relevantes:

| Coluna | Função |
|---|---|
| `NUTAB` | FK lógica → TGFTAB |
| `CODPROD` | FK lógica → TGFPRO |
| `CODLOCAL` | 0 em 100% dos casos amostrados |
| `CONTROLE` | vazio em 100% dos casos amostrados |
| `VLRVENDA` | **Preço de venda** |
| `TIPO` | `'V'` (venda). Pode existir `'C'` (compra) mas não confirmado |
| `DHALTREG` | Data da última alteração |

**Cobertura real** (por NUTAB):

| NUTAB | Produtos com preço |
|---|---|
| 77 (fallback) | **1 produto** ← cobertura quase nula |
| 129 | 109 |
| 130 | 104 |
| 139 | 108 |
| 149 | 102 |
| 138 | 54 |
| 158 | 35 |
| 157 | 35 |
| 159 | 35 |
| 136 | 33 |
| 131 (Assaí) | **30** |
| 125 | 34 |
| 123 | 29 |

**Total**: 709 linhas em TGFEXC. Confirma que cada cliente tem subset diferente — preço **não** é universal.

## 3. Regra de resolução completa

```
preço(codparc, codprod, dtneg):
    # 1. CODTAB do cliente (default 0 quando NULL — fallback geral)
    codtab = TGFPAR.CODTAB WHERE CODPARC=:codparc
    if codtab is None:
        codtab = 0

    # 2. NUTAB ativa: versão com DTVIGOR <= dtneg mais recente
    nutab = SELECT MAX(NUTAB) KEEP (DENSE_RANK FIRST ORDER BY DTVIGOR DESC)
              FROM TGFTAB
             WHERE CODTAB = :codtab
               AND DTVIGOR <= :dtneg

    if nutab is None:
        return None  # cliente sem tabela vigente (raro)

    # 3. Preço em TGFEXC (filtro TIPO='V')
    preco = SELECT VLRVENDA FROM TGFEXC
             WHERE NUTAB = :nutab AND CODPROD = :codprod AND TIPO = 'V'

    return preco  # pode ser None se produto não estiver tabelado
```

**Validação real** (pedido 113098, ASSAI ASA NORTE → CODTAB=5 → NUTAB=131):

| Item | CODPROD | TGFEXC[131,prod] | Pedido VLRUNIT | Bate? |
|---|---|---|---|---|
| 1 | 21 (ABÓBORA) | 3.5 | 3.5 | ✅ |
| 3 | 26 (BERINJELA) | 5.5 | 5.5 | ✅ |
| 10 | 358 (TOMATE) | 8.5 | 8.5 | ✅ |

100% de bate. Regra confirmada.

## 4. Comportamento esperado por cliente

| Cenário | Resultado |
|---|---|
| **Cliente cadastrado com CODTAB** (Assaí, redes) | Preço puxa automático da tabela vigente |
| **Cliente sem CODTAB (NULL)** | Cai em NUTAB=77 (1 produto coberto) → 99% das vezes preço vazio → **operador digita** |
| **Produto novo, não cadastrado em TGFEXC pra aquela NUTAB** | Preço vazio → operador digita |

Esse padrão explica os pedidos IAgro recentes: 100% dos itens TOP 34 dos últimos 7 dias têm `NUTAB=NULL` porque o IAgro nunca consultou TGFEXC e o operador digitou manualmente.

## 5. Plano de implementação (Cat A + Cat B)

### Backend — Cat A (leitura pura)

**Nova função service** em [oracle_conn.py](../sankhya_integration/services/oracle_conn.py):

```python
def consultar_preco_tabela(codparc: int, codprod: int, dtneg=None) -> dict:
    """Resolve preço de venda da tabela do cliente.

    Retorna:
        {
            'ok': True,
            'preco': float | None,
            'nutab': int | None,
            'codtab': int,
            'origem': 'TABELA_CLIENTE' | 'FALLBACK' | 'SEM_PRECO',
        }
    """
```

**Novo endpoint** em [urls.py](../sankhya_integration/urls.py) + [views.py](../sankhya_integration/views.py):

```
GET /sankhya/venda/api/preco-tabela/?codparc=X&codprod=Y[&dtneg=DD/MM/AAAA]
```

### Frontend — Cat A

[venda.js](../sankhya_integration/static/sankhya_integration/venda.js): no `onSelect` do typeahead `item_prod_vis`, depois de gravar `item_prod_hidden`, chama o endpoint passando `codparc` (do cabeçalho atual) e `codprod` (selecionado). Se vier `preco > 0`, popula `item_preco`. Senão deixa em branco (operador digita).

### Backend escrita — Cat B

[inserir_item_nota_banco / atualizar_item_nota_banco](../sankhya_integration/services/oracle_conn.py): popular `TGFITE.NUTAB` no INSERT/UPDATE quando o frontend enviar. Espelha o Sankhya nativo, fecha o gap detectado no smoke 113083.

### UX

- Preço puxa no `onSelect` do produto
- Campo `item_preco` continua editável (operador pode sobrescrever)
- Quando preço veio da tabela, exibir badge sutil ao lado do campo: `📋 R$ 8,50 da Tabela 131` (Cat A — refinamento opcional)
- Quando não veio preço (cliente sem CODTAB ou produto sem entrada): silêncio (campo vazio normal)

## 6. Cuidados / riscos

1. **DTVIGOR vs SYSDATE**: a regra usa `DTVIGOR <= SYSDATE`. Mas pedidos com `DTNEG` futura ou passada podem precisar usar `DTVIGOR <= DTNEG`. Confirmar se houver pedidos com data manual.
2. **Cobertura parcial**: cliente Assaí tem 30 produtos cobertos; demais 99% dos clientes não têm tabela. Frontend não deve "obrigar" preço — só preencher quando achar.
3. **Não escrever em TGFTAB nem TGFEXC**: tabelas de cadastro são geridas pelo Sankhya nativo. IAgro só **lê**.
4. **TGFITE.NUTAB** começa NULL no IAgro hoje. Popular **só pra TOP 34/35/37** (paridade Sankhya nativo).

## 7. Implementação Cat A (Mai/2026 — 2026-05-20)

### Backend
- **Função service** `consultar_preco_tabela(codparc, codprod, dtneg=None)` em [oracle_conn.py](../sankhya_integration/services/oracle_conn.py) — SELECT puro. Retorna `{ok, preco, nutab, codtab, origem}`.
- **Endpoint** `GET /sankhya/venda/api/preco-tabela/?codparc=X&codprod=Y[&dtneg=DD/MM/AAAA]` em [views.py `api_preco_tabela`](../sankhya_integration/views.py).
- **Rota** em [urls.py](../sankhya_integration/urls.py): `venda/api/preco-tabela/`.

### Frontend
- [venda.js](../sankhya_integration/static/sankhya_integration/venda.js) `puxarPrecoTabela()` é chamada no `onChange` do typeahead `item_prod_vis`.
- Popula `item_preco` apenas se vazio (respeita edição manual).
- Toast distinto por cenário (sucesso verde, sem preço/sem tabela cinza-info, erro vermelho).

### Bug corrigido durante implementação
**Conversão implícita de data no Oracle** — primeiro draft passava `dtneg` como string direta em `WHERE DTVIGOR <= :d`. Oracle interpretava `'21/05/2026'` usando `NLS_DATE_FORMAT` da sessão, gerando WHERE inválido → NUTAB=NULL → cliente Assaí (que tem tabela) caía em SEM_PRECO silencioso.

**Fix**: `TO_DATE(:d, 'DD/MM/YYYY')` (ou `'YYYY-MM-DD'`) explícito. Detecta formato pelo separador. Formato desconhecido cai em SYSDATE.

### Cobertura validada (smoke real contra Oracle)

| Cliente | CODTAB | NUTAB | Produto | Preço esperado | Resultado |
|---|---|---|---|---|---|
| Assaí Asa Norte (244) | 5 | 131 | Tomate Salada Extra (358) | 8.5 | ✅ |
| Assaí Asa Norte (244) | 5 | 131 | Abóbora Paulista (21) | 3.5 | ✅ |
| André Patrocinio (536) | NULL → 0 | 77 | Tomate (358) | — (sem preço) | ✅ |
| Cliente inexistente | NULL → 0 | 77 | Tomate (358) | — (sem preço) | ✅ |
| dtneg em 4 formatos | — | — | — | preço correto | ✅ 4/4 |

## 8. Pendência Cat B

⏸ **Popular `TGFITE.NUTAB` no INSERT/UPDATE TGFITE** — fica pra próxima sessão. Mesma situação do fix RESERVA/ATUALESTOQUE/USOPROD do dia 2026-05-20. Vai virar parte do payload do `inserir_item_nota_banco` quando `CODTIPOPER ∈ (34, 35, 37)`. Justificativa: pedido fica com NUTAB=NULL no IAgro (campo no TGFITE vazio), enquanto Sankhya nativo popula com a NUTAB resolvida. Não causa erro fiscal mas perde paridade. Volume baixo agora — pode esperar.
