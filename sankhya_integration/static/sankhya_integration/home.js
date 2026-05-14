// sankhya_integration/static/sankhya_integration/home.js
// Dashboard executivo — Mai/2026
// Sidebar e auth sync agora vivem em iagro_helpers.js + base.html.

(function () {
    'use strict';

    if (!window.IAgro || !window.IAgro.isLogged) return;

    // =========================================================
    // CONFIGURAÇÃO
    // =========================================================
    const URL_DASHBOARD = '/sankhya/api/dashboard/';
    const POLLING_MS = 5 * 60 * 1000; // 5 minutos

    const WIDGETS = [
        {
            key: 'sem_lote', icon: '<i class="ph ph-link"></i>', href: '/sankhya/rastreio/', cta: 'Ir ao Rastreio →',
            corPorContagem: (n) => n === 0 ? 'ok' : (n <= 5 ? 'warn' : 'danger'),
        },
        {
            key: 'aguardando_classif', icon: '<i class="ph ph-plant"></i>', href: '/sankhya/compras/classificacao/', cta: 'Ir à Classificação →',
            corPorContagem: (n) => n === 0 ? 'ok' : (n <= 10 ? 'info' : 'warn'),
        },
        {
            key: 'vales_abertos', icon: '<i class="ph ph-currency-circle-dollar"></i>', href: '/sankhya/comercial/', cta: 'Ir ao Comercial →',
            corPorContagem: (n) => n === 0 ? 'neutral' : 'info',
        },
        {
            key: 'tanques_criticos', icon: '<i class="ph ph-gas-pump"></i>', href: '/sankhya/combustivel/', cta: 'Ir ao Combustível →',
            corPorContagem: (n) => n === 0 ? 'ok' : 'danger',
            renderDetalhes: (d) => {
                if (!d.detalhes || !d.detalhes.length) return '';
                return d.detalhes.slice(0, 3).map(t =>
                    `<div><strong>${escapeHtml(t.descricao)}</strong> · ${t.percentual.toFixed(0)}% (${formatNum(t.qtd_disponivel)} LT)</div>`
                ).join('');
            },
        },
        {
            key: 'prontos_faturar', icon: '<i class="ph ph-receipt"></i>', href: '/sankhya/venda/portal/', cta: 'Ir à Venda →',
            corPorContagem: (n) => n === 0 ? 'neutral' : 'ok',
        },
        {
            key: 'lotes_envelhecidos', icon: '<i class="ph ph-hourglass"></i>', href: '/sankhya/rastreio/', cta: 'Ver no Rastreio →',
            corPorContagem: (n) => n === 0 ? 'ok' : (n <= 5 ? 'warn' : 'danger'),
        },
    ];

    let pollingHandle = null;
    let lastSuccessAt = null;
    let inFlight = false;

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function formatNum(n) {
        if (n == null || isNaN(n)) return '—';
        return Number(n).toLocaleString('pt-BR', { maximumFractionDigits: 2 });
    }

    function formatTimeAgo(date) {
        if (!date) return '—';
        const diff = Math.floor((Date.now() - date.getTime()) / 1000);
        if (diff < 5)   return 'agora';
        if (diff < 60)  return `há ${diff}s`;
        if (diff < 3600) return `há ${Math.floor(diff/60)} min`;
        return `há ${Math.floor(diff/3600)} h`;
    }

    function updateTimestamp() {
        const el = document.getElementById('dashUpdatedAt');
        if (el) el.textContent = formatTimeAgo(lastSuccessAt);
    }

    function renderWidget(cfg, dado) {
        const erro = dado && dado.erro;
        const count = dado && (typeof dado.count === 'number') ? dado.count : null;
        const status = erro || count == null ? 'neutral' : cfg.corPorContagem(count);
        const valorHtml = erro
            ? `<div class="widget-value is-error">Erro ao consultar</div>`
            : `<div class="widget-value">${count == null ? '—' : count.toLocaleString('pt-BR')}</div>`;
        const detHtml = cfg.renderDetalhes && !erro
            ? `<div class="widget-detalhes">${cfg.renderDetalhes(dado) || ''}</div>` : '';
        const label = (dado && dado.label) || cfg.key;
        return `
            <a href="${cfg.href}" class="widget" data-status="${status}" title="${escapeHtml(label)}">
                <div class="widget-header">
                    <span class="widget-icon">${cfg.icon}</span>
                    <span class="widget-cta">${cfg.cta}</span>
                </div>
                ${valorHtml}
                <div class="widget-label">${escapeHtml(label)}</div>
                ${detHtml}
            </a>
        `;
    }

    function renderDashboard(indicadores) {
        const grid = document.getElementById('widgetsGrid');
        if (!grid) return;
        grid.innerHTML = WIDGETS.map(cfg => renderWidget(cfg, indicadores[cfg.key] || {})).join('');
    }

    function renderErroGeral(msg) {
        const grid = document.getElementById('widgetsGrid');
        if (!grid) return;
        grid.innerHTML = `
            <article class="widget" data-status="danger" style="grid-column: 1 / -1;">
                <div class="widget-header"><span class="widget-icon"><i class="ph ph-warning"></i></span></div>
                <div class="widget-value is-error">Falha ao carregar indicadores</div>
                <div class="widget-label">${escapeHtml(msg || 'Tente atualizar em alguns segundos.')}</div>
            </article>
        `;
    }

    async function carregarIndicadores(manual = false) {
        if (inFlight) return;
        inFlight = true;
        const btn = document.getElementById('btnDashRefresh');
        if (btn) btn.classList.add('loading');
        try {
            const resp = await fetch(URL_DASHBOARD, {
                credentials: 'same-origin',
                headers: { 'Accept': 'application/json' },
            });
            if (resp.status === 401) {
                window.location.reload();
                return;
            }
            const data = await resp.json();
            if (!data.ok) {
                renderErroGeral(data.error || 'Erro desconhecido');
                return;
            }
            renderDashboard(data.indicadores || {});
            lastSuccessAt = new Date();
            updateTimestamp();
        } catch (err) {
            console.error('[Dashboard]', err);
            if (!lastSuccessAt) renderErroGeral('Sem conexão com o servidor.');
        } finally {
            inFlight = false;
            if (btn) btn.classList.remove('loading');
        }
    }

    function iniciarPolling() {
        if (pollingHandle) clearInterval(pollingHandle);
        pollingHandle = setInterval(() => carregarIndicadores(false), POLLING_MS);
        setInterval(updateTimestamp, 30000);
    }

    document.addEventListener('DOMContentLoaded', () => {
        const btn = document.getElementById('btnDashRefresh');
        if (btn) btn.addEventListener('click', () => carregarIndicadores(true));
        carregarIndicadores(false);
        iniciarPolling();
    });

})();
