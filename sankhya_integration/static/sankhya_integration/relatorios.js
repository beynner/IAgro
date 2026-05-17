/* ===========================================================================
   MÓDULO RELATÓRIOS — Mai/2026 — 2026-05-17
   IIFE com 1 renderer por sub-aba (lazy load: só carrega quando ativa).
   Helper genérico de fetch + estado loading/erro/vazio padronizado.
   =========================================================================== */
(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Helpers utilitários
    // -----------------------------------------------------------------------
    const fmtBRL = (n) => 'R$ ' + Number(n || 0).toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    const fmtInt = (n) => Number(n || 0).toLocaleString('pt-BR', { maximumFractionDigits: 0 });
    const fmtKg  = (n) => Number(n || 0).toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + ' kg';
    const fmtPct = (n) => {
        const v = Number(n || 0);
        return (v > 0 ? '+' : '') + v.toFixed(1).replace('.', ',') + '%';
    };
    const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));

    // -----------------------------------------------------------------------
    // Estado por painel: período/filtros selecionados, carregado?
    // -----------------------------------------------------------------------
    const STATE = {};

    // -----------------------------------------------------------------------
    // Helper de fetch padronizado
    // -----------------------------------------------------------------------
    async function carregar(pane, url) {
        const conteudo = pane.querySelector('.rel-conteudo');
        const btnRefresh = pane.querySelector('.rel-btn-refresh');
        if (!conteudo) return;

        conteudo.classList.add('rel-loading');
        if (btnRefresh) btnRefresh.classList.add('is-loading');

        try {
            const res = await fetch(url, { credentials: 'same-origin' });
            const body = await res.json().catch(() => ({}));
            if (!res.ok || !body || body.ok === false) {
                renderErro(conteudo, body.error || `Erro ${res.status}`);
                return null;
            }
            return body;
        } catch (err) {
            renderErro(conteudo, 'Falha de rede — tente novamente.');
            return null;
        } finally {
            conteudo.classList.remove('rel-loading');
            if (btnRefresh) btnRefresh.classList.remove('is-loading');
        }
    }

    function renderErro(container, msg) {
        container.innerHTML = `
            <div class="rel-error">
                <i class="ph ph-warning-circle" aria-hidden="true"></i>
                <span>${escapeHtml(msg)}</span>
            </div>
        `;
    }
    function renderVazio(container, msg, sugestao) {
        container.innerHTML = `
            <div class="rel-empty">
                <i class="ph ph-magnifying-glass" aria-hidden="true"></i>
                <span>${escapeHtml(msg)}</span>
                ${sugestao ? `<small>${escapeHtml(sugestao)}</small>` : ''}
            </div>
        `;
    }

    // -----------------------------------------------------------------------
    // Switch de tabs
    // -----------------------------------------------------------------------
    function ativarTab(rel) {
        document.querySelectorAll('.rel-tab').forEach((btn) => {
            const on = btn.dataset.rel === rel;
            btn.classList.toggle('is-on', on);
            btn.setAttribute('aria-pressed', String(on));
        });
        document.querySelectorAll('.rel-pane').forEach((pane) => {
            pane.classList.toggle('is-active', pane.dataset.rel === rel);
        });
        // Lazy load — só carrega na 1ª ativação
        const renderer = RENDERERS[rel];
        if (renderer) renderer.carregar();
    }

    // -----------------------------------------------------------------------
    // Bind de chips/select/refresh dentro de uma pane
    // -----------------------------------------------------------------------
    function bindControles(pane, renderer) {
        // Chips de período/idade — opt-in: chip clicado vira ativo na sua
        // categoria (mesmo grupo de chips dentro do filtro)
        pane.querySelectorAll('.rel-chip').forEach((chip) => {
            chip.addEventListener('click', () => {
                const grupo = chip.parentElement;
                grupo.querySelectorAll('.rel-chip').forEach((c) => c.classList.remove('is-on'));
                chip.classList.add('is-on');
                renderer.carregar(true);
            });
        });
        // Selects (métrica, agrupador, tipo de veículo)
        pane.querySelectorAll('.rel-select').forEach((sel) => {
            sel.addEventListener('change', () => renderer.carregar(true));
        });
        // Botão refresh
        const btn = pane.querySelector('[data-action="refresh"]');
        if (btn) btn.addEventListener('click', () => renderer.carregar(true));
    }

    // -----------------------------------------------------------------------
    // Tradução de "período" em query params (date_de=YYYY-MM-DD&date_ate=...)
    // -----------------------------------------------------------------------
    function periodoToDatas(valor) {
        const hoje = new Date();
        const fmt = (d) => d.toISOString().slice(0, 10);
        const ate = fmt(hoje);
        if (valor === 'mes-atual') {
            const de = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
            return { date_de: fmt(de), date_ate: ate };
        }
        if (valor === 'mes-anterior') {
            const de = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
            const ateP = new Date(hoje.getFullYear(), hoje.getMonth(), 0);
            return { date_de: fmt(de), date_ate: fmt(ateP) };
        }
        const dias = parseInt(valor, 10) || 30;
        const de = new Date(hoje);
        de.setDate(de.getDate() - dias);
        return { date_de: fmt(de), date_ate: ate };
    }

    function periodoAtivo(pane) {
        const chip = pane.querySelector('.rel-filtro-periodo .rel-chip.is-on');
        return chip ? chip.dataset.periodo || chip.dataset.dias || chip.dataset.horizonte : '30';
    }

    // -----------------------------------------------------------------------
    // RENDERERS — 1 por relatório
    // Cada renderer expõe { carregar(force?) }. Carregar idempotente em força=false.
    // -----------------------------------------------------------------------
    const RENDERERS = {};

    // ===== 1. TOP CLIENTES + TOP PRODUTOS =====
    RENDERERS['top-clientes'] = (function () {
        let carregado = false;
        const pane = document.getElementById('painel-top-clientes');

        async function carregar(force) {
            if (carregado && !force) return;
            const periodo = periodoAtivo(pane);
            const metrica = pane.querySelector('#topClientesMetrica').value || 'valor';
            const { date_de, date_ate } = periodoToDatas(periodo);

            const url = `/sankhya/relatorios/api/top-clientes-produtos/?date_de=${date_de}&date_ate=${date_ate}&metrica=${metrica}`;
            const body = await carregar_(url);
            if (!body) return;
            render(body, metrica);
            carregado = true;
        }
        function carregar_(url) { return carregar.fetcher(url); }
        carregar.fetcher = (url) => carregar_real(pane, url);

        function render(body, metrica) {
            const conteudo = pane.querySelector('.rel-conteudo');
            const clientes = body.top_clientes || [];
            const produtos = body.top_produtos || [];
            const totalClientes = body.total_geral_clientes || 0;
            const totalProdutos = body.total_geral_produtos || 0;
            const labelMetrica = metrica === 'valor' ? 'Valor' : metrica === 'qtd' ? 'Quantidade' : 'Pedidos';
            const fmtMetrica = metrica === 'valor' ? fmtBRL : metrica === 'qtd' ? fmtKg : fmtInt;

            if (clientes.length === 0 && produtos.length === 0) {
                renderVazio(conteudo, 'Sem vendas no período.', 'Tente outro período acima.');
                return;
            }

            conteudo.innerHTML = `
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                    <div>
                        <h4 style="margin: 0 0 8px 0; color: #1e293b; font-size: 0.95rem;">🏆 Top Clientes</h4>
                        <table class="rel-tabela">
                            <thead><tr>
                                <th style="width: 28px;">#</th>
                                <th>Cliente</th>
                                <th class="num">${labelMetrica}</th>
                                <th class="num" style="width: 60px;">%</th>
                            </tr></thead>
                            <tbody>${clientes.map((r, i) => {
                                const v = Number(r.metrica || 0);
                                const pct = totalClientes > 0 ? (v / totalClientes * 100) : 0;
                                return `
                                    <tr>
                                        <td>${i + 1}</td>
                                        <td title="${escapeHtml(r.nome_full || r.nome)}">${escapeHtml(r.nome)}</td>
                                        <td class="num destaque">${fmtMetrica(v)}</td>
                                        <td class="num">${pct.toFixed(1).replace('.', ',')}%</td>
                                    </tr>
                                `;
                            }).join('')}</tbody>
                        </table>
                    </div>
                    <div>
                        <h4 style="margin: 0 0 8px 0; color: #1e293b; font-size: 0.95rem;">📦 Top Produtos</h4>
                        <table class="rel-tabela">
                            <thead><tr>
                                <th style="width: 28px;">#</th>
                                <th>Produto</th>
                                <th class="num">${labelMetrica}</th>
                                <th class="num" style="width: 60px;">%</th>
                            </tr></thead>
                            <tbody>${produtos.map((r, i) => {
                                const v = Number(r.metrica || 0);
                                const pct = totalProdutos > 0 ? (v / totalProdutos * 100) : 0;
                                return `
                                    <tr>
                                        <td>${i + 1}</td>
                                        <td>${escapeHtml(r.descrprod)}</td>
                                        <td class="num destaque">${fmtMetrica(v)}</td>
                                        <td class="num">${pct.toFixed(1).replace('.', ',')}%</td>
                                    </tr>
                                `;
                            }).join('')}</tbody>
                        </table>
                    </div>
                </div>
            `;
        }

        if (pane) bindControles(pane, { carregar });
        return { carregar };
    })();

    // ===== 2. LOTES ENVELHECIDOS =====
    RENDERERS['lotes-envelhecidos'] = (function () {
        let carregado = false;
        const pane = document.getElementById('painel-lotes-envelhecidos');

        async function carregar(force) {
            if (carregado && !force) return;
            const chip = pane.querySelector('.rel-filtro-periodo .rel-chip.is-on');
            const dias = chip ? chip.dataset.dias : '30';
            const url = `/sankhya/relatorios/api/lotes-envelhecidos/?dias_min=${dias}`;
            const body = await carregar_real(pane, url);
            if (!body) return;
            render(body, dias);
            carregado = true;
        }

        function render(body, diasMin) {
            const conteudo = pane.querySelector('.rel-conteudo');
            const lotes = body.lotes || [];
            if (lotes.length === 0) {
                renderVazio(conteudo, `Nenhum lote parado há mais de ${diasMin} dias.`,
                            'Bom sinal — o estoque está girando!');
                return;
            }
            conteudo.innerHTML = `
                <p style="font-size:0.78rem; color:#64748b; margin:0 0 10px 0;">
                    <strong>${lotes.length}</strong> lote(s) com saldo parado há mais de ${diasMin} dias.
                </p>
                <table class="rel-tabela">
                    <thead><tr>
                        <th>Lote</th><th>Produto</th><th>Fornecedor</th>
                        <th class="num">Entrada</th><th class="num">Saldo</th>
                        <th class="num">Dias</th><th>Bandeira</th>
                    </tr></thead>
                    <tbody>${lotes.map((l) => {
                        const dias = Number(l.dias_parado || 0);
                        const bandeira =
                            dias > 90 ? 'vermelho' :
                            dias > 60 ? 'laranja'  :
                            dias > 30 ? 'amarelo'  : 'azul';
                        const label =
                            dias > 90 ? 'CRÍTICO' :
                            dias > 60 ? 'ALERTA'  :
                            dias > 30 ? 'ATENÇÃO' : 'OK';
                        return `
                            <tr>
                                <td><code>${escapeHtml(l.codagregacao)}</code></td>
                                <td>${escapeHtml(l.descrprod || '—')}</td>
                                <td>${escapeHtml(l.fornecedor || '—')}</td>
                                <td class="num">${fmtKg(l.qtd_entrada)}</td>
                                <td class="num destaque">${fmtKg(l.qtd_disponivel)}</td>
                                <td class="num">${dias} d</td>
                                <td><span class="rel-bandeira rel-bandeira--${bandeira}">${label}</span></td>
                            </tr>
                        `;
                    }).join('')}</tbody>
                </table>
            `;
        }

        if (pane) bindControles(pane, { carregar });
        return { carregar };
    })();

    // ===== 3. CONSUMO POR VEÍCULO =====
    RENDERERS['consumo-veiculo'] = (function () {
        let carregado = false;
        const pane = document.getElementById('painel-consumo-veiculo');

        async function carregar(force) {
            if (carregado && !force) return;
            const periodo = periodoAtivo(pane);
            const tipo = pane.querySelector('#consumoTipoVeic').value || '';
            const { date_de, date_ate } = periodoToDatas(periodo);
            const params = new URLSearchParams({ date_de, date_ate });
            if (tipo) params.set('tipo', tipo);
            const url = `/sankhya/relatorios/api/consumo-veiculos/?${params}`;
            const body = await carregar_real(pane, url);
            if (!body) return;
            render(body);
            carregado = true;
        }

        function render(body) {
            const conteudo = pane.querySelector('.rel-conteudo');
            const veiculos = body.veiculos || [];
            if (veiculos.length === 0) {
                renderVazio(conteudo, 'Sem requisições de combustível no período.',
                            'Tente um período maior.');
                return;
            }
            conteudo.innerHTML = `
                <table class="rel-tabela">
                    <thead><tr>
                        <th style="width: 28px;">#</th>
                        <th>Placa</th><th>Veículo</th><th>Tipo</th>
                        <th class="num">Litros</th>
                        <th class="num">Valor</th>
                        <th class="num">km / h</th>
                        <th class="num">Eficiência</th>
                        <th class="num">Nº reqs</th>
                    </tr></thead>
                    <tbody>${veiculos.map((v, i) => {
                        const efic = v.eficiencia_label || '—';
                        return `
                            <tr>
                                <td>${i + 1}</td>
                                <td><strong>${escapeHtml(v.placa || '—')}</strong></td>
                                <td>${escapeHtml(v.marcamodelo || '—')}</td>
                                <td><span class="rel-bandeira rel-bandeira--${v.tipo === 'MAQ' ? 'azul' : 'verde'}">${v.tipo || '—'}</span></td>
                                <td class="num destaque">${fmtInt(v.litros_total)} L</td>
                                <td class="num">${fmtBRL(v.valor_total)}</td>
                                <td class="num">${v.medidor_total != null ? fmtInt(v.medidor_total) : '—'}</td>
                                <td class="num">${efic}</td>
                                <td class="num">${fmtInt(v.qtd_reqs)}</td>
                            </tr>
                        `;
                    }).join('')}</tbody>
                </table>
            `;
        }

        if (pane) bindControles(pane, { carregar });
        return { carregar };
    })();

    // ===== 4. FLUXO DE CAIXA =====
    RENDERERS['fluxo-caixa'] = (function () {
        let carregado = false;
        const pane = document.getElementById('painel-fluxo-caixa');

        async function carregar(force) {
            if (carregado && !force) return;
            const chip = pane.querySelector('.rel-filtro-periodo .rel-chip.is-on');
            const horizonte = chip ? chip.dataset.horizonte : '60';
            const url = `/sankhya/relatorios/api/fluxo-caixa/?dias=${horizonte}`;
            const body = await carregar_real(pane, url);
            if (!body) return;
            render(body, horizonte);
            carregado = true;
        }

        function render(body, horizonte) {
            const conteudo = pane.querySelector('.rel-conteudo');
            const buckets = body.buckets || [];
            if (buckets.length === 0) {
                renderVazio(conteudo, 'Sem títulos abertos no horizonte.',
                            'Tente um horizonte maior.');
                return;
            }
            // Header com totais
            const totalEntrada = body.total_entrada || 0;
            const totalSaida   = body.total_saida   || 0;
            const saldo        = totalEntrada - totalSaida;
            const corSaldo = saldo >= 0 ? 'verde' : 'vermelho';

            conteudo.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
                    <div style="padding: 12px; background: #dcfce7; border-radius: 8px;">
                        <div style="font-size: 0.7rem; font-weight: 700; color: #166534; text-transform: uppercase;">Entradas (a receber)</div>
                        <div style="font-size: 1.4rem; font-weight: 900; color: #15803d; margin-top: 4px;">${fmtBRL(totalEntrada)}</div>
                    </div>
                    <div style="padding: 12px; background: #fee2e2; border-radius: 8px;">
                        <div style="font-size: 0.7rem; font-weight: 700; color: #991b1b; text-transform: uppercase;">Saídas (a pagar)</div>
                        <div style="font-size: 1.4rem; font-weight: 900; color: #b91c1c; margin-top: 4px;">${fmtBRL(totalSaida)}</div>
                    </div>
                    <div style="padding: 12px; background: ${saldo>=0?'#ecfccb':'#fee2e2'}; border-radius: 8px;">
                        <div style="font-size: 0.7rem; font-weight: 700; color: ${saldo>=0?'#3f6212':'#991b1b'}; text-transform: uppercase;">Saldo projetado</div>
                        <div style="font-size: 1.4rem; font-weight: 900; color: ${saldo>=0?'#4d7c0f':'#b91c1c'}; margin-top: 4px;">${fmtBRL(saldo)}</div>
                    </div>
                </div>
                <table class="rel-tabela">
                    <thead><tr>
                        <th>Período</th>
                        <th class="num">Entradas</th>
                        <th class="num">Saídas</th>
                        <th class="num">Saldo</th>
                        <th class="num">Acumulado</th>
                    </tr></thead>
                    <tbody>${buckets.map((b) => {
                        const s = (Number(b.entrada) || 0) - (Number(b.saida) || 0);
                        const ac = Number(b.saldo_acumulado || 0);
                        return `
                            <tr>
                                <td>${escapeHtml(b.label)}</td>
                                <td class="num" style="color:#15803d;">${fmtBRL(b.entrada)}</td>
                                <td class="num" style="color:#b91c1c;">${fmtBRL(b.saida)}</td>
                                <td class="num destaque" style="color:${s>=0?'#15803d':'#b91c1c'};">${fmtBRL(s)}</td>
                                <td class="num destaque" style="color:${ac>=0?'#15803d':'#b91c1c'};">${fmtBRL(ac)}</td>
                            </tr>
                        `;
                    }).join('')}</tbody>
                </table>
            `;
        }

        if (pane) bindControles(pane, { carregar });
        return { carregar };
    })();

    // ===== 5. MARGEM POR VENDA =====
    RENDERERS['margem-venda'] = (function () {
        let carregado = false;
        const pane = document.getElementById('painel-margem-venda');

        async function carregar(force) {
            if (carregado && !force) return;
            const periodo = periodoAtivo(pane);
            const agrupar = pane.querySelector('#margemAgrupar').value || 'cliente';
            const { date_de, date_ate } = periodoToDatas(periodo);
            const url = `/sankhya/relatorios/api/margem-venda/?date_de=${date_de}&date_ate=${date_ate}&agrupar=${agrupar}`;
            const body = await carregar_real(pane, url);
            if (!body) return;
            render(body, agrupar);
            carregado = true;
        }

        function render(body, agrupar) {
            const conteudo = pane.querySelector('.rel-conteudo');
            const linhas = body.linhas || [];
            if (linhas.length === 0) {
                renderVazio(conteudo, 'Sem vendas com custo identificado no período.',
                            'Margem requer JOIN com vale (TOP 13) — pode ser lote externo ou sem vale lançado.');
                return;
            }
            const labelCol = agrupar === 'cliente' ? 'Cliente' : 'Produto';
            conteudo.innerHTML = `
                <p style="font-size:0.78rem; color:#64748b; margin:0 0 10px 0;">
                    Receita: <strong>${fmtBRL(body.total_receita)}</strong> ·
                    Custo: <strong>${fmtBRL(body.total_custo)}</strong> ·
                    Lucro: <strong style="color:${body.total_lucro>=0?'#15803d':'#b91c1c'};">${fmtBRL(body.total_lucro)}</strong>
                    (margem média: <strong>${fmtPct(body.margem_media)}</strong>)
                </p>
                <table class="rel-tabela">
                    <thead><tr>
                        <th style="width: 28px;">#</th>
                        <th>${labelCol}</th>
                        <th class="num">Receita</th>
                        <th class="num">Custo</th>
                        <th class="num">Lucro</th>
                        <th class="num">Margem %</th>
                        <th>Bandeira</th>
                    </tr></thead>
                    <tbody>${linhas.map((r, i) => {
                        const m = Number(r.margem_pct || 0);
                        const bandeira =
                            m >= 15 ? 'verde'    :
                            m >= 5  ? 'amarelo'  :
                            m >= 0  ? 'laranja'  : 'vermelho';
                        const label =
                            m >= 15 ? 'BOM' :
                            m >= 5  ? 'OK'  :
                            m >= 0  ? 'BAIXA' : 'PREJU';
                        return `
                            <tr>
                                <td>${i + 1}</td>
                                <td>${escapeHtml(r.nome)}</td>
                                <td class="num">${fmtBRL(r.receita)}</td>
                                <td class="num">${fmtBRL(r.custo)}</td>
                                <td class="num destaque" style="color:${r.lucro>=0?'#15803d':'#b91c1c'};">${fmtBRL(r.lucro)}</td>
                                <td class="num destaque">${fmtPct(m)}</td>
                                <td><span class="rel-bandeira rel-bandeira--${bandeira}">${label}</span></td>
                            </tr>
                        `;
                    }).join('')}</tbody>
                </table>
            `;
        }

        if (pane) bindControles(pane, { carregar });
        return { carregar };
    })();

    // -----------------------------------------------------------------------
    // Helper compartilhado (todos os renderers chamam)
    // -----------------------------------------------------------------------
    async function carregar_real(pane, url) {
        return await carregar(pane, url);
    }

    // -----------------------------------------------------------------------
    // BOOT
    // -----------------------------------------------------------------------
    document.querySelectorAll('.rel-tab').forEach((btn) => {
        btn.addEventListener('click', () => ativarTab(btn.dataset.rel));
    });
    // Carrega o primeiro relatório (top-clientes) ao montar a tela
    if (RENDERERS['top-clientes']) RENDERERS['top-clientes'].carregar();
})();
