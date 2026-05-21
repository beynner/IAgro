// =====================================================================
// PROMOÇÕES — escopo flexível: Grupo (CODTAB) ou Parceiro
// Mai/2026 — 2026-05-20 (v1) · 2026-05-21 (v2 escopo)
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
    function _hojeISO() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }

    // Cache das tabelas-grupo (carregadas 1× ao montar a página)
    let tabelasGrupo = [];

    async function carregarTabelasGrupo() {
        try {
            const r = await fetch('/sankhya/venda/api/tabelas-grupos/');
            const d = await r.json();
            tabelasGrupo = d.tabelas || [];
            const sel = $('promoCodtab');
            if (sel) {
                sel.innerHTML = '<option value="">Selecione um grupo...</option>';
                tabelasGrupo.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t.codtab;
                    const nome = t.nome_grupo ? ` — ${t.nome_grupo}` : '';
                    opt.textContent = `Tabela ${t.codtab}${nome} · ${t.qtd_clientes} cliente${t.qtd_clientes > 1 ? 's' : ''}`;
                    opt.dataset.clientes = (t.clientes || []).join(' · ');
                    sel.appendChild(opt);
                });
            }
        } catch (e) {
            console.error('Falha ao carregar tabelas-grupo', e);
        }
    }

    function atualizarHintTabela() {
        const sel = $('promoCodtab');
        const hint = $('promoTabHint');
        if (!sel || !hint) return;
        const opt = sel.options[sel.selectedIndex];
        hint.textContent = opt?.dataset?.clientes ? `Inclui: ${opt.dataset.clientes}` : '';
    }

    // ────────────────── Typeaheads ──────────────────
    IAgro.attachTypeahead({
        inputId: 'filtroParcSearch', hiddenId: 'filtroParc', dropdownId: 'filtroParcDropdown',
        url: '/sankhya/parceiros/search/', limit: 15, debounceMs: 350,
        pickCod: (it) => it.cod ?? it.codparc,
        pickDescr: (it) => it.descr ?? it.nomeparc ?? '',
        onSelect: () => carregar(), onClear: () => carregar(),
    });
    IAgro.attachTypeahead({
        inputId: 'filtroProdSearch', hiddenId: 'filtroProd', dropdownId: 'filtroProdDropdown',
        url: '/sankhya/produtos/search/', limit: 15, debounceMs: 350,
        extraQuery: 'grupo_inicia_com=1',
        pickCod: (it) => it.cod, pickDescr: (it) => it.descr,
        onSelect: () => carregar(), onClear: () => carregar(),
    });
    IAgro.attachTypeahead({
        inputId: 'promoParcSearch', hiddenId: 'promoCodparc', dropdownId: 'promoParcDropdown',
        url: '/sankhya/parceiros/search/', limit: 15, debounceMs: 350,
        pickCod: (it) => it.cod ?? it.codparc,
        pickDescr: (it) => it.descr ?? it.nomeparc ?? '',
    });
    IAgro.attachTypeahead({
        inputId: 'promoProdSearch', hiddenId: 'promoCodprod', dropdownId: 'promoProdDropdown',
        url: '/sankhya/produtos/search/', limit: 15, debounceMs: 350,
        extraQuery: 'grupo_inicia_com=1',
        pickCod: (it) => it.cod, pickDescr: (it) => it.descr,
    });

    // ────────────────── Filtros ──────────────────
    function montarQuery() {
        const params = new URLSearchParams();
        const q = $('filtroQ').value.trim();
        if (q) params.set('q', q);
        const cp = $('filtroParc').value.trim();
        if (cp) params.set('codparc', cp);
        const cpr = $('filtroProd').value.trim();
        if (cpr) params.set('codprod', cpr);
        const at = $('filtroAtivo').value;
        if (at) params.set('ativo', at);
        const esc = $('filtroEscopo').value;
        if (esc) params.set('escopo', esc);
        const dt = $('filtroDtRef').value.trim();
        if (dt) params.set('dt_referencia', dt);
        params.set('limit', '200');
        return params.toString();
    }

    async function carregar() {
        const tbody = $('promoListBody');
        tbody.innerHTML = '<tr><td colspan="7" class="ia-placeholder">Carregando…</td></tr>';
        try {
            const r = await fetch(`/sankhya/venda/api/promocoes/listar/?${montarQuery()}`);
            const d = await r.json();
            if (!d.ok) {
                tbody.innerHTML = `<tr><td colspan="7" class="ia-placeholder" style="color:#ef4444">${d.error || 'Erro'}</td></tr>`;
                return;
            }
            const lista = d.promocoes || [];
            $('promoSummary').textContent = `${lista.length} ${lista.length === 1 ? 'promoção' : 'promoções'}`;
            if (!lista.length) {
                tbody.innerHTML = '<tr><td colspan="7" class="ia-placeholder">Nenhuma promoção encontrada.</td></tr>';
                return;
            }
            tbody.innerHTML = '';
            lista.forEach(p => {
                const tr = document.createElement('tr');

                // "Aplica a" — pode ser TABELA ou PARCEIRO
                let aplicaA;
                if (p.escopo === 'TABELA') {
                    // Procura o nome do grupo no cache de tabelas
                    const tg = (tabelasGrupo || []).find(x => Number(x.codtab) === Number(p.codtab));
                    const nome = tg?.nome_grupo ? ` — ${tg.nome_grupo}` : '';
                    aplicaA = `<span class="escopo-badge escopo-tabela"><i class="ph ph-users-three"></i> Tabela ${p.codtab}${nome}</span>
                               <span class="muted"> · ${p.qtd_clientes_grupo} cliente${p.qtd_clientes_grupo > 1 ? 's' : ''}</span>`;
                } else {
                    const nome = p.nomeparc || `(?)`;
                    aplicaA = `<span class="escopo-badge escopo-parceiro"><i class="ph ph-user"></i> ${p.codparc}</span>
                               <span> ${nome}</span>`;
                }

                const produto = `${p.codprod} — ${p.descrprod || '(?)'}`;
                const status = p.ativo === 'S'
                    ? '<span class="promo-status-badge ativa">Ativa</span>'
                    : '<span class="promo-status-badge inativa">Inativa</span>';
                tr.innerHTML = `
                    <td class="ia-truncate">${aplicaA}</td>
                    <td class="ia-truncate" title="${produto}">${produto}</td>
                    <td class="text-right">R$ ${_fmtBRL(p.vlrpromo)}</td>
                    <td>${_fmtDataBR(p.dt_inicio)}</td>
                    <td>${_fmtDataBR(p.dt_fim)}</td>
                    <td class="text-center">${status}</td>
                    <td class="text-center">
                        <button class="icon-btn-mini btn-edit-promo" title="Editar" data-id="${p.id}">
                            <i class="ph ph-pencil-simple" aria-hidden="true"></i>
                        </button>
                        <button class="icon-btn-mini btn-del-promo" title="Excluir" data-id="${p.id}">
                            <i class="ph ph-trash" aria-hidden="true"></i>
                        </button>
                    </td>
                `;
                tr._dadosPromo = p;
                tbody.appendChild(tr);
            });

            tbody.querySelectorAll('.btn-edit-promo').forEach(b => {
                b.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const id = parseInt(b.dataset.id, 10);
                    const linha = b.closest('tr');
                    abrirModal(linha?._dadosPromo || { id });
                });
            });
            tbody.querySelectorAll('.btn-del-promo').forEach(b => {
                b.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const id = parseInt(b.dataset.id, 10);
                    const ok = await IAgro.confirmarAcao({
                        titulo: 'Excluir promoção?',
                        mensagem: 'Tem certeza? Essa operação é permanente.',
                        confirmarLabel: 'Excluir',
                        tipo: 'perigo',
                    });
                    if (!ok) return;
                    const res = await IAgro.postJSON('/sankhya/venda/api/promocao/excluir/', { id });
                    if (res.ok && res.body?.ok) {
                        toast('Promoção excluída.', 'success');
                        carregar();
                    } else {
                        toast(res.body?.error || 'Falha ao excluir.', 'error');
                    }
                });
            });
        } catch (e) {
            console.error(e);
            tbody.innerHTML = `<tr><td colspan="7" class="ia-placeholder" style="color:#ef4444">Erro: ${e.message}</td></tr>`;
        }
    }

    // ────────────────── Modal nova/editar ──────────────────
    function setEscopo(escopo) {
        document.querySelectorAll('input[name="promoEscopo"]').forEach(r => {
            r.checked = (r.value === escopo);
        });
        $('promoEscopoTabelaWrap').classList.toggle('hidden', escopo !== 'TABELA');
        $('promoEscopoParceiroWrap').classList.toggle('hidden', escopo !== 'PARCEIRO');
    }

    function abrirModal(promo) {
        const overlay = $('promoModalOverlay');
        if (!overlay) return;
        $('promoId').value = promo.id || '';
        $('promoModalTitle').textContent = promo.id ? 'Editar promoção' : 'Nova promoção';

        if (promo.id) {
            // Modo edição
            const escopo = promo.escopo || (promo.codtab ? 'TABELA' : 'PARCEIRO');
            setEscopo(escopo);
            if (escopo === 'TABELA') {
                $('promoCodtab').value = promo.codtab || '';
                atualizarHintTabela();
                $('promoCodparc').value = '';
                $('promoParcSearch').value = '';
            } else {
                $('promoCodtab').value = '';
                $('promoCodparc').value = promo.codparc || '';
                $('promoParcSearch').value = promo.codparc ? `${promo.codparc} — ${promo.nomeparc || ''}` : '';
            }
            $('promoCodprod').value     = promo.codprod || '';
            $('promoProdSearch').value  = promo.codprod ? `${promo.codprod} — ${promo.descrprod || ''}` : '';
            $('promoVlr').value         = promo.vlrpromo || '';
            $('promoDtInicio').value    = promo.dt_inicio || '';
            $('promoDtFim').value       = promo.dt_fim || '';
            $('promoAtivo').value       = promo.ativo || 'S';
            $('promoObs').value         = promo.observacao || '';
        } else {
            // Modo nova
            setEscopo('TABELA');
            ['promoCodtab', 'promoCodparc', 'promoParcSearch', 'promoCodprod', 'promoProdSearch',
             'promoVlr', 'promoObs'].forEach(id => { $(id).value = ''; });
            $('promoTabHint').textContent = '';
            $('promoDtInicio').value = _hojeISO();
            const fim = new Date();
            fim.setDate(fim.getDate() + 30);
            $('promoDtFim').value = `${fim.getFullYear()}-${String(fim.getMonth() + 1).padStart(2, '0')}-${String(fim.getDate()).padStart(2, '0')}`;
            $('promoAtivo').value = 'S';
        }

        overlay.classList.remove('hidden');
        overlay.style.display = 'flex';
        setTimeout(() => {
            const escopo = document.querySelector('input[name="promoEscopo"]:checked')?.value;
            if (escopo === 'TABELA') $('promoCodtab')?.focus();
            else $('promoParcSearch')?.focus();
        }, 80);
    }

    function fecharModal() {
        const overlay = $('promoModalOverlay');
        if (!overlay) return;
        overlay.classList.add('hidden');
        overlay.style.display = '';
    }

    async function salvar() {
        const id        = parseInt($('promoId').value || '0', 10);
        const escopo    = document.querySelector('input[name="promoEscopo"]:checked')?.value || 'TABELA';
        const codtab    = parseInt($('promoCodtab').value, 10);
        const codparc   = parseInt($('promoCodparc').value, 10);
        const codprod   = parseInt($('promoCodprod').value, 10);
        const vlrpromo  = parseFloat($('promoVlr').value);
        const dt_inicio = $('promoDtInicio').value;
        const dt_fim    = $('promoDtFim').value;
        const ativo     = $('promoAtivo').value;
        const obs       = $('promoObs').value.trim();

        const falta = [];
        if (escopo === 'TABELA' && !codtab) falta.push('Grupo (tabela)');
        if (escopo === 'PARCEIRO' && !codparc) falta.push('Cliente');
        if (!codprod) falta.push('Produto');
        if (!vlrpromo || vlrpromo <= 0) falta.push('Preço (> 0)');
        if (!dt_inicio) falta.push('Início');
        if (!dt_fim) falta.push('Fim');
        if (falta.length) {
            toast(`Preencha: ${falta.join(', ')}.`, 'warning');
            return;
        }
        if (dt_inicio > dt_fim) {
            toast('Data fim deve ser maior ou igual ao início.', 'warning');
            return;
        }

        const payload = {
            codprod, vlrpromo, dt_inicio, dt_fim, ativo,
            observacao: obs || null,
        };
        if (escopo === 'TABELA') {
            payload.codtab = codtab;
        } else {
            payload.codparc = codparc;
        }

        const url = id
            ? '/sankhya/venda/api/promocao/editar/'
            : '/sankhya/venda/api/promocao/criar/';
        if (id) payload.id = id;

        const btn = $('promoModalSalvar');
        btn.disabled = true;
        try {
            const res = await IAgro.postJSON(url, payload);
            if (res.ok && res.body?.ok) {
                toast(id ? 'Promoção atualizada.' : 'Promoção criada.', 'success');
                fecharModal();
                carregar();
            } else {
                toast(res.body?.error || 'Falha ao salvar.', 'error');
            }
        } finally {
            btn.disabled = false;
        }
    }

    // ────────────────── Bind ──────────────────
    $('btnPromoNova')?.addEventListener('click', () => abrirModal({}));
    $('promoModalClose')?.addEventListener('click', fecharModal);
    $('promoModalCancel')?.addEventListener('click', fecharModal);
    $('promoModalSalvar')?.addEventListener('click', salvar);

    document.querySelectorAll('input[name="promoEscopo"]').forEach(r => {
        r.addEventListener('change', () => setEscopo(r.value));
    });
    $('promoCodtab')?.addEventListener('change', atualizarHintTabela);

    $('btnUpdate')?.addEventListener('click', carregar);
    $('btnClear')?.addEventListener('click', () => {
        ['filtroQ', 'filtroParc', 'filtroParcSearch', 'filtroProd', 'filtroProdSearch', 'filtroDtRef']
            .forEach(id => { const el = $(id); if (el) el.value = ''; });
        $('filtroAtivo').value = 'S';
        $('filtroEscopo').value = '';
        carregar();
    });
    IAgro.wireFilterAuto?.(['filtroQ', 'filtroAtivo', 'filtroEscopo', 'filtroDtRef'], carregar, { debounceMs: 500 });

    // Boot
    carregarTabelasGrupo();
    carregar();
})();
