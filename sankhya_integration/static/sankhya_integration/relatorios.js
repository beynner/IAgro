/* ===========================================================================
   MÓDULO RELATÓRIOS — Mai/2026 — 2026-05-17 (v1.0)
   POLISH v1.1 — Mai/2026 — 2026-05-30
     + Barras horizontais proporcionais nas tabelas
     + Comparação com período anterior (chip +X% / -X%)
     + Drilldown click → modal compartilhado com detalhe da linha
   IIFE com 1 renderer por sub-aba (lazy load: só carrega quando ativa).
   Helper genérico de fetch + estado loading/erro/vazio padronizado.
   =========================================================================== */
(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Helpers utilitários
    // -----------------------------------------------------------------------
    var fmtBRL = function (n) {
        return 'R$ ' + Number(n || 0).toFixed(2)
            .replace('.', ',')
            .replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    };
    var fmtInt = function (n) {
        return Number(n || 0).toLocaleString('pt-BR', { maximumFractionDigits: 0 });
    };
    var fmtKg = function (n) {
        return Number(n || 0).toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + ' kg';
    };
    var fmtPct = function (n) {
        var v = Number(n || 0);
        return (v > 0 ? '+' : '') + v.toFixed(1).replace('.', ',') + '%';
    };
    var escapeHtml = function (s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
            })[c];
        });
    };

    // -----------------------------------------------------------------------
    // Helper de fetch padronizado
    // -----------------------------------------------------------------------
    function carregar_real(pane, url) {
        var conteudo = pane.querySelector('.rel-conteudo');
        var btnRefresh = pane.querySelector('.rel-btn-refresh');
        if (!conteudo) return Promise.resolve(null);

        conteudo.classList.add('rel-loading');
        if (btnRefresh) btnRefresh.classList.add('is-loading');

        return fetch(url, { credentials: 'same-origin' })
            .then(function (res) {
                return res.json().then(function (body) {
                    return { res: res, body: body };
                }).catch(function () {
                    return { res: res, body: {} };
                });
            })
            .then(function (r) {
                if (!r.res.ok || !r.body || r.body.ok === false) {
                    renderErro(conteudo, (r.body && r.body.error) || ('Erro ' + r.res.status));
                    return null;
                }
                return r.body;
            })
            .catch(function () {
                renderErro(conteudo, 'Falha de rede — tente novamente.');
                return null;
            })
            .then(function (out) {
                conteudo.classList.remove('rel-loading');
                if (btnRefresh) btnRefresh.classList.remove('is-loading');
                return out;
            });
    }

    function fetchSimples(url) {
        return fetch(url, { credentials: 'same-origin' })
            .then(function (res) { return res.json().catch(function () { return null; }); })
            .catch(function () { return null; });
    }

    function renderErro(container, msg) {
        container.innerHTML = '' +
            '<div class="rel-error">' +
                '<i class="ph ph-warning-circle" aria-hidden="true"></i>' +
                '<span>' + escapeHtml(msg) + '</span>' +
            '</div>';
    }
    function renderVazio(container, msg, sugestao) {
        container.innerHTML = '' +
            '<div class="rel-empty">' +
                '<i class="ph ph-magnifying-glass" aria-hidden="true"></i>' +
                '<span>' + escapeHtml(msg) + '</span>' +
                (sugestao ? '<small>' + escapeHtml(sugestao) + '</small>' : '') +
            '</div>';
    }

    // -----------------------------------------------------------------------
    // Switch de tabs
    // -----------------------------------------------------------------------
    function ativarTab(rel) {
        document.querySelectorAll('.rel-tab').forEach(function (btn) {
            var on = btn.dataset.rel === rel;
            btn.classList.toggle('is-on', on);
            btn.setAttribute('aria-pressed', String(on));
        });
        document.querySelectorAll('.rel-pane').forEach(function (pane) {
            pane.classList.toggle('is-active', pane.dataset.rel === rel);
        });
        // Lazy load — só carrega na 1ª ativação
        var renderer = RENDERERS[rel];
        if (renderer) renderer.carregar();
    }

    // -----------------------------------------------------------------------
    // Bind de chips/select/refresh dentro de uma pane
    // -----------------------------------------------------------------------
    function bindControles(pane, renderer) {
        // Chips de período/idade — opt-in (mesmo grupo de chips)
        pane.querySelectorAll('.rel-chip').forEach(function (chip) {
            chip.addEventListener('click', function () {
                var grupo = chip.parentElement;
                grupo.querySelectorAll('.rel-chip').forEach(function (c) {
                    c.classList.remove('is-on');
                });
                chip.classList.add('is-on');
                renderer.carregar(true);
            });
        });
        pane.querySelectorAll('.rel-select').forEach(function (sel) {
            sel.addEventListener('change', function () { renderer.carregar(true); });
        });
        var btn = pane.querySelector('[data-action="refresh"]');
        if (btn) btn.addEventListener('click', function () { renderer.carregar(true); });
    }

    // -----------------------------------------------------------------------
    // Período → datas + período anterior espelhado (pra comparação)
    // -----------------------------------------------------------------------
    function fmtIso(d) {
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var dd = String(d.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + dd;
    }

    function periodoToDatas(valor) {
        var hoje = new Date();
        var ate = fmtIso(hoje);
        if (valor === 'mes-atual') {
            var de = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
            return { date_de: fmtIso(de), date_ate: ate };
        }
        if (valor === 'mes-anterior') {
            var de2 = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
            var ateP = new Date(hoje.getFullYear(), hoje.getMonth(), 0);
            return { date_de: fmtIso(de2), date_ate: fmtIso(ateP) };
        }
        var dias = parseInt(valor, 10) || 30;
        var deN = new Date(hoje);
        deN.setDate(deN.getDate() - dias);
        return { date_de: fmtIso(deN), date_ate: ate };
    }

    // Período espelhado anterior — janela equivalente imediatamente antes.
    function periodoEspelhadoAnterior(valor) {
        var hoje = new Date();
        if (valor === 'mes-atual') {
            var de = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
            var ate = new Date(hoje.getFullYear(), hoje.getMonth(), 0);
            return { date_de: fmtIso(de), date_ate: fmtIso(ate) };
        }
        if (valor === 'mes-anterior') {
            var de2 = new Date(hoje.getFullYear(), hoje.getMonth() - 2, 1);
            var ate2 = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 0);
            return { date_de: fmtIso(de2), date_ate: fmtIso(ate2) };
        }
        var dias = parseInt(valor, 10) || 30;
        var ateN = new Date(hoje);
        ateN.setDate(ateN.getDate() - dias - 1);
        var deN = new Date(ateN);
        deN.setDate(deN.getDate() - dias + 1);
        return { date_de: fmtIso(deN), date_ate: fmtIso(ateN) };
    }

    function periodoAtivo(pane) {
        var chip = pane.querySelector('.rel-filtro-periodo .rel-chip.is-on');
        return chip
            ? (chip.dataset.periodo || chip.dataset.dias || chip.dataset.horizonte)
            : '30';
    }

    // Calcula chip de variação % entre atual e anterior.
    function compChipHtml(atual, anterior, opts) {
        opts = opts || {};
        var a = Number(atual || 0);
        var p = Number(anterior || 0);
        if (anterior == null) {
            return '<span class="rel-comp-chip rel-comp-chip--loading">' +
                   '<i class="ph ph-hourglass-low"></i>vs período anterior</span>';
        }
        if (p === 0 && a === 0) {
            return '<span class="rel-comp-chip rel-comp-chip--zero">' +
                   '0% vs anterior</span>';
        }
        if (p === 0) {
            return '<span class="rel-comp-chip rel-comp-chip--up">' +
                   '<i class="ph ph-arrow-up"></i>novo vs anterior</span>';
        }
        var pct = ((a - p) / Math.abs(p)) * 100;
        // Em métricas "saída"/"custo", subir é ruim — flag opcional
        var invert = !!opts.invertirCor;
        var bom = (pct >= 0) !== invert;
        var cls = pct > 0.05
            ? (bom ? 'rel-comp-chip--up' : 'rel-comp-chip--down')
            : pct < -0.05
                ? (bom ? 'rel-comp-chip--down' : 'rel-comp-chip--up')
                : 'rel-comp-chip--zero';
        var icon = pct > 0.05 ? 'ph-arrow-up' : pct < -0.05 ? 'ph-arrow-down' : 'ph-equals';
        return '<span class="rel-comp-chip ' + cls + '">' +
               '<i class="ph ' + icon + '"></i>' +
               fmtPct(pct) +
               ' vs anterior</span>';
    }

    // Helper de barra horizontal proporcional ao % do total
    function barCell(valor, valorMax, formatter, classExtra) {
        var v = Number(valor || 0);
        var max = Number(valorMax || 0);
        var pct = max > 0 ? Math.min(100, Math.max(0, (Math.abs(v) / max) * 100)) : 0;
        var cls = 'rel-bar-cell' + (classExtra ? ' ' + classExtra : '');
        return '<td class="num destaque ' + cls + '" style="--bar-pct: ' + pct.toFixed(1) + '%">' +
               formatter(v) + '</td>';
    }

    // -----------------------------------------------------------------------
    // DRILLDOWN — modal compartilhado
    // -----------------------------------------------------------------------
    var DRILL = {
        overlay: null,
        titulo: null,
        subtitulo: null,
        body: null,
        footer: null,
        totais: null,
        link: null,
    };

    function initDrilldown() {
        DRILL.overlay = document.getElementById('relDrilldownOverlay');
        if (!DRILL.overlay) return;
        DRILL.titulo = document.getElementById('relDrillTitulo');
        DRILL.subtitulo = document.getElementById('relDrillSubtitulo');
        DRILL.body = document.getElementById('relDrillBody');
        DRILL.footer = document.getElementById('relDrillFooter');
        DRILL.totais = document.getElementById('relDrillTotais');
        DRILL.link = document.getElementById('relDrillLinkModulo');

        // Fechar
        DRILL.overlay.addEventListener('click', function (ev) {
            if (ev.target === DRILL.overlay || ev.target.closest('[data-close-drill]')) {
                fecharDrilldown();
            }
        });
        document.addEventListener('keydown', function (ev) {
            if (ev.key === 'Escape' && DRILL.overlay.getAttribute('aria-hidden') === 'false') {
                fecharDrilldown();
            }
        });
    }

    function abrirDrilldown(params) {
        if (!DRILL.overlay) return;
        DRILL.titulo.textContent = 'Carregando...';
        DRILL.subtitulo.textContent = '';
        DRILL.body.innerHTML = '<div class="rel-empty"><i class="ph ph-spinner" aria-hidden="true"></i><span>Buscando dados...</span></div>';
        DRILL.footer.hidden = true;
        DRILL.totais.innerHTML = '';
        DRILL.link.hidden = true;
        DRILL.overlay.setAttribute('aria-hidden', 'false');

        var q = new URLSearchParams();
        q.set('tipo', params.tipo);
        q.set('id', String(params.id));
        if (params.date_de)  q.set('date_de', params.date_de);
        if (params.date_ate) q.set('date_ate', params.date_ate);
        if (params.agrupar)  q.set('agrupar', params.agrupar);

        fetchSimples('/sankhya/relatorios/api/drilldown/?' + q.toString())
            .then(function (body) {
                if (!body || body.ok === false) {
                    DRILL.titulo.textContent = 'Erro';
                    DRILL.body.innerHTML = '<div class="rel-error"><i class="ph ph-warning-circle"></i><span>' +
                        escapeHtml((body && body.error) || 'Falha ao buscar detalhe.') + '</span></div>';
                    return;
                }
                renderDrilldown(body, params);
            });
    }

    function fecharDrilldown() {
        if (DRILL.overlay) DRILL.overlay.setAttribute('aria-hidden', 'true');
    }

    function topBadge(codtipoper) {
        var t = parseInt(codtipoper, 10);
        var label = {
            10: 'Comb.', 11: 'Compra', 13: 'Vale', 26: 'Classif.',
            30: 'Avaria', 33: 'Ajuste', 34: 'PDV',
            35: 'NFe', 36: 'Devol.', 37: 'S/NFe', 53: 'Req.',
        }[t] || String(codtipoper || '—');
        return '<span class="rel-top-mini rel-top-mini--' + t + '">' + label + '</span>';
    }

    function renderDrilldown(body, params) {
        DRILL.titulo.textContent = body.titulo || 'Detalhe';
        DRILL.subtitulo.textContent = body.subtitulo || '';

        var linhas = body.linhas || [];
        var totais = body.totais || {};
        if (linhas.length === 0) {
            DRILL.body.innerHTML = '<div class="rel-empty">' +
                '<i class="ph ph-magnifying-glass"></i>' +
                '<span>Sem detalhes pra mostrar.</span></div>';
            return;
        }

        var html = '<table class="rel-tabela">';
        var tipo = body.tipo;

        if (tipo === 'cliente_vendas') {
            html += '<thead><tr><th>Data</th><th>Pedido</th><th>TOP</th><th>Produto</th><th class="num">Qtd</th><th class="num">Vlr Unit</th><th class="num">Total</th></tr></thead><tbody>';
            linhas.forEach(function (r) {
                html += '<tr>' +
                    '<td>' + escapeHtml(r.dtneg) + '</td>' +
                    '<td><strong>' + (r.numnota || r.nunota || '—') + '</strong></td>' +
                    '<td>' + topBadge(r.codtipoper) + '</td>' +
                    '<td>' + escapeHtml(r.descrprod) + '</td>' +
                    '<td class="num">' + fmtInt(r.qtdneg) + ' ' + escapeHtml(r.codvol || '') + '</td>' +
                    '<td class="num">' + fmtBRL(r.vlrunit) + '</td>' +
                    '<td class="num destaque">' + fmtBRL(r.vlrtot) + '</td>' +
                '</tr>';
            });
            html += '</tbody></table>';
            DRILL.totais.innerHTML = '<strong>' + (totais.count || 0) + '</strong> linha(s) · ' +
                '<strong>' + fmtBRL(totais.vlrtot) + '</strong> total';
            DRILL.footer.hidden = false;
        }
        else if (tipo === 'produto_vendas') {
            html += '<thead><tr><th>Data</th><th>Pedido</th><th>TOP</th><th>Cliente</th><th class="num">Qtd</th><th class="num">Vlr Unit</th><th class="num">Total</th></tr></thead><tbody>';
            linhas.forEach(function (r) {
                html += '<tr>' +
                    '<td>' + escapeHtml(r.dtneg) + '</td>' +
                    '<td><strong>' + (r.numnota || r.nunota || '—') + '</strong></td>' +
                    '<td>' + topBadge(r.codtipoper) + '</td>' +
                    '<td>' + escapeHtml(r.cliente) + '</td>' +
                    '<td class="num">' + fmtInt(r.qtdneg) + ' ' + escapeHtml(r.codvol || '') + '</td>' +
                    '<td class="num">' + fmtBRL(r.vlrunit) + '</td>' +
                    '<td class="num destaque">' + fmtBRL(r.vlrtot) + '</td>' +
                '</tr>';
            });
            html += '</tbody></table>';
            DRILL.totais.innerHTML = '<strong>' + (totais.count || 0) + '</strong> venda(s) · ' +
                '<strong>' + fmtKg(totais.qtdneg) + '</strong> · ' +
                '<strong>' + fmtBRL(totais.vlrtot) + '</strong> total';
            DRILL.footer.hidden = false;
        }
        else if (tipo === 'lote_movs') {
            html += '<thead><tr><th>Data</th><th>TOP</th><th>Nota</th><th>Status</th><th>Parceiro</th><th>Produto</th><th class="num">Qtd</th><th class="num">Total</th></tr></thead><tbody>';
            linhas.forEach(function (r) {
                html += '<tr>' +
                    '<td>' + escapeHtml(r.dtneg) + '</td>' +
                    '<td>' + topBadge(r.codtipoper) + '</td>' +
                    '<td><strong>' + (r.numnota || r.nunota || '—') + '</strong></td>' +
                    '<td>' + escapeHtml(r.statusnota || '—') + '</td>' +
                    '<td>' + escapeHtml(r.parc) + '</td>' +
                    '<td>' + escapeHtml(r.descrprod) + '</td>' +
                    '<td class="num">' + fmtInt(r.qtdneg) + ' ' + escapeHtml(r.codvol || '') + '</td>' +
                    '<td class="num destaque">' + fmtBRL(r.vlrtot) + '</td>' +
                '</tr>';
            });
            html += '</tbody></table>';
            DRILL.totais.innerHTML = '<strong>' + (totais.count || 0) + '</strong> movimentação(ões)';
            DRILL.footer.hidden = false;
            // Link "Abrir no módulo Rastreio" com o lote pré-filtrado
            if (params.id) {
                DRILL.link.href = '/sankhya/rastreio/?lote=' + encodeURIComponent(params.id);
                DRILL.link.hidden = false;
            }
        }
        else if (tipo === 'veiculo_reqs') {
            html += '<thead><tr><th>Data</th><th>Tipo</th><th>Produto</th><th class="num">Litros</th><th class="num">Vlr Unit</th><th class="num">Total</th><th class="num">km/h</th></tr></thead><tbody>';
            linhas.forEach(function (r) {
                var medidor = r.hodometro != null ? fmtInt(r.hodometro) + ' km' :
                              r.horimetro != null ? fmtInt(r.horimetro) + ' h' : '—';
                html += '<tr>' +
                    '<td>' + escapeHtml(r.dtneg) + '</td>' +
                    '<td>' + escapeHtml(r.tipo || topBadge(r.codtipoper)) + '</td>' +
                    '<td>' + escapeHtml(r.descrprod) + '</td>' +
                    '<td class="num destaque">' + fmtInt(r.qtdneg) + ' L</td>' +
                    '<td class="num">' + fmtBRL(r.vlrunit) + '</td>' +
                    '<td class="num">' + fmtBRL(r.vlrtot) + '</td>' +
                    '<td class="num">' + medidor + '</td>' +
                '</tr>';
            });
            html += '</tbody></table>';
            DRILL.totais.innerHTML = '<strong>' + (totais.count || 0) + '</strong> req(s) · ' +
                '<strong>' + fmtInt(totais.litros) + ' L</strong> · ' +
                '<strong>' + fmtBRL(totais.vlrtot) + '</strong> total';
            DRILL.footer.hidden = false;
            if (params.id) {
                DRILL.link.href = '/sankhya/combustivel/';
                DRILL.link.hidden = false;
            }
        }
        else if (tipo === 'fluxo_bucket') {
            html += '<thead><tr><th>Venc.</th><th>NUFIN</th><th>NUNOTA</th><th>Parceiro</th><th>Histórico</th><th class="num">Valor</th></tr></thead><tbody>';
            linhas.forEach(function (r) {
                var corVlr = r.recdesp > 0 ? '#15803d' : r.recdesp < 0 ? '#b91c1c' : '#475569';
                var sinal = r.recdesp > 0 ? '+' : r.recdesp < 0 ? '−' : '';
                html += '<tr>' +
                    '<td>' + escapeHtml(r.dtvenc) + '</td>' +
                    '<td>' + (r.nufin || '—') + '</td>' +
                    '<td>' + (r.nunota || '—') + '</td>' +
                    '<td>' + escapeHtml(r.parc) + '</td>' +
                    '<td>' + escapeHtml(r.historico) + '</td>' +
                    '<td class="num destaque" style="color: ' + corVlr + ';">' + sinal + fmtBRL(r.vlr) + '</td>' +
                '</tr>';
            });
            html += '</tbody></table>';
            DRILL.totais.innerHTML = '<strong>' + (totais.count || 0) + '</strong> título(s) · ' +
                'Entrada <strong>' + fmtBRL(totais.entrada) + '</strong> · ' +
                'Saída <strong>' + fmtBRL(totais.saida) + '</strong>';
            DRILL.footer.hidden = false;
        }
        else if (tipo === 'margem_detalhe') {
            html += '<thead><tr><th>Data</th><th>Pedido</th><th>' +
                (params.agrupar === 'cliente' ? 'Produto' : 'Cliente') +
                '</th><th>Lote</th><th class="num">Receita</th><th class="num">Custo</th><th class="num">Lucro</th><th class="num">M %</th></tr></thead><tbody>';
            linhas.forEach(function (r) {
                var corM = r.margem_pct >= 15 ? '#15803d' :
                           r.margem_pct >= 5  ? '#ca8a04' :
                           r.margem_pct >= 0  ? '#d97706' : '#b91c1c';
                var nomeOutro = params.agrupar === 'cliente' ? r.descrprod : r.cliente;
                html += '<tr>' +
                    '<td>' + escapeHtml(r.dtneg) + '</td>' +
                    '<td><strong>' + (r.numnota || r.nunota || '—') + '</strong></td>' +
                    '<td>' + escapeHtml(nomeOutro) + '</td>' +
                    '<td><code style="font-size:0.74rem;">' + escapeHtml(r.codagregacao) + '</code></td>' +
                    '<td class="num">' + fmtBRL(r.receita) + '</td>' +
                    '<td class="num" style="color:#b91c1c;">' + fmtBRL(r.custo) + '</td>' +
                    '<td class="num destaque" style="color: ' + (r.lucro >= 0 ? '#15803d' : '#b91c1c') + ';">' + fmtBRL(r.lucro) + '</td>' +
                    '<td class="num destaque" style="color: ' + corM + ';">' + fmtPct(r.margem_pct) + '</td>' +
                '</tr>';
            });
            html += '</tbody></table>';
            DRILL.totais.innerHTML = '<strong>' + (totais.count || 0) + '</strong> venda(s) · ' +
                'Lucro <strong style="color: ' + (totais.lucro >= 0 ? '#15803d' : '#b91c1c') + ';">' +
                fmtBRL(totais.lucro) + '</strong> · ' +
                'Margem média <strong>' + fmtPct(totais.margem_media) + '</strong>';
            DRILL.footer.hidden = false;
        }

        DRILL.body.innerHTML = html;
    }

    // -----------------------------------------------------------------------
    // RENDERERS — 1 por relatório
    // -----------------------------------------------------------------------
    var RENDERERS = {};

    // ===== 1. TOP CLIENTES + TOP PRODUTOS =====
    RENDERERS['top-clientes'] = (function () {
        var carregado = false;
        var pane = document.getElementById('painel-top-clientes');

        function carregar(force) {
            if (carregado && !force) return;
            var periodo = periodoAtivo(pane);
            var metrica = pane.querySelector('#topClientesMetrica').value || 'valor';
            var atual = periodoToDatas(periodo);
            var anterior = periodoEspelhadoAnterior(periodo);

            var urlAtual = '/sankhya/relatorios/api/top-clientes-produtos/' +
                '?date_de=' + atual.date_de + '&date_ate=' + atual.date_ate +
                '&metrica=' + metrica;
            var urlAnt = '/sankhya/relatorios/api/top-clientes-produtos/' +
                '?date_de=' + anterior.date_de + '&date_ate=' + anterior.date_ate +
                '&metrica=' + metrica;

            // Fetch atual + anterior em paralelo. Anterior é informativa — falha silenciosa.
            Promise.all([
                carregar_real(pane, urlAtual),
                fetchSimples(urlAnt),
            ]).then(function (results) {
                var body = results[0];
                if (!body) return;
                var anteriorBody = (results[1] && results[1].ok !== false) ? results[1] : null;
                render(body, anteriorBody, metrica, atual);
                carregado = true;
            });
        }

        function render(body, ant, metrica, atual) {
            var conteudo = pane.querySelector('.rel-conteudo');
            var clientes = body.top_clientes || [];
            var produtos = body.top_produtos || [];
            var totalClientes = body.total_geral_clientes || 0;
            var totalProdutos = body.total_geral_produtos || 0;
            var labelMetrica = metrica === 'valor' ? 'Valor' :
                               metrica === 'qtd'   ? 'Quantidade' : 'Pedidos';
            var fmtMetrica = metrica === 'valor' ? fmtBRL :
                             metrica === 'qtd'   ? fmtKg  : fmtInt;

            if (clientes.length === 0 && produtos.length === 0) {
                renderVazio(conteudo, 'Sem vendas no período.', 'Tente outro período acima.');
                return;
            }

            var totalAnt = ant ? (ant.total_geral_clientes || 0) : null;
            var maxCliente = clientes.length ? Number(clientes[0].metrica || 0) : 0;
            var maxProduto = produtos.length ? Number(produtos[0].metrica || 0) : 0;

            var resumoHtml = '' +
                '<div class="rel-resumo">' +
                    '<div class="rel-resumo-card">' +
                        '<span class="rel-resumo-label">' + labelMetrica + ' total</span>' +
                        '<span class="rel-resumo-valor">' + fmtMetrica(totalClientes) + '</span>' +
                        '<span class="rel-resumo-footer">' + compChipHtml(totalClientes, totalAnt) + '</span>' +
                    '</div>' +
                    '<div class="rel-resumo-card">' +
                        '<span class="rel-resumo-label">Clientes ativos</span>' +
                        '<span class="rel-resumo-valor">' + fmtInt(clientes.length) + '</span>' +
                        '<span class="rel-resumo-footer">Top 15 listado abaixo</span>' +
                    '</div>' +
                    '<div class="rel-resumo-card">' +
                        '<span class="rel-resumo-label">Produtos vendidos</span>' +
                        '<span class="rel-resumo-valor">' + fmtInt(produtos.length) + '</span>' +
                        '<span class="rel-resumo-footer">Top 15 listado abaixo</span>' +
                    '</div>' +
                '</div>';

            var clientesHtml = '' +
                '<div>' +
                    '<h4 style="margin: 0 0 8px 0; color: #1e293b; font-size: 0.95rem;">' +
                        '<i class="ph ph-users" style="color:#5e7e4a;"></i> Top Clientes' +
                    '</h4>' +
                    '<table class="rel-tabela">' +
                        '<thead><tr>' +
                            '<th style="width: 28px;">#</th>' +
                            '<th>Cliente</th>' +
                            '<th class="num">' + labelMetrica + '</th>' +
                            '<th class="num" style="width: 60px;">%</th>' +
                        '</tr></thead>' +
                        '<tbody>' +
                            clientes.map(function (r, i) {
                                var v = Number(r.metrica || 0);
                                var pct = totalClientes > 0 ? (v / totalClientes * 100) : 0;
                                return '<tr class="rel-row-clickable" ' +
                                    'data-drill="cliente_vendas" data-id="' + (r.codparc || '') + '" ' +
                                    'data-de="' + atual.date_de + '" data-ate="' + atual.date_ate + '" ' +
                                    'title="Ver vendas detalhadas">' +
                                    '<td>' + (i + 1) + '</td>' +
                                    '<td title="' + escapeHtml(r.nome_full || r.nome) + '">' + escapeHtml(r.nome) + '</td>' +
                                    barCell(v, maxCliente, fmtMetrica) +
                                    '<td class="num">' + pct.toFixed(1).replace('.', ',') + '%</td>' +
                                '</tr>';
                            }).join('') +
                        '</tbody>' +
                    '</table>' +
                '</div>';

            var produtosHtml = '' +
                '<div>' +
                    '<h4 style="margin: 0 0 8px 0; color: #1e293b; font-size: 0.95rem;">' +
                        '<i class="ph ph-package" style="color:#5e7e4a;"></i> Top Produtos' +
                    '</h4>' +
                    '<table class="rel-tabela">' +
                        '<thead><tr>' +
                            '<th style="width: 28px;">#</th>' +
                            '<th>Produto</th>' +
                            '<th class="num">' + labelMetrica + '</th>' +
                            '<th class="num" style="width: 60px;">%</th>' +
                        '</tr></thead>' +
                        '<tbody>' +
                            produtos.map(function (r, i) {
                                var v = Number(r.metrica || 0);
                                var pct = totalProdutos > 0 ? (v / totalProdutos * 100) : 0;
                                return '<tr class="rel-row-clickable" ' +
                                    'data-drill="produto_vendas" data-id="' + (r.codprod || '') + '" ' +
                                    'data-de="' + atual.date_de + '" data-ate="' + atual.date_ate + '" ' +
                                    'title="Ver vendas detalhadas">' +
                                    '<td>' + (i + 1) + '</td>' +
                                    '<td>' + escapeHtml(r.descrprod) + '</td>' +
                                    barCell(v, maxProduto, fmtMetrica) +
                                    '<td class="num">' + pct.toFixed(1).replace('.', ',') + '%</td>' +
                                '</tr>';
                            }).join('') +
                        '</tbody>' +
                    '</table>' +
                '</div>';

            conteudo.innerHTML = resumoHtml +
                '<div style="display:grid; grid-template-columns: 1fr 1fr; gap: 16px;">' +
                    clientesHtml + produtosHtml +
                '</div>';

            bindRowsDrilldown(conteudo);
        }

        if (pane) bindControles(pane, { carregar: carregar });
        return { carregar: carregar };
    })();

    // ===== 2. LOTES ENVELHECIDOS =====
    RENDERERS['lotes-envelhecidos'] = (function () {
        var carregado = false;
        var pane = document.getElementById('painel-lotes-envelhecidos');

        function carregar(force) {
            if (carregado && !force) return;
            var chip = pane.querySelector('.rel-filtro-periodo .rel-chip.is-on');
            var dias = chip ? chip.dataset.dias : '30';
            var url = '/sankhya/relatorios/api/lotes-envelhecidos/?dias_min=' + dias;
            carregar_real(pane, url).then(function (body) {
                if (!body) return;
                render(body, dias);
                carregado = true;
            });
        }

        function render(body, diasMin) {
            var conteudo = pane.querySelector('.rel-conteudo');
            var lotes = body.lotes || [];
            if (lotes.length === 0) {
                renderVazio(conteudo, 'Nenhum lote parado há mais de ' + diasMin + ' dias.',
                            'Bom sinal — o estoque está girando!');
                return;
            }
            // Sumário de status
            var stats = { critico: 0, alerta: 0, atencao: 0, ok: 0, saldoTotal: 0 };
            lotes.forEach(function (l) {
                var d = Number(l.dias_parado || 0);
                stats.saldoTotal += Number(l.qtd_disponivel || 0);
                if (d > 90) stats.critico++;
                else if (d > 60) stats.alerta++;
                else if (d > 30) stats.atencao++;
                else stats.ok++;
            });
            var maxSaldo = Math.max.apply(null,
                lotes.map(function (l) { return Number(l.qtd_disponivel || 0); })
            );

            var resumoHtml = '' +
                '<div class="rel-resumo">' +
                    '<div class="rel-resumo-card">' +
                        '<span class="rel-resumo-label">Lotes parados</span>' +
                        '<span class="rel-resumo-valor">' + fmtInt(lotes.length) + '</span>' +
                        '<span class="rel-resumo-footer">há mais de ' + diasMin + ' dias</span>' +
                    '</div>' +
                    '<div class="rel-resumo-card rel-resumo-card--saida">' +
                        '<span class="rel-resumo-label">Críticos (&gt;90d)</span>' +
                        '<span class="rel-resumo-valor">' + fmtInt(stats.critico) + '</span>' +
                        '<span class="rel-resumo-footer">priorize vender</span>' +
                    '</div>' +
                    '<div class="rel-resumo-card">' +
                        '<span class="rel-resumo-label">Saldo total parado</span>' +
                        '<span class="rel-resumo-valor">' + fmtKg(stats.saldoTotal) + '</span>' +
                        '<span class="rel-resumo-footer">soma dos lotes acima</span>' +
                    '</div>' +
                '</div>';

            conteudo.innerHTML = resumoHtml +
                '<table class="rel-tabela">' +
                    '<thead><tr>' +
                        '<th>Lote</th><th>Produto</th><th>Fornecedor</th>' +
                        '<th class="num">Entrada</th><th class="num">Saldo</th>' +
                        '<th class="num">Dias</th><th>Bandeira</th>' +
                    '</tr></thead>' +
                    '<tbody>' +
                        lotes.map(function (l) {
                            var dias = Number(l.dias_parado || 0);
                            var bandeira =
                                dias > 90 ? 'vermelho' :
                                dias > 60 ? 'laranja'  :
                                dias > 30 ? 'amarelo'  : 'azul';
                            var label =
                                dias > 90 ? 'CRÍTICO' :
                                dias > 60 ? 'ALERTA'  :
                                dias > 30 ? 'ATENÇÃO' : 'OK';
                            var barClass = dias > 60 ? 'rel-bar-cell--warn' : '';
                            return '<tr class="rel-row-clickable" ' +
                                'data-drill="lote_movs" data-id="' + escapeHtml(l.codagregacao) + '" ' +
                                'title="Ver movimentações do lote">' +
                                '<td><code>' + escapeHtml(l.codagregacao) + '</code></td>' +
                                '<td>' + escapeHtml(l.descrprod || '—') + '</td>' +
                                '<td>' + escapeHtml(l.fornecedor || '—') + '</td>' +
                                '<td class="num">' + fmtKg(l.qtd_entrada) + '</td>' +
                                barCell(l.qtd_disponivel, maxSaldo, fmtKg, barClass) +
                                '<td class="num">' + dias + ' d</td>' +
                                '<td><span class="rel-bandeira rel-bandeira--' + bandeira + '">' + label + '</span></td>' +
                            '</tr>';
                        }).join('') +
                    '</tbody>' +
                '</table>';

            bindRowsDrilldown(conteudo);
        }

        if (pane) bindControles(pane, { carregar: carregar });
        return { carregar: carregar };
    })();

    // ===== 3. CONSUMO POR VEÍCULO =====
    RENDERERS['consumo-veiculo'] = (function () {
        var carregado = false;
        var pane = document.getElementById('painel-consumo-veiculo');

        function carregar(force) {
            if (carregado && !force) return;
            var periodo = periodoAtivo(pane);
            var tipo = pane.querySelector('#consumoTipoVeic').value || '';
            var atual = periodoToDatas(periodo);
            var anterior = periodoEspelhadoAnterior(periodo);

            var paramsAtual = new URLSearchParams({
                date_de: atual.date_de, date_ate: atual.date_ate,
            });
            var paramsAnt = new URLSearchParams({
                date_de: anterior.date_de, date_ate: anterior.date_ate,
            });
            if (tipo) { paramsAtual.set('tipo', tipo); paramsAnt.set('tipo', tipo); }

            Promise.all([
                carregar_real(pane, '/sankhya/relatorios/api/consumo-veiculos/?' + paramsAtual),
                fetchSimples('/sankhya/relatorios/api/consumo-veiculos/?' + paramsAnt),
            ]).then(function (results) {
                var body = results[0];
                if (!body) return;
                var ant = (results[1] && results[1].ok !== false) ? results[1] : null;
                render(body, ant, atual);
                carregado = true;
            });
        }

        function render(body, ant, atual) {
            var conteudo = pane.querySelector('.rel-conteudo');
            var veiculos = body.veiculos || [];
            if (veiculos.length === 0) {
                renderVazio(conteudo, 'Sem requisições de combustível no período.',
                            'Tente um período maior.');
                return;
            }
            var totalLitros = body.total_litros || 0;
            var totalValor  = body.total_valor  || 0;
            var antLitros = ant ? (ant.total_litros || 0) : null;
            var antValor  = ant ? (ant.total_valor  || 0) : null;
            var maxLitros = Math.max.apply(null,
                veiculos.map(function (v) { return Number(v.litros_total || 0); })
            );

            var resumoHtml = '' +
                '<div class="rel-resumo">' +
                    '<div class="rel-resumo-card">' +
                        '<span class="rel-resumo-label">Litros total</span>' +
                        '<span class="rel-resumo-valor">' + fmtInt(totalLitros) + ' L</span>' +
                        '<span class="rel-resumo-footer">' + compChipHtml(totalLitros, antLitros, { invertirCor: true }) + '</span>' +
                    '</div>' +
                    '<div class="rel-resumo-card">' +
                        '<span class="rel-resumo-label">Valor total</span>' +
                        '<span class="rel-resumo-valor">' + fmtBRL(totalValor) + '</span>' +
                        '<span class="rel-resumo-footer">' + compChipHtml(totalValor, antValor, { invertirCor: true }) + '</span>' +
                    '</div>' +
                    '<div class="rel-resumo-card">' +
                        '<span class="rel-resumo-label">Veículos ativos</span>' +
                        '<span class="rel-resumo-valor">' + fmtInt(veiculos.length) + '</span>' +
                        '<span class="rel-resumo-footer">com requisições no período</span>' +
                    '</div>' +
                '</div>';

            conteudo.innerHTML = resumoHtml +
                '<table class="rel-tabela">' +
                    '<thead><tr>' +
                        '<th style="width: 28px;">#</th>' +
                        '<th>Placa</th><th>Veículo</th><th>Tipo</th>' +
                        '<th class="num">Litros</th>' +
                        '<th class="num">Valor</th>' +
                        '<th class="num">km / h</th>' +
                        '<th class="num">Eficiência</th>' +
                        '<th class="num">Nº reqs</th>' +
                    '</tr></thead>' +
                    '<tbody>' +
                        veiculos.map(function (v, i) {
                            var efic = v.eficiencia_label || '—';
                            return '<tr class="rel-row-clickable" ' +
                                'data-drill="veiculo_reqs" data-id="' + (v.codveiculo || '') + '" ' +
                                'data-de="' + atual.date_de + '" data-ate="' + atual.date_ate + '" ' +
                                'title="Ver requisições do veículo">' +
                                '<td>' + (i + 1) + '</td>' +
                                '<td><strong>' + escapeHtml(v.placa || '—') + '</strong></td>' +
                                '<td>' + escapeHtml(v.marcamodelo || '—') + '</td>' +
                                '<td><span class="rel-bandeira rel-bandeira--' + (v.tipo === 'MAQ' ? 'azul' : 'verde') + '">' + (v.tipo || '—') + '</span></td>' +
                                barCell(v.litros_total, maxLitros, function (x) { return fmtInt(x) + ' L'; }) +
                                '<td class="num">' + fmtBRL(v.valor_total) + '</td>' +
                                '<td class="num">' + (v.medidor_total != null ? fmtInt(v.medidor_total) : '—') + '</td>' +
                                '<td class="num">' + efic + '</td>' +
                                '<td class="num">' + fmtInt(v.qtd_reqs) + '</td>' +
                            '</tr>';
                        }).join('') +
                    '</tbody>' +
                '</table>';

            bindRowsDrilldown(conteudo);
        }

        if (pane) bindControles(pane, { carregar: carregar });
        return { carregar: carregar };
    })();

    // ===== 4. FLUXO DE CAIXA =====
    RENDERERS['fluxo-caixa'] = (function () {
        var carregado = false;
        var pane = document.getElementById('painel-fluxo-caixa');

        function carregar(force) {
            if (carregado && !force) return;
            var chip = pane.querySelector('.rel-filtro-periodo .rel-chip.is-on');
            var horizonte = chip ? chip.dataset.horizonte : '60';
            var url = '/sankhya/relatorios/api/fluxo-caixa/?dias=' + horizonte;
            carregar_real(pane, url).then(function (body) {
                if (!body) return;
                render(body, horizonte);
                carregado = true;
            });
        }

        function render(body, horizonte) {
            var conteudo = pane.querySelector('.rel-conteudo');
            var buckets = body.buckets || [];
            if (buckets.length === 0) {
                renderVazio(conteudo, 'Sem títulos abertos no horizonte.',
                            'Tente um horizonte maior.');
                return;
            }
            var totalEntrada = body.total_entrada || 0;
            var totalSaida   = body.total_saida   || 0;
            var saldo        = totalEntrada - totalSaida;
            var saldoNeg     = saldo < 0;

            var resumoHtml = '' +
                '<div class="rel-resumo">' +
                    '<div class="rel-resumo-card rel-resumo-card--entrada">' +
                        '<span class="rel-resumo-label">Entradas (a receber)</span>' +
                        '<span class="rel-resumo-valor">' + fmtBRL(totalEntrada) + '</span>' +
                        '<span class="rel-resumo-footer">' + buckets.length + ' bucket(s) · ' + horizonte + 'd</span>' +
                    '</div>' +
                    '<div class="rel-resumo-card rel-resumo-card--saida">' +
                        '<span class="rel-resumo-label">Saídas (a pagar)</span>' +
                        '<span class="rel-resumo-valor">' + fmtBRL(totalSaida) + '</span>' +
                        '<span class="rel-resumo-footer">títulos despesa em aberto</span>' +
                    '</div>' +
                    '<div class="rel-resumo-card rel-resumo-card--' + (saldoNeg ? 'saldo-neg' : 'saldo') + '">' +
                        '<span class="rel-resumo-label">Saldo projetado</span>' +
                        '<span class="rel-resumo-valor">' + fmtBRL(saldo) + '</span>' +
                        '<span class="rel-resumo-footer">' + (saldoNeg ? '⚠ revisar pagamentos' : '✓ caixa positivo') + '</span>' +
                    '</div>' +
                '</div>';

            // Bar máxima: maior absoluto entre entradas e saídas dos buckets
            var maxVal = 0;
            buckets.forEach(function (b) {
                maxVal = Math.max(maxVal,
                    Math.abs(Number(b.entrada || 0)),
                    Math.abs(Number(b.saida || 0))
                );
            });

            conteudo.innerHTML = resumoHtml +
                '<table class="rel-tabela">' +
                    '<thead><tr>' +
                        '<th>Período</th>' +
                        '<th class="num">Entradas</th>' +
                        '<th class="num">Saídas</th>' +
                        '<th class="num">Saldo</th>' +
                        '<th class="num">Acumulado</th>' +
                    '</tr></thead>' +
                    '<tbody>' +
                        buckets.map(function (b) {
                            var entr = Number(b.entrada) || 0;
                            var said = Number(b.saida) || 0;
                            var s = entr - said;
                            var ac = Number(b.saldo_acumulado || 0);
                            var label = b.label;
                            return '<tr class="rel-row-clickable" ' +
                                'data-drill="fluxo_bucket" data-id="' + escapeHtml(label) + '" ' +
                                'title="Ver títulos do bucket">' +
                                '<td>' + escapeHtml(label) + '</td>' +
                                barCell(entr, maxVal, fmtBRL) +
                                barCell(said, maxVal, fmtBRL, 'rel-bar-cell--neg') +
                                '<td class="num destaque" style="color:' + (s >= 0 ? '#15803d' : '#b91c1c') + ';">' + fmtBRL(s) + '</td>' +
                                '<td class="num destaque" style="color:' + (ac >= 0 ? '#15803d' : '#b91c1c') + ';">' + fmtBRL(ac) + '</td>' +
                            '</tr>';
                        }).join('') +
                    '</tbody>' +
                '</table>';

            bindRowsDrilldown(conteudo);
        }

        if (pane) bindControles(pane, { carregar: carregar });
        return { carregar: carregar };
    })();

    // ===== 5. MARGEM POR VENDA =====
    RENDERERS['margem-venda'] = (function () {
        var carregado = false;
        var pane = document.getElementById('painel-margem-venda');

        function carregar(force) {
            if (carregado && !force) return;
            var periodo = periodoAtivo(pane);
            var agrupar = pane.querySelector('#margemAgrupar').value || 'cliente';
            var atual = periodoToDatas(periodo);
            var anterior = periodoEspelhadoAnterior(periodo);

            var urlAtual = '/sankhya/relatorios/api/margem-venda/' +
                '?date_de=' + atual.date_de + '&date_ate=' + atual.date_ate +
                '&agrupar=' + agrupar;
            var urlAnt = '/sankhya/relatorios/api/margem-venda/' +
                '?date_de=' + anterior.date_de + '&date_ate=' + anterior.date_ate +
                '&agrupar=' + agrupar;

            Promise.all([
                carregar_real(pane, urlAtual),
                fetchSimples(urlAnt),
            ]).then(function (results) {
                var body = results[0];
                if (!body) return;
                var ant = (results[1] && results[1].ok !== false) ? results[1] : null;
                render(body, ant, agrupar, atual);
                carregado = true;
            });
        }

        function render(body, ant, agrupar, atual) {
            var conteudo = pane.querySelector('.rel-conteudo');
            var linhas = body.linhas || [];
            if (linhas.length === 0) {
                renderVazio(conteudo, 'Sem vendas com custo identificado no período.',
                            'Margem requer JOIN com vale (TOP 13) — pode ser lote externo ou sem vale lançado.');
                return;
            }
            var labelCol = agrupar === 'cliente' ? 'Cliente' : 'Produto';

            var totalReceita = body.total_receita || 0;
            var totalLucro   = body.total_lucro   || 0;
            var margemMedia  = body.margem_media  || 0;
            var antLucro = ant ? (ant.total_lucro || 0) : null;
            var antMargem = ant ? (ant.margem_media || 0) : null;
            var maxReceita = Math.max.apply(null,
                linhas.map(function (r) { return Number(r.receita || 0); })
            );

            var resumoHtml = '' +
                '<div class="rel-resumo">' +
                    '<div class="rel-resumo-card">' +
                        '<span class="rel-resumo-label">Receita total</span>' +
                        '<span class="rel-resumo-valor">' + fmtBRL(totalReceita) + '</span>' +
                        '<span class="rel-resumo-footer">' + linhas.length + ' ' + labelCol.toLowerCase() + '(s)</span>' +
                    '</div>' +
                    '<div class="rel-resumo-card rel-resumo-card--' + (totalLucro >= 0 ? 'saldo' : 'saldo-neg') + '">' +
                        '<span class="rel-resumo-label">Lucro total</span>' +
                        '<span class="rel-resumo-valor">' + fmtBRL(totalLucro) + '</span>' +
                        '<span class="rel-resumo-footer">' + compChipHtml(totalLucro, antLucro) + '</span>' +
                    '</div>' +
                    '<div class="rel-resumo-card">' +
                        '<span class="rel-resumo-label">Margem média</span>' +
                        '<span class="rel-resumo-valor">' + fmtPct(margemMedia) + '</span>' +
                        '<span class="rel-resumo-footer">' + compChipHtml(margemMedia, antMargem) + '</span>' +
                    '</div>' +
                '</div>';

            conteudo.innerHTML = resumoHtml +
                '<table class="rel-tabela">' +
                    '<thead><tr>' +
                        '<th style="width: 28px;">#</th>' +
                        '<th>' + labelCol + '</th>' +
                        '<th class="num">Receita</th>' +
                        '<th class="num">Custo</th>' +
                        '<th class="num">Lucro</th>' +
                        '<th class="num">Margem %</th>' +
                        '<th>Bandeira</th>' +
                    '</tr></thead>' +
                    '<tbody>' +
                        linhas.map(function (r, i) {
                            var m = Number(r.margem_pct || 0);
                            var bandeira =
                                m >= 15 ? 'verde'    :
                                m >= 5  ? 'amarelo'  :
                                m >= 0  ? 'laranja'  : 'vermelho';
                            var label =
                                m >= 15 ? 'BOM' :
                                m >= 5  ? 'OK'  :
                                m >= 0  ? 'BAIXA' : 'PREJU';
                            return '<tr class="rel-row-clickable" ' +
                                'data-drill="margem_detalhe" data-id="' + (r.codigo || '') + '" ' +
                                'data-de="' + atual.date_de + '" data-ate="' + atual.date_ate + '" ' +
                                'data-agrupar="' + agrupar + '" ' +
                                'title="Ver vendas que compuseram a margem">' +
                                '<td>' + (i + 1) + '</td>' +
                                '<td>' + escapeHtml(r.nome) + '</td>' +
                                barCell(r.receita, maxReceita, fmtBRL) +
                                '<td class="num">' + fmtBRL(r.custo) + '</td>' +
                                '<td class="num destaque" style="color:' + (r.lucro >= 0 ? '#15803d' : '#b91c1c') + ';">' + fmtBRL(r.lucro) + '</td>' +
                                '<td class="num destaque">' + fmtPct(m) + '</td>' +
                                '<td><span class="rel-bandeira rel-bandeira--' + bandeira + '">' + label + '</span></td>' +
                            '</tr>';
                        }).join('') +
                    '</tbody>' +
                '</table>';

            bindRowsDrilldown(conteudo);
        }

        if (pane) bindControles(pane, { carregar: carregar });
        return { carregar: carregar };
    })();

    // -----------------------------------------------------------------------
    // Bind delegation pra rows com data-drill
    // -----------------------------------------------------------------------
    function bindRowsDrilldown(container) {
        var rows = container.querySelectorAll('.rel-row-clickable[data-drill]');
        rows.forEach(function (tr) {
            tr.addEventListener('click', function () {
                var tipo = tr.getAttribute('data-drill');
                var id = tr.getAttribute('data-id');
                if (!tipo || !id) return;
                abrirDrilldown({
                    tipo: tipo,
                    id: id,
                    date_de: tr.getAttribute('data-de') || '',
                    date_ate: tr.getAttribute('data-ate') || '',
                    agrupar: tr.getAttribute('data-agrupar') || '',
                });
            });
        });
    }

    // -----------------------------------------------------------------------
    // BOOT
    // -----------------------------------------------------------------------
    initDrilldown();
    document.querySelectorAll('.rel-tab').forEach(function (btn) {
        btn.addEventListener('click', function () { ativarTab(btn.dataset.rel); });
    });
    // Carrega o primeiro relatório ao montar a tela
    if (RENDERERS['top-clientes']) RENDERERS['top-clientes'].carregar();
})();
