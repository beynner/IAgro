# ChatBaseProjeto — histórico e decisões

Este arquivo consolida o histórico das conversas e decisões técnicas aplicadas ao projeto (Packing House / Classificação e Portal). Última atualização: 2025-09-30.

## Objetivos principais trabalhados

- Portal (Itens — Nota):
  - Confirmação ao salvar item repetido e limpar formulário ao cancelar.
  - Proteção contra duplo clique ao adicionar.
  - Formatação numérica (Qtd, Peso, Total) com separador de milhar e 1 casa.
  - Colunas reordenadas para: Produto, Lote, Classifica, Qtd, Vol, Peso, Total.
  - Comportamento dos botões de fechar/salvar ajustados; “X” em vermelho, “Fechar” cinza.
  - Ícone “+” maior e centralizado; vira “v” ao editar.
  - Validações com borda/vermelho imediato em campos obrigatórios.
  - Total = Qtd × Peso (no cliente, com fallback servidor).

- Cabeçalho (Portal):
  - Título “Cabeçalho”. Parceiro em branco por padrão (novo lançamento).
  - Validações obrigatórias com borda vermelha, exceto Nº Documento e Observação.

- Classificação (página LOTES):
  - Redução leve de fonte (body 14px; tabela 13px).
  - Ao abrir, e no modal “Classificar”, mostrar apenas itens que classificam.
  - Em “Itens — Nota”, produto com autocomplete filtrado pelo In Natura (coluna FABRICANTE; exceção TOMATE por subtipo via token na descrição: SALADA/ITALIANO).

## Regras de negócio implementadas

- Item “Classifica” (front):
  - Se geraproducao estiver presente: classifica = (upper(geraproducao) != 'N').
  - Senão, se classifica (boolean) presente: usa o boolean.
  - Senão: considera classificável (fallback permissivo; ajustável).

- Backend de “lote/consultar” (entradas/classificáveis):
  - Classificáveis: apenas itens com GERAPRODUCAO = 'S' (NVL(...,'N') = 'S').
  - Badge de NUNOTA TOP 26 quando existente; agregados e entradas convertidos a JSON.

- Criação de cabeçalho TOP 26 (Classificação):
  - Ao executar classificação: se já existir TGFCAB TOP 26 para o mesmo CODAGREGACAO, reutiliza; senão cria novo cabeçalho 26 com CODEMP/CODPARC/DTs/CODNAT/CODCENCUS herdados da origem.

- Autocomplete de Produto no Itens — Nota (Classificação):
  - Envia &cod_innatura=<cod> para /sankhya/produtos/search/.
  - O backend filtra por FABRICANTE do produto In Natura.
  - Caso FABRICANTE = 'TOMATE', restringe também por token na descrição (SALADA/ITALIANO).
  - No front, o cod_innatura é definido a partir das entradas do lote (prioriza match com prod_in_natura; senão pega a primeira entrada) e atualizado ao trocar a “Origem”.

## Endpoints relevantes

- GET /sankhya/lote/consultar/?controle=... — Detalhes do lote (agregados, classificações, classificáveis, entradas, nunota_class, prod_in_natura).
- GET /sankhya/item/list/?nunota=... — Lista itens da nota (inclui classifica/geraproducao; calcula total = qtd×peso).
- POST /sankhya/item/plan | /sankhya/item/save | /sankhya/item/delete — Planejamento, gravação e exclusão de item.
- POST /sankhya/header/plan | /sankhya/packing/central/salvar | /sankhya/header/update — Cabeçalho TOP 26 (plan/insert/update).
- POST /sankhya/class/plan | /sankhya/class/execute — Plano de classificação e execução (cria/reutiliza cabeçalho 26, insere saídas).
- GET /sankhya/produtos/search/?q=...&limit=...&cod_innatura=... — Busca de produtos com filtro por FABRICANTE do In Natura (e subtipo de TOMATE por token).

## Arquivos editados com impacto

- `sankhya_integration/templates/sankhya_integration/compras_portal.html`
  - UI do Portal: confirmação de duplicidade, formatações, validações, layout e botões.

- `sankhya_integration/templates/sankhya_integration/compras_classificacao.html`
  - Redução de fonte; filtro “Somente classifica”; modais de Classificar e Itens; autocomplete de produtos enviando cod_innatura; lógica para manter o In Natura em sincronia com a origem selecionada.

- `sankhya_integration/services/oracle_conn.py`
  - `consultar_lote`: classificáveis com GERAPRODUCAO = 'S'; agregados e sumários.
  - `plan_classificacao`/`execute_classificacao`: plano/execução TOP 26; reutilização de cabeçalho.

- `sankhya_integration/views.py`
  - `/sankhya/produtos/search/`: suporte a `cod_innatura` com filtro por FABRICANTE; regra de subtipo para TOMATE.
  - `/sankhya/lote/consultar/`: JSON para front (entradas/classificações/classificáveis), conversões e prod_in_natura.
  - `/sankhya/item/list/`: shape com classifica/geraproducao; cálculo de total; conversões de unidade.

## Como testar rapidamente

1) Filtro de classifica (Itens):
   - Abra um lote, verifique “Somente classifica” ativo: linhas com gp='N' devem sumir.

