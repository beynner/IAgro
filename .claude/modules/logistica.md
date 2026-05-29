# Módulo Logística — Rotas de entrega

Tela de planejamento de viagens de entrega: caminhão, motorista, ajudantes, horário de saída e **destinos com qtd de caixas por parada**. Schema persistente em produção desde **Mai/2026 — 2026-05-29**.

Referência operacional: tela VBA existente "Entrada de Mercadoria" (apesar do título, é Rota) que o operador usa pra escalar caminhões + imprimir ficha pro motorista. IAgro replica o conceito com layout moderno + integração nativa ao TGFPAR/TGFVEI.

---

## Status atual

| Item | Estado |
|---|---|
| Tabelas `AD_VIAGEM_ENTREGA/DESTINO/AJUDANTE` + FK CASCADE | ✅ Em produção (Mai/2026 — 2026-05-29) |
| Cadastro de tipos `AD_TIPO_PARCEIRO` + junção `AD_PARCEIRO_TIPO` | ✅ Em produção — 885 vínculos migrados das flags TGFPAR |
| Funções service Cat A (leitura) | ✅ `listar_tipos_parceiro`, `consultar_parceiros_por_tipo`, `consultar_veiculos_logistica`, `consultar_proximo_num_viagem`, `listar_viagens`, `obter_viagem_detalhe` |
| Funções service Cat B (escrita) | ✅ `criar_viagem_banco`, `editar_viagem_banco`, `excluir_viagem_banco` — todas transacionais + audit + lock pessimista |
| Endpoints REST GET + POST | ✅ 9 endpoints (6 GET + 3 POST + 1 PDF) |
| PDF reportlab A6 vertical da ficha | ✅ `services/ficha_viagem_pdf.py` |
| Frontend desktop + mobile | ✅ `LogisticaApi` (REST) substituiu `LogisticaMock` (in-memory) |
| Tests mockados | ✅ 42 testes Cat A em `test_logistica.py` |
| Integração com Sankhya Viagens / MDFe | ⏸ Backlog longo prazo — ponte fiscal opcional documentada |

---

## Schema (Mai/2026 — 2026-05-29)

### Cadastro genérico de tipos de parceiro

| Tabela | Propósito |
|---|---|
| `AD_TIPO_PARCEIRO` | Cadastro de tipos (IDs 1-7 seed: CLIENTE, FORNECEDOR, USUARIO, MOTORISTA, AJUDANTE, TRANSPORTADORA, VENDEDOR). Sequence `SEQ_AD_TIPO_PARCEIRO` start=100 pra IDs novos. |
| `AD_PARCEIRO_TIPO` | Junção N:N parceiro × tipo. PK composta `(CODPARC, AD_CODTIPPARC)`. Índice reverso `(AD_CODTIPPARC, CODPARC)` pra typeahead. **885 vínculos migrados** das flags nativas TGFPAR (CLIENTE=381, FORNECEDOR=457, USUARIO=3, MOTORISTA=24, TRANSPORTADORA=4, VENDEDOR=16). |

**Migração one-time**: copiou flags TGFPAR para `AD_PARCEIRO_TIPO` com `NOMEUSU='MIGRACAO_INICIAL'`. Sankhya nativo permaneceu intocado. Reversível via `DELETE WHERE NOMEUSU='MIGRACAO_INICIAL'`. Tipo AJUDANTE (=5) é só IAgro — sem flag nativa correspondente.

### Tabelas de viagem

| Tabela | Estrutura |
|---|---|
| `AD_VIAGEM_ENTREGA` | Cabeçalho. ID (PK via `SEQ_AD_VIAGEM_ENTREGA`), NUM_VIAGEM (UNIQUE, visível ao operador, gerado por MAX+1), DATA_VIAGEM, HORA_SAIDA (CHECK regex HH:MM), CODVEICULO (FK lógica TGFVEI), CODPARC_MOTORISTA (FK lógica TGFPAR), OBSERVACAO, audit completo. 3 índices: DATA, MOTORISTA, VEICULO. |
| `AD_VIAGEM_DESTINO` | Paradas da viagem. ID (PK), VIAGEM_ID (FK ON DELETE CASCADE), ORDEM (UNIQUE por viagem), CODPARC_DESTINO, QTD_CAIXAS (CHECK > 0), OBSERVACAO. |
| `AD_VIAGEM_AJUDANTE` | N:N viagem × ajudante. PK composta `(VIAGEM_ID, CODPARC_AJUDANTE)`. FK ON DELETE CASCADE com `AD_VIAGEM_ENTREGA`. |

