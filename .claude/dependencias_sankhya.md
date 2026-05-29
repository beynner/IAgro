# Dependências do Sankhya — Mapa Completo

> **Propósito:** documento vivo que mapeia TODA dependência do IAgro no schema Sankhya — tabelas, triggers, funções proprietárias, regras invisíveis. Servirá de blueprint pra recriar o schema necessário quando o IAgro for desacoplado e virar produto independente.
>
> **Regra de manutenção (CLAUDE.md):** sempre que detectar **nova tabela**, **nova trigger**, **nova função/sequence**, **nova constante** ou **regra invisível** do Sankhya sendo consumida pelo IAgro, **atualizar este arquivo** antes/junto da implementação. Não deixar acumular.

---

## 1. Tabelas Sankhya Consumidas pelo IAgro

### 1.1 TGFCAB — Cabeçalho de Notas / Pedidos

**Propósito:** Núcleo de qualquer documento (compra, venda, transferência, classificação, devolução, avaria, requisição).

**Operações do IAgro:**
- **SELECT**: Leitura de pedidos abertos, notas faturadas, detalhes de cabeçalho
- **INSERT**: Criação de notas (Entrada TOP 11, Classificação TOP 26, Venda TOP 34, Combustível TOP 10/53, Avaria TOP 30, Devolução TOP 36)
- **UPDATE**: Atualização de status, observações, dados de negociação
- **DELETE**: Exclusão física de requisições não faturadas (Combustível TOP 53)

**Colunas usadas pelo IAgro:**
- `NUNOTA` — Número único da nota (PK)
- `NUMNOTA` — Número sequencial por empresa (gerado em faturamento ou manual)
- `CODEMP` — Código da empresa
- `CODPARC` — Código do parceiro (cliente/fornecedor)
- `CODTIPOPER` — TOP (Tipo de Operação): 10, 11, 13, 26, 30, 34, 35, 36, 37, 53
- `CODNAT` — Código de natureza de receita/despesa
- `CODTIPVENDA` — Tipo de negociação (FK → TGFTPV)
- `DHTIPVENDA` — Timestamp de alteração da TGFTPV (exigido por trigger)
- `STATUSNOTA` — Status: `L` (liberada), `E` (excluída), NULL/outro (em aberto)
- `DTNEG` — Data da negociação
- `DTMOV` — Data do movimento
- `DTFATUR` — Data do faturamento
- `VLRNOTA` — Valor total
- `QTDVOL` — Quantidade total de volumes
- `OBSERVACAO` — Observação livre
- `CODUSU` — Usuário criador
- `AD_NUMPEDIDOORIG` — Campo customizado: pedido raiz (auto-cura Entrada/Classificação)

**Funções que manipulam:**
- `inserir_cabecalho_nota_banco` — INSERT (Entrada TOP 11, Classificação TOP 26, etc.)
- `atualizar_cabecalho_venda_banco` — UPDATE Venda (TOP 34, sem auto-cura)
- `atualizar_cabecalho_nota_banco` — UPDATE genérico com auto-cura AD_NUMPEDIDOORIG
- `faturar_pedido_venda_banco` — INSERT+UPDATE (cria TOP 35/37)
- `criar_avaria_top30_banco` — INSERT (TOP 30)
- `criar_devolucao_top36_banco` — INSERT (TOP 36)
- `criar_requisicao_combustivel_banco` — INSERT (TOP 53)
- `criar_entrada_combustivel_banco` — INSERT (TOP 10)
- `excluir_requisicao_combustivel_banco` — DELETE (TOP 53)

---

### 1.2 TGFITE — Itens de Notas / Pedidos

**Propósito:** Linhas de cada documento, vinculadas a TGFCAB.

**Operações do IAgro:**
- **SELECT**: Leitura de itens, saldos, lotes, rastreabilidade
- **INSERT**: Adição de produtos a notas
- **UPDATE**: Mudança de quantidade, lote, peso, status de conferência
- **DELETE**: Remoção de itens não faturados

**Colunas usadas pelo IAgro:**
- `NUNOTA` — FK → TGFCAB.NUNOTA
- `SEQUENCIA` — Sequência do item (PK composto)
- `CODPROD` — Código do produto
- `CODVOL` — Unidade de volume (KG, UN, LT, etc.)
- `QTDNEG` — Quantidade negociada
- `VLRUNIT` — Valor unitário
- `VLRTOT` — Valor total da linha
- `CODLOCALORIG` — Local de origem do estoque (default 101)
- `CODAGREGACAO` — **Lote** (rastreabilidade). Formato: `NUNOTAS{SEQ}D{YYMMDD}` (Entrada), livre (Venda), NULL (Venda até atribuição)
- `PESO` — **Peso da caixa** (canônico em TODAS as TOPs IAgro). TOP 11 (Entrada): digitado pelo operador na pesagem. TOP 26 (Classificação): peso classificado. TOP 13 (Vale): propagado da TOP 11. TOP 34/35/37/30/36 (Venda/Avaria/Devolução — Mai/2026 / 2026-05-16): grava peso da caixa pra cálculo de etiqueta SafeTrace (`math.ceil(qtdneg/peso)`). Anteriormente o Rastreio usava `QTDFIXADA` aqui — migrado pra `PESO` por coerência semântica.
- `QTDFIXADA` — Quantidade fixada por contrato (semântica nativa Sankhya). IAgro **não escreve** mais nesse campo na TOP 34/35/37/30/36 desde 2026-05-16. Mantém intocada — Sankhya nativo continua populando 0 por default em ~99.999% das vendas
- `AD_QTDAVARIA` — Quantidade de avaria (descarte — Classificação)
- `AD_PESO` — Peso registrado na pesagem (Entrada)
- `AD_QTDCONFERIDA` — Quantidade conferida (Entrada)
- `GERAPRODUCAO` — Flag `S`/`N` para gerar TOP 26 (Entrada)
- `QTDENTREGUE` — Quantidade entregue (populada por trigger TGFVAR)
- `RESERVA` — Flag `S`/`N` de reserva de estoque. **Mai/2026 (2026-05-20)**: IAgro grava `'S'` em TOP 34/35/37 pra bater com a definição da TOP — trigger `TRG_UPT_TGFITE` rejeita UPDATE quando NEW.RESERVA diverge
- `ATUALESTOQUE` — Flag de atualização de estoque. **Mai/2026 (2026-05-20)**: IAgro grava `1` em TOP 34/35/37 (era default `-1` que aciona o trigger)
- `USOPROD` — Tipo de uso do produto (`'V'`=Venda, `'R'`=Revenda, `'C'`=Consumo, etc). **Mai/2026 (2026-05-20)**: IAgro lê de `TGFPRO.USOPROD` em TOP 34/35/37 (era chute fixo `'V'`)

**Funções que manipulam:**
- `inserir_item_nota_banco` — INSERT (gera lote auto ou manual; grava PESO em TOP 11/26/13)
- `atualizar_item_nota_banco` — UPDATE
- `atribuir_lote_item_pedido` — UPDATE/INSERT (Rastreio: atribui CODAGREGACAO+**PESO** na TOP 34/35/37 — Mai/2026 / 2026-05-16)
- `desvincular_lote_item_pedido` — UPDATE (Rastreio: limpa CODAGREGACAO+**PESO** no caminho CLEAR)
- `consultar_pesos_classificacao_lote` — SELECT DISTINCT PESO da TOP 26 (fallback de etiqueta — Mai/2026 / 2026-05-16)
- `excluir_itens_nota_banco` — DELETE

---

### 1.3 TGFPAR — Parceiros (Clientes/Fornecedores)

**Propósito:** Cadastro de clientes e fornecedores.

**Operações do IAgro:**
- **SELECT**: Leitura de dados do parceiro (nome, CNPJ)
- Nenhuma escrita

**Colunas usadas:**
- `CODPARC` — PK
- `NOMEPARC` — Nome/razão social
- `RAZAOSOCIAL` — Razão social oficial
- `CGC_CPF` — CNPJ/CPF
- `ATIVO` — Flag `S`/`N`
- `CODTAB` — **Seletor da tabela de preço** (Mai/2026 — 2026-05-20). NULL = sem tabela (fallback CODTAB=0 → NUTAB=77). Apontado pra base de versão em TGFTAB. Detalhes em `.claude/tabela_precos_sankhya.md`.

**Funções:**
- `consultar_parceiros_oracle` — Typeahead (busca por código ou nome)
- `consultar_preco_tabela` (Mai/2026 — 2026-05-20) — Lê `CODTAB` pra resolver preço de venda do produto

---

### 1.4 TGFTPV — Tipos de Negociação

**Propósito:** Cadastro de tipos de venda (à vista, crédito, etc.).

**Operações do IAgro:**
- **SELECT**: Leitura de tipos ativos, busca por DHALTER mais recente

**Colunas usadas:**
- `CODTIPVENDA` — PK
- `DESCRTIPVENDA` — Descrição
- `ATIVO` — Flag `S`/`N`
- `DHALTER` — Timestamp de última alteração (crítico para DHTIPVENDA em TGFCAB)
- `BASEPRAZO` — Prazo padrão em dias

**Funções:**
- `consultar_tipos_negociacao_oracle` — Typeahead
- `inserir_cabecalho_nota_banco` — Busca DHALTER mais recente
- `consultar_prazo_tipvenda` — Lê BASEPRAZO + regex em DESCRTIPVENDA

**Trigger dependência:** `TRG_INC_TGFCAB` exige tupla `(CODTIPVENDA, DHTIPVENDA)` coerente. Erro: `ORA-20101: Verifique se o TIPO DE NEGOCIAÇÃO X está ativo...`

**Coluna `CODTAB`:** Existe mas é **NULL em todos os 20 tipos ativos** na Agromil (validado Mai/2026 — 2026-05-20). Tipo de venda NÃO participa da resolução de preço.

---

### 1.4.4 TGFNTA — Cadastro Nominal das Tabelas de Preço (Mai/2026 — 2026-05-21)