2) Origem do modal Classificar:
   - Apenas entradas classificáveis devem aparecer (GERAPRODUCAO='S').

3) Autocomplete por In Natura:
   - Com um lote de TOMATE SALADA, ao digitar produto no Itens — Nota, resultados devem ser do mesmo FABRICANTE e subtipo.
   - Trocar a “Origem” deve atualizar o filtro do autocomplete.

4) Cabeçalho 26:
   - Executar classificação; se já houver nota 26 do mesmo controle, deve reutilizar; senão criar nova (ver badge de NUNOTA).

## Observações e próximos passos

- Tokens de TOMATE podem ser ampliados (CEREJA, GRAPE etc.).
- Se `prod_in_natura` não vier no payload, o front usa a primeira entrada do lote como fallback.
- Podemos exibir um badge “Filtrando por In Natura: <cod>” ao lado do campo Produto para transparência.

---

Se precisar, crio também um arquivo em `docs/` com changelog incremental (por data) e uma versão resumida deste histórico para consulta rápida.

## Resumo expandido da sessão (timeline)

1) Portal — Itens e Cabeçalho
- Anti-duplicação (confirmação ao detectar item repetido); limpar form ao cancelar.
- Busy flag e desabilitar botão para evitar duplo clique.
- Formatação pt-BR (separador milhar e 1 casa decimal) para Qtd, Peso, Total; Total = Qtd × Peso.
- UI: colunas reordenadas; botões “X” vermelho e “Fechar” cinza; “+” maior/centralizado; “+”→“v” em modo edição.
- Validações com borda vermelha e destaque leve; foco no primeiro inválido; Observação opcional.
- Cabeçalho: título “Cabeçalho”, Parceiro em branco (novo), validações obrigatórias no salvar.

2) Classificação — LOTES e modais
- Redução de fontes; “Somente classifica” nos itens do modal.
- Origem do modal Classificar lista apenas GERAPRODUCAO='S' (servidor).
- Autocomplete de produto nos Itens filtrado por FABRICANTE do In Natura (+ subtipo TOMATE por token em descrição).
- Contexto In Natura mantido e atualizado ao trocar Origem.

3) Backend
- `consultar_lote`: classificáveis com `NVL(GERAPRODUCAO,'N')='S'`; agregados; nunota_class; prod_in_natura.
- `produtos_search`: aceita `cod_innatura`; filtra por `FABRICANTE`; se TOMATE, restringe por token (SALADA/ITALIANO) na descrição.
- `plan/execute_classificacao`: reutiliza cabeçalho TOP 26 existente ou cria novo; insere itens.
- `item_list`: inclui classifica/geraproducao; calcula total e ajusta unidades por fator (VOA).

## Contratos (inputs/outputs)

- GET `/sankhya/lote/consultar/?controle={string}`
  - ok, agregados, classificacoes[], classificaveis[], entradas[], nunota_class, prod_in_natura.
- GET `/sankhya/produtos/search/?q={string}&limit={int}&cod_innatura={int?}`
  - results: [{ cod, descr }], filtrado por FABRICANTE do In Natura; TOMATE → token (SALADA/ITALIANO).
- GET `/sankhya/item/list/?nunota={int}`
  - items: [{ nunota, sequencia, cod, descr, lote, codvol, qtd, peso, total, vlu, vlt, obs, classifica, geraproducao }].
- POST `/sankhya/item/plan|save|delete`
  - Plan retorna SQL/binds (preview); Save/ Delete retornam executed, warnings/errors.
- POST `/sankhya/class/plan|execute`
  - Plano de classificação e execução; write_enabled; nunota_dest.

## Helpers de front relevantes

- Validação/UX: `markInvalidField`, `.invalid` (borda + fundo leve vermelho #fee2e2).
- Números: `parseFlexibleNumber`, `formatBR1`.
- Itens: `recalcItemTotal`, `setItemAddBtnMode`, `hasDuplicateItemInList`, `itemAddBusy`.
- Navegação tabela: selecionar linha, setActive via ArrowUp/Down, Apply via Enter.

## Edge cases e testes sugeridos

- Filtro de produto sem `prod_in_natura`: deve cair para primeira entrada do lote.
- TOMATE sem token claro na descrição: decidir entre permissivo (só por FABRICANTE) ou restritivo (sem retorno) — hoje permissivo por FABRICANTE.
- Unidades alternativas (VOA): verificar fator; lista de itens deve apresentar quantidade convertida.
- Duplo clique rápido no botão “+”: item único devido ao busy flag.
- Exclusão de item/cabeçalho: verificar mensagens e atualização de badges/contadores.

## Instruções para anexar a transcrição integral

1) No VS Code (Copilot Chat), exporte a conversa pelo menu “⋯” → “Export chat” e salve como Markdown, por exemplo:
   - `docs/chat-export-YYYY-MM-DD.md`
2) Se não houver opção Export, selecione todo o chat (Ctrl+A), copie e cole em um arquivo `.md` em `docs/`.
3) Após salvar no repo, avise o caminho. Posso então:
   - Substituir o conteúdo deste arquivo pela transcrição integral; ou
   - Manter este resumo e anexar a transcrição abaixo (preferência recomendada).