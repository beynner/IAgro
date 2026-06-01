/* ============================================================================
   COMERCIAL MOBILE — versão app-like (Mai/2026 — 2026-05-29)
   IIFE escopada. Só ativa em viewport <=900px (ou device touch).
   Reusa endpoints existentes do Comercial (zero novo endpoint backend).
   - GET  /sankhya/comercial/lista/                  (listagem)
   - GET  /sankhya/comercial/api/margem-lote/        (margem)
   - GET  /sankhya/comercial/api/vendas-lote/        (sparkline)
   - POST /sankhya/comercial/api/atualizar-preco/    (editar preço)
   - POST /sankhya/comercial/api/atualizar-peso/     (peso classificado)
   - window.ComercialFinanceiro.abrir(nunota)        (modal Faturamento desktop)
   ============================================================================ */
(function () {
    'use strict';

    // Ativa só em viewport mobile ou touch real (tablet/celular)
    var isMobileViewport = window.matchMedia('(max-width: 900px)').matches;
    var isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
    if (!isMobileViewport && !isTouch) {
        return;
    }

    // ====== Helpers ============================================================
    function $(id) { return document.getElementById(id); }
    function escapeHtml(s) {
        if (s === null || s === undefined) return '';
        return String(s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function fmtBRL(v) {
        var n = Number(v) || 0;
        return 'R$ ' + n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    function fmtBRLcompact(v) {
        var n = Number(v) || 0;
        if (n >= 1000) {
            return 'R$ ' + (n / 1000).toFixed(1).replace('.', ',') + 'k';
        }
        return fmtBRL(n);
    }
    function fmtNum(v, casas) {
        casas = typeof casas === 'number' ? casas : 0;
        var n = Number(v) || 0;
        return n.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
    }
    function fmtPct(v) {
        var n = Number(v) || 0;
        return (n >= 0 ? '+' : '') + n.toFixed(1).replace('.', ',') + '%';
    }
    function fmtDataBR(iso) {
        if (!iso) return '—';
        try {
            // Aceita ISO ou já formatado
            if (/^\d{4}-\d{2}-\d{2}/.test(iso)) {
                var p = iso.substring(0, 10).split('-');
                return p[2] + '/' + p[1] + '/' + p[0];
            }
            return iso;
        } catch (e) { return iso; }
    }
    function parseBR(s) {
        if (s === null || s === undefined) return 0;
        var clean = String(s).trim().replace(/\./g, '').replace(',', '.');
        var n = parseFloat(clean);
        return isNaN(n) ? 0 : n;
    }
    function normalizar(s) {
        if (s === null || s === undefined) return '';
        return String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    }
    function debounce(fn, ms) {
        var t;
        return function () {
            var args = arguments;
            clearTimeout(t);
            t = setTimeout(function () { fn.apply(null, args); }, ms);
        };
    }
    function getCsrf() {
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }
    function mostrarToast(msg, tipo) {
        if (window.IAgro && window.IAgro.showToast) {
            window.IAgro.showToast(msg, tipo || 'info');
            return;
        }
        if (window.ComercialUtils && window.ComercialUtils.mostrarToast) {
            window.ComercialUtils.mostrarToast(msg, tipo === 'error' ? 'erro' : tipo);
            return;
        }
        // fallback
        console.log('[' + (tipo || 'info') + ']', msg);
    }
    function _hojeIso() {
        var d = new Date();
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var dd = String(d.getDate()).padStart(2, '0');
        return d.getFullYear() + '-' + m + '-' + dd;
    }
    function _shiftIso(iso, delta) {
        if (!iso) iso = _hojeIso();
        var p = iso.split('-');
        var d = new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
        d.setDate(d.getDate() + delta);
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var dd = String(d.getDate()).padStart(2, '0');
        return d.getFullYear() + '-' + m + '-' + dd;
    }

    // ====== STATE ==============================================================
    var STATE = {
        listaRows: [],          // todos os itens (linha-a-linha) que vieram do backend
        listaFiltrada: [],      // após search client-side
        valeSelecionado: null,  // dadosDaLinha do vale clicado pra abrir detalhe
        valeMargem: null,       // resposta de /api/margem-lote/
        valeVendas: null,       // resposta de /api/vendas-lote/
        filtros: {
            dataIni: '',
            dataFim: '',
            parceiroCode: '',
            parceiroNome: '',
            produto: '',
            vale: '',
            pendentes: false,
            faturados: false,
        },
        carregando: false,
        searchTermo: '',
    };

    // ====== SCREEN STACK + SHEETS =============================================
    var screens = {
        lista: null,
        detalhe: null,
    };
    var screenAtiva = 'lista';

    function setActiveScreen(name) {
        if (!screens[name]) return;
        Object.keys(screens).forEach(function (k) {
            screens[k].classList.toggle('is-active', k === name);
        });
        screenAtiva = name;
    }

    function pushScreen(name) {
        setActiveScreen(name);
        try { history.pushState({ s: name }, '', '#' + name); } catch (e) {}
    }
    function popScreen() {
        setActiveScreen('lista');
        try { history.replaceState({ s: 'lista' }, '', '#lista'); } catch (e) {}
    }

    function openSheet(name) {
        var sheet = document.querySelector('.comercial-mobile .m-sheet[data-sheet="' + name + '"]');
        if (!sheet) return;
        sheet.setAttribute('aria-hidden', 'false');
    }
    function closeSheet(name) {
        var sheet = document.querySelector('.comercial-mobile .m-sheet[data-sheet="' + name + '"]');
        if (!sheet) return;
        sheet.setAttribute('aria-hidden', 'true');
    }
    function closeAllSheets() {
        document.querySelectorAll('.comercial-mobile .m-sheet').forEach(function (s) {
            s.setAttribute('aria-hidden', 'true');
        });
    }

    // ====== FETCHERS ===========================================================
    function buildQueryString() {
        var qs = new URLSearchParams();
        if (STATE.filtros.dataIni) {
            qs.set('start', STATE.filtros.dataIni);
            qs.set('end', STATE.filtros.dataFim || STATE.filtros.dataIni);
        } else {
            qs.set('days', '60');
        }
        if (STATE.filtros.parceiroCode) qs.set('codparc', STATE.filtros.parceiroCode);
        if (STATE.filtros.vale) qs.set('nunota', STATE.filtros.vale.replace(/\D/g, ''));
        if (STATE.filtros.produto) qs.set('fabricante', STATE.filtros.produto);

        var isP = STATE.filtros.pendentes;
        var isF = STATE.filtros.faturados;
        if (isP && isF) {
            qs.set('faturado', 'T'); qs.set('sem_preco', 'T');
        } else if (isP) {
            qs.set('faturado', 'N'); qs.set('sem_preco', '1');
        } else if (isF) {
            qs.set('faturado', 'S'); qs.set('sem_preco', '0');
        } else {
            qs.set('faturado', 'N'); qs.set('sem_preco', '');
        }
        qs.set('limit', '500');
        qs.set('offset', '0');
        qs.set('_t', Date.now().toString());
        return qs.toString();
    }

    async function carregarLista() {
        STATE.carregando = true;
        renderListaSkeleton();
        atualizarBadgeFiltros();
        try {
            var url = '/sankhya/comercial/lista/?' + buildQueryString();
            var resp = await fetch(url, { cache: 'no-cache' });
            var data = await resp.json();
            STATE.listaRows = Array.isArray(data.rows) ? data.rows : [];
            // Atribui índice estável (paridade com ComercialLista desktop)
            STATE.listaRows.forEach(function (r, i) { r._i = i; });
            STATE.listaFiltrada = STATE.listaRows.slice();
            // share com desktop pra modal de faturamento funcionar
            window.__COM_LIST_ROWS = STATE.listaRows;
            renderLista();
        } catch (err) {
            console.error('Comercial mobile — erro ao carregar lista:', err);
            mostrarToast('Erro ao carregar vales', 'error');
            $('m_cm_lista').innerHTML = '<div class="m-empty-state"><i class="ph ph-warning"></i><p>Erro ao carregar. Tente novamente.</p></div>';
        } finally {
            STATE.carregando = false;
        }
    }

    async function carregarMargem(lote) {
        if (!lote) { STATE.valeMargem = null; return; }
        try {
            var url = '/sankhya/comercial/api/margem-lote/?lote=' + encodeURIComponent(lote);
            var resp = await fetch(url);
            var data = await resp.json();
            STATE.valeMargem = data.ok ? data : null;
        } catch (e) {
            STATE.valeMargem = null;
        }
    }

    async function carregarVendasLote(lote) {
        if (!lote) { STATE.valeVendas = null; return; }
        try {
            var url = '/sankhya/comercial/api/vendas-lote/?lote=' + encodeURIComponent(lote);
            var resp = await fetch(url);
            var data = await resp.json();
            STATE.valeVendas = data.ok ? data : null;
        } catch (e) {
            STATE.valeVendas = null;
        }
    }

    // ====== RENDER LISTA =======================================================
    function renderListaSkeleton() {
        var lista = $('m_cm_lista');
        if (!lista) return;
        if (STATE.listaRows.length === 0) {
            lista.innerHTML = '<div class="m-empty-state"><i class="ph ph-clipboard-text"></i><p>Carregando vales…</p></div>';
        }
    }

    function renderLista() {
        var lista = $('m_cm_lista');
        if (!lista) return;

        var termoBusca = normalizar(STATE.searchTermo).trim();
        var rows = STATE.listaRows;

        if (termoBusca) {
            rows = rows.filter(function (r) {
                var parc = normalizar(r.parceiro || '');
                var prod = normalizar(r.produto || '');
                var nun = String(r.nunota || '');
                return parc.indexOf(termoBusca) >= 0 ||
                       prod.indexOf(termoBusca) >= 0 ||
                       nun.indexOf(termoBusca) >= 0;
            });
        }

        STATE.listaFiltrada = rows;
        renderResumo(rows);

        if (rows.length === 0) {
            var msg = termoBusca ? 'Nenhum vale bate com "' + escapeHtml(STATE.searchTermo) + '"' : 'Nenhum vale no filtro.';
            lista.innerHTML = '<div class="m-empty-state"><i class="ph ph-clipboard-text"></i><p>' + msg + '</p></div>';
            return;
        }

        // Agrupar por NUNOTA
        var byNun = new Map();
        rows.forEach(function (r) {
            var k = String(r.nunota || '');
            if (!k) return;
            if (!byNun.has(k)) byNun.set(k, []);
            byNun.get(k).push(r);
        });

        var html = '';
        byNun.forEach(function (arr, nun) {
            var primeiro = arr[0];
            var isFaturado = arr.some(function (x) { return x && x.nufin; });
            var temSemPreco = arr.some(function (r) {
                return Number(r.precobase || r.preco_inicial || 0) <= 0;
            });
            var statusCls = isFaturado ? ' is-faturado' : (temSemPreco ? ' is-pendente' : '');

            html += '<div class="m-cm-lista-grupo">';
            html += '<div class="m-cm-vale-header' + statusCls + '" data-nun="' + escapeHtml(nun) + '" data-expanded="false">';
            html += '<span class="m-cm-vale-num">' + escapeHtml(nun) + '</span>';
            html += '<div class="m-cm-vale-info">';
            html += '<div class="m-cm-vale-parc">' + escapeHtml(primeiro.parceiro || '—') + '</div>';
            html += '<div class="m-cm-vale-meta">';
            html += '<span>' + fmtDataBR(primeiro.dtneg) + '</span>';
            html += '<span class="m-cm-vale-sep">·</span>';
            html += '<span>' + arr.length + ' item' + (arr.length > 1 ? 'ns' : '') + '</span>';
            if (isFaturado) {
                html += '<span class="m-cm-vale-sep">·</span>';
                html += '<span style="color:var(--m-success);font-weight:800;">FATURADO</span>';
            } else if (temSemPreco) {
                html += '<span class="m-cm-vale-sep">·</span>';
                html += '<span style="color:var(--m-danger);font-weight:800;">SEM PREÇO</span>';
            }
            html += '</div>';
            html += '</div>';
            html += '<i class="ph ph-caret-right m-cm-vale-chevron"></i>';
            html += '</div>';

            // Itens (escondidos por default)
            html += '<div class="m-cm-vale-itens">';
            arr.forEach(function (r) {
                var isClass = isClassificavelItem(r);
                var clsItem = isClass ? ' is-classificavel' : ' is-nao-classif';
                var precoZero = Number(r.precobase || r.preco_inicial || 0) <= 0;
                if (precoZero) clsItem += ' is-sem-preco';
                var qtyInfo = resolveQuantidade(r);
                html += '<div class="m-cm-item-card' + clsItem + '" data-idx="' + r._i + '">';
                html += '<div class="m-cm-item-prod">' + escapeHtml(r.produto || '—') + '</div>';
                html += '<div class="m-cm-item-qtd">' + fmtNum(qtyInfo.value, 0) + '<small>' + escapeHtml(qtyInfo.unit) + '</small></div>';
                html += '</div>';
            });
            html += '</div>';
            html += '</div>';
        });

        lista.innerHTML = html;
        bindListaHandlers();
    }

    function renderResumo(rows) {
        var totalValor = 0;
        var totalPendentes = 0;
        var totalFaturados = 0;
        var byNun = new Map();
        rows.forEach(function (r) {
            var k = String(r.nunota || '');
            if (!k) return;
            if (!byNun.has(k)) byNun.set(k, []);
            byNun.get(k).push(r);
            totalValor += Number(r.vlrtot || 0);
        });
        byNun.forEach(function (arr) {
            var fat = arr.some(function (x) { return x && x.nufin; });
            var sp = arr.some(function (r) { return Number(r.precobase || r.preco_inicial || 0) <= 0; });
            if (fat) totalFaturados++;
            if (sp) totalPendentes++;
        });

        if ($('m_cm_resumoVales'))      $('m_cm_resumoVales').textContent = byNun.size;
        if ($('m_cm_resumoValor'))      $('m_cm_resumoValor').textContent = fmtBRLcompact(totalValor);
        if ($('m_cm_resumoPendentes'))  $('m_cm_resumoPendentes').textContent = totalPendentes;
        if ($('m_cm_resumoFaturados'))  $('m_cm_resumoFaturados').textContent = totalFaturados;
    }

    function isClassificavelItem(r) {
        if (window.ComercialUtils && window.ComercialUtils.isClassificavel) {
            return window.ComercialUtils.isClassificavel(r);
        }
        // fallback: GERAPRODUCAO='S' indica classificável
        return String(r.geraproducao || '').toUpperCase() === 'S';
    }

    function resolveQuantidade(r) {
        if (window.ComercialUtils && window.ComercialUtils.toNumber) {
            var toNumber = window.ComercialUtils.toNumber;
            var unit = ((r.__raw_codvol != null ? r.__raw_codvol : r.codvol) || 'CX').toString().trim().toUpperCase();
            if (r.qtdconferida !== undefined && r.qtdconferida !== null) {
                return { value: toNumber(r.qtdconferida), unit: unit };
            }
            return { value: toNumber(r.qtdneg), unit: unit };
        }
        var v = Number(r.qtdconferida || r.qtdneg || 0);
        var u = ((r.codvol) || 'CX').toString().toUpperCase();
        return { value: v, unit: u };
    }

    function bindListaHandlers() {
        var lista = $('m_cm_lista');
        if (!lista) return;
        lista.querySelectorAll('.m-cm-vale-header').forEach(function (h) {
            h.addEventListener('click', function () {
                var nun = h.getAttribute('data-nun');
                // Pega os itens desse vale dentro do STATE
                var itens = STATE.listaRows.filter(function (r) {
                    return String(r.nunota) === String(nun);
                });
                // UX: se o vale tem 1 item só, abre detalhe direto (sem expandir)
                if (itens.length === 1) {
                    abrirDetalheVale(itens[0]);
                    return;
                }
                // Caso contrário, expande/colapsa
                var isExp = h.getAttribute('data-expanded') === 'true';
                h.setAttribute('data-expanded', isExp ? 'false' : 'true');
            });
        });
        lista.querySelectorAll('.m-cm-item-card').forEach(function (c) {
            c.addEventListener('click', function (ev) {
                ev.stopPropagation();
                var idx = parseInt(c.getAttribute('data-idx'));
                var row = STATE.listaRows[idx];
                if (row) abrirDetalheVale(row);
            });
        });
    }

    // ====== TELA 2 — DETALHE DO VALE ==========================================
    async function abrirDetalheVale(row) {
        STATE.valeSelecionado = row;
        // limpa estado anterior
        STATE.valeMargem = null;
        STATE.valeVendas = null;

        // Hero
        if ($('m_cm_heroParceiro')) $('m_cm_heroParceiro').textContent = row.parceiro || '—';
        if ($('m_cm_heroProduto'))  $('m_cm_heroProduto').textContent = row.produto || '—';
        if ($('m_cm_heroPedidoData')) {
            var partes = [];
            if (row.nunota) partes.push('Pedido ' + row.nunota);
            partes.push(fmtDataBR(row.dtneg));
            $('m_cm_heroPedidoData').textContent = partes.join(' · ');
        }
        if ($('m_cm_heroLote')) $('m_cm_heroLote').textContent = row.codagregacao || row.lote || '—';

        // Status faturado
        var isFaturado = Number(row.nufin || 0) > 0;
        var statusBar = $('m_cm_statusBar');
        if (statusBar) statusBar.hidden = !isFaturado;

        // Renderiza KPIs/classes com dados que já temos do row
        renderDetalheKPIsFromRow(row);
        renderClassFromRow(row);
        renderAcoesFatura(row);

        // Sparkline / Margem em paralelo
        var lote = row.codagregacao || row.lote || '';
        if (lote) {
            Promise.allSettled([
                carregarMargem(lote),
                carregarVendasLote(lote),
            ]).then(function () {
                renderMargem();
                renderSparkline();
            });
        }

        pushScreen('detalhe');
    }

    function renderDetalheKPIsFromRow(row) {
        var qtdCx = Number(row.qtdconferida || row.qtdneg || 0);
        var pesoUnit = Number(row.peso || row.fator_conversao || 0);
        var totalKg = pesoUnit > 0 ? (qtdCx * pesoUnit) : qtdCx;
        var custoCx = Number(row.precobase || row.preco_inicial || row.vlrunit || 0);
        var totalCompra = qtdCx * custoCx;
        var custoKg = totalKg > 0 ? (totalCompra / totalKg) : 0;

        if ($('m_cm_qtdKg')) $('m_cm_qtdKg').textContent = fmtNum(totalKg, 0);
        if ($('m_cm_qtdCx')) $('m_cm_qtdCx').textContent = fmtNum(qtdCx, 0);
        if ($('m_cm_custoKg')) $('m_cm_custoKg').textContent = fmtNum(custoKg, 2);
        if ($('m_cm_custoCx')) $('m_cm_custoCx').textContent = fmtNum(custoCx, 2);
        if ($('m_cm_totalCompra')) $('m_cm_totalCompra').textContent = fmtBRL(totalCompra);
    }

    function renderClassFromRow(row) {
        // Dados simplificados — backend não traz breakdown por categoria
        // direto na listagem. Mobile mostra estado básico; pra full breakdown
        // o operador volta no desktop. Show qtd/custo total no card EXTRA.
        var qtdCx = Number(row.qtdconferida || row.qtdneg || 0);
        var pesoUnit = Number(row.peso || row.fator_conversao || 0);
        var totalKg = pesoUnit > 0 ? (qtdCx * pesoUnit) : qtdCx;
        var custoCx = Number(row.precobase || row.preco_inicial || row.vlrunit || 0);
        var totalCompra = qtdCx * custoCx;
        var custoKg = totalKg > 0 ? (totalCompra / totalKg) : 0;
        var isClass = isClassificavelItem(row);

        // Reseta tudo
        ['m_cm_extraShare','m_cm_extraTotal','m_cm_extraQtdKg','m_cm_extraQtdCx','m_cm_extraCustoKg','m_cm_extraCustoCx',
         'm_cm_medioShare','m_cm_medioTotal','m_cm_medioQtdKg','m_cm_medioQtdCx','m_cm_medioCustoKg','m_cm_medioCustoCx'
        ].forEach(function (id) {
            var el = $(id);
            if (!el) return;
            if (id.indexOf('Share') >= 0) el.textContent = '0%';
            else if (id.indexOf('Total') >= 0) el.textContent = 'R$ 0,00';
            else el.textContent = id.indexOf('Custo') >= 0 ? '0,00' : '0';
        });
        if ($('m_cm_extraBar')) $('m_cm_extraBar').style.width = '0%';
        if ($('m_cm_medioBar')) $('m_cm_medioBar').style.width = '0%';

        if (!isClass) {
            // Não-classificável: mostra dado no card EXTRA, MÉDIO fica zero
            if ($('m_cm_extraShare'))    $('m_cm_extraShare').textContent = '100%';
            if ($('m_cm_extraTotal'))    $('m_cm_extraTotal').textContent = fmtBRL(totalCompra);
            if ($('m_cm_extraBar'))      $('m_cm_extraBar').style.width = '100%';
            if ($('m_cm_extraQtdKg'))    $('m_cm_extraQtdKg').textContent = fmtNum(totalKg, 0);
            if ($('m_cm_extraQtdCx'))    $('m_cm_extraQtdCx').textContent = fmtNum(qtdCx, 0);
            if ($('m_cm_extraCustoKg'))  $('m_cm_extraCustoKg').textContent = fmtNum(custoKg, 2);
            if ($('m_cm_extraCustoCx'))  $('m_cm_extraCustoCx').textContent = fmtNum(custoCx, 2);
        } else {
            // Classificável: distribuição padrão (sem breakdown — operador
            // edita pesos no desktop)
            if ($('m_cm_extraShare'))    $('m_cm_extraShare').textContent = '—';
            if ($('m_cm_extraTotal'))    $('m_cm_extraTotal').textContent = fmtBRL(totalCompra);
            if ($('m_cm_extraQtdKg'))    $('m_cm_extraQtdKg').textContent = fmtNum(totalKg, 0);
            if ($('m_cm_extraQtdCx'))    $('m_cm_extraQtdCx').textContent = fmtNum(qtdCx, 0);
            if ($('m_cm_extraCustoKg'))  $('m_cm_extraCustoKg').textContent = fmtNum(custoKg, 2);
            if ($('m_cm_extraCustoCx'))  $('m_cm_extraCustoCx').textContent = fmtNum(custoCx, 2);
        }
    }

    function renderMargem() {
        var kpi = $('m_cm_kpiMargem');
        var val = $('m_cm_margemValue');
        var lucroEl = $('m_cm_margemLucro');
        var badge = $('m_cm_margemBadge');
        if (!val) return;

        if (!STATE.valeMargem || !STATE.valeMargem.tem_custo) {
            val.textContent = '—';
            val.dataset.margemCor = 'neutro';
            if (lucroEl) lucroEl.textContent = 'R$ 0,00';
            if (badge) badge.hidden = true;
            if (kpi) kpi.title = 'Vale ainda não lançado pra esse lote';
            return;
        }

        var m = STATE.valeMargem;
        var pct = Number(m.margem_pct || 0);
        var sinal = '';
        var cor = 'neutro';
        if (pct > 0.05) { sinal = '+'; cor = 'positivo'; }
        else if (pct < -0.05) { sinal = '−'; cor = 'negativo'; pct = Math.abs(pct); }

        val.textContent = sinal + pct.toFixed(1).replace('.', ',') + '%';
        val.dataset.margemCor = cor;

        if (lucroEl) {
            var lucro = Number(m.lucro || 0);
            lucroEl.textContent = (lucro >= 0 ? '' : '−') + fmtBRL(Math.abs(lucro));
        }

        if (badge) {
            badge.hidden = !(m.status === 'PROVISORIA');
        }

        if (kpi) {
            var tip = 'Receita bruta: ' + fmtBRL(m.receita_bruta || 0) + '\n';
            tip += 'Devolução: ' + fmtBRL(m.devolucao || 0) + '\n';
            tip += 'Custo vale: ' + fmtBRL(m.custo || 0) + '\n';
            tip += 'Lucro: ' + fmtBRL(m.lucro || 0);
            kpi.title = tip;
        }
    }

    function renderSparkline() {
        var card = $('m_cm_sparkCard');
        var svg = $('m_cm_sparkSvg');
        var stats = $('m_cm_sparkStats');
        if (!svg) return;

        var pontos = (STATE.valeVendas && Array.isArray(STATE.valeVendas.vendas)) ? STATE.valeVendas.vendas : [];
        if (!pontos.length) {
            if (card) card.hidden = true;
            return;
        }
        if (card) card.hidden = false;

        // Pontos: cada item tem preco_kg, dtneg, cliente, etc.
        var pre = pontos.map(function (p) {
            return Number(p.preco_kg || 0);
        }).filter(function (v) { return v > 0; });

        if (!pre.length) {
            if (card) card.hidden = true;
            return;
        }

        var min = Math.min.apply(null, pre);
        var max = Math.max.apply(null, pre);
        var avg = pre.reduce(function (a, b) { return a + b; }, 0) / pre.length;
        var range = max - min || 1;
        var margin = range * 0.1;
        var yMin = min - margin;
        var yMax = max + margin;
        var yRange = yMax - yMin || 1;

        var W = 600, H = 100;
        var pad = 6;
        var n = pre.length;
        var step = n > 1 ? (W - pad * 2) / (n - 1) : 0;

        var pathD = '';
        var pts = '';
        pre.forEach(function (v, i) {
            var x = pad + i * step;
            var y = pad + (yMax - v) / yRange * (H - pad * 2);
            pathD += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1);
            pts += '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="3" fill="#5e7e4a"/>';
        });

        var avgY = pad + (yMax - avg) / yRange * (H - pad * 2);

        svg.innerHTML =
            '<line x1="' + pad + '" y1="' + avgY.toFixed(1) + '" x2="' + (W - pad) + '" y2="' + avgY.toFixed(1) + '" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="4 3"/>' +
            '<path d="' + pathD + '" stroke="#5e7e4a" stroke-width="2" fill="none"/>' +
            pts;

        if (stats) {
            stats.innerHTML =
                '<strong>' + fmtBRL(avg) + '/kg</strong> · min ' + fmtBRL(min) + ' · max ' + fmtBRL(max) +
                ' · <strong>' + n + '</strong> vendas';
        }
    }

    function renderAcoesFatura(row) {
        var btn = $('m_cm_btnFaturar');
        var motivos = $('m_cm_faturarMotivos');
        if (!btn) return;

        var temPreco = Number(row.precobase || row.preco_inicial || row.vlrunit || 0) > 0;
        var temVale = !!row.nunota_13;
        var faturado = Number(row.nufin || 0) > 0;

        var listMotivos = [];
        if (faturado) {
            btn.disabled = true;
            btn.innerHTML = '<i class="ph ph-lock"></i> Já faturado';
        } else if (!temPreco) {
            btn.disabled = true;
            btn.innerHTML = '<i class="ph ph-currency-circle-dollar"></i> Faturar';
            listMotivos.push('Item sem preço — edite o preço antes.');
        } else if (!temVale) {
            btn.disabled = true;
            btn.innerHTML = '<i class="ph ph-currency-circle-dollar"></i> Faturar';
            listMotivos.push('Vale ainda não foi salvo. Salve o preço pra criar o vale.');
        } else {
            btn.disabled = false;
            btn.innerHTML = '<i class="ph ph-currency-circle-dollar"></i> Faturar';
        }

        if (motivos) {
            if (listMotivos.length) {
                motivos.innerHTML = listMotivos.map(function (m) { return '<li>' + escapeHtml(m) + '</li>'; }).join('');
                motivos.hidden = false;
            } else {
                motivos.innerHTML = '';
                motivos.hidden = true;
            }
        }
    }

    // ====== AÇÕES ==============================================================
    async function salvarEdicaoPreco() {
        var row = STATE.valeSelecionado;
        if (!row) return;
        var precoCxStr = $('m_cm_editPrecoCx').value;
        var pesoStr = $('m_cm_editPesoClassificado').value;
        var precoCx = parseBR(precoCxStr);
        var peso = parseBR(pesoStr);

        var msg = $('m_cm_editMsg');
        if (precoCx <= 0) {
            mostraMsgEdit('Informe um preço maior que zero.', 'error');
            return;
        }

        var btn = $('m_cm_editSalvar');
        if (btn) { btn.disabled = true; btn.textContent = 'Salvando…'; }

        try {
            // 1) Salva preço (sempre)
            var payloadPreco = {
                nunota: parseInt(row.nunota),
                sequencia: parseInt(row.sequencia),
                preco_inicial: precoCx,
                qtdconferida: Number(row.qtdconferida || row.qtdneg || 0),
                geraproducao: row.geraproducao || 'S',
                peso: Number(row.peso || 0),
            };
            var respPreco = await fetch('/sankhya/comercial/api/atualizar-preco/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                body: JSON.stringify(payloadPreco),
            });
            var dataPreco = await respPreco.json();
            if (!dataPreco.ok) throw new Error(dataPreco.error || 'Erro ao salvar preço');

            // 2) Salva peso classificado (se informado e classificável)
            if (peso > 0 && String(row.geraproducao || '').toUpperCase() === 'S') {
                var payloadPeso = {
                    nunota: parseInt(row.nunota),
                    sequencia: parseInt(row.sequencia),
                    peso_classificado: peso,
                };
                var respPeso = await fetch('/sankhya/comercial/api/atualizar-peso/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                    body: JSON.stringify(payloadPeso),
                });
                var dataPeso = await respPeso.json();
                if (!dataPeso.ok) throw new Error(dataPeso.error || 'Erro ao salvar peso');
                row.qtdfixada = peso;
            }

            row.vlrunit = precoCx;
            row.precobase = precoCx;

            mostraMsgEdit('Salvo!', 'ok');
            mostrarToast('Preço atualizado', 'success');

            setTimeout(function () {
                closeSheet('editar-preco');
                // Recarrega o detalhe com novos valores
                abrirDetalheVale(row);
                // Recarrega lista em background
                carregarLista();
            }, 600);
        } catch (err) {
            console.error('Erro salvarEdicaoPreco:', err);
            mostraMsgEdit('Erro: ' + err.message, 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = 'Salvar'; }
        }
    }

    function mostraMsgEdit(texto, tipo) {
        var m = $('m_cm_editMsg');
        if (!m) return;
        m.textContent = texto;
        m.classList.remove('is-error', 'is-ok');
        m.classList.add(tipo === 'error' ? 'is-error' : 'is-ok');
        m.hidden = false;
    }

    function abrirSheetEditarPreco() {
        var row = STATE.valeSelecionado;
        if (!row) return;
        var precoCx = Number(row.precobase || row.preco_inicial || row.vlrunit || 0);
        var peso = Number(row.qtdfixada || 0);

        if ($('m_cm_editPrecoCx')) {
            $('m_cm_editPrecoCx').value = precoCx > 0 ? precoCx.toFixed(2).replace('.', ',') : '';
        }
        if ($('m_cm_editPesoClassificado')) {
            $('m_cm_editPesoClassificado').value = peso > 0 ? String(Math.round(peso)) : '';
        }
        if ($('m_cm_editMsg')) {
            $('m_cm_editMsg').textContent = '';
            $('m_cm_editMsg').hidden = true;
        }
        atualizarPrecoKgDerivado();
        openSheet('editar-preco');
    }

    function atualizarPrecoKgDerivado() {
        var row = STATE.valeSelecionado;
        var hint = $('m_cm_editPrecoKg');
        if (!row || !hint) return;
        var precoCx = parseBR($('m_cm_editPrecoCx').value);
        var peso = Number(row.peso || row.fator_conversao || 0);
        if (peso > 0 && precoCx > 0) {
            hint.textContent = fmtBRL(precoCx / peso) + '/kg';
        } else {
            hint.textContent = '—';
        }
    }

    function abrirFaturamento() {
        var row = STATE.valeSelecionado;
        if (!row || !row.nunota) return;
        if (window.ComercialFinanceiro && typeof window.ComercialFinanceiro.abrir === 'function') {
            window.ComercialFinanceiro.abrir(row.nunota);
        } else {
            mostrarToast('Módulo de faturamento indisponível', 'error');
        }
    }

    // ====== FILTROS ============================================================
    function atualizarBadgeFiltros() {
        var bot = document.querySelector('.comercial-mobile .m-bottom-nav__item[data-nav="filtros"]');
        if (!bot) return;
        var ativo = !!(STATE.filtros.dataIni || STATE.filtros.parceiroCode ||
                       STATE.filtros.produto || STATE.filtros.vale ||
                       STATE.filtros.pendentes || STATE.filtros.faturados);
        bot.classList.toggle('has-filtros-ativos', ativo);
    }

    function abrirSheetFiltros() {
        // Popula os inputs com STATE
        if ($('m_cm_filtroDataIni')) $('m_cm_filtroDataIni').value = STATE.filtros.dataIni || '';
        if ($('m_cm_filtroDataFim')) $('m_cm_filtroDataFim').value = STATE.filtros.dataFim || '';
        if ($('m_cm_filtroParceiroNome')) $('m_cm_filtroParceiroNome').value = STATE.filtros.parceiroNome || '';
        if ($('m_cm_filtroParceiroCode')) $('m_cm_filtroParceiroCode').value = STATE.filtros.parceiroCode || '';
        if ($('m_cm_filtroProduto')) $('m_cm_filtroProduto').value = STATE.filtros.produto || '';
        if ($('m_cm_filtroVale')) $('m_cm_filtroVale').value = STATE.filtros.vale || '';

        // Status chips
        document.querySelectorAll('.comercial-mobile .m-cm-status-chip').forEach(function (c) {
            var key = c.getAttribute('data-status');
            c.classList.toggle('is-on', !!STATE.filtros[key]);
        });

        openSheet('filtros');
    }

    function aplicarFiltros() {
        STATE.filtros.dataIni = $('m_cm_filtroDataIni') ? $('m_cm_filtroDataIni').value : '';
        STATE.filtros.dataFim = $('m_cm_filtroDataFim') ? $('m_cm_filtroDataFim').value : '';
        STATE.filtros.parceiroNome = $('m_cm_filtroParceiroNome') ? $('m_cm_filtroParceiroNome').value.trim() : '';
        STATE.filtros.parceiroCode = $('m_cm_filtroParceiroCode') ? $('m_cm_filtroParceiroCode').value.trim() : '';
        STATE.filtros.produto = $('m_cm_filtroProduto') ? $('m_cm_filtroProduto').value.trim() : '';
        STATE.filtros.vale = $('m_cm_filtroVale') ? $('m_cm_filtroVale').value.trim() : '';

        closeSheet('filtros');
        carregarLista();
    }

    function limparFiltros() {
        STATE.filtros = {
            dataIni: '', dataFim: '',
            parceiroCode: '', parceiroNome: '',
            produto: '', vale: '',
            pendentes: false, faturados: false,
        };
        if ($('m_cm_filtroDataIni')) $('m_cm_filtroDataIni').value = '';
        if ($('m_cm_filtroDataFim')) $('m_cm_filtroDataFim').value = '';
        if ($('m_cm_filtroParceiroNome')) $('m_cm_filtroParceiroNome').value = '';
        if ($('m_cm_filtroParceiroCode')) $('m_cm_filtroParceiroCode').value = '';
        if ($('m_cm_filtroProduto')) $('m_cm_filtroProduto').value = '';
        if ($('m_cm_filtroVale')) $('m_cm_filtroVale').value = '';
        document.querySelectorAll('.comercial-mobile .m-cm-status-chip').forEach(function (c) {
            c.classList.remove('is-on');
        });
        closeSheet('filtros');
        carregarLista();
    }

    // ====== TYPEAHEAD parceiro/produto =======================================
    function setupTypeaheadParceiro() {
        var inp = $('m_cm_filtroParceiroNome');
        var hidden = $('m_cm_filtroParceiroCode');
        var drop = $('m_cm_filtroParceiroDrop');
        if (!inp || !drop) return;

        var doFetch = debounce(async function () {
            var q = inp.value.trim();
            if (q.length < 2) { drop.hidden = true; drop.innerHTML = ''; return; }
            try {
                var url = '/sankhya/parceiros/search/?q=' + encodeURIComponent(q) + '&limit=10';
                var resp = await fetch(url);
                var data = await resp.json();
                var arr = data.results || [];
                if (!arr.length) { drop.hidden = true; drop.innerHTML = ''; return; }
                drop.innerHTML = arr.map(function (it) {
                    var cod = it.codparc || it.cod || '';
                    var nome = it.nomeparc || it.descr || '';
                    return '<div class="m-cm-typeahead-item" data-cod="' + escapeHtml(cod) + '" data-nome="' + escapeHtml(nome) + '">' +
                           escapeHtml(cod) + ' — ' + escapeHtml(nome) + '</div>';
                }).join('');
                drop.hidden = false;
                drop.querySelectorAll('.m-cm-typeahead-item').forEach(function (i) {
                    i.addEventListener('click', function () {
                        inp.value = i.getAttribute('data-nome');
                        if (hidden) hidden.value = i.getAttribute('data-cod');
                        drop.hidden = true;
                    });
                });
            } catch (e) {
                drop.hidden = true;
            }
        }, 300);

        inp.addEventListener('input', function () {
            if (hidden) hidden.value = '';
            doFetch();
        });
        inp.addEventListener('blur', function () {
            setTimeout(function () { drop.hidden = true; }, 200);
        });
    }

    function setupTypeaheadProduto() {
        var inp = $('m_cm_filtroProduto');
        var drop = $('m_cm_filtroProdutoDrop');
        if (!inp || !drop) return;

        var doFetch = debounce(async function () {
            var q = inp.value.trim();
            if (q.length < 2) { drop.hidden = true; drop.innerHTML = ''; return; }
            try {
                var url = '/sankhya/produtos/search/?q=' + encodeURIComponent(q) + '&limit=10&fabricante=1';
                var resp = await fetch(url);
                var data = await resp.json();
                var arr = data.results || [];
                if (!arr.length) { drop.hidden = true; drop.innerHTML = ''; return; }
                drop.innerHTML = arr.map(function (it) {
                    var nome = (it.fabricante || it.descr || '').toString().trim();
                    return '<div class="m-cm-typeahead-item" data-nome="' + escapeHtml(nome) + '">' +
                           escapeHtml(nome) + '</div>';
                }).join('');
                drop.hidden = false;
                drop.querySelectorAll('.m-cm-typeahead-item').forEach(function (i) {
                    i.addEventListener('click', function () {
                        inp.value = i.getAttribute('data-nome');
                        drop.hidden = true;
                    });
                });
            } catch (e) {
                drop.hidden = true;
            }
        }, 300);

        inp.addEventListener('input', doFetch);
        inp.addEventListener('blur', function () {
            setTimeout(function () { drop.hidden = true; }, 200);
        });
    }

    // ====== BOTTOM NAV =========================================================
    function bindBottomNav() {
        document.querySelectorAll('.comercial-mobile .m-bottom-nav__item').forEach(function (b) {
            b.addEventListener('click', function () {
                var nav = b.getAttribute('data-nav');
                document.querySelectorAll('.comercial-mobile .m-bottom-nav__item').forEach(function (x) {
                    x.classList.toggle('is-active', x === b);
                });
                if (nav === 'lista') {
                    setActiveScreen('lista');
                } else if (nav === 'buscar') {
                    setActiveScreen('lista');
                    var s = $('m_cm_search');
                    if (s) { s.focus(); }
                } else if (nav === 'filtros') {
                    abrirSheetFiltros();
                } else if (nav === 'mais') {
                    openSheet('mais');
                }
            });
        });
    }

    // ====== SIDEBAR TOGGLE (hambúrguer) =======================================
    function bindSidebarToggle() {
        var btn = $('m_cm_btnSidebar');
        if (!btn) return;
        btn.addEventListener('click', function () {
            // Mesmo padrão dos outros módulos — usa toggle global da sidebar
            if (window.IAgro && window.IAgro.toggleSidebar) {
                window.IAgro.toggleSidebar();
            } else {
                var sidebar = $('appSidebar');
                if (sidebar) sidebar.classList.toggle('is-open');
            }
        });
    }

    // ====== SETUP DATA RANGE <<>> ==============================================
    function setupDateRange() {
        var ini = $('m_cm_filtroDataIni');
        var fim = $('m_cm_filtroDataFim');
        var prev = $('m_cm_btnDataPrev');
        var next = $('m_cm_btnDataNext');

        if (ini && fim) {
            var replicar = function () {
                var v = ini.value || '';
                if (v) fim.value = v;
            };
            ini.addEventListener('change', replicar);
            ini.addEventListener('input', replicar);
        }
        if (prev && ini && fim) {
            prev.addEventListener('click', function () {
                var base = ini.value || _hojeIso();
                var novo = _shiftIso(base, -1);
                ini.value = novo;
                fim.value = novo;
            });
        }
        if (next && ini && fim) {
            next.addEventListener('click', function () {
                var base = ini.value || _hojeIso();
                var novo = _shiftIso(base, 1);
                ini.value = novo;
                fim.value = novo;
            });
        }
    }

    // ====== BIND SHEETS ========================================================
    function bindSheets() {
        document.querySelectorAll('.comercial-mobile [data-close-sheet]').forEach(function (el) {
            el.addEventListener('click', function () {
                var sheet = el.closest('.m-sheet');
                if (sheet) sheet.setAttribute('aria-hidden', 'true');
            });
        });

        if ($('m_cm_filtrosAplicar')) $('m_cm_filtrosAplicar').addEventListener('click', aplicarFiltros);
        if ($('m_cm_filtrosLimpar')) $('m_cm_filtrosLimpar').addEventListener('click', limparFiltros);

        document.querySelectorAll('.comercial-mobile .m-cm-status-chip').forEach(function (c) {
            c.addEventListener('click', function () {
                var key = c.getAttribute('data-status');
                STATE.filtros[key] = !STATE.filtros[key];
                c.classList.toggle('is-on', !!STATE.filtros[key]);
            });
        });

        if ($('m_cm_editSalvar')) $('m_cm_editSalvar').addEventListener('click', salvarEdicaoPreco);
        if ($('m_cm_editPrecoCx')) {
            $('m_cm_editPrecoCx').addEventListener('input', atualizarPrecoKgDerivado);
            $('m_cm_editPrecoCx').addEventListener('change', atualizarPrecoKgDerivado);
        }

        if ($('m_cm_acaoAtualizar')) {
            $('m_cm_acaoAtualizar').addEventListener('click', function () {
                closeSheet('mais');
                carregarLista();
            });
        }
        if ($('m_cm_acaoFiltros')) {
            $('m_cm_acaoFiltros').addEventListener('click', function () {
                closeSheet('mais');
                abrirSheetFiltros();
            });
        }
    }

    // ====== HISTORY BACK =======================================================
    function bindHistory() {
        window.addEventListener('popstate', function () {
            // Detecta se há sheet aberto
            var openSheetEl = document.querySelector('.comercial-mobile .m-sheet[aria-hidden="false"]');
            if (openSheetEl) {
                openSheetEl.setAttribute('aria-hidden', 'true');
                return;
            }
            // Se tela atual é detalhe, volta pra lista
            if (screenAtiva === 'detalhe') {
                setActiveScreen('lista');
            }
        });
    }

    // ====== BIND DETALHE BUTTONS ==============================================
    function bindDetalheBtns() {
        if ($('m_cm_btnEditarPreco')) {
            $('m_cm_btnEditarPreco').addEventListener('click', abrirSheetEditarPreco);
        }
        if ($('m_cm_btnFaturar')) {
            $('m_cm_btnFaturar').addEventListener('click', abrirFaturamento);
        }
    }

    // ====== INIT ===============================================================
    function init() {
        screens.lista = document.querySelector('.comercial-mobile .m-screen--lista');
        screens.detalhe = document.querySelector('.comercial-mobile .m-screen--detalhe');
        if (!screens.lista) return;

        bindBottomNav();
        bindSidebarToggle();
        bindSheets();
        bindDetalheBtns();
        bindHistory();
        setupDateRange();
        setupTypeaheadParceiro();
        setupTypeaheadProduto();

        // FAB Atualizar
        if ($('m_cm_fabAtualizar')) {
            $('m_cm_fabAtualizar').addEventListener('click', function () {
                var btn = $('m_cm_fabAtualizar');
                if (btn) btn.classList.add('is-loading');
                carregarLista().finally(function () {
                    setTimeout(function () { if (btn) btn.classList.remove('is-loading'); }, 300);
                });
            });
        }

        // Busca client-side com debounce
        var search = $('m_cm_search');
        if (search) {
            var doSearch = debounce(function () {
                STATE.searchTermo = search.value || '';
                renderLista();
            }, 200);
            search.addEventListener('input', doSearch);
        }

        // Carrega lista inicial
        carregarLista();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