**Propósito:** Mestre nominal das tabelas de preço — 1 linha por `CODTAB` com o nome humano (ASSAI, ECONOMART, EXAL, JC, VERDI...). É a tabela que aparece na tela "Tabelas de Preços" do Sankhya com a coluna "Nome".

**Operações do IAgro:**
- **SELECT**: lê NOMETAB pra exibir nome do grupo na tela de Tabela de Preços + select de Promoção

**Colunas usadas:**
- `CODTAB` (PK)
- `NOMETAB` — nome humano da tabela
- `OBS` — observação
- `DECVENDA` — casas decimais
- `CODTIPPARC` — tipo de parceiro
- `CODREG` — região
- `CODMOEDA` — moeda
- `ATIVO` — `S`/`N`

**Função que consulta:**
- `listar_tabelas_grupos` — `SELECT n.CODTAB, n.NOMETAB, n.ATIVO ... FROM TGFNTA n` (LEFT JOIN com TGFPAR pra contar clientes vinculados; ordena por UPPER(NOMETAB))

**Discoverability:** view `VGFTAB` faz `INNER JOIN TGFNTA ON TGFNTA.CODTAB = TGFTAB.CODTAB AND TGFTAB.DTVIGOR = MAX(DTVIGOR)`. IAgro lê **direto de TGFNTA** pra leitura mais leve e semântica clara (mestre vs versionamento).

---

### 1.4.5 TGFTAB — Cadastro de Tabelas de Preço (Mai/2026 — 2026-05-20)

**Propósito:** Histórico de versões das tabelas de preço — cada combinação `(CODTAB, DTVIGOR)` é uma versão.

**Operações do IAgro:**
- **SELECT**: Resolve NUTAB ativa por CODTAB + data

**Colunas usadas:**
- `NUTAB` — PK (ID único da versão)
- `CODTAB` — Código da tabela base (a Agromil usa 0, 2, 4, 5, 6, 10, 15, 17, 18)
- `DTVIGOR` — Data inicial de vigência
- `DTALTER` — Data limite (não validado)
- `CODTABORIG` — NUTAB de origem (versionamento)

**Função:**
- `consultar_preco_tabela` — Resolve `MAX(NUTAB) KEEP DENSE_RANK FIRST ORDER BY DTVIGOR DESC WHERE CODTAB=:ct AND DTVIGOR <= TO_DATE(:d, 'DD/MM/YYYY')`

**Volume na Agromil:** 16 linhas. Mapa CODTAB → NUTAB ativa: 0→77 (fallback geral), 5→131 (Assaí), 17→159, 18→158, etc.

---

### 1.4.6 TGFEXC — Preços por Produto e Tabela (Mai/2026 — 2026-05-20)

**Propósito:** Tabela operacional de preços. Apesar do nome "exceções", é a fonte principal na Agromil.

**Operações do IAgro:**
- **SELECT**: Resolve VLRVENDA por `(NUTAB, CODPROD)`

**Colunas usadas:**
- `NUTAB` — FK lógica → TGFTAB
- `CODPROD` — FK lógica → TGFPRO
- `VLRVENDA` — Preço de venda
- `TIPO` — `'V'` (venda); pode haver `'C'` (compra) mas não confirmado
- `CODLOCAL` — 0 em todos os casos amostrados (não usado)
- `CONTROLE` — vazio em todos os casos (não usado)
- `DHALTREG` — Data da última alteração

**Função:**
- `consultar_preco_tabela` — `SELECT VLRVENDA FROM TGFEXC WHERE NUTAB=:n AND CODPROD=:p AND TIPO='V'`

**Volume na Agromil:** 709 linhas. Cobertura por NUTAB varia (NUTAB 77 fallback = 1 produto; NUTAB 131 Assaí = 30; NUTAB 129 = 109 produtos).

---

### 1.5 TSIEMP — Empresas

**Propósito:** Cadastro de empresas do grupo (Agromil, Semear, etc.).

**Operações do IAgro:**
- **SELECT**: Leitura de nome fantasia, razão social, dados pra etiqueta SafeTrace

**Colunas usadas:**
- `CODEMP` — PK
- `RAZAOSOCIAL` — Razão social
- `NOMEFANTASIA` — Nome fantasia
- `CGC` — CNPJ
- `LATITUDE` / `LONGITUDE` — Geolocalização (Mai/2026, etiqueta)
- `ENDERECO` / `LOGRADOURO` / `NOMEEND` — Endereço (opcional, detectado via `_existe_coluna`)
- `CEP` — CEP (opcional)

**Funções:**
- `consultar_empresas_oracle` — Typeahead
- `consultar_dados_etiqueta_pedido` — JOIN pra cabeçalho da etiqueta

---

### 1.6 TGFFIN — Financeiro

**Propósito:** Registros de títulos a receber/pagar.

**Operações do IAgro:**
- **INSERT**: Criação de financeiro (Comercial vale TOP 13, Combustível TOP 10, Abastecimento externo TOP 53)
- **SELECT**: Leitura de detalhes (futura expansão)
- **UPDATE**: Edição de financeiro em aberto (Combustível)

**Colunas usadas:**
- `NUFIN` — Número financeiro (PK)
- `NUNOTA` — FK → TGFCAB
- `CODPARC` — Parceiro
- `VLRDESDOB` — Valor do desdobramento
- `DTVENC` — Data de vencimento
- `RECDESP` — 1 (receita) ou -1 (despesa)
- `DHBAIXA`, `VLRBAIXA`, `CODTIPOPERBAIXA`, `DHTIPOPERBAIXA` — Dados de baixa (deve estar em aberto pra IAgro)
- `ORIGEM` — `E` (entrada de nota) ou `F` (financeiro avulso)
- `CODEMPBAIXA`, `CODUSUBAIXA` — Audit de baixa
- `CODBCO`, `CODCTABCOINT`, `CODTIPTIT`, `CODTIPOPER` — Default model

**Funções:**
- `criar_entrada_combustivel_banco` — INSERT TGFFIN em aberto
- `criar_abastecimento_externo_banco` — INSERT TGFFIN despesa
- `editar_entrada_combustivel_banco` — UPDATE TGFFIN preservando aberto
- Comercial (vale TOP 13): geração indireta via `gerar_financeiro_banco`

**Trigger dependências:**
- `TRG_INC_TGFFIN` — Exige `ORIGEM='E'` quando `NUNOTA` preenchido
- `TRG_UPT_TGFFIN_NUBCO` — Rejeita baixa sem TGFMBC (movimentação bancária)
- `TRG_UPT_TGFFIN` — Valida `VLRBAIXA` e `CODTIPOPERBAIXA` coerentes (ambos zerados ou preenchidos)

---

### 1.7 TGFPRO — Produtos

**Propósito:** Cadastro de produtos.

**Operações do IAgro:**
- **SELECT**: Leitura de descrição, código de volume, grupo de produto, EAN

**Colunas usadas:**
- `CODPROD` — PK
- `DESCRPROD` — Descrição
- `CODVOL` — Volume padrão (KG, UN, LT, BD, etc) — unidade da venda
- `CODGRUPOPROD` — Código do grupo de produto
- `FABRICANTE` — Fabricante cadastrado (na Agromil = nome do produto, não fabricante real)
- `REFERENCIA` — EAN13 (campo de código de barras — usado em etiquetas Mai/2026)
- `USOPROD` — Tipo de uso (`V`=Venda, `R`=Revenda, `C`=Consumo). IAgro lê e propaga pra `TGFITE.USOPROD` em TOP 34/35/37 desde Mai/2026 (2026-05-20) — sem isso, trigger `TRG_UPT_TGFITE` rejeita

**Funções:**
- `consultar_produtos_oracle` — Typeahead
- `consultar_fabricantes_disponiveis` — SELECT DISTINCT FABRICANTE → migrado para SELECT DISTINCT NOMEPARC_ORIGEM em Mai/2026
- `consultar_produtos_combustivel` — Filtra CODGRUPOPROD=200400
- `consultar_dados_etiqueta_pedido` — Lê REFERENCIA pra EAN

---

### 1.7.5 TGFVOA — Volumes Alternativos (Unidades de conversão) (Mai/2026 — 2026-05-21)

**Propósito:** Cadastro nativo Sankhya que registra **unidades alternativas** por produto com fator de conversão pra unidade padrão. Permite vender em uma unidade (BD) e transportar em outra (CX).

**Operações do IAgro:**
- **SELECT**: leitura do fator de conversão pra calcular nº de caixas no PDF/tela de impressão

**Colunas usadas:**
- `CODPROD` — FK lógica TGFPRO (PK composto)
- `CODVOL` — Unidade alternativa (PK composto): `CX`, `BD`, `DZ`, `SC`, etc
- `DIVIDEMULTIPLICA` — `M`=multiplica · `D`=divide
- `QUANTIDADE` — Fator de conversão. Com `DIV='M'`: `1 unidade_alt = QUANTIDADE × unidade_padrão (TGFPRO.CODVOL)`
- `ATIVO` — `S`/`N`

**Exemplos reais Agromil:**

| CODPROD | DESCR | TGFPRO.CODVOL | CODVOL alt | DIV | QUANTIDADE | Significa |
|---|---|---|---|---|---|---|
| 372 | TOMATE GRAPE | KG | CX | M | 20.0 | 1 CX = 20 KG |
| 372 | TOMATE GRAPE | KG | BD | M | 0.25 | 1 BD = 0.25 KG |
| 61  | MILHO VERDE  | BD | CX | M | 10.0 | 1 CX = 10 BD |

**Função que consulta:**
- `consultar_pesos_referencia_por_codprods` — Camada 2 da cascata de cálculo de caixas no PDF (após moda TOP 26, antes da moda TOP 11). 1 query única com CTEs unidos por `UNION ALL` + prioridade.

**Cobertura observada na Agromil (Mai/2026):** 1078 linhas TGFVOA ATIVO=S, 921 produtos distintos. Dos 87 produtos vendidos no último mês, 62% têm `CODVOL='CX'` cadastrado em TGFVOA (cálculo de caixas automático); 97% têm alguma unidade alternativa.