**Sem coluna STATUS** — exclusão é DELETE físico, histórico preservado via `AD_AUDITORIA_GERAL` (snapshot completo ANTES do DELETE).

**`AD_AUDITORIA_GERAL.CK_AD_AUDIT_MODULO`** ampliado pra aceitar `'logistica'` e `'ajustes'` (2026-05-29).

---

## Funções service

### Leitura (Cat A)

| Função | Propósito |
|---|---|
| `listar_tipos_parceiro(incluir_inativos=False)` | Cadastro de tipos ordenado por ORDEM_EXIBICAO |
| `consultar_parceiros_por_tipo(tipo_id, q, limite, somente_ativos)` | Typeahead Motorista/Ajudante/Cliente via JOIN AD_PARCEIRO_TIPO + TGFPAR. Constantes `TIPO_PARCEIRO_CLIENTE/MOTORISTA/AJUDANTE/etc` exportadas |
| `consultar_veiculos_logistica(q, somente_ativos, limite)` | Typeahead Veículo TGFVEI (sem restrição de grupo, diferente de Combustível) |
| `consultar_proximo_num_viagem()` | `MAX(NUM_VIAGEM)+1` (sem sequence; operador conhece o número) |
| `listar_viagens(filtros, limite, offset)` | Listagem paginada (ROW_NUMBER Oracle 11g). Filtros: data_de/ate, codparc_motorista, codveiculo, q (busca livre em motorista/placa). Retorna cabeçalho + LISTAGG de destinos + ajudantes. Inclui `qtd_caixas_total` agregado |
| `obter_viagem_detalhe(viagem_id)` | Detalhe completo: cabeçalho + destinos (com ID estável) + ajudantes |

### Escrita (Cat B)

| Função | Operação |
|---|---|
| `criar_viagem_banco(dados, codusu, nomeusu)` | Transação atômica: INSERT cabeçalho + N destinos + M ajudantes deduplicados. Lock pessimista em `MAX(NUM_VIAGEM)+1`. Valida FKs lógicas (TGFVEI ativo, MOTORISTA via tipo=4, CLIENTE via tipo=1, AJUDANTE via tipo=5). Audit `CRIAR_VIAGEM` com snapshot completo |
| `editar_viagem_banco(viagem_id, dados, codusu, nomeusu)` | UPDATE diferencial: cabeçalho atualizado, destinos por ORDEM (UPDATE se já existia, INSERT se nova, DELETE se sumiu) preservando IDs estáveis. Ajudantes via set diff. `NUM_VIAGEM` imutável. Audit `EDITAR_VIAGEM` com snapshot ANTES e DEPOIS |
| `excluir_viagem_banco(viagem_id, codusu, nomeusu, motivo)` | DELETE físico de `AD_VIAGEM_ENTREGA`. FK CASCADE remove destinos + ajudantes. Snapshot ANTES no audit pra reconstrução em emergência |

Todas: `verificar_permissao_escrita()` no topo (anti-fakes), transação atômica, mensagens humanizadas, Sankhya nativo intocado.

---

## Endpoints REST

| Método | Rota | Service |
|---|---|---|
| GET | `/sankhya/logistica/api/tipos-parceiro/` | `listar_tipos_parceiro` |
| GET | `/sankhya/logistica/api/parceiros/?tipo=N&q=...&limite=N` | `consultar_parceiros_por_tipo` |
| GET | `/sankhya/logistica/api/veiculos/?q=...&limite=N` | `consultar_veiculos_logistica` |
| GET | `/sankhya/logistica/api/viagens/?data_de=...&data_ate=...&q=...` | `listar_viagens` (+ `proximo_num_viagem` no payload) |
| GET | `/sankhya/logistica/api/viagem/<id>/` | `obter_viagem_detalhe` |
| GET | `/sankhya/logistica/api/viagem/<id>/ficha-pdf/` | `gerar_pdf_ficha_viagem` (PDF inline A6 vertical) |
| POST | `/sankhya/logistica/api/viagem/criar/` | `criar_viagem_banco` |
| POST | `/sankhya/logistica/api/viagem/<id>/editar/` | `editar_viagem_banco` |
| POST | `/sankhya/logistica/api/viagem/<id>/excluir/` | `excluir_viagem_banco` |

