Painel Comercial — README (Português)

Visão geral
-----------
Este arquivo documenta a página `comercial_dashboard.html`, que é um dashboard simples usado pela equipe comercial para gerenciar entradas, distribuição, classificação e simulações.

Estrutura básica
----------------
- `Filtros` (sidebar superior)
  - ID: `filtersCard`
  - Uso: conter inputs e controles de filtragem (a implementar)
- `Tabela` (sidebar inferior)
  - ID: `tableCard`
  - Uso: tabela de lotes/entradas (a implementar)
- Área principal direita: grid Z-pattern (2 colunas x 2 linhas)
  - Topo (span full-width): `Distribuição`
    - ID: `distCard`
    - Contém: `#distWrapper` (flex) com `#distMain` e `#distSim`
  - Bottom-left: `Classificação`
    - ID: `classCard`
  - Bottom-right: `Entrada`
    - ID: `entradaCard`

IDs e propósito (rápido)
------------------------
- `distCard`: card principal de Distribuição. Atualmente possui altura fixa e overflow para rolar internamente.
- `distWrapper`: container flex dentro de `distCard` que organiza `distMain` (conteúdo principal) e `distSim` (painel de simulação)
- `distMain`: área principal de distribuição (conteúdo a implementar, ex: EXTRA/MÉDIO, métricas)
- `distSim`: painel de simulação embutido à direita — possui largura fixa e margens; sua altura é alinhada à do `distCard`.

Estilos importantes
-------------------
- O layout principal usa CSS Grid: `.layout` (sidebar + main) e `.zgrid` (área em Z).
- `#distCard` usa `height: 350px` por padrão (ajustável) e `overflow:auto` para evitar que empurre os cards abaixo.
- `#distSim` tem `width: 320px` e margens top/bottom/direita para criar espaçamento visual.

Como ajustar
------------
- Alterar a altura do `distCard`: editar a regra `#distCard{ height: ... }` no template.
- Para que o painel de simulação acompanhe a altura, mantenha `#distSim` com `box-sizing:border-box` e a regra de `height: calc(100% - 16px)` (subtrai as margens verticalmente).
- Para mudar o espaçamento entre `distMain` e `distSim`, ajustar `#distWrapper{ gap: ... }`.

Recomendações
------------
- Quando implementar a lógica de simulação, mantenha IDs atuais para não quebrar scripts previstos.
- Se for necessário imprimir/gerar relatórios, considere extrair o painel Simulação para um template parcial e reutilizá-lo.

Como testar localmente
---------------------
1. Inicie o servidor Django: `python manage.py runserver`
2. Abra o template via a URL configurada no projeto (ex: `/comercial/`)
3. Recarregue a página com cache limpo (Ctrl+F5) se alterações de CSS não aparecerem.

Notas finais
------------
Este README é um ponto de partida — atualizar conforme o conteúdo e comportamentos reais sejam implementados.