**Diretriz operacional:** quando aparecer produto com CX vazio no PDF (cascata falhou), orientar operador a cadastrar `(CODPROD, 'CX', 'M', X)` em TGFVOA via tela nativa do Sankhya. Fonte única, sem coluna `AD_*` paralela.

---

### 1.8 TSIGRU — Grupos de Usuário

**Propósito:** Cadastro de grupos de acesso (Diretoria, Suporte, IAgro_Packing, etc.).

**Operações do IAgro:**
- **SELECT**: Validação de grupo do usuário logado

**Colunas usadas:**
- `CODGRUPO` — PK (1, 6, 8, 9, 10, 11)
- `NOMEGRUPO` — Nome (ex: "IAGRO_PACKING", "IAGRO_COMERCIAL")

**Mapeamento:**
- 1 = DIRETORIA (acesso irrestrito)
- 6 = SUPORTE (acesso irrestrito)
- 8 = IAGRO_PACKING (Entrada, Classificação) — renomeado de IAGRO_ENTRADA em 2026-05-14
- 9 = IAGRO_COMERCIAL (Comercial)
- 10 = IAGRO_ADMINISTRATIVO (Venda, Rastreio, Combustível) — renomeado de IAGRO_VENDAS em 2026-05-14
- 11 = IAGRO_FROTA (Combustível) — renomeado de PACKING_FROTA em 2026-05-14

---

### 1.9 TGFNAT — Naturezas de Receita/Despesa

**Propósito:** Classificação contábil.

**Operações do IAgro:**
- **SELECT**: Leitura de código e descrição

**Colunas usadas:**
- `CODNAT` — PK
- `DESCRNAT` — Descrição

**Mapeamento TOP → CODNAT:** ver `CODNAT_POR_TOP` em `oracle_conn.py`.

**Funções:**
- `consultar_naturezas_oracle` — Typeahead

---

### 1.10 TGFTOP — Tipos de Operação

**Propósito:** Cadastro das TOPs (tipos de operação) do sistema.

**Operações do IAgro:**
- **SELECT**: Leitura de descrição, DHALTER

**Colunas usadas:**
- `CODTIPOPER` — PK (10, 11, 13, 26, 30, 34, 35, 36, 37, 53)
- `DESCROPER` — Descrição
- `TIPMOV` — Tipo de movimento (E=entrada, S=saída, Q=requisição)
- `DHALTER` — Timestamp (usado em DHTIPOPER do TGFCAB)

**Funções:**
- `consultar_tipos_operacao_oracle` — Typeahead

---

### 1.11 TGFVEI — Veículos

**Propósito:** Cadastro de veículos da frota.

**Operações do IAgro:**
- **SELECT**: Leitura para dropdown Combustível

**Colunas usadas:**
- `CODVEICULO` — PK
- `PLACA` — Placa visível
- `MARCAMODELO` — Descrição (ex: "FIAT STRADA")
- `ESPECIETIPO` — Categoria (CAVALO, CARGA CAMINHAO, TRATOR, etc.)
- `PROPRIO` — `S` (frota própria) ou `N` (terceiro)
- `COMBUSTIVEL` — Tipo (D, G, F)
- `CODPARC` — Proprietário
- `CODCENCUS` — Centro de resultado
- `ATIVO` — Flag

**Funções:**
- `consultar_veiculos_disponiveis` — Typeahead filtrado por tipo

---

### 1.12 TGFGRU — Grupos de Produto

**Propósito:** Hierarquia de categorias de produtos.

**Operações do IAgro:**
- **SELECT**: Leitura para filtrar produtos combustível

**Colunas usadas:**
- `CODGRUPOPROD` — PK (200400 = COMBUSTÍVEIS)
- `DESCRGRUPOPROD` — Descrição
- `CODGRUPAI` — Hierarquia (pai)

**Grupos críticos:**
- 200000 (MEF) → 200400 (COMBUSTÍVEIS) — Diesel S10 (392), Diesel S500 (1373), Gasolina (391), Óleo (550)

---

### 1.13 TSIUSU — Usuários

**Propósito:** Cadastro de usuários Sankhya.

**Operações do IAgro:**
- **SELECT**: Autenticação e leitura de grupos
- **UPDATE**: Alteração de senha (futuro)

**Colunas usadas:**
- `CODUSU` — PK
- `NOMEUSU` — Login/nome de usuário
- `INTERNO` — Senha (criptografada via `STP_CRYPT`)
- `CODGRUPO` — Grupo principal
- `DTLIMACESSO` — Data limite de acesso

**Funções:**
- `autenticar_usuario_sankhya` — Autenticação via API HTTP do Sankhya (não via SELECT direto na tabela)

---

### 1.14 TSIGPU — Grupos Adicionais do Usuário

**Propósito:** Associação N:N usuário ↔ grupo.

**Operações do IAgro:**
- **SELECT**: Leitura de grupos extras do usuário (potencial)

**Colunas usadas:**
- `CODUSU` — FK → TSIUSU
- `CODGRUPO` — FK → TSIGRU
- `DATAFIM` — Data de expiração

---

### 1.15 TGFVAR — Vínculo entre Notas (Sankhya Nativo)

**Propósito:** Rastreamento de atendimento de pedido (quando pedido vira nota, quando compra vira vale, etc.).

**Operações do IAgro:**
- **SELECT** (leitura apenas): Consulta vínculo pedido ↔ nota via TGFVAR
- **INSERT** (devolução TOP 36 Mai/2026): Excepcionalmente, cria TGFVAR para TOP 36 (replicando Sankhya nativo — única exceção permitida)

**Colunas usadas:**
- `NUNOTA` — NUNOTA da nota gerada (destino)
- `SEQUENCIA` — SEQ do item na nota
- `NUNOTAORIG` — NUNOTA do pedido origem
- `SEQUENCIAORIG` — SEQ do item no pedido
- `QTDATENDIDA` — Quantidade transferida
- `STATUSNOTA` — Status replicado

**Estrutura real (211k linhas em Agromil Mai/2026):**
- 185.221 → TOP 35 ← TOP 34 (NFe ← Pedido de Venda)
- 16.623 → TOP 36 ← TOP 35 (Devolução ← NFe)
- 9.376 → TOP 13 ← TOP 11 (Vale ← Compra)
- 75 → TOP 37 ← TOP 34 (Venda s/NFe)
- 6 → TOP 36 ← TOP 37 (Devolução ← Venda s/NFe)

**Triggers (6 ao total — NÃO escrever direto, exceto devolução TOP 36):**
- `TRG_INC_TGFVAR` — INSERT: cascata em TGMTRA, TGFITE.QTDENTREGUE, funções internas SNK_VERIFICA_PK_TGMTRA
- `TRG_UPT_TGFVAR` — UPDATE: delete+insert em TGMTRA, revalidação
- `TRG_DLT_TGFVAR` — DELETE: subtrai QTDATENDIDA de TGFITE.QTDENTREGUE
- `TRG_DLT_TGFVAR_AFTER` — Cascata pós-delete
- `TRG_INC_TGFVAR_BLOQ_SAFRA` — Validação contra TGABDLC.BLOQUEAR
- `TRG_INC_UPD_DEL_TGFVAR_CFIDEL` — Cupons de fidelidade (fora do escopo IAgro)

**Função que consulta:**
- `consultar_pedidos_abertos_para_atribuicao` — Subquery correlacionada pra trazer nota vinculada
- View `ANDRE_IAGRO_SALDO_LOTE` — NOT EXISTS pra dedup baixa pedido vs nota

---

### 1.16 TGMTRA — Movimentação Financeira / Meta / Orçamento

**Propósito:** Rastreamento de valores a receber/pagar, metas de vendas.

**Operações do IAgro:**
- Nenhuma direta (apenas leitura indireta futura)

**Popula automaticamente via:**
- `TRG_INC_TGFVAR` — Quando INSERT em TGFVAR, trigger cria 2-N linhas em TGMTRA

**Funções internas críticas:**
- `SNK_VERIFICA_PK_TGMTRA` — Valida PK
- `STP_TROCA_NUMTRANSF` — Pode renomear NUMTRANSF dinamicamente

**Nota:** IAgro nunca escreve diretamente. Qualquer INSERT em TGFVAR dispara cascata aqui.

---

### 1.17 TSICUS — Centros de Resultado

**Propósito:** Centros de custo (departamentos, filiais, etc.).

**Operações do IAgro:**
- **SELECT**: Leitura para typeahead

**Colunas usadas:**
- `CODCENCUS` — PK
- `DESCRCENCUS` — Descrição

**Função:**
- `consultar_centros_resultado_oracle` — Typeahead

---

### 1.18 Tabelas de Viagem / MDFe (planejado leitura — Logística Cat B futuro)

**Mapeadas em Mai/2026 (2026-05-29) via smoke completo no Oracle Agromil.** Documentadas como dependência **planejada (leitura apenas)** para o módulo Logística — operador emite MDFe no Sankhya nativo, IAgro só correlaciona via `NUVIAG` opcional.

**Achado-chave**: as 6 tabelas têm **ZERO triggers próprias** (diferente de TGFCAB/TGFITE/TGFVAR/TGFFIN). Apenas `TRG_INC_UPD_TGFCAB_ORD` em TGFCAB referencia TGFVIAG como leitura. Java do Sankhya escreve direto.

#### 1.18.1 TGFVIAG — Cabeçalho da viagem fiscal

**Volume Agromil (Mai/2026):** 1.089 viagens (crescimento ~30%/ano).

**Operações do IAgro:** **SELECT apenas** (ponte fiscal opcional via `AD_VIAGEM_ENTREGA.NUVIAG_SANKHYA`).