Acesso: `@exige_grupo('logistica')` — grupos `1` (Diretoria), `6` (Suporte), `10` (Administrativo).

---

## PDF reportlab da ficha

`services/ficha_viagem_pdf.py` gera PDF A6 vertical (~105×148mm) imprimível pra motorista. Layout:

- "ROTA" gigante centralizado (32pt verde Agromil)
- "VIAGEM Nº NNNN" (verde escuro)
- Data por extenso (`quinta-feira, 29/05/2026`)
- Hora destacada
- Motorista (nome grande)
- Ajudantes (linha menor)
- **PLACA gigante** centralizada (24pt Courier-Bold dentro de box verde) — operador identifica caminhão no pátio
- Destinos numerados com seta `>` e qtd, truncamento automático em nomes longos
- Linha de TOTAL
- Quadro amarelo de Observação (texto quebrado em linhas)
- Rodapé "IAgro · Logística"

Servido como `inline` via `Content-Disposition: inline; filename="rota_viagem_N.pdf"` — abre em aba nova pro operador imprimir ou baixar.

---

## Frontend

`LogisticaApi` (em `logistica.js`) é a camada de API REST exposta globalmente:

```js
window.LogisticaApi = {
    criarViagem(payload),
    editarViagem(viagemId, payload),
    excluirViagem(viagemId, motivo),
    carregarViagens(filtros),
    carregarParceiros(tipoId),
    carregarVeiculos(),
    recarregarTudo(),
    fichaPdfUrl(viagemId),
};
```

No boot do desktop:
1. Render inicial com `MOCK_ROTAS_FALLBACK` (8 viagens de demo) — UI aparece instantâneo
2. `recarregarDadosBackend()` fetch paralelo de 5 endpoints (veículos + 3 tipos de parceiros + viagens)
3. Sobrescreve `VEICULOS_MOCK`, `PARCEIROS_MOCK`, `MOCK_ROTAS` com dados reais
4. Re-render

`logistica_mobile.js` reusa `LogisticaApi` pra criar/editar/excluir, mantendo `LogisticaMock` pros helpers de display (`nomeMotorista`, `placaModelo`, `fmtDataBR` etc).

**Mapeamento de campos** entre backend e frontend interno:
- `data_viagem` ↔ `data` (formato JS)
- `destinos[i].observacao` ↔ `destinos[i].obs`
- `ajudantes[i] = {codparc, nomeparc}` ↔ `ajudantes[i] = codparc` (array de int)
- Funções `normalizarViagem()` e `payloadParaBackend()` cuidam da conversão

---

## Escopo (planejado)

- Planejar viagens de entrega com Nº VIAGEM sequencial
- Selecionar veículo (TGFVEI) + motorista (TGFPAR.TIPO=MOTORISTA) + ajudantes (TGFPAR.TIPO=AJUDANTE)
- Lista ordenada de **destinos** (TGFPAR.TIPO=CLIENTE) com qtd de caixas e obs por parada
- Observação geral do gestor (instruções pra rota toda)
- Imprimir ficha individual pro motorista (PDF formato vertical — placa gigante, hora destacada, destinos com `>` e qtd)
- CRUD completo (criar / editar / excluir)
- Filtros: período (default hoje), motorista, veículo, busca livre

### Fora de escopo (por enquanto)

- Status da viagem (Planejada/Em rota/Concluída) — VBA atual não usa
- Vínculo automático com vendas/classificação (qtd caixas vem manual do gestor por enquanto)
- Vínculo com MDFe do Sankhya
- Drag & drop pra reordenar destinos (excluir + re-adicionar resolve)

---

## URL e acesso

| Rota | Método | Propósito |
|---|---|---|
| `/sankhya/logistica/` | GET | Página HTML (simulação) — `@ensure_csrf_cookie` |

