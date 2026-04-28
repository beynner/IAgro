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
    let produtosFiltrados   = new Set();    // Set<codprod>; vazio = sem filtro
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

    function temFiltroProdutos()         { return produtosFiltrados.size > 0; }
    function produtoEstaFiltrado(codprod){ return produtosFiltrados.has(Number(codprod)); }
    function setsIguais(a, b) {
        if (a.size !== b.size) return false;
        for (const v of a) if (!b.has(v)) return false;
        return true;
    }
    /** Aplica filtro de produto vindo de um clique em card de lote ou produto-linha.
     *  Substitui o set inteiro (replace). Click no mesmo conjunto limpa o filtro.
     *  TRAVAR FILTRO bloqueia este caminho — usuário pode alterar o filtro só pelos
     *  campos do topo (typeahead/datas/radios) e pelos × dos chips. */
    function aplicarFiltroProdutos(codprods) {
        if (checkTrava && checkTrava.checked) return;   // travado: clique não filtra

        const lista = Array.isArray(codprods) ? codprods : [codprods];
        const novo  = new Set(lista.map(Number));
        const igual = setsIguais(novo, produtosFiltrados) && pedidoIsolado === null;
        if (igual) produtosFiltrados = new Set();
        else       produtosFiltrados = novo;
        pedidoIsolado = null;
        carregarLotes(true);
        carregarPedidos(true);
    }

    /** Aplica isolamento ao clicar no header do pedido (replace + isolamento).
     *  Click no mesmo pedido limpa tudo. TRAVAR FILTRO bloqueia este caminho. */
    function aplicarFiltroPedidoIsolado(nunota, codprods) {
        if (checkTrava && checkTrava.checked) return;   // travado: clique não filtra

        const novoSet = new Set((codprods || []).map(Number));
        const jaIsolado = pedidoIsolado === Number(nunota) &&
                          setsIguais(novoSet, produtosFiltrados);
        if (jaIsolado) {
            pedidoIsolado = null;
            produtosFiltrados = new Set();
        } else {
            pedidoIsolado = Number(nunota);
            produtosFiltrados = novoSet;
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
    const PH = window.PackingHouse || {};

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
        if (!filtrosAtivosEl) return;
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
        if (produtosFiltrados.size > 0) {
            const lista = [...produtosFiltrados];
            const valor = lista.length === 1
                ? _descricaoProduto(lista[0])
                : `${lista.length} produtos`;
            chip('cruzado', 'produtos', 'Produto', valor);
        }

        if (chips.length === 0) {
            filtrosAtivosEl.classList.add('hidden');
            filtrosAtivosEl.innerHTML = '';
            return;
        }
        filtrosAtivosEl.classList.remove('hidden');
        filtrosAtivosEl.innerHTML =
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
                produtosFiltrados = new Set();
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
            if (produtosFiltrados.size > 0) {
                params.set('codprods', [...produtosFiltrados].join(','));
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
                if (produtosFiltrados.size > 0) {
                    params.set('codprods', [...produtosFiltrados].join(','));
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
    function renderLotes() {
        containerLotes.innerHTML = '';

        const visiveis = lotesData
            .filter(l => !temFiltroProdutos() || produtoEstaFiltrado(l.codprod));

        if (visiveis.length === 0 && !lotesCarregando) {
            containerLotes.innerHTML = '<div class="empty-state">Nenhum lote encontrado.</div>';
            return;
        }

        visiveis.forEach(l => {
            const status = l.status_linha;
            const qtd    = l.qtd_disponivel;

            const card = document.createElement('div');
            card.className = 'rastreio-card card-lote compacto';
            if (produtoEstaFiltrado(l.codprod)) card.classList.add('selected');
            if (loteArmado && loteArmado.codagregacao === l.codagregacao) {
                card.classList.add('lote-armado');
            }
            card.dataset.codprod      = l.codprod;
            card.dataset.codagregacao = l.codagregacao;

            const badgeAvaria = (l.qtd_avaria_interna && l.qtd_avaria_interna > 0)
                ? `<span class="badge-avaria-interna" title="Avaria interna">▼ ${fmtQtd(l.qtd_avaria_interna)}</span>`
                : '';

            const tagStatus = status === 'NAO_CLASSIFICAVEL'
                ? '<span class="tag-naoclass" title="Sem classificação">N/C</span>'
                : '';

            // Lotes listados aqui já são vendáveis (qtd_disponivel > 0).
            const podeArmar = Number(l.qtd_disponivel) > 0;
            const armarBtn = podeArmar
                ? '<button class="btn-armar" title="Armar este lote para vincular a um pedido" type="button">🔗</button>'
                : '';

            // Layout em 1 linha: produto · parceiro · lote · data · qtd · armar · olho
            card.innerHTML = `
                <span class="col-prod"  title="${escapeHtml(l.descrprod)}">
                    <strong>${escapeHtml(l.descrprod)}</strong>${tagStatus}
                </span>
                <span class="col-parc"  title="${escapeHtml(l.nomeparc_origem || '')}">
                    ${escapeHtml(l.nomeparc_origem || '—')}
                </span>
                <span class="col-lote"  title="Lote ${escapeHtml(l.codagregacao)}">
                    ${escapeHtml(l.codagregacao)}
                </span>
                <span class="col-data">${escapeHtml(l.dtneg_origem || '')}</span>
                <span class="col-qtd">${fmtQtd(qtd)} ${badgeAvaria}</span>
                ${armarBtn}
                <button class="btn-olho" title="Ver pedidos/vendas que usam este lote" type="button">👁</button>
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

            // Click no resto do card mantém o filtro cruzado
            card.addEventListener('click', () => aplicarFiltroProdutos(l.codprod));

            containerLotes.appendChild(card);
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
        return pedido.produtos.some(p => produtoEstaFiltrado(p.codprod));
    }

    function renderPedidos() {
        containerPedidos.innerHTML = '';

        const pedidos = agruparPedidos(pedidosData)
            .filter(pedidoCasaFiltro);
        if (pedidos.length === 0 && !pedidosCarregando) {
            containerPedidos.innerHTML = '<div class="empty-state">Nenhum pedido em aberto.</div>';
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
                    if (temFiltroProdutos() && !produtoEstaFiltrado(pr.codprod)) return;
                    const key = pr.descrprod || '—';
                    (grupos[key] = grupos[key] || []).push({ pedido: p, produto: pr });
                });
            });
        }

        Object.keys(grupos).sort().forEach(nomeGrupo => {
            const groupHeader = document.createElement('div');
            groupHeader.className = 'group-header-major';
            groupHeader.textContent = nomeGrupo;
            containerPedidos.appendChild(groupHeader);

            if (agrupamentoAtual === 'parceiro') {
                grupos[nomeGrupo].forEach(p => renderPedidoBloco(p));
            } else {
                grupos[nomeGrupo].forEach(({ pedido, produto }) =>
                    renderProdutoBlocoSolitario(pedido, produto));
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
        // Selected quando este pedido específico está isolado
        if (pedidoIsolado === Number(pedido.nunota)) header.classList.add('selected');
        header.innerHTML = `
            <span class="pb-parc">${escapeHtml(pedido.nomeparc || '—')}</span>
            <span class="pb-sep">|</span>
            <span class="pb-data">${escapeHtml(pedido.dtneg || '')}</span>
            <span class="pb-nunota">Pedido ${escapeHtml(pedido.nunota)}</span>
        `;
        // Click no header → ISOLA esse pedido específico nos pedidos +
        // filtra lotes pelos N produtos dele.
        header.addEventListener('click', () => {
            aplicarFiltroPedidoIsolado(pedido.nunota, codprodsPedido);
        });
        return header;
    }

    function renderPedidoBloco(pedido) {
        containerPedidos.appendChild(_criarPedidoHeader(pedido, false));
        // Quando há filtro de produtos ativo, mostra apenas os produtos filtrados
        // dentro do pedido (esconde os outros produtos do mesmo pedido).
        // No isolamento (click no header), todos os codprods do pedido estão
        // no Set, então todos aparecem normalmente.
        const produtos = temFiltroProdutos()
            ? pedido.produtos.filter(p => produtoEstaFiltrado(p.codprod))
            : pedido.produtos;
        produtos.forEach(prod => {
            containerPedidos.appendChild(renderProdutoLinha(pedido, prod));
        });
    }

    function renderProdutoBlocoSolitario(pedido, prod) {
        // Modo "agrupado por produto": mostra o pedido como sub-header
        containerPedidos.appendChild(_criarPedidoHeader(pedido, true));
        containerPedidos.appendChild(renderProdutoLinha(pedido, prod));
    }

    function renderProdutoLinha(pedido, prod) {
        const completo = prod.qtd_falta <= 0.000001;
        const faded    = temFiltroProdutos() && !produtoEstaFiltrado(prod.codprod);
        const selected = produtoEstaFiltrado(prod.codprod);
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
            ? '<span class="tag-atribuido-mini">OK</span>'
            : `<span class="tag-falta">falta ${fmtInt(prod.qtd_falta)}</span>`;

        const temVinculos = prod.lotes_vinculados && prod.lotes_vinculados.length > 0;
        const olhoBtn = temVinculos
            ? '<button class="btn-olho" title="Ver lotes vinculados" type="button">👁</button>'
            : '';

        linha.innerHTML = `
            <span class="col-prod" title="${escapeHtml(prod.descrprod)}">
                ${escapeHtml(prod.descrprod)}
            </span>
            <span class="col-progresso" title="Vinculada / Total">
                <span class="qtd-vinculada">${fmtInt(prod.qtd_atribuida)}</span>/<span class="qtd-total">${fmtInt(prod.qtd_total)}</span>
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

        // Click na linha (fora do olho)
        // - Se há lote armado E o CODPROD bate E a linha tem falta → abre modal de vínculo
        // - Caso contrário → filtra lotes pelo CODPROD desse produto (comportamento antigo)
        linha.addEventListener('click', () => {
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
            aplicarFiltroProdutos(prod.codprod);
        });
        return linha;
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
        // Re-render para refletir .lote-armado nos cards e .alvo-armado nas linhas
        renderLotes();
        renderPedidos();
    }

    function desarmarLote() {
        if (!loteArmado) return;
        loteArmado = null;
        atualizarBarArmado();
        renderLotes();
        renderPedidos();
    }

    function atualizarBarArmado() {
        if (!barArmado) return;
        if (loteArmado) {
            if (barArmadoLote) {
                barArmadoLote.textContent =
                    `${loteArmado.descrprod} — ${loteArmado.codagregacao}`;
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

        btnConfirmarTransfer.disabled = true;
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
                showToast(`Lote atribuído (${fmtQtd(totalAtribuido)}).`, 'success');
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
                const ok = window.confirm(
                    `Desvincular lote ${codagregacao} do pedido ${nunota} (item ${sequencia})?`
                );
                if (!ok) return;

                const btn = e.target.closest('.btn-desvincular');
                btn.disabled = true;
                try {
                    const res = await postJSON(URLS.desvincularLote, {
                        nunota:    Number(nunota),
                        sequencia: Number(sequencia),
                    });
                    if (!res.ok || !res.body || !res.body.ok) {
                        showToast((res.body && res.body.error) || 'Falha ao desvincular.', 'error');
                        btn.disabled = false;
                        return;
                    }
                    showToast('Lote desvinculado.', 'success');
                    fecharModalVinculos();
                    recarregarTudo();
                } catch (_) {
                    btn.disabled = false;
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
                // Só pedidos TOP 34 podem desvincular (35/37 já faturado, sem operação reversível aqui)
                const podeDesvincular = Number(v.codtipoper) === 34 && v.statusnota !== 'L';
                const acaoHtml = podeDesvincular
                    ? '<button class="btn-desvincular" type="button" title="Desvincular este lote do pedido">🗑</button>'
                    : '';
                return `
                    <tr class="vinc-linha"
                        data-nunota="${escapeHtml(v.nunota)}"
                        data-sequencia="${escapeHtml(v.sequencia)}"
                        data-codagregacao="${escapeHtml(lote.codagregacao)}"
                        ${podeDesvincular ? '' : 'data-bloqueado="1"'}>
                        <td>${escapeHtml(v.dtneg || '')}</td>
                        <td class="vmono">${escapeHtml(v.nunota)}</td>
                        <td>${escapeHtml(v.nomeparc || '—')}</td>
                        <td>${escapeHtml(v.descrprod || '')}</td>
                        <td class="vnum">${fmtQtd(v.qtdneg)}</td>
                        <td class="vacao">${acaoHtml}</td>
                    </tr>
                `;
            }).join('');
            vinculosBody.innerHTML = `
                <table class="vinculos-tabela">
                    <thead>
                        <tr>
                            <th>Data</th><th>NUNOTA</th><th>Parceiro (pedido)</th>
                            <th>Produto</th><th>Qtd</th><th></th>
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
        });
    });

    document.querySelectorAll('input[name="tipoLote"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            tipoLote = e.target.value;
            carregarLotes(true);   // refaz busca server-side
        });
    });

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

    if (inputDataIniLotes) {
        inputDataIniLotes.addEventListener('change', (e) => {
            const v = e.target.value || '';
            if (!_validarRange(v, dataFimLotes, 'lotes')) {
                inputDataIniLotes.value = dataIniLotes;
                return;
            }
            dataIniLotes = v;
            carregarLotes(true);
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

    // Esc fecha modais (prioridade) ou desarma o lote
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        if (modalVinculos && !modalVinculos.classList.contains('hidden')) {
            fecharModalVinculos();
            return;
        }
        if (modalTransfer && !modalTransfer.classList.contains('hidden')) {
            return;   // o próprio input do modal já trata o Esc
        }
        if (loteArmado) desarmarLote();
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
        produtosFiltrados = new Set();
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
        if (checkTrava) checkTrava.checked = false;

        // Datas → defaults (hoje−7 → hoje)
        _inicializarPeriodos();

        recarregarTudo();
    }

    if (btnLimparTudo) btnLimparTudo.addEventListener('click', limparTudo);
    if (btnAtualizar)  btnAtualizar.addEventListener('click', recarregarTudo);

    // ==========================================================================
    // 14. BOOTSTRAP
    // ==========================================================================
    if (modalTransfer) modalTransfer.style.display = 'none';
    if (modalVinculos) modalVinculos.style.display = 'none';
    recarregarTudo();
});