**Colunas usadas pelo IAgro:**
- `NUVIAG` — PK
- `CODEMP` — FK TSIEMP
- `SERIE` — Série do MDFe
- `STATUSDOC` — `'C'` (encerrado/confirmado fiscal) / `'E'` (excluído) — 98% das viagens são 'C'
- `CODVEIPRIN` — FK TGFVEI (veículo principal)
- `CODVEIREB1, CODVEIREB2, CODVEIREB3` — FK TGFVEI (até 3 reboques)
- `TIPAMB` — Ambiente SEFAZ (1=produção, 2=homologação)
- `TIPMODALMDFE` — Modal de transporte (`'1'` rodoviário — 100% na Agromil)
- `DHALTER, CODUSU` — Audit

**FK:** 4× TGFVEI, TSIEMP, TSIUSU.

**Sem motorista nem ajudantes nesse envelope** — Sankhya espera CODMOTORISTA via TGFEMDF como evento "Inclusão de Condutor", mas Agromil **NÃO USA esse fluxo** (0% de cobertura).

#### 1.18.2 TGFMDFE — Dados do manifesto SEFAZ

**Volume:** 1.050 manifestos (quase 1:1 com TGFVIAG na Agromil).

**Operações do IAgro:** **SELECT apenas** — pra exibir status, chave, peso bruto, UFs.

**Colunas relevantes:**
- PK composta `(NUVIAG, SEQMDFE)` — permite múltiplos MDFe por viagem
- `NUMMDFE` — Número sequencial visível
- `STATUSMDFE` — Status SEFAZ
- `CHAVEMDFE` — Chave de 44 dígitos da NFe MDFe
- `DHEMISS, DHRECIBO` — Datas
- `UFINICIAL, UFFINAL` — FK TSIUFS
- `PESOBRUTOTOT` — Peso bruto total
- `XML, XMLPROTAUT, XMLENVCLI` — CLOBs com XML SEFAZ (não usados pelo IAgro)
- 30+ colunas fiscais adicionais (geocodes carregamento/descarregamento, modal aquaviário, etc.) — não relevantes

**FK:** TGFVIAG, TSIUFS×2, TSIUSU.

#### 1.18.3 TGFNMDFE — NFs vinculadas ao manifesto

**Volume:** 1.588 vínculos. Distribuição: 76% das viagens têm exatamente 2 NFs (padrão Agromil: 1-2 lojas Assaí por carregamento).

**Operações do IAgro:** **SELECT apenas** — pra mostrar quais TGFCAB (NFs) estão num MDFe.

**Colunas:**
- PK composta `(NUVIAG, SEQMDFE, NUNOTA)`
- `STATUSENVIO, INDREENTREGA` — Flags SEFAZ

**FK:** TGFMDFE, TGFCAB (NUNOTA).

#### 1.18.4 TGFEMDF — Eventos do MDFe

**Volume:** 979 eventos. Distribuição real Agromil:
- `CODEVE='110112'` (Encerramento) — 918 eventos
- `CODEVE='110111'` (Cancelamento) — 61 eventos
- `CODMOTORISTA` populado em **0 dos 979 eventos** — Agromil não usa Inclusão de Condutor SEFAZ

**Operações do IAgro:** **SELECT apenas** (futuro — mostrar timeline de eventos do MDFe).

**FK:** TGFMDFE, TGFPAR (CODMOTORISTA), TSICID, TSIUFS.

#### 1.18.5 TGFOMDF — Ocorrências livres

**Volume:** 748 ocorrências (campo CLOB `OCORRENCIAS`).

**Operações do IAgro:** **SELECT apenas** (futuro).

**FK:** TGFMDFE, TSIUSU.

#### 1.18.6 TGFNCTE — XMLs do CT-e por NUNOTA

**Volume:** 1.916 linhas. Não vinculada diretamente à viagem.

**Operações do IAgro:** **SELECT apenas** (futuro — anexar PDF do CT-e à NF).

**FK:** PK = NUNOTA (1:1 com TGFCAB de CT-e).

#### Triggers — ausência confirmada

```
TGFVIAG    → 0 triggers
TGFMDFE    → 0 triggers
TGFNMDFE   → 0 triggers
TGFOMDF    → 0 triggers
TGFEMDF    → 0 triggers
TGFNCTE    → 0 triggers
```

Apenas `TRG_INC_UPD_TGFCAB_ORD` (em TGFCAB, não nas 6) faz **leitura** de TGFVIAG.

**Por que IAgro NÃO escreve em TGFVIAG/TGFMDFE** (apesar de ausência de triggers):
1. Java do Sankhya pode escrever direto via rotina nativa de emissão MDFe — INSERT IAgro pode ser ignorado/sobrescrito
2. Falta semântica operacional (motorista, ajudantes, destinos com qtd_caixas, observação do gestor) — adicionar `AD_*` poluiria envelope fiscal
3. STATUSDOC fiscal (`'C'`/`'E'`) conflita com status operacional IAgro (Planejada/Em rota/Concluída)
4. Spin-off futuro: replicar TGFVIAG+TGFMDFE (43 colunas fiscais + XMLs SEFAZ) é caro; AD_VIAGEM_ENTREGA paralela é trivial
5. Sem ambiente de homologação Sankhya pra validar INSERT manual

**Arquitetura recomendada** (Opção C — ponte fiscal opcional):
- `AD_VIAGEM_ENTREGA` (IAgro operacional) — motorista + ajudantes + destinos + qtd_caixas + obs + status
- Campo `NUVIAG_SANKHYA` opcional pra correlacionar quando MDFe é emitido
- Função aditiva Cat A `consultar_mdfe_da_viagem(nuviag)` — SELECT em TGFVIAG + TGFMDFE + TGFNMDFE pra exibir badge `📋 MDFe N (chave XX...)` na rota IAgro
- Zero escrita pelo IAgro nas 6 tabelas Sankhya

Detalhes em [`modules/logistica.md`](modules/logistica.md) → "Ponte fiscal opcional com TGFVIAG".

---

## 2. Triggers Sankhya Conhecidas (Mapa de Riscos)

### 2.1 Triggers em TGFCAB

| Trigger | Evento | Erro Conhecido | Causa | Solução IAgro |
|---|---|---|---|---|
| `TRG_INC_TGFCAB` | BEFORE INSERT | ORA-20101 | `(CODTIPVENDA, DHTIPVENDA)` inconsistente | Busca DHALTER mais recente de TGFTPV antes do INSERT |
| `TRG_INC_TGFCAB` (Mai/2026 — 2026-05-20) | BEFORE INSERT | ORA-20101: "Campo Tipo de negociação obrigatório" | INSERT em **qualquer TOP** sem `CODTIPVENDA` — inclusive TOP 30 (avaria interna que conceitualmente não tem negociação) | Sempre passar `CODTIPVENDA` no payload. Em TGFCAB TOP 30 automática (`upsert_avaria_top30_lote`), herda de `c.CODTIPVENDA` da TOP 11 origem; fallback `11` (mesma estratégia da `criar_avaria_top30_banco` do módulo Venda) |
| `TRG_UPD_TGFCAB` | BEFORE UPDATE | ORA-20101 | Tenta `UPDATE STATUSNOTA='E'` — trigger bloqueia, só permite → 'L' | Use DELETE físico pra "excluir" (Combustível B6) |
| `TRG_UPD_TGFCAB` (Mai/2026 — 2026-05-22) | BEFORE UPDATE | ORA-20101: "Tipo de operação não esta ativo" | UPDATE muda `CODTIPOPER` mas mantém `DHTIPOPER` antigo — par `(CODTIPOPER, DHTIPOPER)` não bate com TGFTOP ativa | Atualizar `DHTIPOPER = MAX(DHALTER) FROM TGFTOP WHERE CODTIPOPER=:t AND ATIVO='S'` no mesmo UPDATE |
| `TRG_UPD_TGFCAB` (Mai/2026 — 2026-05-22) | BEFORE UPDATE | ORA-20101: "Esta TOP X não pode ser lançada nesta opção" | UPDATE muda `CODTIPOPER` mas mantém `TIPMOV` antigo. TOP 34 (PEDIDO) tem TIPMOV='P', TOP 35/37 (VENDA) tem TIPMOV='V' — incompatibilidade detectada | Atualizar `TIPMOV` junto: ler de TGFTOP.TIPMOV da nova TOP e gravar no UPDATE. Alternativa preferível: criar TGFCAB nova (caminho C) em vez de UPDATE in-place — vide `faturar_pedido_venda_banco` |

### 2.2 Triggers em TGFFIN

| Trigger | Evento | Erro Conhecido | Causa | Solução IAgro |
|---|---|---|---|---|
| `TRG_INC_TGFFIN` | BEFORE INSERT | ORA-20101 | `NUNOTA` preenchido mas `ORIGEM <> 'E'` | Sempre `ORIGEM='E'` quando há NUNOTA |
| `TRG_UPT_TGFFIN_NUBCO` | BEFORE UPDATE | ORA-20101: "Baixa sem ligação com TGFMBC" | Tenta baixa (`DHBAIXA NOT NULL`) sem TGFMBC | Deixar TGFFIN em aberto (DHBAIXA=NULL, VLRBAIXA=0) |
| `TRG_UPT_TGFFIN` | BEFORE UPDATE | ORA-20101: "Informe valor e TOP da baixa simultaneamente" | `VLRBAIXA > 0` mas `CODTIPOPERBAIXA` faltando (ou vice-versa) | Ou ambos zerados ou ambos preenchidos |

### 2.2.5 Triggers em TGFITE