**Acesso:** Grupos `1` (Diretoria), `6` (Suporte), `10` (Administrativo). Decorator `@exige_grupo('logistica')`. Configurado em [decorators.py](../../sankhya_integration/decorators.py).

Quando vier o real, somam endpoints REST sob `/sankhya/logistica/api/*` (criar/listar/obter/editar/excluir + listar parceiros por tipo).

---

## Modelo de dados (planejado)

### Tabela cabeçalho `AD_VIAGEM_ENTREGA`

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_VIAGEM_ENTREGA` |
| `NUM_VIAGEM` | NUMBER UNIQUE | Sequencial visível ao operador (3043, 3044…) — separado do ID PK |
| `DATA_VIAGEM` | DATE NOT NULL | Data planejada |
| `HORA_SAIDA` | VARCHAR2(5) NOT NULL | `'HH:MM'` |
| `CODVEICULO` | NUMBER NOT NULL | FK lógica TGFVEI |
| `CODPARC_MOTORISTA` | NUMBER NOT NULL | FK lógica TGFPAR (tipo MOTORISTA) |
| `OBSERVACAO` | VARCHAR2(1000) | Texto livre do gestor pra rota toda |
| `STATUS` | VARCHAR2(20) DEFAULT 'ATIVA' CHECK | `'ATIVA'` / `'EXCLUIDA'` (soft-delete) |
| `CODUSU`, `NOMEUSU`, `CRIADO_EM` | — | Audit |
| `ATUALIZADO_EM`, `ATUALIZADO_POR` | — | Audit |

### Tabela auxiliar `AD_VIAGEM_DESTINO`

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_VIAGEM_DESTINO` |
| `VIAGEM_ID` | NUMBER FK ON DELETE CASCADE | → AD_VIAGEM_ENTREGA.ID |
| `ORDEM` | NUMBER NOT NULL | Sequência da parada (1, 2, 3…) |
| `CODPARC_DESTINO` | NUMBER NOT NULL | FK lógica TGFPAR (tipo CLIENTE) |
| `QTD_CAIXAS` | NUMBER NOT NULL CHECK > 0 | Manual por enquanto |
| `OBSERVACAO` | VARCHAR2(500) | Texto livre da parada (ex: "entregar antes 9h") |
| `CRIADO_EM` | TIMESTAMP DEFAULT SYSTIMESTAMP | — |

### Tabela auxiliar `AD_VIAGEM_AJUDANTE` (N:N)

| Coluna | Tipo | Função |
|---|---|---|
| `VIAGEM_ID` | NUMBER FK ON DELETE CASCADE | PK composto |
| `CODPARC_AJUDANTE` | NUMBER FK lógica TGFPAR | PK composto |

UNIQUE composto `(VIAGEM_ID, CODPARC_AJUDANTE)`.

### Campo de ponte fiscal — `NUVIAG_SANKHYA` em `AD_VIAGEM_ENTREGA`

Coluna **opcional NULLABLE** que correlaciona a rota IAgro com a viagem fiscal Sankhya (`TGFVIAG.NUVIAG`). Preenchida pelo operador **após emitir o MDFe** no Sankhya nativo. Permite ao IAgro exibir badge `📋 MDFe nº X (chave 53260...)` com STATUSMDFE/PESOBRUTOTOT/UFs lidos via JOIN read-only — sem nunca escrever em TGFVIAG/TGFMDFE.

| Coluna adicional | Tipo | Função |
|---|---|---|
| `NUVIAG_SANKHYA` | NUMBER NULL | FK lógica TGFVIAG. NULL até operador correlacionar |

