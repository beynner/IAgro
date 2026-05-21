// =====================================================================
// TABELA DE PREÇOS — visualização leitura (Mai/2026 — 2026-05-21)
// =====================================================================
(function () {
    'use strict';

    const $ = (id) => document.getElementById(id);
    const toast = (msg, tipo) => window.IAgro?.showToast?.(msg, tipo);

    function _fmtBRL(n) { return Number(n || 0).toFixed(2).replace('.', ','); }
    function _fmtDataBR(iso) {
        if (!iso) return '—';
        const [y, m, d] = iso.split('-');
        return `${d}/${m}/${y}`;
    }

    let grupos = [];
    let codtabAtivo = null;
    let precosCarregados = [];

    async function carregarGrupos() {
        const ul = $('tpListaGrupos');
        const incluirInativas = $('tpToggleInativas')?.checked ? 'true' : 'false';
        try {
            const r = await fetch(`/sankhya/venda/api/tabelas-grupos/?incluir_inativas=${incluirInativas}`);
            const d = await r.json();
            if (!d.ok) {
                ul.innerHTML = `<div class="ia-placeholder" style="color:#ef4444">${d.error || 'Erro'}</div>`;
                return;
            }
            grupos = d.tabelas || [];
            $('tpSummary').textContent = `${grupos.length} ${grupos.length === 1 ? 'grupo' : 'grupos'}`;
            if (!grupos.length) {
                ul.innerHTML = '<div class="ia-placeholder">Nenhum grupo cadastrado.</div>';
                return;
            }
            ul.innerHTML = '';
            grupos.forEach(g => {
                const div = document.createElement('div');
                div.className = 'tp-grupo-item';
                if (g.ativo === 'N') div.classList.add('is-inativa');
                div.dataset.codtab = g.codtab;
                div.dataset.nomeGrupo = g.nome_grupo || '';
                const amostra = (g.clientes || []).slice(0, 3).join(' · ');
                const sufx = (g.clientes || []).length > 3 ? '...' : '';
                const titulo = g.nome_grupo
                    ? `<strong>${g.codtab}</strong> — ${g.nome_grupo}`
                    : `Tabela ${g.codtab}`;
                const badgeInativa = g.ativo === 'N'
                    ? '<span class="tp-badge-inativa">inativa</span>'
                    : '';
                const infoLinha = g.nutab_ativa
                    ? `NUTAB ${g.nutab_ativa} · ${g.qtd_clientes} cliente${g.qtd_clientes !== 1 ? 's' : ''}`
                    : `Sem vigência · ${g.qtd_clientes} cliente${g.qtd_clientes !== 1 ? 's' : ''}`;
                const amostraLinha = amostra
                    ? `<div class="tp-grupo-clientes-amostra" title="${(g.clientes || []).join(' · ')}">${amostra}${sufx}</div>`
                    : '<div class="tp-grupo-clientes-amostra muted">Sem clientes vinculados</div>';
                div.innerHTML = `
                    <div class="tp-grupo-titulo">${titulo}${badgeInativa}</div>
                    <div class="tp-grupo-info">${infoLinha}</div>
                    ${amostraLinha}
                `;
                div.addEventListener('click', () => selecionarGrupo(g.codtab, g.nome_grupo));
                ul.appendChild(div);
            });
        } catch (e) {
            console.error(e);
            ul.innerHTML = `<div class="ia-placeholder" style="color:#ef4444">Erro: ${e.message}</div>`;
        }
    }

    async function selecionarGrupo(codtab, nomeGrupo) {
        codtabAtivo = parseInt(codtab, 10);
        // Marca visual
        document.querySelectorAll('.tp-grupo-item').forEach(el => {
            el.classList.toggle('is-active', String(el.dataset.codtab) === String(codtab));
        });

        $('tpTituloGrupo').textContent = nomeGrupo
            ? `Tabela ${codtab} — ${nomeGrupo}`
            : `Tabela ${codtab}`;
        $('tpSubtitulo').textContent = 'Carregando preços...';
        $('tpFiltro').disabled = false;
        $('tpClientesChips').innerHTML = '';
        $('tpPrecosBody').innerHTML = '<tr><td colspan="5" class="ia-placeholder">Carregando...</td></tr>';

        try {
            const r = await fetch(`/sankhya/venda/api/tabela-precos/?codtab=${codtab}`);
            const d = await r.json();
            if (!d.ok) {
                $('tpPrecosBody').innerHTML = `<tr><td colspan="5" class="ia-placeholder" style="color:#ef4444">${d.error || 'Erro'}</td></tr>`;
                return;
            }
            precosCarregados = d.precos || [];

            $('tpSubtitulo').textContent = `NUTAB ${d.nutab_ativa} · vigência desde ${_fmtDataBR(d.dtvigor)} · ${d.qtd_clientes} cliente${d.qtd_clientes > 1 ? 's' : ''} · ${precosCarregados.length} produto${precosCarregados.length !== 1 ? 's' : ''} cadastrado${precosCarregados.length !== 1 ? 's' : ''}`;

            const chips = $('tpClientesChips');
            chips.innerHTML = '';
            (d.clientes || []).forEach(c => {
                const sp = document.createElement('span');
                sp.className = 'tp-cliente-chip';
                sp.textContent = `${c.codparc} · ${c.nomeparc}`;
                chips.appendChild(sp);
            });

            renderPrecos(precosCarregados);
        } catch (e) {
            console.error(e);
            $('tpPrecosBody').innerHTML = `<tr><td colspan="5" class="ia-placeholder" style="color:#ef4444">Erro: ${e.message}</td></tr>`;
        }
    }

    function renderPrecos(lista) {
        const tbody = $('tpPrecosBody');
        if (!lista.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="ia-placeholder">Nenhum produto cadastrado nessa tabela.</td></tr>';
            return;
        }
        tbody.innerHTML = '';
        lista.forEach(p => {
            const tem_promo = p.promocao_vlr != null && p.promocao_vlr > 0;
            const tr = document.createElement('tr');
            if (tem_promo) tr.classList.add('tp-row-promo');
            const promoHtml = tem_promo
                ? `<span class="tp-preco-promo"><i class="ph ph-gift"></i> R$ ${_fmtBRL(p.promocao_vlr)}</span>`
                : `<span class="tp-preco-sem">—</span>`;
            tr.innerHTML = `
                <td class="text-right">${p.codprod}</td>
                <td class="ia-truncate" title="${p.descrprod}">${p.descrprod || '—'}</td>
                <td class="text-right"><span class="tp-preco-valor">R$ ${_fmtBRL(p.vlrvenda)}</span></td>
                <td class="text-right">${promoHtml}</td>
                <td>${_fmtDataBR(p.dhaltreg)}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    // Filtro client-side (rápido — preços já carregados)
    $('tpFiltro')?.addEventListener('input', (e) => {
        const q = (e.target.value || '').trim().toLowerCase();
        if (!q) {
            renderPrecos(precosCarregados);
            return;
        }
        const filtrado = precosCarregados.filter(p =>
            (p.descrprod || '').toLowerCase().includes(q) ||
            String(p.codprod).includes(q)
        );
        renderPrecos(filtrado);
    });

    // Toggle "Mostrar inativas"
    $('tpToggleInativas')?.addEventListener('change', () => carregarGrupos());

    // Boot
    carregarGrupos();
})();