| Trigger | Evento | Erro Conhecido | Causa | Solução IAgro |
|---|---|---|---|---|
| `TRG_UPT_TGFITE` (Mai/2026 — 2026-05-20) | BEFORE UPDATE (via `STP_CONFIRMANOTA2` em impressão/faturamento) | ORA-20101: "Reserva diferente da definicao na TOP" | INSERT do IAgro deixava `RESERVA='N'`/`ATUALESTOQUE=-1`/`USOPROD='V'` em TOP de venda. Quando Sankhya tenta UPDATE pra valor da TOP, trigger compara NEW vs definição da TOP e rejeita | `inserir_item_nota_banco` agora popula `RESERVA='S'`, `ATUALESTOQUE=1`, `USOPROD=<TGFPRO.USOPROD>` quando `CODTIPOPER IN (34, 35, 37)`. Schema-resilient via `if 'COL' in colunas_tabela`. **Pedidos antigos pré-fix continuam quebrados** (UPDATE retroativo é Cat B, não aplicado porque volume é pequeno) |
| `TRG_INC_UPD_TGFITE_PRODNFE` (Mai/2026 — 2026-05-27) | BEFORE INSERT OR UPDATE | (sem erro — popula campos automaticamente) | Popula `GTINNFE`, `GTINTRIBNFE`, `PRODUTONFE` a partir de `TGFPRO.TIPGTINNFE` + `TGFPRO.REFERENCIA` (EAN13 cadastrado) + `TGFEST.CODBARRA` + `TGFVOA.CODBARRA`. **Não exige nada do IAgro** — basta INSERT padrão. Produto sem `TGFPRO.REFERENCIA` cadastrado → campos NULL na TGFITE. Detalhes em `gotchas.md` |

### 2.3 Triggers em TGFVAR

| Trigger | Evento | Efeito Colateral | Razão NÃO escrever |
|---|---|---|---|
| `TRG_INC_TGFVAR` | BEFORE INSERT | Cascata em TGMTRA (N linhas), UPDATE TGFITE.QTDENTREGUE | Funções internas `SNK_VERIFICA_PK_TGMTRA`, `STP_TROCA_NUMTRANSF` podem renomear PKs |
| `TRG_UPT_TGFVAR` | BEFORE UPDATE | DELETE+INSERT em TGMTRA, recalcula metas | Risco de duplicação ou desincronização |
| `TRG_DLT_TGFVAR` | BEFORE DELETE | Subtrai QTDATENDIDA de TGFITE | Danifica rastreabilidade histórica |
| `TRG_DLT_TGFVAR_AFTER` | AFTER DELETE | Cleanup em TGMTRA | Efeito cascata |
| `TRG_INC_TGFVAR_BLOQ_SAFRA` | BEFORE INSERT | Bloqueia por TGABDLC.BLOQUEAR='S' | Validação de projeto (fora do escopo IAgro) |
| `TRG_INC_UPD_DEL_TGFVAR_CFIDEL` | BEFORE INSERT/UPDATE/DELETE | Maneja TGFCFM (cupons fidelidade) | Fora do escopo IAgro |

**Estratégia IAgro:** Leitura apenas em 2 lugares: (1) `consultar_pedidos_abertos_para_atribuicao` para badge "FATURADO"; (2) `ANDRE_IAGRO_SALDO_LOTE` view pra deduplicação de baixas. **Exceção documentada:** devolução TOP 36 (Mai/2026) insere em TGFVAR replicando Sankhya nativo (legítimo — operador confirma no Sankhya, que dispara financeiro reverso + NFe).

---

## 3. Funções/Procedures Proprietárias Sankhya

### 3.1 Funções Utilizadas pelo IAgro

| Função | Uso |
|---|---|
| `STP_CRYPT(senha)` — Criptografia Sankhya | Alteração de senha (futuro) |
| `SNK_VERIFICA_PK_TGMTRA` | Disparada por TRG_INC_TGFVAR (validação interna) |
| `STP_TROCA_NUMTRANSF` | Disparada por TRG_INC_TGFVAR (pode renomear NUMTRANSF) |

### 3.2 Sequences Consultadas

| Sequence | Propósito | Uso |
|---|---|---|
| `SEQ_AD_AUDITORIA_GERAL` | Audit log global | (preparado, ativo) |
| `SEQ_AD_REQUISICAO_COMBUSTIVEL` | PK de AD_REQUISICAO_COMBUSTIVEL | `criar_requisicao_combustivel_banco` |
| `SEQ_AD_VINCULO_PEDIDO_NOTA` | PK de AD_VINCULO_PEDIDO_NOTA | `inserir_vinculo_manual_pedido_nota` |
| `SEQ_AD_PEDIDO_EMAIL_RECEBIDO` | PK | Worker IMAP |
| `SEQ_AD_PEDIDO_EMAIL_ITEM` | PK | Worker IMAP |
| `SEQ_AD_PRODUTO_ALIAS` | PK | Aprendizado matching |
| `SEQ_AD_PARCEIRO_ALIAS` | PK | Aprendizado matching |
| `SEQ_AD_CLIENTE_PRODUTO_COD` | PK | Vinculação cod_cliente |

### 3.3 Views Nativas Sankhya (Consultadas, Não Alteradas)

- Nenhuma view nativa do Sankhya é consultada — apenas tabelas

---

## 4. Views Customizadas IAgro (Prefixo `ANDRE_IAGRO_*`)

### 4.1 ANDRE_IAGRO_SALDO_LOTE

**DDL:** `sankhya_integration/sql/ANDRE_IAGRO_SALDO_LOTE.sql`

**Propósito:** Calcular saldo disponível de lotes por `(CODPROD, CODAGREGACAO)` sem tocar `TGFEST` nativa.

**Estrutura (6 pernas):**

| Perna | Status | Fonte | Vendável? |
|---|---|---|:-:|
| A | CLASSIFICADO | TOP 26 (lotes confirmados) | ✅ |
| B | NAO_CLASSIFICAVEL | TOP 13 (lotes sem TOP 26) | ✅ |
| C | AGUARDANDO_CLASSIFICACAO | TOP 11 com GERAPRODUCAO='S' pendente | ❌ |
| D | AVARIA_INTERNA | TOP 30 (perda no estoque) | ❌ |
| E | AVARIA_FORNECEDOR | AD_QTDAVARIA da TOP 11 | ❌ |
| F | DEVOLVIDO | TOP 36 STATUSNOTA='L' (Mai/2026) | ❌ (informativo) |

**Fórmula:**
```
QTD_DISPONIVEL = ENTRADA
               + Σ TOP 36 confirmadas (devolvido)
               − BAIXA_VENDA (deduplicada: TOP 34 L + TOP 35/37 L sem par no TOP 34)
               − Σ TOP 30 confirmadas
               − Σ TOP 34 abertas
```

**Colunas retornadas:**
- `CODPROD`, `DESCRPROD`, `CODAGREGACAO`, `NOMEPARC_ORIGEM` (fornecedor), `DTNEG_ORIGEM`
- `QTD_ENTRADA`, `QTD_DISPONIVEL`, `QTD_RESERVADA`, `QTD_BAIXADA_VENDA`, `QTD_AVARIA_INTERNA`, `QTD_AVARIA_FORNECEDOR`
- `STATUS_LINHA` (perna discriminadora)
- `NUNOTA_ORIGEM`, `GERAPRODUCAO`, `QTDNEG`

**Função que consulta:**
- `consultar_saldo_lote_disponivel(filtros, limite, offset)` — Paginação com ROW_NUMBER (Oracle 11g compat)

---

### 4.2 ANDRE_IAGRO_SALDO_COMBUSTIVEL

**DDL:** `sankhya_integration/sql/ANDRE_IAGRO_SALDO_COMBUSTIVEL.sql`

**Propósito:** Calcular saldo disponível de combustível por `CODPROD` (Diesel S10, Diesel S500, etc.) sem segregação por CODEMP (estoque único compartilhado).

**Fórmula:**
```
QTD_DISPONIVEL = GREATEST( Σ TOP 10 entradas (STATUSNOTA <> 'E')
                          − Σ TOP 53 saídas (STATUSNOTA <> 'E', excluindo EXTERNA_POSTO),
                          0 )
```

**Filtros:**
- `pr.CODGRUPOPROD = 200400` (COMBUSTÍVEIS)
- `NOT EXISTS` (SELECT 1 FROM AD_REQUISICAO_COMBUSTIVEL WHERE TIPO='EXTERNA_POSTO') — exclui abastecimentos externos

**Função que consulta:**
- `consultar_saldo_combustivel(filtros)` — Retorna dict com SALDO_INICIAL_TANQUE somado em Python (não usar GREATEST da view — corrompe saldo quando inicial > 0)

---

## 5. Tabelas Auxiliares Customizadas (Prefixo `AD_*`)

### 5.1 AD_PEDIDO_EMAIL_RECEBIDO

**DDL:** `sankhya_integration/sql/AD_PEDIDO_EMAIL.sql`

**Propósito:** Cabeçalho de pré-pedido capturado de e-mail (antes de virar TGFCAB TOP 34).

Estrutura completa documentada em `.claude/modules/email.md`.

---

### 5.2 AD_PEDIDO_EMAIL_ITEM

**DDL:** `sankhya_integration/sql/AD_PEDIDO_EMAIL.sql` + `AD_CLIENTE_PRODUTO_COD.sql`

**Propósito:** Itens do pré-pedido com matching de produto.

Hierarquia de matching:
1. **AD_CLIENTE_PRODUTO_COD** — Exato por `(CODPARC, COD_CLIENTE)` (score 100, etapa 0)
2. **AD_PRODUTO_ALIAS** — Por descrição normalizada (score 100, etapa 1)
3. **Fuzzy (rapidfuzz.WRatio)** — Contra TGFPRO completo (score 75-100, etapa 2)

---

### 5.3 AD_PRODUTO_ALIAS

**DDL:** `sankhya_integration/sql/AD_ALIAS_APRENDIZADO.sql`

**Propósito:** De-para normalizado de descrições de produtos → CODPROD.

---

### 5.4 AD_PARCEIRO_ALIAS

**DDL:** `sankhya_integration/sql/AD_ALIAS_APRENDIZADO.sql`

**Propósito:** De-para normalizado de nomes de clientes → CODPARC.

---

### 5.5 AD_CLIENTE_PRODUTO_COD

**DDL:** `sankhya_integration/sql/AD_CLIENTE_PRODUTO_COD.sql`

**Propósito:** De-para forte para clientes que usam códigos próprios (Consinco).

---

### 5.6 AD_VINCULO_PEDIDO_NOTA