Detalhes da arquitetura na seção [Ponte fiscal opcional com TGFVIAG](#ponte-fiscal-opcional-com-tgfviag) abaixo.

---

## Frontend — arquivos

| Arquivo | Função |
|---|---|
| [templates/sankhya_integration/logistica.html](../../sankhya_integration/templates/sankhya_integration/logistica.html) | Desktop (resumo + filtros + lista) + mobile (2 telas + 3 sheets) + modal desktop nova/editar + modal ficha de impressão |
| [static/sankhya_integration/logistica.css](../../sankhya_integration/static/sankhya_integration/logistica.css) | Layout desktop + bloco "REDESIGN MOBILE-FIRST" escopado por `body[data-active-module="logistica"]` + ficha de impressão com `@media print` |
| [static/sankhya_integration/logistica.js](../../sankhya_integration/static/sankhya_integration/logistica.js) | Desktop com mock TGFPAR (35+ parceiros, 3 tipos) + mock TGFVEI (8 veículos) + 8 viagens exemplo (Nº 3042-3048). Expõe `window.LogisticaMock` |
| [static/sankhya_integration/logistica_mobile.js](../../sankhya_integration/static/sankhya_integration/logistica_mobile.js) | Mobile IIFE — reusa `LogisticaMock`. Edições refletem em ambos os lados |

---

## UX — Tela desktop

### Topo
- **4 cards de resumo**: Viagens no período · Caixas a entregar · Destinos no dia · Motoristas escalados

### Layout principal (grid 220px + 1fr)
- **Sidebar filtros (esquerda, 220px)**: Período com `<<`/`>>`, busca livre, select de motorista, select de veículo, botão "Limpar filtros"
- **Lista de cards (direita)**: cards horizontais com Nº VIAGEM em destaque + placa + motorista/ajudantes + destinos resumidos (3 primeiros + "+N") + total de caixas + botão impressora

### Cards de viagem
Layout grid 4 colunas: `[Nº VIAGEM destacado | dados centrais | preview destinos | total + botão imprimir]`. Cor de borda esquerda verde Agromil. Hover eleva +1px com box-shadow. Click no card abre edição; click no botão impressora abre ficha.

### Modal Nova/Editar (2 colunas, 960px)
- **Coluna esquerda**: typeahead Veículo (TGFVEI) + Data + Hora + typeahead Motorista (TGFPAR.MOTORISTA) + multi-typeahead Ajudantes (chips) + Observação
- **Coluna direita**: lista de destinos editável — cada linha tem ordem (badge circular), typeahead de cliente (TGFPAR.CLIENTE), input qtd_caixas, botão remover. Total de caixas calculado em runtime no rodapé do bloco
- Footer: Excluir (vermelho, só edição) · Ver ficha (só edição) · Cancelar · Confirmar viagem

### Modal Ficha de impressão
Layout vertical estilo papel (420px de largura) com:
- "ROTA" gigante centralizado
- "VIAGEM Nº NNNN" em verde monospace
- Data por extenso (`quinta-feira, 28/05/2026`) + Saída às `HH:MM`
- Motorista (nome grande)
- Ajudantes (menor)
- **PLACA gigante** centralizada (48px, monospace) — operador identifica o caminhão de longe
- Destinos numerados com seta `>` + qtd ao lado
- Linha de total
- Quadro de observação
- Rodapé "IAgro · Logística"

Botão "Imprimir" usa `window.print()` com CSS `@media print` escondendo tudo menos a ficha (toolbar + sombras removidas).

---

## UX — Tela mobile

### Telas
1. **lista** — header com user badge + Sair + 4 pílulas de resumo + busca + lista de cards + bottom nav 4 itens + 2 FABs (verde "+" Nova / azul "Atualizar")
2. **detalhe** — hero verde com Nº VIAGEM gigante + card branco com placa em destaque + hora + info (motorista, ajudantes) + bloco de destinos numerados + observação âmbar + ações (Ver ficha, Excluir)

### Sheets
- **rota** (`m-sheet__content--tall`): form de nova/editar com mesma estrutura do desktop, destinos numerados editáveis
- **filtros**: período + select motorista + select veículo
- **mais**: Atualizar lista + Nova viagem

### Cards de viagem (mobile)
Grid 3 colunas: `[Nº VIAGEM circular | dados (placa+motorista+hora+destinos resumidos) | qtd total caixas]`. Click abre detalhe.

### Ficha mobile
Reutiliza o overlay desktop (sempre presente no DOM). Click "Ver ficha" no detalhe ou no header da tela 2 abre o mesmo modal vertical. `window.print()` funciona igual.

### Gestos
- **Swipe-to-back** nas telas internas (detalhe → lista) via history API
- Sem swipe-to-edit/delete nos cards (decisão: ações via tap → tela detalhe ou header)

---

## Mock data (memória)

### TGFPAR (3 tipos, 35+ parceiros)

| Tipo | Exemplos | Uso |
|---|---|---|
| **CLIENTE** | ASSAI SIA · ASSAI ASA NORTE · ASSAI CEILANDIA · ASSAI TAGUATINGA · ASSAI PALMAS TEOTONIO/CESAMAR · ASSAI ARAGUAINA · VERDI ASA SUL/NORTE/LAGO SUL · ECONOMART BARREIRAS/LEM · EXAL LUNDIN/AURA · NA HORTA · JC ANAPOLIS/GOIANIA | Destinos da viagem |
| **MOTORISTA** | VICENTE · ALAN · HENRIQUE · ALVERI · WELINGTON · CARLOS · ROBERTO · JOSÉ MENDES | Typeahead Motorista |
| **AJUDANTE** | JULIANO · PEDRO · MARIA · BRUNO · FELIPE · ANDERSON · PAULO HENRIQUE · LUCAS · TIAGO | Multi-typeahead Ajudantes |

### TGFVEI (8 veículos)

Placas formato Mercosul (`JFO-5H79`, `OVT-0B51`, `PBW-0D02`, `RER-2B08`, etc.) com modelos reais (MB 2544, VW 24.280, MB ACCELO, FORD CARGO, IVECO TECTOR…).

### Viagens (8 exemplos)

Nº 3042-3048 distribuídos entre ontem/hoje/amanhã, cobrindo cenários reais:
- Vicente + Juliano → 2 destinos Assaí
- Alan + 2 ajudantes → 3 destinos Verdi DF
- Henrique + Juliano → 2 Assaí (modelo da ficha do print VBA)
- Alveri + 2 ajudantes → 2 Palmas (saída 04:00 madrugada)
- Welington + 3 ajudantes → 2 Economart Bahia (saída 02:30 — viagem longa)
- Carlos + 1 ajudante → 2 destinos mix (ontem)
- Roberto + 2 ajudantes → 3 destinos Goiás (amanhã)

---

## Helpers expostos pra mobile (`window.LogisticaMock`)

| Método | Função |
|---|---|
| `getRotas()` / `getParceiros()` / `getVeiculos()` | Listas in-memory |
| `parceirosPorTipo(tipo)` | Filtra TGFPAR mock por TIPO |
| `buscarParceiro(codparc)` / `buscarVeiculo(codveiculo)` | Lookup |
| `addRota(r)` / `atualizarRota(id, dados)` / `removerRota(id)` | CRUD in-memory |
| `nomeMotorista(r)` / `nomeAjudantes(r)` / `nomeDestino(codparc)` / `placaModelo(r)` / `totalCaixas(r)` | Helpers de display |
| `fmtDataBR(iso)` / `fmtDataExtenso(iso)` | Formatação de data |
| `rerenderDesktop()` | Re-render do desktop após mudança no mobile |
| `proximoNumViagem()` | Próximo nº sequencial |

Edições no mobile chamam `rerenderDesktop()` pra manter desktop sincronizado quando houver troca de orientação ou redimensionamento.

---

## Decisões de regra

1. **Tudo é mock por enquanto** — refresh limpa edições. Pra persistir, criar Cat B com DDL + endpoints + chamar TGFPAR/TGFVEI reais.
2. **NUM_VIAGEM separado do ID PK** — operador conhece o número (espelha VBA). Inicia em 3049 na simulação; no real, definir se continua do último do VBA ou começa do 1.
3. **Sem status** (Planejada/Em rota/Concluída) — VBA atual não usa, IAgro não cria complexidade até aparecer demanda. Soft-delete via `STATUS='EXCLUIDA'` se vier.
4. **Qtd_caixas é manual** — responsável da rota digita. Integração com vendas/classificação fica pra fase 2.
5. **Destinos em tabela auxiliar `AD_VIAGEM_DESTINO`** com ORDEM explícita — permite reordenar sem trigger.
6. **Ajudantes em tabela auxiliar `AD_VIAGEM_AJUDANTE`** (N:N) — múltiplos por viagem, mesmo ajudante em viagens diferentes.
7. **Motorista, ajudante e destino vêm todos de TGFPAR** com discriminador por TIPO. Confirmado pelo operador: cada parceiro Sankhya pode ser classificado em tipos (cliente, fornecedor, motorista, etc).
8. **Ficha de impressão tem layout vertical** — operador entrega na mão do motorista, formato compacto. PLACA gigante por causa do pátio (motorista identifica o caminhão).
9. **Botão Imprimir usa `window.print()` no MVP** — na simulação. No real, gera PDF reportlab com mesmo layout (mesmo padrão das etiquetas SafeTrace).

---

## Próximos passos

1. **Operador navega na simulação** e valida UX (fluxo de criação, sub-tabela de destinos, ficha de impressão)
2. **Plano Cat B** com schema (`AD_VIAGEM_ENTREGA` + `AD_VIAGEM_DESTINO` + `AD_VIAGEM_AJUDANTE`)
3. **Função `consultar_parceiros_por_tipo(tipo)`** em [oracle_conn.py](../../sankhya_integration/services/oracle_conn.py) lendo TGFPAR + filtro de tipo (verificar como o operador classifica — provavelmente `TGFPAR.CODTIPPARC` ou flag customizada)
4. **5 endpoints REST**: criar / listar (paginado) / obter / editar / excluir + 1 endpoint de typeahead `/api/parceiros/por-tipo/?tipo=X`
5. **PDF reportlab** da ficha — replicar layout HTML, formato A6 ou meia-A5
6. **Tests** mockados (acesso por grupo, criar/listar/editar/excluir, integridade dos destinos)
7. **Eventual integração com Sankhya Viagens/MDFe** — vide nota do operador: "no sankhya tem viagens, pra fazer o MDFe. mas depois vemos isso"

---

## Pendência conhecida — classificação de parceiros por tipo no Sankhya

O operador mencionou: *"Cada parceiro tem um tipo. cliente, fornecedor, motorista, etc..."* Investigar antes da implementação Cat B:

- Existe campo `TGFPAR.CODTIPPARC` ou similar com enumeração de tipo?
- Como o operador atualmente diferencia MOTORISTA/AJUDANTE de CLIENTE no Sankhya?
- Há tabela auxiliar `TGFTPP` (Tipos de Parceiro) ou customização local?

Smoke simples no Oracle resolve isso. Resultado vira parâmetro de filtro em `consultar_parceiros_por_tipo`.

---

## Ponte fiscal opcional com TGFVIAG

**Análise feita em Mai/2026 (2026-05-29) via 4 smokes completos** contra Oracle de produção (1.089 viagens históricas Agromil). Decisão arquitetural: **Opção C — paralelo + ponte fiscal opcional**.

### O que o Sankhya tem (envelope técnico SEFAZ)

6 tabelas mapeadas, **todas sem triggers próprias** (achado importante: diferente de TGFCAB/TGFITE/TGFVAR, escritas são "inertes" no nível do schema; Java escreve direto). Detalhes completos em [`dependencias_sankhya.md`](../dependencias_sankhya.md) §1.18.

| Tabela | Volume Agromil | Papel |
|---|:-:|---|
| `TGFVIAG` | 1.089 | Cabeçalho fiscal (15 colunas: CODEMP, CODVEIPRIN+3 reboques, STATUSDOC, TIPMODALMDFE) |
| `TGFMDFE` | 1.050 | Dados do manifesto (chave, XML, peso bruto, UFs) |
| `TGFNMDFE` | 1.588 | NFs vinculadas (PK composta NUVIAG+SEQMDFE+NUNOTA) |
| `TGFEMDF` | 979 | Eventos SEFAZ — **100% Encerramento/Cancelamento, 0% Inclusão Condutor** |
| `TGFOMDF` | 748 | Ocorrências livres (CLOB) |
| `TGFNCTE` | 1.916 | XMLs de CT-e por NUNOTA |

### Por que NÃO reusar TGFVIAG como tabela primária

| Conceito IAgro precisa | Existe em TGFVIAG? | Comentário |
|---|:-:|---|
| Motorista principal | ❌ | Sankhya espera via TGFEMDF como evento "Inclusão de Condutor" — **0% usado pela Agromil** |
| Ajudantes | ❌ | MDFe SEFAZ não tem esse conceito |
| Hora planejada de saída | ❌ | Só `DHALTER` (cadastro) |
| Destinos com qtd_caixas por parada | ❌ | MDFe vincula NF inteira — sem rateio |
| Observação livre do gestor | ❌ | TGFOMDF é log de ocorrência fiscal |
| Status operacional | ⚠ | STATUSDOC fiscal ('C'/'E') conflita com Planejada/Em rota/Concluída |

Forçar reuso exigiria ~8 colunas `AD_*` em TGFVIAG + 2-3 tabelas auxiliares — poluiria envelope fiscal e dificulta spin-off (replicar TGFMDFE com 43 colunas + XMLs SEFAZ é caro).

### Arquitetura escolhida

**`AD_VIAGEM_ENTREGA` paralela** (operacional puro, definida acima) com **campo `NUVIAG_SANKHYA` NULLABLE** correlacionando com `TGFVIAG.NUVIAG` quando MDFe é emitido.

**Fluxo operacional**:
1. Operador planeja rota no IAgro → cria `AD_VIAGEM_ENTREGA` com motorista + ajudantes + destinos + qtd_caixas
2. Operador imprime ficha pro motorista (PDF reportlab)
3. Motorista executa rota
4. Operador (no Sankhya nativo) emite o MDFe quando preciso (1-2 NFs por viagem, padrão Agromil)
5. Operador volta no IAgro e digita `NUVIAG_SANKHYA` na rota (ou seleciona via lookup)
6. IAgro passa a exibir badge `📋 MDFe nº NUMMDFE (chave XX...)` na rota correlacionada

### Funções service Cat A planejadas (leitura pura — sem aprovação ponto-a-ponto)

```python
def consultar_mdfe_da_viagem(nuviag_sankhya: int) -> Optional[dict]:
    """
    SELECT JOIN TGFVIAG + TGFMDFE + TGFNMDFE.
    Retorna {numero_mdfe, status_mdfe, chave_mdfe, dt_emissao,
             uf_inicial, uf_final, peso_bruto_tot, nfs: [...]}
    ou None se nuviag não existe.
    """

def listar_viagens_sankhya_disponiveis(filtros) -> list:
    """
    SELECT TGFVIAG WHERE NUVIAG NOT IN (
        SELECT NUVIAG_SANKHYA FROM AD_VIAGEM_ENTREGA
         WHERE NUVIAG_SANKHYA IS NOT NULL
    )
    + filtros por CODEMP, CODVEIPRIN, periodo.
    Pra typeahead "correlacionar com MDFe existente".
    """
```

### Endpoint REST planejado

```
GET /sankhya/logistica/api/viagem/<id>/mdfe-info/
    → {numero_mdfe, status_mdfe, chave, dt_emissao, peso_bruto_tot, nfs: [...]}
       ou {sem_mdfe: true}

GET /sankhya/logistica/api/sankhya-viagens-disponiveis/?q=&codemp=
    → [{nuviag, codveiprin, placa, dt_emissao, status}] (typeahead)
```

### Decisões consolidadas

| # | Decisão |
|---|---|
| 1 | **Zero escrita em TGFVIAG/TGFMDFE/TGFNMDFE/etc** pelo IAgro |
| 2 | `NUVIAG_SANKHYA` na `AD_VIAGEM_ENTREGA` é **opcional** — operador pode usar IAgro sem nunca emitir MDFe |
| 3 | Ponte fiscal é **read-only ponto a ponto** — não cacheado |
| 4 | Badge `📋 MDFe...` no card da rota mostra status fiscal em tempo real |
| 5 | Operador digita NUVIAG manualmente ou seleciona via lookup `listar_viagens_sankhya_disponiveis` |
| 6 | IAgro **nunca dispara emissão MDFe** — continua sendo no Sankhya nativo |
| 7 | Spin-off futuro: AD_VIAGEM_ENTREGA migra direto; ponte fiscal vira plugin SEFAZ próprio |

### Limitações conscientes

- Operador esquecer de correlacionar = ficha IAgro fica sem badge MDFe (não bloqueia operação)
- Volume IAgro (~415 rotas/ano projetadas) ≠ volume MDFe (Sankhya pode emitir múltiplos MDFe por rota IAgro ou 1 MDFe consolidando várias rotas — relação livre, sem constraint)
- Sem busca reversa "Sankhya emite MDFe → notifica IAgro" — fluxo é manual one-way
