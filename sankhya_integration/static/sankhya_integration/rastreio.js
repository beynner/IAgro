document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    // ==========================================================================
    // 1. CONFIGURAÇÃO
    // ==========================================================================
    const URLS = {
        lotes:           '/sankhya/rastreio/api/lotes-disponiveis/',
        pedidos:         '/sankhya/rastreio/api/pedidos-abertos/',
        atribuirLote:    '/sankhya/rastreio/api/atribuir-lote/',
        desvincularLote: '/sankhya/rastreio/api/desvincular-lote/',
        fabricantes:     '/sankhya/rastreio/api/fabricantes/',
        loteVinculos:    '/sankhya/rastreio/api/lote-vinculos/',
    };
    const PAGE_SIZE = 50;
    const SCROLL_THRESHOLD = 200;   // px do fim para disparar próxima página

    // ==========================================================================
    // 2. ESTADO
    // ==========================================================================
    // Lotes
    let lotesData       = [];
    let lotesOffset     = 0;
    let lotesTemMais    = true;
    let lotesCarregando = false;

    // Pedidos (lista linhas TGFITE; o front agrupa por NUNOTA e por CODPROD)
    let pedidosData       = [];
    let pedidosOffset     = 0;
    let pedidosTemMais    = true;
    let pedidosCarregando = false;

    // Filtros / agrupamento / interação
    // CHECKS DE FILTRO CRUZADO — separados em dois eixos pra que marcar
    // o produto X num pedido NÃO marque automaticamente os checks de produto X
    // em outros pedidos (que era o comportamento confuso anterior).
    //   - checksLotes: produtos marcados via checkbox dos cards de LOTE
    //   - checksPorPedido: produtos marcados via checkbox de cada PRODUTO-LINHA,
    //                      mantidos separados por NUNOTA (Map<nunota, Set<codprod>>)
    // O filtro cruzado (lotes ↔ pedidos) usa a UNIÃO dos dois para enviar
    // codprods ao backend e para esconder/mostrar lotes/pedidos.
    const checksLotes       = new Set();
    const checksPorPedido   = new Map();
    let pedidoIsolado       = null;         // NUNOTA quando o usuário clica no header de um pedido específico
    let agrupamentoAtual    = 'parceiro';   // 'parceiro' | 'produto' (header agrupador)
    let tipoLote            = 'todos';      // 'todos' | 'classificavel' | 'nao_classificavel'
    let textoFiltroLotes    = '';           // filtro LIKE de codagregacao
    let fabricanteAtivo     = '';           // filtro exato de FABRICANTE (vem do typeahead)
    let textoFiltroPedidos  = '';
    // Filtros de período (formato ISO YYYY-MM-DD; '' = sem filtro daquele lado)
    let dataIniLotes        = '';
    let dataFimLotes        = '';
    let dataIniPedidos      = '';
    let dataFimPedidos      = '';
    let loteArmado          = null;         // lote selecionado para vincular (click-to-select)
    // Fase 4.6 — toggle "só pendentes" (esconde produto-linhas já 100% atribuídas)
    let somentePendentes    = false;
    // Set<NUNOTA> — pedidos atualmente colapsados (produtos escondidos).
    // Default: TODOS os pedidos vêm colapsados; o usuário expande clicando
    // no header. Click no nome do parceiro/chevron alterna o estado.
    const pedidosColapsados = new Set();
    // Set<nomeProduto> — grupos de produto atualmente colapsados (no modo
    // POR PRODUTO). Click no header do grupo expande/recolhe.
    const gruposProdutoColapsados = new Set();
    // Set<nomeProduto> — grupos de produto já inicializados ao menos uma vez.
    // Mesmo padrão de pedidosJaVistos: novos grupos vêm colapsados por
    // padrão; estado escolhido pelo usuário se mantém após scroll/refresh.
    const gruposProdutoJaVistos    = new Set();
    // Set<NUNOTA> — pedidos já inicializados pelo menos uma vez. Garante que
    // o "default colapsado" só aplica na PRIMEIRA aparição do pedido na tela
    // (subsequente scroll infinito ou refresh preserva o estado escolhido
    // pelo usuário). Reset acontece em limparTudo().
    const pedidosJaVistos   = new Set();
    // Fase 2.13 — alerta visual em lote envelhecido (DTNEG_ORIGEM > N dias)
    const DIAS_ALERTA_LOTE  = 60;

    // ----- Persistência de preferências em localStorage (Fase 2.12) ---------
    // Restaura/grava: agrupamento, tipoLote, datas (ini/fim) lotes e pedidos,
    // checkTrava, somentePendentes, loteArmadoCodag. Filtros cruzados continuam
    // efêmeros (decisão consciente — operador re-marca por ciclo de trabalho).
    // loteArmadoCodag (Mai/2026) — re-arma o lote ao reload. Útil quando o
    // operador é interrompido/perde a conexão no meio de uma vinculação.
    const LS_KEY = 'iagro:rastreio:prefs:v1';
    function _salvarPrefs() {
        try {
            localStorage.setItem(LS_KEY, JSON.stringify({
                agrupamento: agrupamentoAtual,
                tipoLote,
                dataIniLotes, dataFimLotes,
                dataIniPedidos, dataFimPedidos,
                travado: !!(checkTrava && checkTrava.classList.contains('is-on')),
                somentePendentes,
                loteArmadoCodag: loteArmado ? loteArmado.codagregacao : null,
            }));
        } catch (_) {}
    }
    function _carregarPrefs() {
        try {
            const raw = localStorage.getItem(LS_KEY);
            if (!raw) return null;
            return JSON.parse(raw);
        } catch (_) { return null; }
    }

    // Re-arma o lote pelo CODAGREGACAO salvo nas prefs. Roda 1× por boot
    // (após primeiro carregamento de lotes). Se o lote não estiver mais
    // disponível (vendido/avariado/fora do filtro), a pref é descartada
    // silenciosamente — operador retoma do zero sem mensagem assustadora.
    let _restaurouArmado = false;
    function _tentarRestaurarLoteArmado() {
        if (_restaurouArmado) return;
        _restaurouArmado = true;
        const prefs = _carregarPrefs();
        const codag = prefs && prefs.loteArmadoCodag;
        if (!codag) return;
        const lote = lotesData.find(l => l.codagregacao === codag);
        if (!lote) {
            // Lote não está mais visível — limpa pref pra não tentar de novo
            try {
                const p = _carregarPrefs() || {};
                delete p.loteArmadoCodag;
                localStorage.setItem(LS_KEY, JSON.stringify(p));
            } catch (_) {}
            return;
        }
        loteArmado = lote;
        atualizarBarArmado();
    }

    /** União de todos os produtos marcados em checksLotes + checksPorPedido. */
    function _uniaoFiltrosProdutos() {
        const u = new Set(checksLotes);
        for (const cps of checksPorPedido.values()) {
            for (const cp of cps) u.add(cp);
        }
        return u;
    }
    function temFiltroProdutos() {
        if (checksLotes.size > 0) return true;
        for (const cps of checksPorPedido.values()) if (cps.size > 0) return true;
        return false;
    }
    /** Para cards de LOTE: o lote está "selecionado" se foi marcado direto
     *  (checksLotes) OU se algum pedido tem o produto marcado (cross filter). */
    function loteEstaCheckado(codprod) {
        const cp = Number(codprod);
        if (checksLotes.has(cp)) return true;
        for (const cps of checksPorPedido.values()) if (cps.has(cp)) return true;
        return false;
    }
    /** Para PRODUTO-LINHA: marcado SOMENTE se o usuário marcou
     *  esta linha específica naquele pedido. Não cascateia entre pedidos. */
    function produtoLinhaEstaCheckada(codprod, nunota) {
        const cps = checksPorPedido.get(Number(nunota));
        return cps ? cps.has(Number(codprod)) : false;
    }
    /** Compatibilidade — usado quando NÃO há nunota disponível (lotes,
     *  filtragem genérica). Equivale ao "tem em qualquer eixo". */
    function produtoEstaFiltrado(codprod, nunota) {
        if (nunota !== undefined) return produtoLinhaEstaCheckada(codprod, nunota);
        return loteEstaCheckado(codprod);
    }
    function setsIguais(a, b) {
        if (a.size !== b.size) return false;
        for (const v of a) if (!b.has(v)) return false;
        return true;
    }
    /** Limpa todos os checks dos dois eixos. Usado em LIMPAR e isolamento. */
    function _limparTodosChecks() {
        checksLotes.clear();
        checksPorPedido.clear();
    }

    /** [LEGACY] Mantido pra retro-compat — não chamado por nada de UI.
     *  Click em card/linha não filtra mais (substituído por checkboxes). */
    function aplicarFiltroProdutos(codprods) {
        if (checkTrava && checkTrava.classList.contains('is-on')) return;
        const lista = Array.isArray(codprods) ? codprods : [codprods];
        _limparTodosChecks();
        lista.forEach(cp => checksLotes.add(Number(cp)));
        pedidoIsolado = null;
        carregarLotes(true);
        carregarPedidos(true);
    }

    /** Toggle do checkbox dentro de um CARD de LOTE — atua em checksLotes. */
    function toggleCheckLote(codprod, marcado) {
        const cp = Number(codprod);
        if (!Number.isFinite(cp)) return;
        if (marcado) checksLotes.add(cp);
        else         checksLotes.delete(cp);
        if (marcado) pedidoIsolado = null;
        carregarLotes(true);
        carregarPedidos(true);
    }

    /** Toggle do checkbox dentro de uma PRODUTO-LINHA — atua em
     *  checksPorPedido[nunota], sem afetar checks dos mesmos codprods em
     *  outros pedidos (foi o que o usuário pediu para corrigir). */
    function toggleCheckProdutoPedido(codprod, nunota, marcado) {
        const cp = Number(codprod);
        const nu = Number(nunota);
        if (!Number.isFinite(cp) || !Number.isFinite(nu)) return;
        let set = checksPorPedido.get(nu);
        if (!set) {
            if (!marcado) return;
            set = new Set();
            checksPorPedido.set(nu, set);
        }
        if (marcado) set.add(cp);
        else         set.delete(cp);
        // Limpa entradas vazias para o Map não acumular
        if (set.size === 0) checksPorPedido.delete(nu);
        if (marcado) pedidoIsolado = null;
        carregarLotes(true);
        carregarPedidos(true);
    }

    /** Versão antiga `toggleFiltroProduto` mantida só pra não quebrar callers
     *  que ainda existam — defaultando ao comportamento antigo de cards de lote. */
    function toggleFiltroProduto(codprod, marcado) {
        toggleCheckLote(codprod, marcado);
    }

    /** Aplica isolamento ao clicar no header do pedido (replace + isolamento).
     *  Click no mesmo pedido limpa tudo. TRAVAR FILTRO bloqueia este caminho. */
    function aplicarFiltroPedidoIsolado(nunota, codprods) {
        if (checkTrava && checkTrava.classList.contains('is-on')) return;

        const novoSet = new Set((codprods || []).map(Number));
        // Compara a representação atual de filtros de pedido isolado (todos os
        // codprods desse pedido em checksPorPedido[nunota] e checksLotes vazio)
        const cpsAtuais = checksPorPedido.get(Number(nunota)) || new Set();
        const jaIsolado = pedidoIsolado === Number(nunota) &&
                          checksLotes.size === 0 &&
                          checksPorPedido.size === 1 &&
                          setsIguais(novoSet, cpsAtuais);
        _limparTodosChecks();
        if (jaIsolado) {
            pedidoIsolado = null;
        } else {
            pedidoIsolado = Number(nunota);
            checksPorPedido.set(Number(nunota), novoSet);
        }
        carregarLotes(true);
        carregarPedidos(true);
    }

    // ==========================================================================
    // 3. ELEMENTOS
    // ==========================================================================
    const containerLotes      = document.getElementById('lotesContainer');
    const containerPedidos    = document.getElementById('pedidosContainer');
    const checkTrava          = document.getElementById('checkTrava');
    const inputFiltroLotes    = document.getElementById('filtroLotes');
    const inputFiltroPedidos  = document.getElementById('filtroPedidos');
    const dropdownLotes       = document.getElementById('dropdownLotes');
    const dropdownPedidos     = document.getElementById('dropdownPedidos');
    const inputDataIniLotes   = document.getElementById('dataIniLotes');
    const inputDataFimLotes   = document.getElementById('dataFimLotes');
    const inputDataIniPedidos = document.getElementById('dataIniPedidos');
    const inputDataFimPedidos = document.getElementById('dataFimPedidos');
    const btnLimparPerLotes   = document.getElementById('btnLimparPeriodoLotes');
    const btnLimparPerPedidos = document.getElementById('btnLimparPeriodoPedidos');
    const filtrosAtivosEl     = document.getElementById('filtrosAtivos');
    const filtrosAtivosChipsEl = document.getElementById('filtrosAtivosChips');
    // Modal de vínculos (lote→pedidos ou pedido→lotes)
    const modalVinculos       = document.getElementById('modalVinculos');
    const vinculosTitulo      = document.getElementById('vinculosTitulo');
    const vinculosBody        = document.getElementById('vinculosBody');
    const btnFecharVinculos   = document.getElementById('btnFecharVinculos');
    const modalTransfer       = document.getElementById('modalTransferencia');
    const transferLoteName    = document.getElementById('transferLoteName');
    const transferDestino     = document.getElementById('transferDestino');
    const inputQtdTransfer    = document.getElementById('inputQtdTransfer');
    const maxLoteSpan         = document.getElementById('maxLote');
    const maxPedidoSpan       = document.getElementById('maxPedido');
    const btnFecharModal      = document.getElementById('btnFecharModal');
    const btnCancelarTransfer = document.getElementById('btnCancelarTransfer');
    const btnConfirmarTransfer = document.getElementById('btnConfirmarTransfer');
    // Barra "lote armado"
    const barArmado           = document.getElementById('barArmado');
    const barArmadoLote       = document.getElementById('barArmadoLote');
    const barArmadoDisp       = document.getElementById('barArmadoDisp');
    const btnDesarmar         = document.getElementById('btnDesarmar');

    let transferenciaContexto = null;  // { lote, item, qtdLinhaPendente }

    // ==========================================================================
    // 4. HELPERS
    // ==========================================================================
    const PH = window.IAgro || {};

    function getCookie(name) {
        if (PH.getCookie) return PH.getCookie(name);
        const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return m ? decodeURIComponent(m[1]) : '';
    }
    async function postJSON(url, data) {
        if (PH.postJSON) return PH.postJSON(url, data);
        const r = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify(data),
        });
        return { ok: r.ok, status: r.status, body: await r.json() };
    }
    function showToast(msg, type) {
        if (!document.getElementById('toastContainer')) {
            const tc = document.createElement('div'); tc.id = 'toastContainer';
            document.body.appendChild(tc);
        }
        if (PH.showToast) PH.showToast(msg, type || 'info');
        else console.log('[' + (type || 'info') + ']', msg);
    }

    // Modal de confirmação (Fase 1.5) — fallback pra window.confirm se helper indisponível
    const phConfirmar = PH.confirmarAcao || (async (o) =>
        Promise.resolve(window.confirm(o.mensagem || 'Confirmar?'))
    );

    /** Gera avatar circular do fornecedor com 2 letras + cor estável por hash do nome.
     *  Retorna string HTML. Cor é determinística — mesmo nome sempre mesma cor,
     *  ajuda a escanear lotes do mesmo fornecedor visualmente. */
    function _avatarFornecedor(nome) {
        const txt = String(nome || '—').trim();
        // 2 iniciais (primeiras letras de até 2 palavras)
        const partes = txt.split(/\s+/).filter(Boolean);
        const iniciais = (
            (partes[0] || '?').charAt(0) +
            ((partes[1] || partes[0] || '').charAt(0) || '')
        ).toUpperCase();
        // Hash simples do nome → índice de paleta de 12 cores
        let h = 0;
        for (let i = 0; i < txt.length; i++) {
            h = ((h << 5) - h + txt.charCodeAt(i)) | 0;
        }
        const cores = [
            '#0ea5e9', '#8b5cf6', '#ec4899', '#f43f5e',
            '#f59e0b', '#84cc16', '#10b981', '#06b6d4',
            '#6366f1', '#a855f7', '#ef4444', '#14b8a6',
        ];
        const cor = cores[Math.abs(h) % cores.length];
        return `<span class="ras-avatar" style="background:${cor}" title="${escapeHtml(txt)}">${escapeHtml(iniciais)}</span>`;
    }

    /** Renderiza barra de progresso compacta com cor adaptativa.
     *  pct < 50% vermelho, < 100% azul, 100% verde. Se pct=0, mostra a barra
     *  vazia mas presente (não some) — dá referência visual da ausência. */
    function _renderProgressBar(atribuida, total) {
        const a = Number(atribuida) || 0;
        const t = Number(total) || 0;
        const pct = t > 0 ? Math.min(100, Math.round((a / t) * 100)) : 0;
        let cor = '#ef4444';   // vermelho
        if (pct >= 100)      cor = '#10b981';  // verde
        else if (pct >= 50)  cor = '#3b82f6';  // azul
        else if (pct >= 25)  cor = '#f59e0b';  // laranja
        return `<span class="ras-pbar" title="${pct}% vinculado">
            <span class="ras-pbar-fill" style="width:${pct}%;background:${cor}"></span>
        </span>`;
    }

    /** Converte data BR "DD/MM/YYYY" em timestamp (ms). Vazio/inválido → 0,
     *  o que faz pedidos sem data caírem para o fim quando ordenamos DESC. */
    function _timestampFromBR(dataBR) {
        if (!dataBR) return 0;
        const m = String(dataBR).match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
        if (!m) return 0;
        return new Date(parseInt(m[3], 10),
                        parseInt(m[2], 10) - 1,
                        parseInt(m[1], 10)).getTime();
    }

    /** Comparator: data DESC, depois parceiro ASC. Usado pra POR PRODUTO. */
    function _comparePedidosPadrao(a, b) {
        const ta = _timestampFromBR(a.dtneg);
        const tb = _timestampFromBR(b.dtneg);
        if (tb !== ta) return tb - ta;   // mais recente primeiro
        return String(a.nomeparc || '').localeCompare(String(b.nomeparc || ''));
    }
    /** Comparator: data ASC (mais antigo primeiro), depois parceiro ASC.
     *  Usado pra POR PARCEIRO conforme pedido do usuário. */
    function _comparePedidosPorParceiro(a, b) {
        const ta = _timestampFromBR(a.dtneg);
        const tb = _timestampFromBR(b.dtneg);
        if (ta !== tb) return ta - tb;   // mais antigo primeiro
        return String(a.nomeparc || '').localeCompare(String(b.nomeparc || ''));
    }

    /** Calcula idade em dias entre uma data dd/mm/yyyy (vem assim do backend) e hoje. */
    function _idadeDiasFromBR(dataBR) {
        if (!dataBR) return 0;
        const m = String(dataBR).match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
        if (!m) return 0;
        const [, dd, mm, yyyy] = m;
        const data = new Date(parseInt(yyyy, 10), parseInt(mm, 10) - 1, parseInt(dd, 10));
        const hoje = new Date();
        const diff = hoje.getTime() - data.getTime();
        return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
    }
    function debounce(fn, wait) {
        if (PH.debounce) return PH.debounce(fn, wait);
        let t;
        return function (...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), wait);
        };
    }
    function fmtQtd(v) {
        const n = Number(v) || 0;
        return n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    function fmtInt(v) {
        return (Number(v) || 0).toLocaleString('pt-BR', { maximumFractionDigits: 0 });
    }
    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    // Tenta achar a descrição de um produto a partir dos dados já carregados.
    // Fallback: "#CODPROD".
    function _descricaoProduto(codprod) {
        const cp = Number(codprod);
        for (const l of lotesData) {
            if (Number(l.codprod) === cp) return l.descrprod;
        }
        for (const p of pedidosData) {
            if (Number(p.codprod) === cp) return p.descrprod;
        }
        return '#' + codprod;
    }

    // Formata "YYYY-MM-DD" → "DD/MM"
    function _fmtDataChip(iso) {
        if (!iso) return '';
        const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
        return m ? `${m[3]}/${m[2]}` : iso;
    }

    // ==========================================================================
    // 4b. CHIPS DE FILTROS ATIVOS
    // ==========================================================================
    /** Lê o estado e (re)renderiza os chips dentro de #filtrosAtivos.
     *  Cada chip tem data-filtro identificando o tipo, e o handler de × chama
     *  removerFiltro(tipo). O container some quando não há filtro ativo. */
    function renderFiltrosAtivos() {
        // O container externo (#filtrosAtivos) fica SEMPRE visível agora —
        // contém os botões fixos Limpar/Atualizar à direita. Aqui só
        // populamos a parte dos chips à esquerda (#filtrosAtivosChips).
        const alvo = filtrosAtivosChipsEl || filtrosAtivosEl;
        if (!alvo) return;
        const chips = [];

        function chip(grupo, tipo, label, valor) {
            chips.push(
                `<span class="filtro-chip ${grupo}" data-filtro="${tipo}">` +
                    `<span class="chip-tipo">${escapeHtml(label)}:</span>` +
                    `<span class="chip-valor" title="${escapeHtml(valor)}">${escapeHtml(valor)}</span>` +
                    `<button type="button" class="chip-fechar" title="Remover filtro">×</button>` +
                `</span>`
            );
        }

        // ---- Lotes ----
        if (fabricanteAtivo) chip('lotes', 'fabricante', 'Fabricante', fabricanteAtivo);
        if (textoFiltroLotes) chip('lotes', 'lote_texto', 'Lote', textoFiltroLotes);
        if (tipoLote === 'classificavel')           chip('lotes', 'tipo_lote', 'Tipo', 'Classificáveis');
        else if (tipoLote === 'nao_classificavel')  chip('lotes', 'tipo_lote', 'Tipo', 'Não-classif.');
        if (dataIniLotes || dataFimLotes) {
            const ini = _fmtDataChip(dataIniLotes);
            const fim = _fmtDataChip(dataFimLotes);
            const valor = ini && fim ? `${ini} → ${fim}` : (ini ? `≥ ${ini}` : `≤ ${fim}`);
            chip('lotes', 'periodo_lotes', 'Período lotes', valor);
        }

        // ---- Pedidos ----
        if (textoFiltroPedidos) {
            const lab = /^\d+$/.test(textoFiltroPedidos) ? 'Pedido' : 'Cliente';
            chip('pedidos', 'pedido_texto', lab, textoFiltroPedidos);
        }
        if (pedidoIsolado != null) chip('pedidos', 'pedido_isolado', 'Pedido', String(pedidoIsolado));
        if (dataIniPedidos || dataFimPedidos) {
            const ini = _fmtDataChip(dataIniPedidos);
            const fim = _fmtDataChip(dataFimPedidos);
            const valor = ini && fim ? `${ini} → ${fim}` : (ini ? `≥ ${ini}` : `≤ ${fim}`);
            chip('pedidos', 'periodo_pedidos', 'Período pedidos', valor);
        }

        // ---- Filtro cruzado de produtos ----
        const uniao = _uniaoFiltrosProdutos();
        if (uniao.size > 0) {
            const lista = [...uniao];
            const valor = lista.length === 1
                ? _descricaoProduto(lista[0])
                : `${lista.length} produtos`;
            chip('cruzado', 'produtos', 'Produto', valor);
        }

        if (chips.length === 0) {
            // Sem filtros: deixa só uma mensagem leve à esquerda
            alvo.innerHTML =
                '<span class="filtros-ativos-vazio">Sem filtros aplicados</span>';
            filtrosAtivosEl?.classList.add('vazio');
            return;
        }
        filtrosAtivosEl?.classList.remove('vazio');
        alvo.innerHTML =
            '<span class="filtros-ativos-label">Filtros:</span>' + chips.join('');
    }

    /** Limpa um filtro específico identificado pelo data-filtro do chip. */
    function removerFiltro(tipo) {
        switch (tipo) {
            case 'fabricante':
                fabricanteAtivo = '';
                if (inputFiltroLotes) inputFiltroLotes.value = '';
                carregarLotes(true);
                carregarPedidos(true);   // cross filter: limpar fabricante reflete nos pedidos
                break;
            case 'lote_texto':
                textoFiltroLotes = '';
                if (inputFiltroLotes) inputFiltroLotes.value = '';
                carregarLotes(true);
                break;
            case 'tipo_lote': {
                tipoLote = 'todos';
                const radioTodos = document.getElementById('tipoTodos');
                if (radioTodos) radioTodos.checked = true;
                carregarLotes(true);
                break;
            }
            case 'periodo_lotes':
                dataIniLotes = '';
                dataFimLotes = '';
                if (inputDataIniLotes) inputDataIniLotes.value = '';
                if (inputDataFimLotes) inputDataFimLotes.value = '';
                carregarLotes(true);
                break;
            case 'pedido_texto':
                textoFiltroPedidos = '';
                if (inputFiltroPedidos) inputFiltroPedidos.value = '';
                carregarPedidos(true);
                carregarLotes(true);   // cross filter: limpar cliente reflete nos lotes
                break;
            case 'pedido_isolado':
                pedidoIsolado = null;
                carregarPedidos(true);
                break;
            case 'periodo_pedidos':
                dataIniPedidos = '';
                dataFimPedidos = '';
                if (inputDataIniPedidos) inputDataIniPedidos.value = '';
                if (inputDataFimPedidos) inputDataFimPedidos.value = '';
                carregarPedidos(true);
                break;
            case 'produtos':
                _limparTodosChecks();
                pedidoIsolado = null;
                carregarLotes(true);
                carregarPedidos(true);
                break;
        }
    }

    if (filtrosAtivosEl) {
        filtrosAtivosEl.addEventListener('click', (e) => {
            const btn = e.target.closest('.chip-fechar');
            if (!btn) return;
            const chip = btn.closest('.filtro-chip');
            if (!chip) return;
            removerFiltro(chip.dataset.filtro);
        });
    }

    // ==========================================================================
    // 5. CARGA DE DADOS — LOTES (paginado)
    // ==========================================================================
    async function carregarLotes(reset) {
        if (lotesCarregando) return;
        if (reset) {
            lotesData = [];
            lotesOffset = 0;
            lotesTemMais = true;
            renderFiltrosAtivos();   // sincroniza chips quando o filtro muda
        }
        if (!lotesTemMais) return;

        lotesCarregando = true;
        // Render imediato: limpa o painel e mostra "Carregando..." enquanto a
        // view de saldo é processada no Oracle. Sem isto, o painel mostraria
        // os lotes do filtro ANTERIOR até a fetch terminar.
        if (reset) renderLotes();
        try {
            const params = new URLSearchParams({
                limit: String(PAGE_SIZE),
                offset: String(lotesOffset),
            });
            if (textoFiltroLotes) params.set('codagregacao', textoFiltroLotes);
            if (fabricanteAtivo)  params.set('fabricante',   fabricanteAtivo);
            if (tipoLote && tipoLote !== 'todos') params.set('tipo', tipoLote);
            if (dataIniLotes) params.set('data_ini', dataIniLotes);
            if (dataFimLotes) params.set('data_fim', dataFimLotes);
            // Cross filter vindo do typeahead de Pedidos: quando o usuário
            // selecionou/digitou um nome de cliente (texto, não NUNOTA), filtra
            // os lotes para mostrar apenas os de produtos que esse cliente compra.
            if (textoFiltroPedidos && !/^\d+$/.test(textoFiltroPedidos)) {
                params.set('cliente_q', textoFiltroPedidos);
            }
            const uniaoLotes = _uniaoFiltrosProdutos();
            if (uniaoLotes.size > 0) {
                params.set('codprods', [...uniaoLotes].join(','));
            }

            const r = await fetch(URLS.lotes + '?' + params.toString(), {
                credentials: 'same-origin', cache: 'no-store',
            });
            const data = await r.json();
            if (!data.ok) throw new Error(data.error || 'Falha ao listar lotes');

            lotesData = lotesData.concat(data.lotes || []);
            lotesOffset += (data.lotes || []).length;
            lotesTemMais = !!data.tem_mais;
        } catch (e) {
            showToast('Erro ao carregar lotes: ' + e.message, 'error');
        } finally {
            // Limpa o flag ANTES de renderizar — assim o loader inline some.
            lotesCarregando = false;
            // Restaura lote armado vindo de prefs (se ainda não restaurado e
            // o lote ainda existir nos dados atuais). Roda 1× por boot via
            // flag _restaurouArmado — refresh ulterior do operador não
            // re-arma silenciosamente.
            _tentarRestaurarLoteArmado();
            renderLotes();
        }
    }

    // ==========================================================================
    // 6. CARGA DE DADOS — PEDIDOS (paginado por cabeçalho)
    // ==========================================================================
    async function carregarPedidos(reset) {
        if (pedidosCarregando) return;
        if (reset) {
            pedidosData = [];
            pedidosOffset = 0;
            pedidosTemMais = true;
            renderFiltrosAtivos();   // sincroniza chips quando o filtro muda
        }
        if (!pedidosTemMais) return;

        pedidosCarregando = true;
        // Render imediato: limpa o painel e mostra "Carregando..." na hora,
        // sem esperar o fetch terminar.
        if (reset) renderPedidos();
        try {
            const params = new URLSearchParams({
                limit: String(PAGE_SIZE),
                offset: String(pedidosOffset),
            });
            // Isolamento de pedido tem prioridade — manda só esse NUNOTA e ignora
            // outros filtros que poderiam encolher mais a busca (codprods, q, etc).
            if (pedidoIsolado) {
                params.set('nunota', String(pedidoIsolado));
                // Em isolamento NÃO mandamos desde_dias nem codprods — queremos achar
                // o pedido independentemente da janela de data.
            } else {
                if (textoFiltroPedidos) {
                    if (/^\d+$/.test(textoFiltroPedidos)) params.set('nunota', textoFiltroPedidos);
                    else                                  params.set('q', textoFiltroPedidos);
                }
                if (dataIniPedidos) params.set('data_ini', dataIniPedidos);
                if (dataFimPedidos) params.set('data_fim', dataFimPedidos);
                // Cross filter vindo do typeahead de Lotes: quando há FABRICANTE
                // selecionado, filtra os pedidos para mostrar apenas os que têm
                // produtos desse fabricante.
                if (fabricanteAtivo) params.set('fabricante', fabricanteAtivo);
                const uniaoPed = _uniaoFiltrosProdutos();
                if (uniaoPed.size > 0) {
                    params.set('codprods', [...uniaoPed].join(','));
                }
            }

            const r = await fetch(URLS.pedidos + '?' + params.toString(), {
                credentials: 'same-origin', cache: 'no-store',
            });
            const data = await r.json();
            if (!data.ok) throw new Error(data.error || 'Falha ao listar pedidos');

            pedidosData = pedidosData.concat(data.itens || []);
            pedidosOffset += (data.limit || PAGE_SIZE);    // avança em N cabeçalhos
            pedidosTemMais = !!data.tem_mais;
        } catch (e) {
            showToast('Erro ao carregar pedidos: ' + e.message, 'error');
        } finally {
            // Limpa o flag ANTES de renderizar — assim o loader inline some.
            pedidosCarregando = false;
            renderPedidos();
        }
    }

    function recarregarTudo() {
        carregarLotes(true);
        carregarPedidos(true);
    }

    // ==========================================================================
    // 7. RENDERIZAÇÃO — LOTES (cards 1-linha)
    // ==========================================================================
    /** Gera placeholder cards cinzas pra mostrar durante o fetch inicial.
     *  Usado nos dois painéis (lotes/pedidos). Reduz "tela parece travada"
     *  nos 1-2s do Oracle real respondendo. */
    function _renderSkeletonCards(n) {
        let html = '';
        for (let i = 0; i < n; i++) {
            html += `
                <div class="ras-skeleton-card" aria-hidden="true">
                    <div class="ras-skel-line ras-skel-w70"></div>
                    <div class="ras-skel-line ras-skel-w50"></div>
                    <div class="ras-skel-line ras-skel-w30"></div>
                </div>`;
        }
        return html;
    }

    /**
     * Soma a quantidade de falta agregada por CODPROD a partir de pedidosData
     * (linhas brutas do TGFITE). Considera só linhas SEM codagregacao_atual
     * (não-atribuídas). Usado pra detectar "encaixe exato" entre saldo de
     * lote e falta total de produto. Map<codprod:Number, kgFalta:Number>.
     */
    function _calcularFaltaPorCodprod() {
        const m = new Map();
        for (const it of pedidosData) {
            if (it.codagregacao_atual) continue;   // já atribuído — ignora
            const k = Number(it.codprod);
            const q = Number(it.qtd_pedida) || 0;
            m.set(k, (m.get(k) || 0) + q);
        }
        return m;
    }

    /**
     * Card de "avaria interna" (Opção B): linha não-vendável separada,
     * mostrada logo após o card vendável do mesmo lote quando
     * qtd_avaria_interna > 0. Estilo cinza tracejado — visualmente dá
     * pra ver "tem X kg deste lote reservados em avaria, fora do
     * vendável". Sem botão armar (não é vendável).
     */
    function _criarCardLoteAvariaInterna(l) {
        const card = document.createElement('div');
        card.className = 'rastreio-card card-lote compacto nao-vendavel card-lote-avaria-int';
        card.dataset.codprod      = l.codprod;
        card.dataset.codagregacao = l.codagregacao;
        // Lê do campo qtd_avaria_interna que vem da view ANDRE_IAGRO_SALDO_LOTE
        const qtdAvaria = Number(l.qtd_avaria_interna) || 0;
        card.innerHTML = `
            <span class="ras-row-check-wrap" aria-hidden="true">
                <span class="ras-row-check-box ras-row-check-box-disabled"></span>
            </span>
            <span class="col-prod" title="${escapeHtml(l.descrprod)} (avaria interna deste lote)">
                <strong>${escapeHtml(l.descrprod)}</strong>
                <span class="tag-avaria-int" title="Avaria interna reservada — não disponível para vincular em pedido">AVARIA INT.</span>
            </span>
            <span class="col-parc" title="${escapeHtml(l.nomeparc_origem || '')}">
                ${_avatarFornecedor(l.nomeparc_origem || '—')}
                <span class="parc-name-text">${escapeHtml(l.nomeparc_origem || '—')}</span>
            </span>
            <span class="col-lote" title="Lote ${escapeHtml(l.codagregacao)}">
                ${escapeHtml(l.codagregacao)}
            </span>
            <span class="col-data">${escapeHtml(l.dtneg_origem || '')}</span>
            <span class="col-qtd col-qtd-avaria">${fmtQtd(qtdAvaria)}</span>
        `;
        return card;
    }

    function renderLotes() {
        containerLotes.innerHTML = '';

        // Skeleton de carga inicial — quando carregando e ainda sem dados,
        // mostra placeholders cinzas em vez de tela vazia ou "Carregando..."
        // pelado. Reduz a sensação de tela travada nos ~1-2s do Oracle real.
        if (lotesData.length === 0 && lotesCarregando) {
            containerLotes.innerHTML = _renderSkeletonCards(4);
            return;
        }

        // Filtra lotes pela união (checksLotes + qualquer codprod marcado em
        // qualquer pedido). Garante que se você marca um produto num pedido,
        // os lotes daquele produto também aparecem destacados aqui.
        const visiveis = lotesData
            .filter(l => !temFiltroProdutos() || loteEstaCheckado(l.codprod));

        // Pré-calcula falta total por CODPROD (Mai/2026) — usado pra
        // detectar quando o saldo de UM lote casa exatamente com a falta
        // total daquele produto nos pedidos visíveis. Insight forte:
        // "este lote esgota essa demanda em 1 atribuição".
        const faltaPorCodprod = _calcularFaltaPorCodprod();

        // Quick stats — mostra só quando há ao menos 1 lote (não polui empty state)
        if (visiveis.length > 0) {
            const totalKg = visiveis.reduce((s, l) => s + (Number(l.qtd_disponivel) || 0), 0);
            const produtosUnicos = new Set(visiveis.map(l => l.codprod)).size;
            const fornecedoresUnicos = new Set(visiveis.map(l => l.nomeparc_origem || '—')).size;
            const stats = document.createElement('div');
            stats.className = 'ras-quickstats ras-quickstats-lotes';
            stats.innerHTML = `
                <span class="qs-num">${fmtInt(visiveis.length)}</span><span class="qs-lab">lotes</span>
                <span class="qs-sep">·</span>
                <span class="qs-num">${fmtInt(produtosUnicos)}</span><span class="qs-lab">produtos</span>
                <span class="qs-sep">·</span>
                <span class="qs-num">${fmtInt(fornecedoresUnicos)}</span><span class="qs-lab">fornecedores</span>
                <span class="qs-spacer"></span>
                <span class="qs-num qs-destaque">${fmtQtd(totalKg)}</span><span class="qs-lab">kg disponíveis</span>
            `;
            containerLotes.appendChild(stats);
        }

        if (visiveis.length === 0 && !lotesCarregando) {
            const temFiltro = (textoFiltroLotes || fabricanteAtivo
                || tipoLote !== 'todos' || temFiltroProdutos());
            const titulo = temFiltro
                ? 'Nenhum lote encontrado com os filtros atuais'
                : 'Sem lotes disponíveis no período';
            const msg = temFiltro
                ? 'Os filtros ativos não retornaram resultados. Limpe-os ou amplie o período pra ver mais lotes.'
                : 'Não há lotes com saldo no período selecionado. Tente aumentar o período de busca.';
            const acao = temFiltro
                ? '<button type="button" class="ras-empty-action" data-action="limpar-tudo">Limpar filtros</button>'
                : '';
            containerLotes.innerHTML = `
                <div class="ras-empty">
                    <div class="ras-empty-icone">📦</div>
                    <div class="ras-empty-titulo">${titulo}</div>
                    <div class="ras-empty-msg">${msg}</div>
                    ${acao}
                </div>`;
            return;
        }

        visiveis.forEach(l => {
            const status = l.status_linha;
            const qtd    = l.qtd_disponivel;

            const card = document.createElement('div');
            card.className = 'rastreio-card card-lote compacto';
            if (loteEstaCheckado(l.codprod)) card.classList.add('selected');
            if (loteArmado && loteArmado.codagregacao === l.codagregacao) {
                card.classList.add('lote-armado');
            }
            card.dataset.codprod      = l.codprod;
            card.dataset.codagregacao = l.codagregacao;

            // (Avaria interna agora aparece como CARD separado abaixo do vendável,
            // não mais como badge inline — vide _criarCardLoteAvariaInterna no fim.)

            const tagStatus = status === 'NAO_CLASSIFICAVEL'
                ? '<span class="tag-naoclass" title="Sem classificação confirmada — vendável como in natura (vem da TOP 13, não passou pela TOP 26)">N/C</span>'
                : '';

            // Fase 2.13 — alerta de lote envelhecido (DTNEG_ORIGEM > 60 dias)
            const idadeDias = _idadeDiasFromBR(l.dtneg_origem);
            const badgeIdade = idadeDias > DIAS_ALERTA_LOTE
                ? `<span class="badge-idade-lote" title="Lote com ${idadeDias} dias desde a entrada">⚠ ${idadeDias}d</span>`
                : '';
            if (idadeDias > DIAS_ALERTA_LOTE) card.classList.add('lote-envelhecido');

            // Badge "✨ encaixa" (Mai/2026): saldo do lote bate exatamente com
            // a falta total deste produto nos pedidos visíveis. Tolerância de
            // 0.001 (kg) para arredondamento. Só aparece quando há falta > 0
            // — sem demanda não há "encaixe" a destacar.
            const faltaCodprod = faltaPorCodprod.get(Number(l.codprod)) || 0;
            const encaixaExato = faltaCodprod > 0.001 &&
                                 Math.abs(faltaCodprod - Number(qtd)) < 0.001;
            const badgeEncaixa = encaixaExato
                ? `<span class="badge-encaixa-exato" title="Saldo deste lote (${fmtQtd(qtd)}) bate exatamente com a falta total deste produto nos pedidos visíveis. Atribuição em 1 passo, sem split.">✨ encaixa</span>`
                : '';
            if (encaixaExato) card.classList.add('lote-encaixa-exato');

            // Lotes listados aqui já são vendáveis (qtd_disponivel > 0).
            const podeArmar = Number(l.qtd_disponivel) > 0;
            // Ícones SVG inline — substituem os emojis 🔗 e 👁 e permitem
            // animação/cor consistentes via CSS quando a linha é selecionada.
            const armarBtn = podeArmar
                ? `<button class="btn-armar btn-acao-linha" title="Selecionar este lote para vincular num pedido (clique no produto-linha do pedido em seguida)" type="button">
                       <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                           <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                           <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
                       </svg>
                   </button>`
                : '';

            // Estado do checkbox de filtro cruzado dessa linha — só marca se
            // o usuário marcou diretamente no card de lote (checksLotes), não
            // por reflexo de marcação em pedidos.
            const cpFiltrado = checksLotes.has(Number(l.codprod));
            const checkAttr  = cpFiltrado ? 'checked' : '';

            // Layout em 1 linha: [check] avatar · produto · parceiro · lote · data · qtd · armar · olho
            card.innerHTML = `
                <label class="ras-row-check-wrap" title="Cruzar lotes e pedidos deste produto">
                    <input type="checkbox" class="ras-row-check" ${checkAttr}>
                    <span class="ras-row-check-box"></span>
                </label>
                <span class="col-prod"  title="${escapeHtml(l.descrprod)}">
                    <strong>${escapeHtml(l.descrprod)}</strong>${tagStatus}
                </span>
                <span class="col-parc"  title="${escapeHtml(l.nomeparc_origem || '')}">
                    ${_avatarFornecedor(l.nomeparc_origem || '—')}
                    <span class="parc-name-text">${escapeHtml(l.nomeparc_origem || '—')}</span>
                </span>
                <span class="col-lote"  title="Lote ${escapeHtml(l.codagregacao)}">
                    ${escapeHtml(l.codagregacao)}
                </span>
                <span class="col-data">${escapeHtml(l.dtneg_origem || '')} ${badgeIdade}</span>
                <span class="col-qtd">${fmtQtd(qtd)} ${badgeEncaixa}</span>
                ${armarBtn}
                <button class="btn-olho btn-acao-linha" title="Ver pedidos/vendas que usam este lote" type="button">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
                        <circle cx="12" cy="12" r="3"/>
                    </svg>
                </button>
            `;

            // Click no olho → modal com pedidos/vendas que usam este lote
            const olhoEl = card.querySelector('.btn-olho');
            if (olhoEl) {
                olhoEl.addEventListener('click', (e) => {
                    e.stopPropagation();
                    abrirModalVinculosDeLote(l);
                });
            }

            // Click no botão armar — toggle: arma o lote, ou desarma se já era ele
            const armarEl = card.querySelector('.btn-armar');
            if (armarEl) {
                armarEl.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (loteArmado && loteArmado.codagregacao === l.codagregacao) {
                        desarmarLote();
                    } else {
                        armarLote(l);
                    }
                });
            }

            // Checkbox dispara o filtro cruzado — independente de selecionar a linha
            const checkEl = card.querySelector('.ras-row-check');
            if (checkEl) {
                checkEl.addEventListener('click', (e) => e.stopPropagation());
                checkEl.addEventListener('change', (e) => {
                    toggleCheckLote(l.codprod, e.target.checked);
                });
            }
            card.querySelector('.ras-row-check-wrap')
                ?.addEventListener('click', (e) => e.stopPropagation());
            // Click na linha (fora do check e dos botões) → SELECIONA a linha
            // (revela os botões olho/armar). Click novamente desmarca.
            card.addEventListener('click', (e) => {
                // Ignora cliques em botões internos e no checkbox (já tratados)
                if (e.target.closest('.btn-armar') ||
                    e.target.closest('.btn-olho') ||
                    e.target.closest('.ras-row-check-wrap')) return;
                _selecionarLinha(card, '#lotesContainer');
            });

            containerLotes.appendChild(card);

            // Card adicional de avaria interna (Opção B, Mai/2026): linha
            // não-vendável separada logo abaixo do vendável. Antes era badge
            // inline ▼Xkg na col-qtd; mudou pra linha dedicada que dá
            // visibilidade clara de quanto deste lote está reservado em
            // avaria, fora do saldo vendável.
            if (l.qtd_avaria_interna && Number(l.qtd_avaria_interna) > 0) {
                containerLotes.appendChild(_criarCardLoteAvariaInterna(l));
            }
        });

        if (lotesCarregando) {
            const loader = document.createElement('div');
            loader.className = 'inline-loader';
            loader.textContent = 'Carregando...';
            containerLotes.appendChild(loader);
        }
    }

    // ==========================================================================
    // 8. RENDERIZAÇÃO — PEDIDOS (agrupado por NUNOTA, itens agregados por CODPROD)
    // ==========================================================================
    /**
     * Recebe linhas brutas do TGFITE e devolve uma estrutura agrupada:
     *   [{ nunota, nomeparc, dtneg, produtos: [{ codprod, descrprod,
     *      qtd_total, qtd_atribuida, qtd_falta, sequencias_pendentes: [...] }] }]
     */
    function agruparPedidos(linhas) {
        const porNunota = new Map();
        for (const it of linhas) {
            const k = it.nunota;
            if (!porNunota.has(k)) {
                porNunota.set(k, {
                    nunota:   it.nunota,
                    codemp:   it.codemp,
                    codparc:  it.codparc,
                    nomeparc: it.nomeparc,
                    dtneg:    it.dtneg,
                    _produtos: new Map(),
                });
            }
            const ped = porNunota.get(k);
            const pk = it.codprod;
            if (!ped._produtos.has(pk)) {
                ped._produtos.set(pk, {
                    codprod:               it.codprod,
                    descrprod:             it.descrprod,
                    qtd_total:             0,
                    qtd_atribuida:         0,
                    qtd_falta:             0,
                    linhas_pendentes:      [],   // {sequencia, qtd}
                    lotes_vinculados:      [],   // {codagregacao, qtd, sequencia}
                });
            }
            const prod = ped._produtos.get(pk);
            const q = Number(it.qtd_pedida) || 0;
            prod.qtd_total += q;
            if (it.codagregacao_atual) {
                prod.qtd_atribuida += q;
                prod.lotes_vinculados.push({
                    codagregacao:  it.codagregacao_atual,
                    qtd:           q,
                    sequencia:     it.sequencia,
                    descrprod:     it.descrprod,        // produto da linha do pedido
                    lote_nunota:   it.lote_nunota,      // NUNOTA da TOP 11 que originou o lote
                    lote_dtneg:    it.lote_dtneg,
                    lote_codparc:  it.lote_codparc,
                    lote_nomeparc: it.lote_nomeparc,
                });
            } else {
                prod.qtd_falta += q;
                prod.linhas_pendentes.push({ sequencia: it.sequencia, qtd: q });
            }
        }
        // Materializa Maps em arrays
        return Array.from(porNunota.values()).map(p => ({
            ...p, produtos: Array.from(p._produtos.values()),
        }));
    }

    function pedidoCasaFiltro(pedido) {
        if (!temFiltroProdutos()) return true;
        // Pedido aparece se: (a) algum produto seu está no checksLotes
        // (cross-filter vindo dos lotes), OU (b) algum produto está marcado
        // EM ALGUM PEDIDO (igual em qualquer pedido — basta ter intersecção).
        const uniao = _uniaoFiltrosProdutos();
        return pedido.produtos.some(p => uniao.has(Number(p.codprod)));
    }

    function renderPedidos() {
        containerPedidos.innerHTML = '';

        // Skeleton de carga inicial — placeholders cinzas em vez de tela vazia
        if (pedidosData.length === 0 && pedidosCarregando) {
            containerPedidos.innerHTML = _renderSkeletonCards(3);
            return;
        }

        let pedidos = agruparPedidos(pedidosData).filter(pedidoCasaFiltro);

        // Fase 4.6 — toggle "só pendentes": esconde produtos já 100% atribuídos
        // e remove pedidos cujos produtos visíveis ficaram todos completos.
        if (somentePendentes) {
            pedidos = pedidos
                .map(p => ({ ...p, produtos: p.produtos.filter(pr => pr.qtd_falta > 0.000001) }))
                .filter(p => p.produtos.length > 0);
        }

        // Quick stats do painel direito — sempre acima da lista quando há pedidos
        if (pedidos.length > 0) {
            let qtdTotal = 0, qtdAtribuida = 0, itensPendentes = 0, kgFaltaTotal = 0;
            pedidos.forEach(p => {
                p.produtos.forEach(pr => {
                    qtdTotal     += Number(pr.qtd_total) || 0;
                    qtdAtribuida += Number(pr.qtd_atribuida) || 0;
                    if (pr.qtd_falta > 0.000001) {
                        itensPendentes++;
                        kgFaltaTotal += Number(pr.qtd_falta) || 0;
                    }
                });
            });
            const pct = qtdTotal > 0 ? Math.round((qtdAtribuida / qtdTotal) * 100) : 0;
            const stats = document.createElement('div');
            stats.className = 'ras-quickstats ras-quickstats-pedidos';
            // Mostra `qtd a atribuir` em destaque — operador compara visualmente
            // com `kg disponíveis` da quickstats de lotes (lado esquerdo) pra ver
            // se a oferta cobre a demanda. Cor avermelhada (qs-falta) reforça
            // que é "ainda falta".
            stats.innerHTML = `
                <span class="qs-num">${fmtInt(pedidos.length)}</span><span class="qs-lab">pedidos</span>
                <span class="qs-sep">·</span>
                <span class="qs-num qs-falta">${fmtInt(itensPendentes)}</span><span class="qs-lab">pendentes</span>
                <span class="qs-sep">·</span>
                <span class="qs-num qs-destaque qs-falta">${fmtQtd(kgFaltaTotal)}</span><span class="qs-lab">kg a atribuir</span>
                <span class="qs-spacer"></span>
                <span class="ras-pct-mini">
                    ${_renderProgressBar(qtdAtribuida, qtdTotal)}
                    <strong class="qs-pct">${pct}%</strong>
                </span>
            `;
            containerPedidos.appendChild(stats);
        }

        // Default colapsado — todo pedido NOVO entra como colapsado.
        // pedidosJaVistos garante que isso só acontece na primeira renderização
        // de cada NUNOTA (não sobrescreve estado escolhido pelo usuário).
        pedidos.forEach(p => {
            const nun = Number(p.nunota);
            if (!pedidosJaVistos.has(nun)) {
                pedidosJaVistos.add(nun);
                pedidosColapsados.add(nun);
            }
        });

        if (pedidos.length === 0 && !pedidosCarregando) {
            const temFiltro = textoFiltroPedidos || pedidoIsolado != null
                            || dataIniPedidos || dataFimPedidos || temFiltroProdutos();
            let titulo, msg, icone, acao = '';
            if (somentePendentes) {
                titulo = '✓ Tudo vinculado!';
                icone  = '🎉';
                msg    = 'Não há itens pendentes nos pedidos visíveis. Para ver pedidos já vinculados, desligue <strong>SÓ PENDENTES</strong>.';
                acao   = '<button type="button" class="ras-empty-action" data-action="desligar-pendentes">Mostrar pedidos vinculados</button>';
            } else if (temFiltro) {
                titulo = 'Nenhum pedido encontrado com os filtros atuais';
                icone  = '🔍';
                msg    = 'Os filtros ativos não retornaram pedidos. Limpe-os ou amplie o período pra ver mais resultados.';
                acao   = '<button type="button" class="ras-empty-action" data-action="limpar-tudo">Limpar filtros</button>';
            } else {
                titulo = 'Sem pedidos em aberto no período';
                icone  = '📋';
                msg    = 'Não há pedidos TOP 34 (em aberto) no período. Tente aumentar o período de busca acima.';
            }
            containerPedidos.innerHTML = `
                <div class="ras-empty">
                    <div class="ras-empty-icone">${icone}</div>
                    <div class="ras-empty-titulo">${titulo}</div>
                    <div class="ras-empty-msg">${msg}</div>
                    ${acao}
                </div>`;
            return;
        }

        // Agrupador grosso (PARCEIRO ou PRODUTO) — header mais alto
        const grupos = {};
        if (agrupamentoAtual === 'parceiro') {
            pedidos.forEach(p => {
                const key = p.nomeparc || '—';
                (grupos[key] = grupos[key] || []).push(p);
            });
        } else {
            // por produto: cada produto vira um grupo, e cada pedido aparece dentro
            pedidos.forEach(p => {
                p.produtos.forEach(pr => {
                    if (temFiltroProdutos() && !_uniaoFiltrosProdutos().has(Number(pr.codprod))) return;
                    const key = pr.descrprod || '—';
                    (grupos[key] = grupos[key] || []).push({ pedido: p, produto: pr });
                });
            });
        }

        // POR PRODUTO: novos grupos vêm colapsados por padrão. gruposProdutoJaVistos
        // garante que isso só ocorre na primeira vez que o nome do produto aparece —
        // nas renderizações seguintes o estado escolhido pelo usuário é preservado.
        if (agrupamentoAtual === 'produto') {
            Object.keys(grupos).forEach(nomeGrupo => {
                if (!gruposProdutoJaVistos.has(nomeGrupo)) {
                    gruposProdutoJaVistos.add(nomeGrupo);
                    gruposProdutoColapsados.add(nomeGrupo);
                }
            });
        }

        Object.keys(grupos).sort().forEach(nomeGrupo => {
            if (agrupamentoAtual === 'parceiro') {
                // POR PARCEIRO: sem header de grupo (cada pedido tem o seu próprio
                // pedido-bloco-header com avatar+nome do parceiro). Ordena os
                // pedidos do grupo por data ASC (mais antigo primeiro), depois
                // parceiro ASC — conforme regra explícita do usuário.
                grupos[nomeGrupo]
                    .slice()
                    .sort(_comparePedidosPorParceiro)
                    .forEach(p => renderPedidoBloco(p));
            } else {
                // POR PRODUTO: header rico do produto (mesmo estilo do header de
                // parceiro) + linhas compactas de pedido dentro. Ordena os items
                // por data DESC, depois parceiro ASC. Se o grupo está colapsado,
                // só renderiza o header (linhas internas escondidas).
                const items = grupos[nomeGrupo].slice().sort((a, b) =>
                    _comparePedidosPadrao(a.pedido, b.pedido)
                );
                containerPedidos.appendChild(_criarHeaderGrupoProduto(nomeGrupo, items));
                if (gruposProdutoColapsados.has(nomeGrupo)) return;
                items.forEach(({ pedido, produto }) => {
                    containerPedidos.appendChild(
                        renderLinhaCompactaPedidoProduto(pedido, produto)
                    );
                });
            }
        });

        if (pedidosCarregando) {
            const loader = document.createElement('div');
            loader.className = 'inline-loader';
            loader.textContent = 'Carregando...';
            containerPedidos.appendChild(loader);
        }
    }

    function _criarPedidoHeader(pedido, sub) {
        const header = document.createElement('div');
        header.className = 'pedido-bloco-header clicavel' + (sub ? ' sub' : '');
        const codprodsPedido = pedido.produtos.map(p => Number(p.codprod));
        // Calcula totais agregados do pedido (soma de todos os produtos)
        let qtdTotal = 0, qtdAtribuida = 0, prodCompletos = 0;
        pedido.produtos.forEach(pr => {
            qtdTotal     += Number(pr.qtd_total) || 0;
            qtdAtribuida += Number(pr.qtd_atribuida) || 0;
            if (pr.qtd_falta <= 0.000001) prodCompletos++;
        });
        const pct = qtdTotal > 0 ? Math.round((qtdAtribuida / qtdTotal) * 100) : 0;
        const completo = prodCompletos === pedido.produtos.length;
        if (completo) header.classList.add('pedido-completo');

        // Estado do colapso — ao clicar no nome, esconde/mostra os produtos
        const colapsado = pedidosColapsados.has(Number(pedido.nunota));
        if (colapsado) header.classList.add('colapsado');

        // Estado do checkbox do pedido — count quantos produtos estão marcados
        // ESPECIFICAMENTE neste pedido (Map<nunota, Set<codprod>>). Não cascata
        // para outros pedidos.
        const totalProdutos    = codprodsPedido.length;
        const cpsDoPedido      = checksPorPedido.get(Number(pedido.nunota)) || new Set();
        const filtradosNoSet   = codprodsPedido.filter(cp => cpsDoPedido.has(Number(cp))).length;
        let estadoCheck = 'none';
        if (filtradosNoSet === totalProdutos && totalProdutos > 0) estadoCheck = 'all';
        else if (filtradosNoSet > 0) estadoCheck = 'some';
        const checkAttr = estadoCheck === 'all' ? 'checked' : '';

        const checkOk = completo
            ? '<span class="pb-check" title="Todos os produtos vinculados">✓</span>'
            : '';

        // Layout: [check] [chevron] avatar  parceiro · data ··· progresso · NUNOTA
        // O check fica antes do chevron para alinhar com os checks das produto-linhas.
        header.innerHTML = `
            <label class="ras-row-check-wrap pb-check-wrap" title="Selecionar todos os produtos deste pedido">
                <input type="checkbox" class="ras-row-check pb-check-input" ${checkAttr}>
                <span class="ras-row-check-box"></span>
            </label>
            <button type="button" class="pb-chevron" aria-label="${colapsado ? 'Expandir' : 'Colapsar'} produtos" title="${colapsado ? 'Expandir' : 'Colapsar'} produtos do pedido">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <polyline points="6 9 12 15 18 9"/>
                </svg>
            </button>
            ${_avatarFornecedor(pedido.nomeparc || '—')}
            <span class="pb-parc">${escapeHtml(pedido.nomeparc || '—')}</span>
            <span class="pb-data">${escapeHtml(pedido.dtneg || '')}</span>
            <span class="pb-spacer"></span>
            <span class="pb-progresso" title="${pct}% vinculado (${fmtInt(prodCompletos)}/${fmtInt(pedido.produtos.length)} produtos completos)">
                ${_renderProgressBar(qtdAtribuida, qtdTotal)}
                <strong>${pct}%</strong>
            </span>
            <span class="pb-nunota">Pedido ${escapeHtml(pedido.nunota)}</span>
            ${checkOk}
        `;

        // Indeterminate visualmente — após inserir no DOM, marca a propriedade
        // (não dá pra fazer via atributo HTML; é só JS).
        const inputCheck = header.querySelector('.pb-check-input');
        if (inputCheck) inputCheck.indeterminate = (estadoCheck === 'some');

        // ----- Listeners -----
        // (a) Checkbox do header: marca/desmarca TODOS os produtos APENAS DESTE
        // pedido (não afeta outros pedidos com os mesmos codprods, conforme
        // pedido do usuário). Atua em checksPorPedido[nunota].
        if (inputCheck) {
            inputCheck.addEventListener('click', (e) => e.stopPropagation());
            inputCheck.addEventListener('change', (e) => {
                const marcar = e.target.checked;
                const nu = Number(pedido.nunota);
                if (marcar) {
                    const set = new Set(codprodsPedido);
                    checksPorPedido.set(nu, set);
                    pedidoIsolado = null;
                } else {
                    checksPorPedido.delete(nu);
                }
                carregarLotes(true);
                carregarPedidos(true);
            });
        }
        header.querySelector('.pb-check-wrap')
              ?.addEventListener('click', (e) => e.stopPropagation());

        // (b) Click no header (no nome do parceiro / chevron / espaço) → expand/collapse
        header.addEventListener('click', (e) => {
            // Click direto no checkbox/wrap já foi tratado (stopPropagation)
            if (e.target.closest('.pb-check-wrap')) return;
            const nun = Number(pedido.nunota);
            if (pedidosColapsados.has(nun)) pedidosColapsados.delete(nun);
            else                            pedidosColapsados.add(nun);
            renderPedidos();
        });
        return header;
    }

    function renderPedidoBloco(pedido) {
        containerPedidos.appendChild(_criarPedidoHeader(pedido, false));
        // Pedido colapsado → esconde produtos (header continua mostrando o resumo)
        if (pedidosColapsados.has(Number(pedido.nunota))) return;
        // Quando há filtro de produtos ativo, mostra apenas os produtos cuja
        // intersecção bate (qualquer eixo: lotes ou pedidos).
        const uniao = _uniaoFiltrosProdutos();
        const produtos = temFiltroProdutos()
            ? pedido.produtos.filter(p => uniao.has(Number(p.codprod)))
            : pedido.produtos;
        produtos.forEach(prod => {
            containerPedidos.appendChild(renderProdutoLinha(pedido, prod));
        });
    }

    function renderProdutoBlocoSolitario(pedido, prod) {
        // [LEGADO] não é mais usado pelo modo POR PRODUTO — substituído por
        // _criarHeaderGrupoProduto + renderLinhaCompactaPedidoProduto.
        // Mantido apenas como fallback caso algum chamador externo use.
        containerPedidos.appendChild(_criarPedidoHeader(pedido, true));
        containerPedidos.appendChild(renderProdutoLinha(pedido, prod));
    }

    /** Cria o cabeçalho de grupo no modo POR PRODUTO. Mesmo estilo visual do
     *  pedido-bloco-header mas com NOME do PRODUTO e contagem de pedidos.
     *  Click no header alterna expand/collapse do grupo (gruposProdutoColapsados).
     *  `items` é o array já agrupado (`{pedido, produto}`). */
    function _criarHeaderGrupoProduto(nomeProduto, items) {
        const header = document.createElement('div');
        header.className = 'pedido-bloco-header tipo-produto';
        const colapsado = gruposProdutoColapsados.has(nomeProduto);
        if (colapsado) header.classList.add('colapsado');
        // Soma agregada de todos os pedidos com esse produto
        let qtdTotal = 0, qtdAtribuida = 0;
        const pedidosUnicos = new Set();
        items.forEach(({ pedido, produto }) => {
            pedidosUnicos.add(pedido.nunota);
            qtdTotal     += Number(produto.qtd_total) || 0;
            qtdAtribuida += Number(produto.qtd_atribuida) || 0;
        });
        const numPedidos = pedidosUnicos.size;
        const pct = qtdTotal > 0 ? Math.round((qtdAtribuida / qtdTotal) * 100) : 0;
        const completo = pct >= 100 && qtdTotal > 0;
        if (completo) header.classList.add('pedido-completo');

        // Codprod do grupo (todos os items têm o mesmo). Usado pelo checkbox
        // do header — marca/desmarca o filtro cruzado por aquele produto via
        // checksLotes (afeta lotes globalmente + reflete em todos os pedidos
        // que contêm o produto).
        const codprodGrupo = items[0]?.produto?.codprod;
        const checkAttr    = (codprodGrupo != null && checksLotes.has(Number(codprodGrupo)))
                             ? 'checked' : '';

        header.innerHTML = `
            <label class="ras-row-check-wrap pb-check-wrap" title="Filtrar cruzado por este produto">
                <input type="checkbox" class="ras-row-check" ${checkAttr}>
                <span class="ras-row-check-box"></span>
            </label>
            <span class="grupo-chevron" aria-label="${colapsado ? 'Expandir' : 'Recolher'} grupo">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <polyline points="6 9 12 15 18 9"/>
                </svg>
            </span>
            ${_avatarFornecedor(nomeProduto)}
            <span class="pb-parc">${escapeHtml(nomeProduto)}</span>
            <span class="pb-spacer"></span>
            <span class="pb-progresso" title="${pct}% vinculado · ${fmtQtd(qtdAtribuida)} de ${fmtQtd(qtdTotal)}">
                ${_renderProgressBar(qtdAtribuida, qtdTotal)}
                <strong>${pct}%</strong>
            </span>
            <span class="pb-nunota">${fmtInt(numPedidos)} ${numPedidos === 1 ? 'pedido' : 'pedidos'}</span>
        `;

        // Checkbox: filtra cruzado por este produto (atua em checksLotes).
        // stopPropagation no wrap impede que o click chegue ao header.
        const inputCheck = header.querySelector('.ras-row-check');
        if (inputCheck && codprodGrupo != null) {
            inputCheck.addEventListener('click', (e) => e.stopPropagation());
            inputCheck.addEventListener('change', (e) => {
                toggleCheckLote(codprodGrupo, e.target.checked);
            });
        }
        header.querySelector('.pb-check-wrap')
              ?.addEventListener('click', (e) => e.stopPropagation());

        // Click no header (fora do checkbox) → toggle do colapso + re-render
        header.addEventListener('click', (e) => {
            if (e.target.closest('.pb-check-wrap')) return;
            if (gruposProdutoColapsados.has(nomeProduto))
                gruposProdutoColapsados.delete(nomeProduto);
            else
                gruposProdutoColapsados.add(nomeProduto);
            renderPedidos();
        });
        return header;
    }

    /** Linha compacta de pedido dentro do grupo POR PRODUTO. Mostra o parceiro
     *  com avatar (porque o produto já é o agrupador) + data + progresso + qtd
     *  faltante + NUNOTA. Mesma lógica de seleção/check/lote-armado da
     *  produto-linha — só o layout muda. */
    function renderLinhaCompactaPedidoProduto(pedido, prod) {
        const completo = prod.qtd_falta <= 0.000001;
        const selected = produtoLinhaEstaCheckada(prod.codprod, pedido.nunota);
        const ehAlvo   = !!loteArmado &&
                         Number(loteArmado.codprod) === Number(prod.codprod) &&
                         !completo;

        const linha = document.createElement('div');
        linha.className = 'linha-pedido-compacta clicavel';
        if (completo) linha.classList.add('completo');
        if (selected) linha.classList.add('selected');
        if (ehAlvo)   linha.classList.add('alvo-armado');
        linha.dataset.nunota  = pedido.nunota;
        linha.dataset.codprod = prod.codprod;

        const checkAttr = selected ? 'checked' : '';
        const tagFalta = completo
            ? '<span class="tag-atribuido-mini">✓ OK</span>'
            : `<span class="tag-falta">falta ${fmtInt(prod.qtd_falta)}</span>`;

        const temVinculos = prod.lotes_vinculados && prod.lotes_vinculados.length > 0;
        const olhoBtn = temVinculos
            ? `<button class="btn-olho btn-acao-linha" title="Ver lotes vinculados" type="button">
                   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                       <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
                       <circle cx="12" cy="12" r="3"/>
                   </svg>
               </button>`
            : '';
        const setaAlvo = ehAlvo
            ? '<span class="ras-arrow-alvo" title="Solte aqui para vincular">←</span>'
            : '';

        linha.innerHTML = `
            <label class="ras-row-check-wrap" title="Cruzar este produto neste pedido">
                <input type="checkbox" class="ras-row-check" ${checkAttr}>
                <span class="ras-row-check-box"></span>
            </label>
            ${_avatarFornecedor(pedido.nomeparc || '—')}
            <span class="lpc-parc" title="${escapeHtml(pedido.nomeparc || '—')}">
                ${setaAlvo}${escapeHtml(pedido.nomeparc || '—')}
            </span>
            <span class="lpc-data">${escapeHtml(pedido.dtneg || '')}</span>
            <span class="lpc-spacer"></span>
            <span class="lpc-progresso" title="${fmtInt(prod.qtd_atribuida)} de ${fmtInt(prod.qtd_total)} vinculado">
                ${_renderProgressBar(prod.qtd_atribuida, prod.qtd_total)}
                <span class="lpc-progresso-num">
                    <span class="qtd-vinculada">${fmtInt(prod.qtd_atribuida)}</span>/<span class="qtd-total">${fmtInt(prod.qtd_total)}</span>
                </span>
            </span>
            <span class="lpc-tag">${tagFalta}</span>
            ${olhoBtn}
            <span class="lpc-nunota">Pedido ${escapeHtml(pedido.nunota)}</span>
        `;

        // Listeners (mesmos da produto-linha — replicados pra linha compacta) -----
        const olhoEl = linha.querySelector('.btn-olho');
        if (olhoEl) {
            olhoEl.addEventListener('click', (e) => {
                e.stopPropagation();
                abrirModalVinculosDeProduto(pedido, prod);
            });
        }
        const checkEl = linha.querySelector('.ras-row-check');
        if (checkEl) {
            checkEl.addEventListener('click', (e) => e.stopPropagation());
            checkEl.addEventListener('change', (e) => {
                toggleCheckProdutoPedido(prod.codprod, pedido.nunota, e.target.checked);
            });
        }
        linha.querySelector('.ras-row-check-wrap')
             ?.addEventListener('click', (e) => e.stopPropagation());

        // Click na linha:
        // - Se há lote armado compatível e tem falta → modal de transferência
        // - Senão → seleciona a linha (revela botão olho)
        linha.addEventListener('click', (e) => {
            if (e.target.closest('.btn-olho') ||
                e.target.closest('.ras-row-check-wrap')) return;
            if (loteArmado && !completo &&
                Number(loteArmado.codprod) === Number(prod.codprod)) {
                if (!prod.linhas_pendentes.length) {
                    showToast('Não há item pendente nesse produto do pedido.', 'warning');
                    return;
                }
                abrirModalTransferencia(loteArmado, pedido, prod);
                return;
            }
            if (loteArmado && Number(loteArmado.codprod) !== Number(prod.codprod)) {
                showToast(
                    `Lote armado é de "${loteArmado.descrprod}". Esta linha é de "${prod.descrprod}".`,
                    'warning'
                );
                return;
            }
            _selecionarLinha(linha, '#pedidosContainer');
        });
        return linha;
    }

    function renderProdutoLinha(pedido, prod) {
        const completo = prod.qtd_falta <= 0.000001;
        // "selected" só fica marcado se ESTE produto-linha (pedido+codprod)
        // foi marcado especificamente. Outros pedidos com mesmo codprod NÃO
        // ficam selected, conforme pedido do usuário.
        const selected = produtoLinhaEstaCheckada(prod.codprod, pedido.nunota);
        const faded    = temFiltroProdutos() &&
                         !_uniaoFiltrosProdutos().has(Number(prod.codprod));
        // Quando há lote armado e esta linha tem o mesmo CODPROD, ela vira "alvo"
        const ehAlvo = !!loteArmado &&
                       Number(loteArmado.codprod) === Number(prod.codprod) &&
                       !completo;

        const linha = document.createElement('div');
        linha.className = 'rastreio-card card-pedido compacto produto-linha clicavel';
        if (completo) linha.classList.add('completo');
        if (faded)    linha.classList.add('faded');
        if (selected) linha.classList.add('selected');
        if (ehAlvo)   linha.classList.add('alvo-armado');

        linha.dataset.nunota  = pedido.nunota;
        linha.dataset.codprod = prod.codprod;

        const tagFalta = completo
            ? '<span class="tag-atribuido-mini">✓ OK</span>'
            : `<span class="tag-falta">falta ${fmtInt(prod.qtd_falta)}</span>`;

        const temVinculos = prod.lotes_vinculados && prod.lotes_vinculados.length > 0;
        const olhoBtn = temVinculos
            ? `<button class="btn-olho btn-acao-linha" title="Ver lotes vinculados" type="button">
                   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                       <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
                       <circle cx="12" cy="12" r="3"/>
                   </svg>
               </button>`
            : '';

        // Indicador de "linha-alvo" quando há lote armado compatível
        const setaAlvo = ehAlvo
            ? '<span class="ras-arrow-alvo" title="Solte aqui para vincular o lote armado">←</span>'
            : '';

        // Estado do checkbox dessa linha — específico ao pedido (não cruza)
        const cpFiltrado = produtoLinhaEstaCheckada(prod.codprod, pedido.nunota);
        const checkAttr  = cpFiltrado ? 'checked' : '';

        linha.innerHTML = `
            <label class="ras-row-check-wrap" title="Cruzar lotes deste produto">
                <input type="checkbox" class="ras-row-check" ${checkAttr}>
                <span class="ras-row-check-box"></span>
            </label>
            <span class="col-prod" title="${escapeHtml(prod.descrprod)}">
                ${setaAlvo}${escapeHtml(prod.descrprod)}
            </span>
            <span class="col-progresso" title="${fmtInt(prod.qtd_atribuida)} de ${fmtInt(prod.qtd_total)} vinculado">
                ${_renderProgressBar(prod.qtd_atribuida, prod.qtd_total)}
                <span class="col-progresso-num">
                    <span class="qtd-vinculada">${fmtInt(prod.qtd_atribuida)}</span>/<span class="qtd-total">${fmtInt(prod.qtd_total)}</span>
                </span>
            </span>
            <span class="col-tag">${tagFalta}${olhoBtn}</span>
        `;

        // Click no olho → modal com lotes vinculados (sem fetch — usa o que já temos)
        const olhoEl = linha.querySelector('.btn-olho');
        if (olhoEl) {
            olhoEl.addEventListener('click', (e) => {
                e.stopPropagation();
                abrirModalVinculosDeProduto(pedido, prod);
            });
        }

        // Checkbox: opt-in explícito do filtro cruzado, por PEDIDO+CODPROD.
        // Marcar este produto NÃO afeta produtos iguais em outros pedidos.
        const checkEl = linha.querySelector('.ras-row-check');
        if (checkEl) {
            checkEl.addEventListener('click', (e) => e.stopPropagation());
            checkEl.addEventListener('change', (e) => {
                toggleCheckProdutoPedido(prod.codprod, pedido.nunota, e.target.checked);
            });
        }
        linha.querySelector('.ras-row-check-wrap')
             ?.addEventListener('click', (e) => e.stopPropagation());

        // Click na linha (fora do checkbox e do olho):
        // - Se há lote armado compatível e tem falta → modal de transferência
        // - Lote armado incompatível → toast
        // - Sem lote armado → SELECIONA a linha (revela botão olho)
        linha.addEventListener('click', (e) => {
            if (e.target.closest('.btn-olho') ||
                e.target.closest('.ras-row-check-wrap')) return;
            if (loteArmado && !completo &&
                Number(loteArmado.codprod) === Number(prod.codprod)) {
                if (!prod.linhas_pendentes.length) {
                    showToast('Não há item pendente nesse produto do pedido.', 'warning');
                    return;
                }
                abrirModalTransferencia(loteArmado, pedido, prod);
                return;
            }
            if (loteArmado && Number(loteArmado.codprod) !== Number(prod.codprod)) {
                showToast(
                    `Lote armado é de "${loteArmado.descrprod}". Esta linha é de "${prod.descrprod}".`,
                    'warning'
                );
                return;
            }
            // Sem lote armado: seleciona a linha pra revelar botões de ação
            _selecionarLinha(linha, '#pedidosContainer');
        });
        return linha;
    }

    /** Seleciona uma linha (lote ou produto-linha) no painel — desmarca outras
     *  do mesmo painel e marca esta. Click novamente desmarca (toggle).
     *  A classe `.linha-ativa` é o gatilho CSS que revela os botões de ação. */
    function _selecionarLinha(elementoLinha, seletorContainer) {
        const ja = elementoLinha.classList.contains('linha-ativa');
        const container = document.querySelector(seletorContainer);
        if (container) {
            container.querySelectorAll('.linha-ativa')
                     .forEach(el => el.classList.remove('linha-ativa'));
        }
        if (!ja) elementoLinha.classList.add('linha-ativa');
    }

    // ==========================================================================
    // 9. ARMAR / DESARMAR LOTE (click-to-select)
    // ==========================================================================
    /** Arma o lote para a próxima vinculação. Mostra a barra fixa, destaca o
     *  card do lote e marca todas as produto-linhas com o mesmo CODPROD como
     *  "alvo válido". Se outro lote já estava armado, troca pelo novo. */
    function armarLote(lote) {
        loteArmado = lote;
        atualizarBarArmado();
        _salvarPrefs();
        // Re-render para refletir .lote-armado nos cards e .alvo-armado nas linhas
        renderLotes();
        renderPedidos();
    }

    function desarmarLote() {
        if (!loteArmado) return;
        loteArmado = null;
        atualizarBarArmado();
        _salvarPrefs();
        renderLotes();
        renderPedidos();
    }

    function atualizarBarArmado() {
        if (!barArmado) return;
        if (loteArmado) {
            // Inclui avatar + produto + parceiro origem para escaneabilidade
            if (barArmadoLote) {
                barArmadoLote.innerHTML =
                    `${_avatarFornecedor(loteArmado.nomeparc_origem || '—')}` +
                    `<span class="bar-armado-prod">${escapeHtml(loteArmado.descrprod)}</span>` +
                    `<span class="bar-armado-codigo">${escapeHtml(loteArmado.codagregacao)}</span>`;
            }
            if (barArmadoDisp) {
                barArmadoDisp.textContent = fmtQtd(loteArmado.qtd_disponivel);
            }
            barArmado.classList.remove('hidden');
        } else {
            barArmado.classList.add('hidden');
        }
    }

    // ==========================================================================
    // 10. MODAL DE TRANSFERÊNCIA
    // ==========================================================================
    function abrirModalTransferencia(lote, pedido, prod) {
        transferenciaContexto = { lote, pedido, prod };

        const dispLote   = Number(lote.qtd_disponivel) || 0;
        const faltaProd  = Number(prod.qtd_falta)      || 0;   // agregado do produto no pedido
        // Sugestão automática:
        //  - se o lote tem ≥ que falta no pedido → preenche com a falta total
        //  - se não, preenche com o que o lote tem disponível
        const sugerida   = Math.min(dispLote, faltaProd);

        transferLoteName.textContent =
            `${lote.descrprod} — Lote ${lote.codagregacao}`;
        transferDestino.textContent =
            `Pedido ${pedido.nunota} — ${pedido.nomeparc || ''}`;
        maxLoteSpan.textContent   = fmtQtd(dispLote);
        maxPedidoSpan.textContent = fmtQtd(faltaProd);
        inputQtdTransfer.value    = sugerida.toFixed(2);
        // Trava: nunca aceita vincular mais do que o pedido pediu
        inputQtdTransfer.max      = faltaProd;
        inputQtdTransfer.min      = 0.01;

        modalTransfer.classList.remove('hidden');
        modalTransfer.style.display = 'flex';
        setTimeout(() => { inputQtdTransfer.focus(); inputQtdTransfer.select(); }, 50);
    }

    function fecharModalTransferencia() {
        modalTransfer.classList.add('hidden');
        modalTransfer.style.display = 'none';
        transferenciaContexto = null;
    }

    async function confirmarTransferencia() {
        if (!transferenciaContexto) return;
        const { lote, pedido, prod } = transferenciaContexto;

        let qtdRestante = parseFloat(inputQtdTransfer.value);
        if (!qtdRestante || qtdRestante <= 0) {
            showToast('Informe uma quantidade válida.', 'warning');
            inputQtdTransfer.focus();
            return;
        }
        const dispLote  = Number(lote.qtd_disponivel) || 0;
        const faltaProd = Number(prod.qtd_falta)      || 0;
        if (qtdRestante > dispLote + 1e-6) {
            showToast(`Qtd maior que disponível no lote (${fmtQtd(dispLote)}).`, 'warning');
            return;
        }
        if (qtdRestante > faltaProd + 1e-6) {
            showToast(`Qtd maior que faltante no pedido (${fmtQtd(faltaProd)}).`, 'warning');
            return;
        }

        // Estado loading no botão: desabilita + troca texto pra "Vinculando..."
        // Sem isso, operador clica 2× pensando que "não funcionou" e dispara
        // 2 chamadas de UPDATE — corrida concorrente desnecessária.
        const labelOriginal = btnConfirmarTransfer.textContent;
        btnConfirmarTransfer.disabled = true;
        btnConfirmarTransfer.classList.add('btn--loading');
        btnConfirmarTransfer.textContent = 'Vinculando...';
        try {
            // Distribui a qtd entre as linhas pendentes do produto, na ordem
            // que vieram (por SEQUENCIA). Cada linha recebe o que cabe.
            // Coleta o resultado de cada chamada — o backend retorna
            // {operacao: 'UPDATE'|'SPLIT', nova_sequencia: N|null} e usamos
            // a SEQ real para a atualização local (sem inventar valores).
            const linhas = [...prod.linhas_pendentes];
            let totalAtribuido = 0;
            let erro = null;
            const operacoes = [];

            for (const linha of linhas) {
                if (qtdRestante < 0.01) break;
                const qtdParaLinha = Math.min(qtdRestante, Number(linha.qtd) || 0);
                if (qtdParaLinha <= 0) continue;

                const res = await postJSON(URLS.atribuirLote, {
                    nunota:       pedido.nunota,
                    sequencia:    linha.sequencia,
                    codagregacao: lote.codagregacao,
                    qtd:          qtdParaLinha,
                });
                if (!res.ok || !res.body || !res.body.ok) {
                    erro = (res.body && res.body.error) || 'Falha ao atribuir lote.';
                    break;
                }
                operacoes.push({
                    seqOrig:     linha.sequencia,
                    qtdAplicada: qtdParaLinha,
                    operacao:    res.body.operacao,        // 'UPDATE' ou 'SPLIT'
                    novaSeq:     res.body.nova_sequencia,  // != null só quando SPLIT
                });
                qtdRestante   -= qtdParaLinha;
                totalAtribuido += qtdParaLinha;
            }

            if (erro && totalAtribuido === 0) {
                showToast(erro, 'error');
                return;
            }
            if (erro) {
                showToast(`Vinculado ${fmtQtd(totalAtribuido)} antes do erro: ${erro}`, 'warning');
            } else {
                // Toast contextual: cliente + pedido + qtd em vez de "Sucesso"
                // genérico. Operador sabe exatamente o que aconteceu sem
                // precisar voltar pra lista pra confirmar.
                const cliente = pedido.nomeparc ? ` · ${pedido.nomeparc}` : '';
                showToast(
                    `Lote ${lote.codagregacao} vinculado: ${fmtQtd(totalAtribuido)} ` +
                    `→ Pedido ${pedido.nunota}${cliente}`,
                    'success',
                );
            }

            // Atualização otimista — atualiza o estado local e re-renderiza
            // SEM esperar reload do servidor. O usuário pode clicar ATUALIZAR
            // se quiser confirmar com a base. Evita o "demora pra recarregar".
            _atualizarLocalAposAtribuicao(lote, pedido, operacoes);
            renderLotes();
            renderPedidos();

            fecharModalTransferencia();
            desarmarLote();
        } finally {
            btnConfirmarTransfer.disabled = false;
            btnConfirmarTransfer.classList.remove('btn--loading');
            btnConfirmarTransfer.textContent = labelOriginal;
        }
    }

    /** Aplica em lotesData e pedidosData o efeito de uma atribuição
     *  bem-sucedida — sem chamar o servidor. Usado para feedback instantâneo
     *  após confirmarTransferencia().
     *  `operacoes`: array de {seqOrig, qtdAplicada, operacao, novaSeq}, uma
     *  entrada por linha pendente que o backend modificou. */
    function _atualizarLocalAposAtribuicao(lote, pedido, operacoes) {
        const totalAtribuido = operacoes.reduce(
            (acc, op) => acc + (Number(op.qtdAplicada) || 0), 0,
        );
        if (totalAtribuido <= 0) return;

        // 1) Lote: reduz qtd_disponivel e aumenta qtd_reservada.
        //    Se zerar, retira de lotesData (a view backend só lista > 0).
        const idxL = lotesData.findIndex(
            l => String(l.codagregacao) === String(lote.codagregacao)
        );
        if (idxL !== -1) {
            const l = lotesData[idxL];
            const novoSaldo = Math.max(0, (Number(l.qtd_disponivel) || 0) - totalAtribuido);
            l.qtd_disponivel = novoSaldo;
            l.qtd_reservada  = (Number(l.qtd_reservada) || 0) + totalAtribuido;
            if (novoSaldo <= 0.000001) lotesData.splice(idxL, 1);
        }

        // 2) Pedido: aplica operação por operação, usando SEQ ORIGINAL e a
        //    NOVA SEQ retornada pelo backend (no caso de SPLIT). Sem inventar
        //    sequências locais — assim o modal de vínculos pode desvincular
        //    a linha imediatamente sem 400.
        const dadosLote = {
            codagregacao_atual: lote.codagregacao,
            status_item:        'ATRIBUIDO',
            lote_dtneg:         lote.dtneg_origem  || null,
            lote_nunota:        lote.nunota_origem || null,
            lote_codparc:       lote.codparc_origem|| null,
            lote_nomeparc:      lote.nomeparc_origem|| null,
        };
        for (const op of operacoes) {
            const item = pedidosData.find(it =>
                Number(it.nunota)    === Number(pedido.nunota) &&
                Number(it.sequencia) === Number(op.seqOrig)
            );
            if (!item) continue;

            if (op.operacao === 'SPLIT' && op.novaSeq != null) {
                // Linha original perde qtd e fica pendente; nova linha real
                // (SEQ vinda do backend) recebe a atribuição
                const qtdOrig = Number(item.qtd_pedida) || 0;
                item.qtd_pedida = Math.max(0, qtdOrig - Number(op.qtdAplicada || 0));
                pedidosData.push({
                    ...item,
                    sequencia:        Number(op.novaSeq),
                    qtd_pedida:       Number(op.qtdAplicada) || 0,
                    ...dadosLote,
                });
            } else {
                // UPDATE total: linha original recebe o lote (qtd não muda)
                Object.assign(item, dadosLote);
            }
        }
    }

    // ==========================================================================
    // 10b. MODAL DE VÍNCULOS (lote→pedidos OU pedido→lotes)
    // ==========================================================================
    function abrirModalVinculos(titulo, html) {
        if (!modalVinculos) return;
        vinculosTitulo.textContent = titulo;
        vinculosBody.innerHTML     = html;
        modalVinculos.classList.remove('hidden');
        modalVinculos.style.display = 'flex';
    }
    function fecharModalVinculos() {
        if (!modalVinculos) return;
        modalVinculos.classList.add('hidden');
        modalVinculos.style.display = 'none';
        vinculosBody.innerHTML = '';
    }

    /** Liga eventos do modal de vínculos pra desvincular lote.
     *  Click na linha → marca selected (mostra lixeira). Click no lixeira → confirm + POST. */
    function bindDesvincularNoModal() {
        const tabela = vinculosBody.querySelector('.vinculos-tabela');
        if (!tabela) return;

        tabela.addEventListener('click', async (e) => {
            const tr = e.target.closest('tr.vinc-linha');
            if (!tr) return;

            // Click no botão de lixeira
            if (e.target.closest('.btn-desvincular')) {
                e.stopPropagation();
                const nunota       = tr.dataset.nunota;
                const sequencia    = tr.dataset.sequencia;
                const codagregacao = tr.dataset.codagregacao;
                const ok = await phConfirmar({
                    titulo:   'Desvincular lote?',
                    mensagem: `Remover o vínculo do lote <strong>${escapeHtml(codagregacao)}</strong> ` +
                              `do pedido <strong>${escapeHtml(nunota)}</strong> (item ${escapeHtml(sequencia)})?`,
                    confirmarLabel: 'Desvincular',
                    tipo: 'perigo',
                });
                if (!ok) return;

                const btn = e.target.closest('.btn-desvincular');
                btn.disabled = true;
                btn.classList.add('btn--loading');
                try {
                    const res = await postJSON(URLS.desvincularLote, {
                        nunota:    Number(nunota),
                        sequencia: Number(sequencia),
                    });
                    if (!res.ok || !res.body || !res.body.ok) {
                        showToast((res.body && res.body.error) || 'Falha ao desvincular.', 'error');
                        btn.disabled = false;
                        btn.classList.remove('btn--loading');
                        return;
                    }
                    // Toast contextual: lote + pedido + parceiro
                    const parc = tr.querySelector('td:nth-child(3)')?.textContent?.trim() || '';
                    const ctx  = parc && parc !== '—' ? ` · ${parc}` : '';
                    showToast(
                        `Lote ${codagregacao} desvinculado do Pedido ${nunota}${ctx}.`,
                        'success',
                    );
                    fecharModalVinculos();
                    recarregarTudo();
                } catch (_) {
                    btn.disabled = false;
                    btn.classList.remove('btn--loading');
                }
                return;
            }

            // Click na linha (fora do botão) — toggle de seleção
            if (tr.dataset.bloqueado === '1') return;
            const ja = tr.classList.contains('selected');
            tabela.querySelectorAll('tr.vinc-linha.selected')
                  .forEach(t => t.classList.remove('selected'));
            if (!ja) tr.classList.add('selected');
        });
    }

    /** Modal mostrando os lotes que estão vinculados a este produto neste pedido.
     *  Colunas: DATA · NUNOTA · PARCEIRO (do lote) · PRODUTO · QTD
     *  Não precisa fetch — os dados já estão em prod.lotes_vinculados. */
    function abrirModalVinculosDeProduto(pedido, prod) {
        const titulo = `Lotes vinculados — ${prod.descrprod} · Pedido ${pedido.nunota}`;
        if (!prod.lotes_vinculados || prod.lotes_vinculados.length === 0) {
            abrirModalVinculos(titulo, '<div class="empty-state">Nenhum lote vinculado.</div>');
            return;
        }
        const linhas = prod.lotes_vinculados.map(lv => `
            <tr class="vinc-linha"
                data-nunota="${escapeHtml(pedido.nunota)}"
                data-sequencia="${escapeHtml(lv.sequencia)}"
                data-codagregacao="${escapeHtml(lv.codagregacao)}">
                <td>${escapeHtml(lv.lote_dtneg || '—')}</td>
                <td class="vmono">${escapeHtml(lv.lote_nunota != null ? lv.lote_nunota : '—')}</td>
                <td class="vmono">${escapeHtml(lv.codagregacao)}</td>
                <td>${escapeHtml(lv.lote_nomeparc || '—')}</td>
                <td>${escapeHtml(lv.descrprod || prod.descrprod || '')}</td>
                <td class="vnum">${fmtQtd(lv.qtd)}</td>
                <td class="vacao"><button class="btn-desvincular" type="button" title="Desvincular este lote do pedido">🗑</button></td>
            </tr>
        `).join('');
        const html = `
            <table class="vinculos-tabela">
                <thead>
                    <tr>
                        <th>Data</th><th>NUNOTA</th><th>Lote</th>
                        <th>Parceiro (lote)</th><th>Produto</th><th>Qtd</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>${linhas}</tbody>
            </table>
        `;
        abrirModalVinculos(titulo, html);
        bindDesvincularNoModal();
    }

    /** Modal mostrando os pedidos/vendas que estão consumindo este lote.
     *  Faz fetch a /api/lote-vinculos/?codagregacao=... */
    async function abrirModalVinculosDeLote(lote) {
        const titulo = `Pedidos/vendas usando lote ${lote.codagregacao}`;
        abrirModalVinculos(titulo, '<div class="empty-state">Carregando...</div>');
        try {
            const params = new URLSearchParams({ codagregacao: lote.codagregacao });
            const r = await fetch(URLS.loteVinculos + '?' + params.toString(), {
                credentials: 'same-origin', cache: 'no-store',
            });
            const data = await r.json();
            if (!data.ok) throw new Error(data.error || 'Falha ao buscar vínculos');
            const itens = data.vinculos || [];
            if (itens.length === 0) {
                vinculosBody.innerHTML = '<div class="empty-state">Nenhum pedido/venda usa este lote.</div>';
                return;
            }
            const linhas = itens.map(v => {
                const top = Number(v.codtipoper);
                const faturado = top === 35 || top === 37 || v.statusnota === 'L';
                // Só pedidos TOP 34 não-faturados podem ser desvinculados
                const podeDesvincular = top === 34 && v.statusnota !== 'L';
                const acaoHtml = podeDesvincular
                    ? '<button class="btn-desvincular" type="button" title="Desvincular este lote do pedido">🗑</button>'
                    : '';
                // Fase 2.10 — badge FATURADO vs ATRIBUIDO
                const tipNomeTop = top === 35
                    ? 'Venda com NFe'
                    : top === 37 ? 'Venda sem NFe'
                    : top === 34 ? 'Pedido em aberto'
                    : `TOP ${top}`;
                const statusLabel = faturado
                    ? `<span class="vinc-status vinc-status-faturado" title="Pedido já faturado (TOP ${top} - ${tipNomeTop}). Não pode mais ser desvinculado.">FATURADO</span>`
                    : `<span class="vinc-status vinc-status-atribuido" title="Pedido em aberto (TOP 34) — pode ser desvinculado se necessário">ATRIBUÍDO</span>`;
                return `
                    <tr class="vinc-linha ${faturado ? 'linha-faturada' : ''}"
                        data-nunota="${escapeHtml(v.nunota)}"
                        data-sequencia="${escapeHtml(v.sequencia)}"
                        data-codagregacao="${escapeHtml(lote.codagregacao)}"
                        ${podeDesvincular ? '' : 'data-bloqueado="1"'}>
                        <td>${escapeHtml(v.dtneg || '')}</td>
                        <td class="vmono">${escapeHtml(v.nunota)}</td>
                        <td>${escapeHtml(v.nomeparc || '—')}</td>
                        <td>${escapeHtml(v.descrprod || '')}</td>
                        <td class="vnum">${fmtQtd(v.qtdneg)}</td>
                        <td>${statusLabel}</td>
                        <td class="vacao">${acaoHtml}</td>
                    </tr>
                `;
            }).join('');
            vinculosBody.innerHTML = `
                <table class="vinculos-tabela">
                    <thead>
                        <tr>
                            <th>Data</th><th>NUNOTA</th><th>Parceiro (pedido)</th>
                            <th>Produto</th><th>Qtd</th><th>Status</th><th></th>
                        </tr>
                    </thead>
                    <tbody>${linhas}</tbody>
                </table>
            `;
            bindDesvincularNoModal();
        } catch (e) {
            vinculosBody.innerHTML =
                `<div class="empty-state">Erro: ${escapeHtml(e.message)}</div>`;
        }
    }

    // ==========================================================================
    // 11. SCROLL INFINITO
    // ==========================================================================
    function bindScrollInfinito(container, fnCarregar) {
        container.addEventListener('scroll', () => {
            const dist = container.scrollHeight - (container.scrollTop + container.clientHeight);
            if (dist < SCROLL_THRESHOLD) fnCarregar(false);
        });
    }
    bindScrollInfinito(containerLotes,   () => carregarLotes(false));
    bindScrollInfinito(containerPedidos, () => carregarPedidos(false));

    // ==========================================================================
    // 12. BINDINGS DA UI
    // ==========================================================================
    document.querySelectorAll('input[name="grpPedidos"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            agrupamentoAtual = e.target.value;
            renderPedidos();
            _salvarPrefs();
        });
    });

    document.querySelectorAll('input[name="tipoLote"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            tipoLote = e.target.value;
            carregarLotes(true);   // refaz busca server-side
            _salvarPrefs();
        });
    });

    // Helper: liga toggle de botão (aria-pressed + classe is-on) a uma callback.
    // Substituímos os <input type=checkbox> por <button> pra ter aparência de
    // pílula consistente com os outros controles. O JS gerencia o estado.
    function _bindToggleBtn(btn, getValor, setValor, aoMudar) {
        if (!btn) return;
        // Estado inicial reflete o estado da variável JS
        const aplicar = (v) => {
            btn.classList.toggle('is-on', !!v);
            btn.setAttribute('aria-pressed', !!v);
        };
        aplicar(getValor());
        btn.addEventListener('click', () => {
            const novo = !getValor();
            setValor(novo);
            aplicar(novo);
            if (aoMudar) aoMudar(novo);
            _salvarPrefs();
        });
        // Permite forçar refresh visual quando o estado muda externamente
        btn._aplicarToggle = aplicar;
    }
    const checkSomentePendente = document.getElementById('checkSomentePendente');
    _bindToggleBtn(
        checkSomentePendente,
        () => somentePendentes,
        (v) => { somentePendentes = v; },
        () => renderPedidos(),
    );
    _bindToggleBtn(
        checkTrava,
        () => checkTrava && checkTrava.classList.contains('is-on'),
        () => {},   // estado vive na própria classe; setValor é no-op
        null,
    );

    // ----- FILTRO DE PERÍODO (data inicial → data final) ------------------
    /** Formata um Date como ISO YYYY-MM-DD (sem fuso). */
    function _formatarISO(d) {
        const y  = d.getFullYear();
        const m  = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${dd}`;
    }
    /** Valida se data_fim >= data_ini. Mostra toast e devolve false se inválido. */
    function _validarRange(ini, fim, label) {
        if (ini && fim && fim < ini) {
            showToast(`Período ${label}: data final < inicial.`, 'warning');
            return false;
        }
        return true;
    }
    /** Aplica defaults (hoje−7 → hoje) nos 4 inputs e sincroniza o estado. */
    function _inicializarPeriodos() {
        const hoje    = new Date();
        const ha7Dias = new Date(); ha7Dias.setDate(hoje.getDate() - 7);
        const ini = _formatarISO(ha7Dias);
        const fim = _formatarISO(hoje);
        if (inputDataIniLotes)   { inputDataIniLotes.value   = ini; dataIniLotes   = ini; }
        if (inputDataFimLotes)   { inputDataFimLotes.value   = fim; dataFimLotes   = fim; }
        if (inputDataIniPedidos) { inputDataIniPedidos.value = ini; dataIniPedidos = ini; }
        if (inputDataFimPedidos) { inputDataFimPedidos.value = fim; dataFimPedidos = fim; }
    }

    _inicializarPeriodos();

    // Fase 2.12 — restaura preferências persistidas (sobrescreve defaults se houver)
    (function _aplicarPrefs() {
        const prefs = _carregarPrefs();
        if (!prefs) return;
        if (prefs.agrupamento === 'parceiro' || prefs.agrupamento === 'produto') {
            agrupamentoAtual = prefs.agrupamento;
            const r = document.getElementById(prefs.agrupamento === 'parceiro' ? 'grpParceiro' : 'grpProduto');
            if (r) r.checked = true;
        }
        if (['todos', 'classificavel', 'nao_classificavel'].includes(prefs.tipoLote)) {
            tipoLote = prefs.tipoLote;
            const id = prefs.tipoLote === 'todos' ? 'tipoTodos'
                     : prefs.tipoLote === 'classificavel' ? 'tipoClass' : 'tipoNclass';
            const r = document.getElementById(id);
            if (r) r.checked = true;
        }
        // Datas: aplica só se string ISO válida (ou string vazia explícita)
        const isISO = (s) => s === '' || /^\d{4}-\d{2}-\d{2}$/.test(s);
        if (typeof prefs.dataIniLotes === 'string' && isISO(prefs.dataIniLotes)) {
            dataIniLotes = prefs.dataIniLotes;
            if (inputDataIniLotes) inputDataIniLotes.value = prefs.dataIniLotes;
        }
        if (typeof prefs.dataFimLotes === 'string' && isISO(prefs.dataFimLotes)) {
            dataFimLotes = prefs.dataFimLotes;
            if (inputDataFimLotes) inputDataFimLotes.value = prefs.dataFimLotes;
        }
        if (typeof prefs.dataIniPedidos === 'string' && isISO(prefs.dataIniPedidos)) {
            dataIniPedidos = prefs.dataIniPedidos;
            if (inputDataIniPedidos) inputDataIniPedidos.value = prefs.dataIniPedidos;
        }
        if (typeof prefs.dataFimPedidos === 'string' && isISO(prefs.dataFimPedidos)) {
            dataFimPedidos = prefs.dataFimPedidos;
            if (inputDataFimPedidos) inputDataFimPedidos.value = prefs.dataFimPedidos;
        }
        if (typeof prefs.travado === 'boolean' && checkTrava) {
            checkTrava.classList.toggle('is-on', prefs.travado);
            checkTrava.setAttribute('aria-pressed', prefs.travado);
        }
        if (typeof prefs.somentePendentes === 'boolean') {
            somentePendentes = prefs.somentePendentes;
            const c = document.getElementById('checkSomentePendente');
            if (c) {
                c.classList.toggle('is-on', somentePendentes);
                c.setAttribute('aria-pressed', somentePendentes);
            }
        }
    })();

    if (inputDataIniLotes) {
        inputDataIniLotes.addEventListener('change', (e) => {
            const v = e.target.value || '';
            if (!_validarRange(v, dataFimLotes, 'lotes')) {
                inputDataIniLotes.value = dataIniLotes;
                return;
            }
            dataIniLotes = v;
            carregarLotes(true);
            _salvarPrefs();
        });
    }
    if (inputDataFimLotes) {
        inputDataFimLotes.addEventListener('change', (e) => {
            const v = e.target.value || '';
            if (!_validarRange(dataIniLotes, v, 'lotes')) {
                inputDataFimLotes.value = dataFimLotes;
                return;
            }
            dataFimLotes = v;
            carregarLotes(true);
            _salvarPrefs();
        });
    }
    if (inputDataIniPedidos) {
        inputDataIniPedidos.addEventListener('change', (e) => {
            const v = e.target.value || '';
            if (!_validarRange(v, dataFimPedidos, 'pedidos')) {
                inputDataIniPedidos.value = dataIniPedidos;
                return;
            }
            dataIniPedidos = v;
            pedidoIsolado  = null;   // mudar período sai de qualquer isolamento
            carregarPedidos(true);
            _salvarPrefs();
        });
    }
    if (inputDataFimPedidos) {
        inputDataFimPedidos.addEventListener('change', (e) => {
            const v = e.target.value || '';
            if (!_validarRange(dataIniPedidos, v, 'pedidos')) {
                inputDataFimPedidos.value = dataFimPedidos;
                return;
            }
            dataFimPedidos = v;
            pedidoIsolado  = null;
            carregarPedidos(true);
            _salvarPrefs();
        });
    }
    if (btnLimparPerLotes) {
        btnLimparPerLotes.addEventListener('click', () => {
            dataIniLotes = '';
            dataFimLotes = '';
            if (inputDataIniLotes) inputDataIniLotes.value = '';
            if (inputDataFimLotes) inputDataFimLotes.value = '';
            carregarLotes(true);
        });
    }
    if (btnLimparPerPedidos) {
        btnLimparPerPedidos.addEventListener('click', () => {
            dataIniPedidos = '';
            dataFimPedidos = '';
            if (inputDataIniPedidos) inputDataIniPedidos.value = '';
            if (inputDataFimPedidos) inputDataFimPedidos.value = '';
            pedidoIsolado = null;
            carregarPedidos(true);
        });
    }

    // ----- TYPEAHEAD genérico (usado pelos dois inputs) ---------------------
    function criarTypeahead({ input, dropdown, onSelect, formatItem }) {
        const state = { items: [], index: -1 };

        function render() {
            if (!state.items.length) {
                dropdown.innerHTML = '<div class="search-dropdown-empty">Nenhum resultado.</div>';
                return;
            }
            dropdown.innerHTML = state.items.map((it, i) => {
                const cls = i === state.index ? 'search-dropdown-item active' : 'search-dropdown-item';
                return `<div class="${cls}" data-idx="${i}">${formatItem(it)}</div>`;
            }).join('');
        }
        function abrir(items) {
            state.items = items || [];
            state.index = state.items.length ? 0 : -1;
            render();
            dropdown.classList.remove('hidden');
        }
        function fechar() {
            dropdown.classList.add('hidden');
            dropdown.innerHTML = '';
            state.items = [];
            state.index = -1;
        }
        function selecionar(idx) {
            const item = state.items[idx];
            fechar();
            if (item) onSelect(item);
        }
        // Click no item — usa mousedown pra disparar antes do blur
        dropdown.addEventListener('mousedown', (e) => {
            const it = e.target.closest('.search-dropdown-item');
            if (it) {
                e.preventDefault();
                selecionar(Number(it.dataset.idx));
            }
        });
        // Teclado
        input.addEventListener('keydown', (e) => {
            if (dropdown.classList.contains('hidden')) return;
            if (e.key === 'ArrowDown') {
                state.index = Math.min(state.index + 1, state.items.length - 1);
                render(); e.preventDefault();
            } else if (e.key === 'ArrowUp') {
                state.index = Math.max(state.index - 1, 0);
                render(); e.preventDefault();
            } else if (e.key === 'Enter' || e.key === 'Tab') {
                if (state.index >= 0 && state.items.length) {
                    selecionar(state.index);
                    e.preventDefault();
                }
            } else if (e.key === 'Escape') {
                fechar(); e.preventDefault();
            }
        });
        // Blur fecha (pequeno delay pra permitir mousedown nos itens)
        input.addEventListener('blur', () => setTimeout(fechar, 150));
        return { abrir, fechar };
    }

    // ----- Typeahead de Lotes (sugere FABRICANTES distintos) ---------------
    // Cache cliente-side: carrega TODOS os fabricantes uma vez no boot,
    // depois cada keystroke filtra localmente — sem rede, instantâneo.
    // Se o termo digitado não estiver no cache (TGFPRO grande, fabricante
    // depois do limit alfabético), faz fallback no servidor com aquele q.
    let fabricantesCache        = null;   // null = ainda não carregou
    let fabricantesCachePromise = null;
    function startFabricantesCache() {
        if (fabricantesCachePromise) return fabricantesCachePromise;
        fabricantesCachePromise = fetch(URLS.fabricantes + '?limit=5000', {
            credentials: 'same-origin', cache: 'no-store',
        })
            .then(r => r.json())
            .then(d => {
                fabricantesCache = d.ok ? (d.fabricantes || []) : [];
                return fabricantesCache;
            })
            .catch(() => {
                fabricantesCache = [];
                return fabricantesCache;
            });
        return fabricantesCachePromise;
    }
    async function buscarFabricantes(q) {
        if (fabricantesCache === null) await startFabricantesCache();
        const upper = (q || '').toUpperCase();
        const lista = [];
        for (const f of fabricantesCache) {
            if (f && f.toUpperCase().includes(upper)) {
                lista.push(f);
                if (lista.length >= 10) break;
            }
        }
        if (lista.length > 0 || !q || q.length < 2) return lista;

        // Fallback: cache local não tem — vai ao servidor com o termo.
        // Se achar, agrega ao cache pra próximas pesquisas serem locais.
        try {
            const r = await fetch(
                URLS.fabricantes + '?limit=10&q=' + encodeURIComponent(q),
                { credentials: 'same-origin', cache: 'no-store' }
            );
            const data = await r.json();
            if (data.ok && Array.isArray(data.fabricantes) && data.fabricantes.length > 0) {
                for (const f of data.fabricantes) {
                    if (fabricantesCache.indexOf(f) === -1) fabricantesCache.push(f);
                }
                return data.fabricantes.slice(0, 10);
            }
        } catch (_) {}

        return lista;
    }

    let typeaheadLotes = null;
    if (inputFiltroLotes && dropdownLotes) {
        typeaheadLotes = criarTypeahead({
            input:    inputFiltroLotes,
            dropdown: dropdownLotes,
            // Cada item é uma string (nome do fabricante)
            formatItem: (nome) => `<span class="sd-titulo">${escapeHtml(nome)}</span>`,
            onSelect: (nome) => {
                inputFiltroLotes.value = nome;
                fabricanteAtivo        = nome;
                textoFiltroLotes       = '';
                // Cross filter — fabricante refletido nos dois painéis
                carregarLotes(true);
                carregarPedidos(true);
            },
        });

        // 500ms debounce — dá tempo do operador digitar o nome completo do
        // fabricante antes do dropdown filtrar (a pedido do usuário).
        inputFiltroLotes.addEventListener('input', debounce(async (e) => {
            const q = (e.target.value || '').trim();
            if (q.length === 0) {
                fabricanteAtivo  = '';
                textoFiltroLotes = '';
                typeaheadLotes.fechar();
                carregarLotes(true);
                carregarPedidos(true);   // cross filter: limpar fabricante reflete nos pedidos
                return;
            }
            const items = await buscarFabricantes(q);
            typeaheadLotes.abrir(items);
        }, 500));
    }
    // Pre-carrega o cache em background no bootstrap — quando o usuário
    // digitar pela primeira vez, já vai estar pronto.
    startFabricantesCache();

    // ----- Typeahead de Pedidos --------------------------------------------
    let typeaheadPedidos = null;
    if (inputFiltroPedidos && dropdownPedidos) {
        typeaheadPedidos = criarTypeahead({
            input:    inputFiltroPedidos,
            dropdown: dropdownPedidos,
            // Item pode ter tipo='parceiro' (nome único) ou tipo='pedido' (NUNOTA específica)
            formatItem: (p) => {
                if (p.tipo === 'parceiro') {
                    return `<span class="sd-titulo">${escapeHtml(p.nomeparc)}</span>`;
                }
                return `
                    <span class="sd-titulo">${escapeHtml(p.nomeparc || '—')}</span>
                    <span class="sd-detalhe">Pedido ${escapeHtml(p.nunota)} · ${escapeHtml(p.dtneg || '')}</span>
                `;
            },
            onSelect: (p) => {
                if (p.tipo === 'parceiro') {
                    inputFiltroPedidos.value = p.nomeparc;
                    textoFiltroPedidos       = p.nomeparc;
                } else {
                    inputFiltroPedidos.value = String(p.nunota);
                    textoFiltroPedidos       = String(p.nunota);
                }
                pedidoIsolado = null;
                // Cross filter — selecionar parceiro/pedido reflete nos lotes
                carregarPedidos(true);
                carregarLotes(true);
            },
        });

        async function buscarSugestoesPedidos(q) {
            try {
                const ehNumero = /^\d+$/.test(q);
                const params = new URLSearchParams({ limit: '20', offset: '0' });
                if (q) {
                    if (ehNumero) params.set('nunota', q);
                    else          params.set('q', q);
                }
                const r = await fetch(URLS.pedidos + '?' + params.toString(), {
                    credentials: 'same-origin', cache: 'no-store',
                });
                const data = await r.json();
                if (!data.ok) return [];

                if (ehNumero) {
                    // Busca por NUNOTA: deduplica por NUNOTA, mostra pedido(s) que casam
                    const vistos = new Set();
                    const lista = [];
                    for (const it of (data.itens || [])) {
                        if (vistos.has(it.nunota)) continue;
                        vistos.add(it.nunota);
                        lista.push({ tipo: 'pedido', nunota: it.nunota, nomeparc: it.nomeparc, dtneg: it.dtneg });
                        if (lista.length >= 10) break;
                    }
                    return lista;
                }
                // Busca por texto: deduplica por NOMEPARC — UM registro por parceiro
                const vistos = new Set();
                const lista = [];
                for (const it of (data.itens || [])) {
                    const key = (it.nomeparc || '').toUpperCase();
                    if (!key || vistos.has(key)) continue;
                    vistos.add(key);
                    lista.push({ tipo: 'parceiro', nomeparc: it.nomeparc });
                    if (lista.length >= 10) break;
                }
                return lista;
            } catch (_) { return []; }
        }

        inputFiltroPedidos.addEventListener('input', debounce(async (e) => {
            const q = (e.target.value || '').trim();
            textoFiltroPedidos = q;
            pedidoIsolado      = null;
            // Cross filter: digitar texto refilra lotes (cliente_q)
            carregarPedidos(true);
            carregarLotes(true);
            if (q.length >= 1) {
                const items = await buscarSugestoesPedidos(q);
                typeaheadPedidos.abrir(items);
            } else {
                typeaheadPedidos.fechar();
            }
        }, 120));
    }

    if (btnFecharModal)       btnFecharModal.addEventListener('click', fecharModalTransferencia);
    if (btnCancelarTransfer)  btnCancelarTransfer.addEventListener('click', fecharModalTransferencia);
    if (btnConfirmarTransfer) btnConfirmarTransfer.addEventListener('click', confirmarTransferencia);

    if (inputQtdTransfer) {
        inputQtdTransfer.addEventListener('keydown', (e) => {
            if (e.key === 'Enter')       { e.preventDefault(); confirmarTransferencia(); }
            else if (e.key === 'Escape') { e.preventDefault(); fecharModalTransferencia(); }
        });
    }
    if (modalTransfer) {
        modalTransfer.addEventListener('click', (e) => {
            if (e.target === modalTransfer) fecharModalTransferencia();
        });
    }

    if (btnFecharVinculos) btnFecharVinculos.addEventListener('click', fecharModalVinculos);
    if (modalVinculos) {
        modalVinculos.addEventListener('click', (e) => {
            if (e.target === modalVinculos) fecharModalVinculos();
        });
    }
    if (btnDesarmar) btnDesarmar.addEventListener('click', desarmarLote);

    // Atalhos globais de teclado (Mai/2026):
    //   Esc  — fecha modais (prioridade) ou desarma o lote
    //   /    — foca o campo de busca de lote (atalho clássico estilo GitHub)
    //   F    — foca o campo de busca de lote (alternativa pra teclados sem /)
    //   R    — recarrega lotes + pedidos (mesmo efeito do botão Atualizar)
    //   C    — limpa todos os filtros (mesmo efeito do botão Limpar)
    //   G    — alterna agrupamento parceiro ↔ produto
    // Os atalhos só disparam quando o foco NÃO está num input/textarea/contenteditable
    // (caso contrário 'r' digitado num search-input recarregaria a tela).
    document.addEventListener('keydown', (e) => {
        // Esc: prioritário, funciona mesmo dentro de inputs
        if (e.key === 'Escape') {
            if (modalVinculos && !modalVinculos.classList.contains('hidden')) {
                fecharModalVinculos();
                return;
            }
            if (modalTransfer && !modalTransfer.classList.contains('hidden')) {
                return;   // o próprio input do modal já trata o Esc
            }
            if (loteArmado) desarmarLote();
            return;
        }

        // Pra demais atalhos, ignora se foco está em campo editável
        const t = e.target;
        const tag = t && t.tagName;
        const editavel = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' ||
                         (t && t.isContentEditable);
        if (editavel) return;

        // Modais abertos: não dispara atalhos globais
        const modalAberto = (modalVinculos && !modalVinculos.classList.contains('hidden')) ||
                            (modalTransfer && !modalTransfer.classList.contains('hidden'));
        if (modalAberto) return;

        // Modificadores tipo Ctrl/Alt/Meta interromperíam atalhos do navegador,
        // então só agimos em teclas isoladas.
        if (e.ctrlKey || e.altKey || e.metaKey) return;

        const k = (e.key || '').toLowerCase();
        if (k === '/' || k === 'f') {
            // Foca busca de lote (campo mais usado, painel esquerdo)
            const inp = document.getElementById('filtroLotes');
            if (inp) {
                e.preventDefault();
                inp.focus();
                inp.select();
            }
        } else if (k === 'r') {
            // Refresh — disparar via click pra reusar feedback visual do botão
            const btn = document.getElementById('btnAtualizar');
            if (btn) { e.preventDefault(); btn.click(); }
        } else if (k === 'c') {
            const btn = document.getElementById('btnLimparTudo');
            if (btn) { e.preventDefault(); btn.click(); }
        } else if (k === 'g') {
            // Alterna agrupamento. Faz o click no radio pra reusar o handler change.
            const novoId = agrupamentoAtual === 'parceiro' ? 'grpProduto' : 'grpParceiro';
            const radio = document.getElementById(novoId);
            if (radio) { e.preventDefault(); radio.click(); }
        }
    });

    // ==========================================================================
    // 13. BOTÕES LIMPAR / ATUALIZAR (header do painel Pedidos)
    // ==========================================================================
    const btnLimparTudo = document.getElementById('btnLimparTudo');
    const btnAtualizar  = document.getElementById('btnAtualizar');

    /** Reseta toda a tela ao estado inicial: typeaheads, datas (defaults),
     *  agrupamento, tipoLote, filtro cruzado, isolamento, lote armado,
     *  travar filtro. Depois recarrega lotes e pedidos. */
    function limparTudo() {
        // Typeaheads
        textoFiltroLotes   = '';
        fabricanteAtivo    = '';
        textoFiltroPedidos = '';
        if (inputFiltroLotes)   inputFiltroLotes.value   = '';
        if (inputFiltroPedidos) inputFiltroPedidos.value = '';
        if (typeaheadLotes)   typeaheadLotes.fechar();
        if (typeaheadPedidos) typeaheadPedidos.fechar();

        // Filtro cruzado e isolamento
        _limparTodosChecks();
        pedidoIsolado     = null;

        // Lote armado
        if (loteArmado) desarmarLote();

        // Tipo de lote → TODOS
        tipoLote = 'todos';
        const radioTodos = document.getElementById('tipoTodos');
        if (radioTodos) radioTodos.checked = true;

        // Agrupamento → PARCEIRO
        agrupamentoAtual = 'parceiro';
        const radioParc = document.getElementById('grpParceiro');
        if (radioParc) radioParc.checked = true;

        // TRAVAR FILTRO desativado
        if (checkTrava) {
            checkTrava.classList.remove('is-on');
            checkTrava.setAttribute('aria-pressed', 'false');
        }

        // Datas → defaults (hoje−7 → hoje)
        _inicializarPeriodos();

        // "Só pendentes" desligado
        somentePendentes = false;
        const checkSP = document.getElementById('checkSomentePendente');
        if (checkSP) {
            checkSP.classList.remove('is-on');
            checkSP.setAttribute('aria-pressed', 'false');
        }

        // Reset do estado de colapso — todos os pedidos voltam a ser
        // tratados como "novos" e serão colapsados na próxima renderização.
        pedidosColapsados.clear();
        pedidosJaVistos.clear();
        gruposProdutoColapsados.clear();

        // Persiste o reset (limpa preferências antigas)
        _salvarPrefs();

        recarregarTudo();
    }

    if (btnLimparTudo) btnLimparTudo.addEventListener('click', limparTudo);
    if (btnAtualizar)  btnAtualizar.addEventListener('click', recarregarTudo);

    // Botões dentro do empty state — delegação nos containers das duas colunas.
    // Os botões são gerados dinamicamente em renderLotes/renderPedidos quando a
    // lista vem vazia; o handler aqui dispara a ação que destrava o usuário.
    function _bindEmptyActions(container) {
        if (!container) return;
        container.addEventListener('click', (e) => {
            const btn = e.target.closest('.ras-empty-action');
            if (!btn) return;
            const acao = btn.dataset.action;
            if (acao === 'limpar-tudo') {
                limparTudo();
            } else if (acao === 'desligar-pendentes') {
                somentePendentes = false;
                const tog = document.getElementById('checkSomentePendente');
                if (tog) tog.setAttribute('aria-pressed', 'false');
                _salvarPrefs();
                renderPedidos();
            }
        });
    }
    _bindEmptyActions(containerLotes);
    _bindEmptyActions(containerPedidos);

    // Botões "+" e "−" — agrupam/desagrupam todos os grupos visíveis,
    // respeitando o agrupamento ativo (POR PARCEIRO ou POR PRODUTO).
    function agruparTudoVisivel() {
        if (agrupamentoAtual === 'parceiro') {
            agruparPedidos(pedidosData).forEach(p => {
                pedidosColapsados.add(Number(p.nunota));
            });
        } else {
            // POR PRODUTO: pega cada nome de produto único da lista atual
            agruparPedidos(pedidosData).forEach(p => {
                p.produtos.forEach(pr => {
                    gruposProdutoColapsados.add(pr.descrprod || '—');
                });
            });
        }
        renderPedidos();
    }
    function desagruparTudoVisivel() {
        if (agrupamentoAtual === 'parceiro') pedidosColapsados.clear();
        else                                 gruposProdutoColapsados.clear();
        renderPedidos();
    }
    document.getElementById('btnAgruparTudo')
            ?.addEventListener('click', agruparTudoVisivel);
    document.getElementById('btnDesagruparTudo')
            ?.addEventListener('click', desagruparTudoVisivel);

    // ==========================================================================
    // 14. BOOTSTRAP
    // ==========================================================================
    if (modalTransfer) modalTransfer.style.display = 'none';
    if (modalVinculos) modalVinculos.style.display = 'none';
    recarregarTudo();
});