**DDL:** `sankhya_integration/sql/AD_VINCULO_PEDIDO_NOTA.sql`

**Propósito:** Vínculo manual pedido ↔ nota quando TGFVAR não foi populada.

**Dois fluxos:**
- **Leva A (VINCULADO):** Pedido pré-existente pareável, operador vincula manualmente
- **Leva B (PEDIDO_RETROATIVO):** IAgro cria TOP 34 retroativamente espelhando a nota

Estrutura completa em `.claude/modules/rastreio.md` → "Fluxo unificado de resolução de nota órfã".

---

### 5.7 AD_REQUISICAO_COMBUSTIVEL

**DDL:** `sankhya_integration/sql/AD_REQUISICAO_COMBUSTIVEL.sql` + migrations

**Propósito:** Metadados de requisição de combustível (TOP 53, antes era TOP 26).

**Mai/2026 — 2026-05-28**: ALTER aplicado (migration `AD_REQUISICAO_COMBUSTIVEL_MIGRATION_AJUSTE.sql`) tornou `CODVEICULO NULL` permitido e ampliou CHECK de `TIPO` pra aceitar `AJUSTE_AVULSO` (ajuste manual de saldo do tanque sem veículo, lançado pela tela admin `/sankhya/configuracoes/ajustes/`). Quando `TIPO='AJUSTE_AVULSO'`:
- TGFCAB criada é **TOP 10** (qtd positiva → entrada, soma saldo) ou **TOP 53** (qtd negativa → saída, desconta saldo)
- View `ANDRE_IAGRO_SALDO_COMBUSTIVEL` reflete automaticamente — não precisa alterar a view porque AJUSTE_AVULSO não é EXTERNA_POSTO (filtro `NOT EXISTS EXTERNA_POSTO` não exclui)
- Sem TGFFIN (ajuste interno, sem financeiro)

Estrutura completa em `.claude/modules/combustivel.md`.

---

### 5.8 AD_AUDITORIA_GERAL

**DDL:** `sankhya_integration/sql/AD_AUDITORIA_GERAL.sql`

**Propósito:** Audit log centralizado de todos os módulos IAgro.

Detalhes em `.claude/modules/` (referências cruzadas).

---

### 5.9 AD_COLETA_CAIXAS + AD_PRODUTO_CAIXA (Mai/2026 — 2026-05-18)

**DDLs:**
- `sankhya_integration/sql/AD_COLETA_CAIXAS.sql`
- `sankhya_integration/sql/AD_PRODUTO_CAIXA.sql`

**Propósito:** Controle de vasilhame retornável (caixa plástica). Saídas calculadas em runtime via `CEIL(QTDNEG / TGFITE.PESO)` quando `PESO > 0` (vendas IAgro recentes via Rastreio); coletas/quebras/perdas/ajustes manuais em `AD_COLETA_CAIXAS`; tipo de caixa por produto (default PLASTICA) em `AD_PRODUTO_CAIXA`. Vendas legadas sem PESO ficam fora — operador usa AJUSTE_SALDO pra controlar saldo de clientes importantes. Descoberto Mai/2026 que `CODVOL='CX'` na Agromil **não** significa "QTDNEG é nº de caixas" (sempre kg). Tentativa de cadastrar peso default por produto (tabela `AD_PESO_CAIXA_PRODUTO`) foi descartada porque peso varia por lote — cadastro fixo era chute.

Detalhes em `.claude/modules/caixas.md` e `.claude/schema.md` §7.8.

**Tabelas Sankhya consumidas (LEITURA APENAS):** TGFCAB, TGFITE (PESO + QTDNEG), TGFPAR (NOMEPARC), TGFPRO. Nenhuma escrita em Sankhya nativo.

**Zero impacto em queries existentes:** tabelas auxiliares 100% isoladas; views existentes não consultam.

---

### 5.10 AD_SALDO_LOTE_CACHE (Mai/2026 — 2026-05-19)

**DDL:** [`sankhya_integration/sql/AD_SALDO_LOTE_CACHE.sql`](../sankhya_integration/sql/AD_SALDO_LOTE_CACHE.sql)

**Propósito:** Espelho materializado da view `ANDRE_IAGRO_SALDO_LOTE`. View leva 10-22s por hit (5 CTEs com agregações em TGFITE/TGFCAB/TGFVAR); tabela retorna em ~200ms. Refresh por cron Windows Task Scheduler a cada 5 min via `python manage.py refresh_saldo_lote` (TRUNCATE + INSERT-SELECT, ~12s em background — operador nunca espera). Latência máxima de display: 5 min. Lock pessimista em `atribuir_lote_item_pedido` continua validando contra a view real — integridade transacional preservada. Detalhes em `.claude/modules/rastreio.md`.

**Estrutura:** mesmas 19 colunas do retorno da view + `ATUALIZADO_EM`. PK `(CODEMP, CODPROD, CODAGREGACAO, STATUS_LINHA)`. 4 índices (QTD_DISPONIVEL, DTNEG_ORIGEM DESC, CODPROD, VENDAVEL).

**Função service:** `refresh_saldo_lote_cache()` em `oracle_conn.py` (Cat B — escrita em AD_*). Único consumidor swap-ado pra tabela: `consultar_saldo_lote_disponivel` (endpoint do Rastreio). Demais usos da view continuam diretos (relatórios, validação de saldo, lock pessimista).

**Cache Django** (60s TTL + versionamento por escrita) continua em cima — combinado, leituras subsequentes ≤60s são instantâneas. Operador sente Rastreio fluido.

**Tabelas Sankhya consumidas (LEITURA APENAS):** apenas via view (que por sua vez consulta TGFCAB, TGFITE, TGFVAR, TGFPRO, TGFPAR). Nenhuma escrita em tabela Sankhya nativa.

**Zero impacto em queries existentes:** tabela auxiliar 100% isolada; outras funções continuam apontadas pra view real.

---

### 5.11 Módulo Logística — `AD_TIPO_PARCEIRO` + `AD_PARCEIRO_TIPO` + `AD_VIAGEM_*` (Mai/2026 — 2026-05-29)

Pacote completo de 5 tabelas pro módulo Logística. Detalhes operacionais em [`.claude/modules/logistica.md`](modules/logistica.md).

#### Cadastro de tipos de parceiro

| Tabela | DDL | Propósito |
|---|---|---|
| `AD_TIPO_PARCEIRO` | [AD_TIPO_PARCEIRO.sql](../sankhya_integration/sql/AD_TIPO_PARCEIRO.sql) | Cadastro genérico de tipos. PK `ID`, UNIQUE `CODIGO`. Seed inicial 7 tipos com IDs fixos 1-7 (CLIENTE, FORNECEDOR, USUARIO, MOTORISTA, AJUDANTE, TRANSPORTADORA, VENDEDOR). Sequence `SEQ_AD_TIPO_PARCEIRO` start=100 pra tipos novos. |
| `AD_PARCEIRO_TIPO` | [AD_PARCEIRO_TIPO.sql](../sankhya_integration/sql/AD_PARCEIRO_TIPO.sql) | Junção N:N parceiro × tipo. PK composta `(CODPARC, AD_CODTIPPARC)`. Índice reverso `(AD_CODTIPPARC, CODPARC)` pra typeahead. FKs lógicas (sem constraint física) pra TGFPAR e AD_TIPO_PARCEIRO. |

**Migração one-time** copiou flags TGFPAR → AD_PARCEIRO_TIPO: 381 CLIENTE + 457 FORNECEDOR + 3 USUARIO + 24 MOTORISTA + 4 TRANSPORTADORA + 16 VENDEDOR = **885 vínculos** (`NOMEUSU='MIGRACAO_INICIAL'`). Reversível via DELETE. Sankhya nativo intocado. Tipo AJUDANTE (ID=5) só IAgro.

#### Tabelas de viagem

| Tabela | DDL | Propósito |
|---|---|---|
| `AD_VIAGEM_ENTREGA` | [AD_VIAGEM_ENTREGA.sql](../sankhya_integration/sql/AD_VIAGEM_ENTREGA.sql) | Cabeçalho. PK `ID` (via `SEQ_AD_VIAGEM_ENTREGA`), UNIQUE `NUM_VIAGEM` (gerado por `MAX+1`), DATE+HORA, CODVEICULO (FK lógica TGFVEI), CODPARC_MOTORISTA (FK lógica TGFPAR + tipo=4), OBSERVACAO, audit. CHECK regex HH:MM. 3 índices (DATA, MOTORISTA, VEICULO). |
| `AD_VIAGEM_DESTINO` | [AD_VIAGEM_DESTINO.sql](../sankhya_integration/sql/AD_VIAGEM_DESTINO.sql) | Paradas. FK ON DELETE CASCADE com AD_VIAGEM_ENTREGA. UNIQUE `(VIAGEM_ID, ORDEM)`. CHECK QTD>0. Sequence `SEQ_AD_VIAGEM_DESTINO`. |
| `AD_VIAGEM_AJUDANTE` | [AD_VIAGEM_AJUDANTE.sql](../sankhya_integration/sql/AD_VIAGEM_AJUDANTE.sql) | N:N viagem × ajudante. PK composta `(VIAGEM_ID, CODPARC_AJUDANTE)`. FK ON DELETE CASCADE. CODPARC_AJUDANTE = parceiro com tipo=5 em AD_PARCEIRO_TIPO. |

**Sem coluna STATUS** — exclusão é DELETE físico; histórico preservado via AD_AUDITORIA_GERAL com snapshot completo ANTES do DELETE.

#### ALTER em AD_AUDITORIA_GERAL

`CK_AD_AUDIT_MODULO` ampliado em 2026-05-29 pra aceitar `'logistica'` (necessário pras funções de escrita do módulo registrarem audit) e `'ajustes'` (proativo — módulo já existente cuja entrada faltava no enum).

#### Funções service

