# Módulo Classificação (TOP 26)

Triagem e classificação de lotes por qualidade com controle de descartes.

---

## Escopo

- Listar lotes pendentes de classificação (provenientes da Entrada/TOP 11 com `GERAPRODUCAO='S'`)
- Classificar quantidades por qualidade
- Registrar descartes em `AD_QTDAVARIA`
- Confirmar classificação criando TOP 26
- Modais de detalhes do lote

---

## URL e acesso

| Rota | Acesso |
|---|---|
| `/sankhya/compras/classificacao/` | Grupos `1`, `6`, `8` |

---

## Views principais (`views.py`)

| View | Propósito |
|---|---|
| `view_classificacao_lote` | Página HTML do portal |
| `api_lotes_classificacao` | Lista lotes pendentes |
| `api_detalhes_lote` | Detalhes de um lote específico |

---

## Regras específicas

- **`AD_QTDAVARIA`** registra descarte que vira a **perna E** (`AVARIA_FORNECEDOR`) na view `ANDRE_IAGRO_SALDO_LOTE` do WMS.
- Lote só fica disponível para vincular em pedido (Rastreio) **após** existir TOP 26 confirmada → vira **perna A** (`CLASSIFICADO`).
- Lotes ainda sem TOP 26 ficam como **perna C** (`AGUARDANDO_CLASSIFICACAO`) — não-vendáveis.
- Auto-cura de `AD_NUMPEDIDOORIG` aplicável (mesmo padrão da Entrada).

---

## Frontend

- **Template:** `classificacao.html`
- **CSS:** `classificacao.css`
- **JS:** `classificacao.js`
- **Container interno:** `.classificacao-grid` (flex, aside 320px + rightcol)

### CSS específico

- `.appbar { justify-content: space-between; margin-bottom }`
- Override `.main-layout { gap: 12px; padding-bottom: 40px }`
- `.ia-selectable-table`, `.switch .slider`, `.resumo-item`, `#produtosClassificadosWatermark`

---

## Pendências

- **Cobertura de testes dedicada** — hoje sem `test_views_classificacao.py`. Pendência roadmap #4.