| Função | Cat | Operação |
|---|---|---|
| `listar_tipos_parceiro(incluir_inativos)` | A | SELECT AD_TIPO_PARCEIRO ordenado por ORDEM_EXIBICAO |
| `consultar_parceiros_por_tipo(tipo_id, q, limite, somente_ativos)` | A | Typeahead via JOIN AD_PARCEIRO_TIPO + TGFPAR |
| `consultar_veiculos_logistica(q, somente_ativos, limite)` | A | Typeahead TGFVEI (sem restrição de grupo) |
| `consultar_proximo_num_viagem()` | A | `MAX(NUM_VIAGEM)+1` |
| `listar_viagens(filtros, limite, offset)` | A | Listagem paginada com cabeçalho + destinos + ajudantes |
| `obter_viagem_detalhe(viagem_id)` | A | Detalhe completo |
| `criar_viagem_banco(dados, codusu, nomeusu)` | B | INSERT atômico cab + destinos + ajudantes + audit. Lock pessimista em MAX(NUM_VIAGEM). |
| `editar_viagem_banco(viagem_id, dados, codusu, nomeusu)` | B | UPDATE diferencial preservando IDs estáveis dos destinos. NUM_VIAGEM imutável. |
| `excluir_viagem_banco(viagem_id, codusu, nomeusu, motivo)` | B | DELETE físico cascata + snapshot no audit |

#### Endpoints REST

9 endpoints sob `/sankhya/logistica/api/` (6 GET + 3 POST + 1 PDF). Acesso `@exige_grupo('logistica')` — grupos 1 (Diretoria), 6 (Suporte), 10 (Administrativo).

#### Tabelas Sankhya consumidas (LEITURA APENAS)

- `TGFPAR` (via JOIN com AD_PARCEIRO_TIPO pra typeahead)
- `TGFVEI` (typeahead de veículo)

**Zero escrita em tabelas Sankhya nativas.** Spin-off futuro replica AD_VIAGEM_* sem custo adicional.

---

## 5.5 Colunas Customizadas `AD_*` em Tabelas Sankhya Nativas

**Atualizado 2026-05-21** — `ALTER TABLE` em tabela Sankhya nativa adicionando coluna `AD_<NOME>` agora é **permitido** (continua exigindo aprovação Cat B ponto-a-ponto). Diretriz arquitetural em [`CLAUDE.md`](../CLAUDE.md) → "Estratégia de produto".

Razão: o schema do banco do spin-off será **réplica exata** do schema Sankhya atual + nossas extensões `AD_*`. Acoplar via coluna `AD_*` em tabela nativa não cria dívida adicional — basta listar aqui as colunas customizadas.

### Princípios

1. **Prefixo `AD_<NOME>`** obrigatório (sem prefixo é reservado a campos nativos Sankhya).
2. **Ler antes de criar** — se o dado já existe em campo nativo ou tabela Sankhya (ex.: `TGFVOA`, `TGFEXC`, `TGFPRO.PESO_NETO`), **ler** em vez de duplicar.
3. **DDL versionada** em `sankhya_integration/sql/` (mesmo padrão das tabelas `AD_*`).
4. **Tabela auxiliar `AD_*` ainda é preferível** quando o dado é multi-row por entidade (vários clientes por produto, histórico temporal). Coluna escalar única (1 valor por linha da tabela nativa) é candidato natural a coluna.

### Inventário de Colunas Customizadas (estado atual)

| Tabela Nativa | Coluna | Origem | Quem usa |
|---|---|---|---|
| `TGFCAB` | `AD_NUMPEDIDOORIG` | Convenção customizada da Agromil (legado pré-IAgro) | Entrada/Classificação/Comercial — rastreabilidade da "nota raiz via lote". Default = `NUNOTA próprio` (auto-referência) no INSERT do IAgro |
| `TGFITE` | `AD_NUMPEDIDOORIG` | Convenção customizada da Agromil | Propagado do cabeçalho. Auto-cura em `atualizar_cabecalho_nota_banco` busca MIN de outros itens com mesmo CODAGREGACAO |
| `TGFITE` | `AD_QTDAVARIA` | Convenção customizada da Agromil | Classificação registra descarte. Vira perna E (`AVARIA_FORNECEDOR`) na view `ANDRE_IAGRO_SALDO_LOTE`. Mai/2026: editável também em produto não-classificável (modal Entrada) |
| `TGFITE` | `AD_PESO` | Convenção customizada da Agromil | Peso registrado na pesagem da Entrada (TOP 11). Não confundir com `TGFITE.PESO` (campo nativo canônico, usado pelo IAgro desde Mai/2026 — 2026-05-16) |
| `TGFITE` | `AD_QTDCONFERIDA` | Convenção customizada da Agromil | Quantidade conferida na Entrada — atualizado em `inserir_item_nota_banco` (= `QTDNEG` em pedidos novos) |

### Como adicionar nova coluna `AD_*` (checklist)

1. **Smoke prévio (Cat A):** confirmar via `ALL_TAB_COLUMNS` que a coluna ainda não existe + verificar se o dado já não vive em outro lugar do schema Sankhya
2. **Plano Cat B** apresentado ao usuário (o quê · como · por quê · o que afeta)
3. **DDL versionada** em `sankhya_integration/sql/AD_<TABELA>_<COLUNA>.sql` com `ALTER TABLE` idempotente
4. **Atualizar esse arquivo** — adicionar linha na tabela "Inventário" acima
5. **Aplicar no Oracle** (smoke `_apply_*.py` ou execução manual)
6. **Documentar uso** no módulo afetado (`.claude/modules/*.md`) — quem lê, quem escreve, com que regra

### Por que essa lista importa pro spin-off

Quando recriarmos o schema no banco próprio, **toda coluna listada acima precisa ser criada junto com a tabela nativa equivalente**. Sem esse inventário, é fácil esquecer uma extensão e quebrar funcionalidade. Esta seção é o **blueprint complementar** ao do §1 (Tabelas Sankhya consumidas).

---

## 6. Constantes de Domínio Sankhya (Codificadas em Python)

### 6.1 TOPs (Tipos de Operação)

```python
CODTIPOPER = {
    10:  'ENTRADA_COMBUSTIVEL',        # Entrada de combustível (compra)
    11:  'ENTRADA',                     # Compra / Recebimento (gera lote)
    13:  'VALE',                        # Vale de Compra (Comercial, gera TGFFIN)
    26:  'CLASSIFICACAO',               # Classificação confirmada (hortifrúti)
    30:  'AVARIA_INTERNA',              # Perda no estoque (venda interna)
    33:  'AVARIA_DE_AJUSTE',            # Ajuste de fração de lote (Mai/2026 — 2026-05-26)
    34:  'PEDIDO_VENDA',                # Pedido de Venda (em aberto)
    35:  'VENDA_NIFE',                  # Venda com NFe (faturada)
    36:  'DEVOLUCAO_VENDA',             # Devolução de venda
    37:  'VENDA_SEM_NFE',               # Venda sem documento fiscal (faturada)
    53:  'REQUISICAO_INTERNA',          # Requisição interna (combustível, TIPMOV='Q')
}
```

**TOP 33 — Avaria de Ajuste** (Mai/2026 — 2026-05-26, revisada 2026-05-28):
- Confirmada via smoke real (`SELECT * FROM TGFTOP WHERE CODTIPOPER=33`)
- `DESCROPER='AVARIA DE AJUSTE'`, `TIPMOV='V'`, `ATIVO='S'`, `DHALTER=2020-03-02`
- Uso histórico: **269 notas** TOP 33 já criadas pelo Sankhya nativo
- Usada pela IAgro em `zerar_fracao_lote_banco` (módulo Rastreio) — destina-se a ajustes contábeis de desidratação de hortifrúti (sobra natural de 1-10 kg quando vínculo de pedido fica completo)
- TGFITE TOP 33 nativa Sankhya tem `CODAGREGACAO=NULL` em 100% dos casos históricos; IAgro **força CODAGREGACAO preservado** pra rastreabilidade
- **STATUSNOTA do IAgro fica em `'P'`** (decisão operador 2026-05-28) — diferente do Sankhya nativo que finaliza em `'L'`. Facilita consolidação de avarias do mesmo parceiro/dia + edição posterior.
- **Consolidação** (Mai/2026 — 2026-05-28): TGFCAB do mesmo `CODPARC` + `TRUNC(DTNEG)=TRUNC(SYSDATE)` é reusada — novas avarias adicionam TGFITE em vez de criar CAB nova. Mesmo lote/produto diferentes vão pra mesma CAB. Padrão confirmado em smoke histórico Sankhya (NUNOTA 9831 com 3 TGFITEs inseridos 9 dias após DTFATUR — INSERT em CAB 'L' é permitido pelo trigger).
- **View `ANDRE_IAGRO_SALDO_LOTE` desconta TOP 33** desde Mai/2026 — 2026-05-28 (B5). CTEs `baixas_avaria` + `perna_d` ganharam `CODTIPOPER IN (30, 33)` + `STATUSNOTA <> 'E'`. Antes só conhecia TOP 30 — saldo do lote não diminuía após avaria TOP 33 (bug silencioso).

### 6.2 STATUSNOTA (Estados da Nota)

| Status | Significado | Usado em | Filtro Padrão |
|---|---|---|---|
| `L` | Liberada / confirmada / faturada | TOP 13, 30, 35, 37 | `= 'L'` (finalizadas) |
| `E` | Excluída | Qualquer | `<> 'E'` (ativas) |
| `A` | Em aberto (devolução) | TOP 36 | `= 'A'` (aguardando confirmação Sankhya) |
| NULL / outro | Pedido em aberto / em processamento | TOP 11, 26, 34, 53 | `IS NULL` ou `NOT IN ('L','E')` |

### 6.3 CODNAT por TOP

```python
CODNAT_POR_TOP = {
    10: 30070200,   # Entrada Combustível
    11: 10010100,   # Entrada (Compra)
    13: 10010100,   # Vale
    26: 10010100,   # Classificação
    30: 20010200,   # Avaria interna (DESCRNAT "AVARIA")
    33: 20010200,   # Avaria de ajuste (DESCRNAT "AVARIA", mesma da 30) — Mai/2026 — 2026-05-26
    34: 10010100,   # Pedido de Venda
    35: 10010100,   # Venda com NFe
    36: 10020100,   # Devolução de venda (DESCRNAT "DEVOLUCAO DE VENDA")
    37: 10010200,   # Venda sem NFe
    53: 30070200,   # Requisição interna (Combustível)
}
```

**CODNAT 10040800 — Receita de Abastecimento** (Mai/2026 — 2026-05-26): novo CODNAT introduzido em uso pelo IAgro pra TGFFIN automático de **veículos de terceiro** (B1 do módulo Combustível). Quando `TGFVEI.PROPRIO='N'`, criar requisição interna gera TGFFIN com este CODNAT + `RECDESP=+1` (receita a receber do freteiro) + `CODCENCUS=10100` (Comercialização). Vide [`modules/combustivel.md`](modules/combustivel.md) → "TGFFIN automático pra veículos de terceiro".

### 6.4 CODGRUPO (Grupos de Usuário)

| CODGRUPO | NOMEGRUPO | Acesso |
|---|---|---|
| 1 | DIRETORIA | Irrestrito |
| 6 | SUPORTE | Irrestrito |
| 8 | IAGRO_PACKING | Entrada, Classificação |
| 9 | IAGRO_COMERCIAL | Comercial |
| 10 | IAGRO_ADMINISTRATIVO | Venda, Rastreio, Combustível, Importação |
| 11 | IAGRO_FROTA | Combustível |

### 6.5 CODGRUPOPROD (Grupos de Produto)

| CODGRUPOPROD | DESCRGRUPOPROD | Produtos | Uso IAgro |
|---|---|---|---|
| 200000 | MEF | (agrupador pai) | — |
| 200400 | COMBUSTÍVEIS | Diesel S10 (392), Diesel S500 (1373), Gasolina (391), Óleo (550), Arla 32 (1374) | Filtro para TOP 10/53 |

### 6.6 Configurações Python em `oracle_conn.py`

```python
PARAMETROS_PADRAO = {
    'TOP_ENTRADA': 11,
    'PROD_IN_NATURA': 863,
}

CODGRUPOPROD_COMBUSTIVEL = 200400

CAPACIDADE_TANQUE = {
    392:  10000.0,   # DIESEL S10
    1373: 5000.0,    # DIESEL S500
    1374: 1000.0,    # ARLA 32
}

SALDO_INICIAL_TANQUE = {
    392:  896.0,    # DIESEL S10  — ajustado 2026-05-15 (balanço físico)
    1373: 3204.0,   # DIESEL S500 — ajustado 2026-05-15 (balanço físico)
    1374: 300.0,    # ARLA 32
}
```

---

## 7. Mapa de Pontos de Extensão (Armadilhas Técnicas)

### 7.1 `humanizar_erro_oracle` — Tradução de ORA-XXXXX

Converte exceções Oracle em mensagens amigáveis ao operador. ORA-20101 é genérico — função extrai mensagem real via regex antes do fallback.

### 7.2 Flag `is_write_enabled()` — Controle de Escrita

Habilitar/desabilitar INSERT/UPDATE/DELETE em tempo de execução via `IAGRO_WRITE_ENABLED` env var.

### 7.3 Context Manager `obter_conexao_oracle()`

Gerencia commit/rollback. **Bug DPY-1001 histórico:** funções de INSERT antigas tinham `except` que tentava rollback em conexão já fechada → mascarava erro real. **Workaround:** views de escrita gerenciam conexão explicitamente via `conexao_existente=conn`.

### 7.4 Auto-Cura de `AD_NUMPEDIDOORIG`

Em `atualizar_cabecalho_nota_banco`, busca `MIN(AD_NUMPEDIDOORIG)` entre itens com mesmo CODAGREGACAO. **Aplicável só em Entrada/Classificação.** Venda usa função dedicada sem auto-cura.

### 7.5 Lock Pessimista em `atribuir_lote_item_pedido`

`SELECT ... FOR UPDATE` antes de validação de saldo. Defesa contra double-binding + race condition.

### 7.6 Geração de NUMNOTA via `MAX(NUMNOTA) + 1`

Suficiente para MVP (lock pessimista protege). Migrar para sequence Oracle nativa se emissão de NFe paralela aparecer.

### 7.7 Validação de Tupla `(CODTIPVENDA, DHTIPVENDA)`

Trigger `TRG_INC_TGFCAB` exige tupla coerente. Solução: consultar `DHALTER` mais recente de TGFTPV antes do INSERT.

### 7.8 Transações Multi-Item

`gerar_proxima_sequencia_item` aceita `conexao_existente` pra ver INSERTs anteriores da mesma transação. Sem isso, race condition gera SEQUENCIA duplicada (ORA-00001).

### 7.9 DELETE Físico em vez de UPDATE STATUSNOTA='E'

Trigger `TRG_UPD_TGFCAB` bloqueia. Solução: DELETE em cascata (Combustível B6).

### 7.10 TGFFIN Deve Ficar em Aberto

3 triggers Sankhya rejeitam baixa automática. Padrão correto: `ORIGEM='E'`, `VLRBAIXA=0`, `DHBAIXA=NULL`, `CODTIPOPERBAIXA=0`. Operador baixa pelo Sankhya quando paga.

### 7.11 `GREATEST(0)` em view ANDRE_IAGRO_SALDO_COMBUSTIVEL Corrompe Cálculo

Não usar `QTD_DISPONIVEL` da view direto quando há saldo inicial. Calcular em Python.

### 7.12 `int(dict.get(K, default))` Falha com `None` Explícito

`dict.get(K)` retorna `None` (não o default) quando chave existe com `None`. Solução: `int(dados.get(K) or default)` ou omitir a chave.

---

## 8. Estimativa de Esforço de Desacoplamento

### Fácil (CRUD Direto)
- Tabelas lidas apenas (TGFPAR, TGFPRO, TSIEMP) — **0 risco**
- SELECT simples com typeaheads — **0 risco**
- Views customizadas (ANDRE_IAGRO_SALDO_*) — **baixo risco** (recriar em novo schema)
- **Esforço:** 2-5 dias

### Médio (Regras de Negócio Mapeadas)
- Geração de NUNOTA → SEQUENCE Oracle
- Auto-cura AD_NUMPEDIDOORIG → repensar/simplificar
- Lock pessimista em atribuição de lote → reimplementar
- Modelos TGFFIN em aberto → validar regras
- **Esforço:** 2-3 semanas

### Difícil (Triggers Proprietárias com Cascata)
- TRG_INC_TGFCAB (validação CODTIPVENDA/DHTIPVENDA) → validação em Python
- TRG_*_TGFVAR (6 triggers, cascata TGMTRA) → usar tabela auxiliar AD_VINCULO em novo schema
- TRG_UPD_TGFCAB (bloqueia UPDATE STATUSNOTA='E') → acostumar com DELETE físico
- TRG_*_TGFFIN (3 triggers) → validação manual em Python
- **Esforço:** 4-6 semanas

### Crítico (Sem Workaround Documentado)
- **Emissão de NFe** — Desacoplamento exigirá integração com serviço externo (SEFAZ, Bluesoft, etc.)
- **Movimentação de estoque (TGFEST)** — IAgro NÃO toca (usa view derivada). Replicar view em novo schema
- **Função STP_CRYPT** — Usar bcrypt ou outro padrão moderno
- **Esforço:** 3-4 semanas

---

## 9. Checklist de Migração para Novo Schema

- [ ] Criar schema Oracle (ou PostgreSQL) novo com DDLs versionadas
- [ ] Recriar TGFCAB, TGFITE com todas as colunas (exceto triggers — implementar em Python)
- [ ] Recriar TGFPAR, TGFPRO, TSIEMP (read-only, ou sincronizar via API Sankhya pra Agromil)
- [ ] Recriar tabelas nativas de código: TGFTPV, TGFNAT, TGFTOP, TSIGRU, TGFVEI, TGFGRU
- [ ] Recriar views customizadas: ANDRE_IAGRO_SALDO_LOTE, ANDRE_IAGRO_SALDO_COMBUSTIVEL
- [ ] Recriar tabelas auxiliares: AD_*, com sequences
- [ ] Substituir `STP_CRYPT` por bcrypt/Argon2 (Python)
- [ ] Implementar validações Python (triggers TRG_INC_TGFCAB, TRG_*_TGFFIN)
- [ ] Implementar fluxo de emissão de NFe (integração SEFAZ/provedor externo)
- [ ] Testes de integridade: NUNOTA único, SEQUENCIA único, CODAGREGACAO rastreabilidade
- [ ] Migração de dados históricos: SELECT todas as notas do Sankhya, INSERT em novo schema
- [ ] Validar views pós-migração: saldos coincidentes, nenhuma órfã
- [ ] Testes de carga: 211k linhas TGFVAR, 185k TGFITE, multitenant (múltiplas empresas)
- [ ] Cutover: data de transição, rollback plan

---

## 10. Como manter este arquivo atualizado

Sempre que aparecer durante desenvolvimento:

1. **Nova tabela Sankhya** sendo consumida → adicionar em §1 com colunas usadas + funções
2. **Nova trigger detectada** (geralmente via erro ORA-XXXXX) → adicionar em §2 com lógica e mitigação
3. **Nova função/sequence proprietária** → adicionar em §3
4. **Nova view customizada IAgro** → adicionar em §4
5. **Nova tabela auxiliar AD_*** → adicionar em §5 com DDL location
6. **Novo TOP / CODNAT / STATUSNOTA** → adicionar em §6
7. **Nova regra invisível descoberta** (ex: trigger silenciosa, comportamento inesperado) → adicionar em §7

Cada item afetado precisa marcar `Mai/2026 (YYYY-MM-DD)` ou similar pra rastrear quando foi documentado.

---

<!-- Atualizado em 2026-05-15 -->
