/* =============================================================================
   AJUSTES ADMINISTRATIVOS — frontend (Mai/2026 — 2026-05-28)
   Tela: /sankhya/configuracoes/ajustes/
   - Aba Caixas: lança AJUSTE_SALDO em AD_COLETA_CAIXAS (positivo/negativo)
   - Aba Combustível: lança AJUSTE_AVULSO em AD_REQUISICAO_COMBUSTIVEL (sem veículo)
   - Lista lateral mostra últimos ajustes
   ============================================================================= */

(function () {
    'use strict';

    const $  = (sel, ctx = document) => ctx.querySelector(sel);
    const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

    const state = {
        abaAtiva:        'caixas',
        carregadoCaixas: false,
        carregadoCombustivel: false,
    };

    // -------------------- Helpers --------------------
    const fmtNum = (n) => {
        const v = Number(n) || 0;
        return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 }).format(v);
    };

    const fmtNumSign = (n) => {
        const v = Number(n) || 0;
        const sign = v > 0 ? '+' : (v < 0 ? '−' : '');
        return sign + new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 }).format(Math.abs(v));
    };

    const fmtData = (iso) => {
        if (!iso) return '—';
        const [y, m, d] = iso.split('-');
        return `${d}/${m}/${y.slice(2)}`;
    };

    const escapeHtml = (s) => {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    };

    const setLoading = (btn, on) => {
        if (!btn) return;
        btn.classList.toggle('is-loading', !!on);
        btn.disabled = !!on;
    };

    const showToast = (msg, tipo) => {
        if (window.IAgro && window.IAgro.showToast) window.IAgro.showToast(msg, tipo || 'info');
        else alert(msg);
    };

    // -------------------- Tabs --------------------
    function setupTabs() {
        $$('.aj-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const alvo = tab.dataset.tab;
                if (!alvo || alvo === state.abaAtiva) return;
                state.abaAtiva = alvo;

                $$('.aj-tab').forEach(t => {
                    const ativo = t.dataset.tab === alvo;
                    t.classList.toggle('is-active', ativo);
                    t.setAttribute('aria-selected', ativo ? 'true' : 'false');
                });
                $$('.aj-pane').forEach(p => {
                    p.hidden = p.dataset.pane !== alvo;
                });

                if (alvo === 'caixas' && !state.carregadoCaixas) carregarCaixas();
                if (alvo === 'combustivel' && !state.carregadoCombustivel) carregarCombustivel();
            });
        });
    }

    // ====================================================================
    // ABA CAIXAS — AJUSTE_SALDO
    // ====================================================================

    function setupTypeaheadCaixas() {
        if (!window.IAgro || !window.IAgro.attachTypeahead) return;
        window.IAgro.attachTypeahead({
            inputId:    'ajCxCliente',
            hiddenId:   'ajCxCodparc',
            dropdownId: 'ajCxClienteDropdown',
            url:        '/sankhya/parceiros/search/',
            pickItems:  (data) => data.results || [],
            pickCod:    (it) => it.codparc,
            pickDescr:  (it) => it.nomeparc,
            renderItem: (it) => `${it.codparc} — ${it.nomeparc}`,
        });
    }

    function setupFormCaixas() {
        // Data default = hoje
        $('#ajCxData').valueAsDate = new Date();

        $('#ajCxSalvar').addEventListener('click', async () => {
            const msg = $('#ajCxMsg');
            const codparc = parseInt($('#ajCxCodparc').value || '0', 10);
            const qtd     = parseInt($('#ajCxQtd').value || '0', 10);
            const data    = $('#ajCxData').value;
            const obs     = $('#ajCxObs').value.trim();

            if (!codparc) {
                return msgError(msg, 'Selecione um cliente.');
            }
            if (!data) {
                return msgError(msg, 'Informe a data.');
            }
            if (isNaN(qtd) || qtd === 0) {
                return msgError(msg, 'Quantidade deve ser ≠ 0 (positivo soma · negativo desconta).');
            }
            if (obs.length < 5) {
                return msgError(msg, 'Justificativa obrigatória (mínimo 5 caracteres).');
            }

            const btn = $('#ajCxSalvar');
            setLoading(btn, true);
            try {
                const resp = await window.IAgro.postJSON('/sankhya/configuracoes/api/ajustes/caixas/criar/', {
                    codparc, qtd, data, observacao: obs,
                });
                const body = resp.body || {};
                if (!resp.ok || !body.ok) {
                    msgError(msg, body.error || `Erro HTTP ${resp.status}`);
                    return;
                }
                msgSuccess(msg, 'Ajuste lançado.');
                showToast('Ajuste de caixas lançado.', 'success');
                $('#ajCxCliente').value = '';
                $('#ajCxCodparc').value = '';
                $('#ajCxQtd').value = '';
                $('#ajCxObs').value = '';
                carregarCaixas();
            } catch (err) {
                msgError(msg, 'Falha de comunicação: ' + err.message);
            } finally {
                setLoading(btn, false);
            }
        });

        $('#ajCxRefresh').addEventListener('click', () => carregarCaixas());
    }

    async function carregarCaixas() {
        const lista = $('#ajCxLista');
        lista.innerHTML = '<div class="aj-empty">Carregando…</div>';
        setLoading($('#ajCxRefresh'), true);
        try {
            const resp = await fetch('/sankhya/configuracoes/api/ajustes/caixas/listar/?limite=30');
            const data = await resp.json();
            if (!data.ok) throw new Error(data.error || 'Falha');
            state.carregadoCaixas = true;
            renderListaCaixas(data.ajustes || []);
        } catch (err) {
            lista.innerHTML = `<div class="aj-erro">${escapeHtml(err.message)}</div>`;
        } finally {
            setLoading($('#ajCxRefresh'), false);
        }
    }

    function renderListaCaixas(ajustes) {
        const lista = $('#ajCxLista');
        if (!ajustes.length) {
            lista.innerHTML = '<div class="aj-empty">Nenhum ajuste lançado ainda.</div>';
            return;
        }
        lista.innerHTML = ajustes.map(a => {
            const qtdNum = Number(a.qtd_caixas) || 0;
            const sinal = qtdNum >= 0 ? 'positivo' : 'negativo';
            const data = fmtData(a.data_coleta);
            const usuario = a.nomeusu ? ` · ${escapeHtml(a.nomeusu)}` : '';
            const obs = a.observacao ? `<div class="aj-ajuste-obs">${escapeHtml(a.observacao)}</div>` : '';
            return `
                <div class="aj-ajuste-card aj-ajuste-card--${sinal}">
                    <div class="aj-ajuste-info">
                        <div class="aj-ajuste-titulo">${escapeHtml(a.nomeparc || '—')}</div>
                        <div class="aj-ajuste-meta">${data}${usuario} · CODPARC ${a.codparc}</div>
                        ${obs}
                    </div>
                    <div class="aj-ajuste-qtd">${fmtNumSign(qtdNum)}</div>
                </div>
            `;
        }).join('');
    }

    // ====================================================================
    // ABA COMBUSTÍVEL — AJUSTE_AVULSO
    // ====================================================================

    function setupTypeaheadCombustivel() {
        if (!window.IAgro || !window.IAgro.attachTypeahead) return;
        window.IAgro.attachTypeahead({
            inputId:    'ajCbProduto',
            hiddenId:   'ajCbCodprod',
            dropdownId: 'ajCbProdutoDropdown',
            url:        '/sankhya/combustivel/api/produtos/',
            pickItems:  (data) => data.produtos || data.results || [],
            pickCod:    (it) => it.codprod || it.cod,
            pickDescr:  (it) => it.descrprod || it.descr,
            renderItem: (it) => `${it.codprod || it.cod} — ${it.descrprod || it.descr}`,
        });
    }

    function setupFormCombustivel() {
        $('#ajCbData').valueAsDate = new Date();

        $('#ajCbSalvar').addEventListener('click', async () => {
            const msg = $('#ajCbMsg');
            const codprod = parseInt($('#ajCbCodprod').value || '0', 10);
            const qtdRaw  = $('#ajCbQtd').value;
            const qtd     = parseFloat(qtdRaw);
            const data    = $('#ajCbData').value;
            const obs     = $('#ajCbObs').value.trim();

            if (!codprod) {
                return msgError(msg, 'Selecione um combustível.');
            }
            if (!data) {
                return msgError(msg, 'Informe a data.');
            }
            if (isNaN(qtd) || qtd === 0) {
                return msgError(msg, 'Quantidade deve ser ≠ 0 (positivo soma · negativo desconta).');
            }
            if (obs.length < 5) {
                return msgError(msg, 'Justificativa obrigatória (mínimo 5 caracteres).');
            }

            const btn = $('#ajCbSalvar');
            setLoading(btn, true);
            try {
                const resp = await window.IAgro.postJSON('/sankhya/configuracoes/api/ajustes/combustivel/criar/', {
                    codprod, qtd, data, observacao: obs,
                });
                const body = resp.body || {};
                if (!resp.ok || !body.ok) {
                    msgError(msg, body.error || `Erro HTTP ${resp.status}`);
                    return;
                }
                msgSuccess(msg, 'Ajuste lançado.');
                showToast('Ajuste de combustível lançado.', 'success');
                $('#ajCbProduto').value = '';
                $('#ajCbCodprod').value = '';
                $('#ajCbQtd').value = '';
                $('#ajCbObs').value = '';
                carregarCombustivel();
            } catch (err) {
                msgError(msg, 'Falha de comunicação: ' + err.message);
            } finally {
                setLoading(btn, false);
            }
        });

        $('#ajCbRefresh').addEventListener('click', () => carregarCombustivel());
    }

    async function carregarCombustivel() {
        const lista = $('#ajCbLista');
        lista.innerHTML = '<div class="aj-empty">Carregando…</div>';
        setLoading($('#ajCbRefresh'), true);
        try {
            const resp = await fetch('/sankhya/configuracoes/api/ajustes/combustivel/listar/?limite=30');
            const data = await resp.json();
            if (!data.ok) throw new Error(data.error || 'Falha');
            state.carregadoCombustivel = true;
            renderListaCombustivel(data.ajustes || []);
        } catch (err) {
            lista.innerHTML = `<div class="aj-erro">${escapeHtml(err.message)}</div>`;
        } finally {
            setLoading($('#ajCbRefresh'), false);
        }
    }

    function renderListaCombustivel(ajustes) {
        const lista = $('#ajCbLista');
        if (!ajustes.length) {
            lista.innerHTML = '<div class="aj-empty">Nenhum ajuste lançado ainda.</div>';
            return;
        }
        lista.innerHTML = ajustes.map(a => {
            const qtdNum = Number(a.qtdneg) || 0;
            // Sinal: TOP 10 (entrada) é positivo; TOP 53 (requisição) é negativo
            const top = parseInt(a.codtipoper || a.top || 0, 10);
            const sinal = top === 10 ? 'positivo' : 'negativo';
            const qtdAssinada = sinal === 'positivo' ? qtdNum : -qtdNum;
            const data = fmtData(a.dtneg || a.data);
            const usuario = a.nomeusu ? ` · ${escapeHtml(a.nomeusu)}` : '';
            const produto = a.descrprod || a.produto || '—';
            const obs = a.observacao ? `<div class="aj-ajuste-obs">${escapeHtml(a.observacao)}</div>` : '';
            return `
                <div class="aj-ajuste-card aj-ajuste-card--${sinal}">
                    <div class="aj-ajuste-info">
                        <div class="aj-ajuste-titulo">${escapeHtml(produto)}</div>
                        <div class="aj-ajuste-meta">${data}${usuario} · NUNOTA ${a.nunota || '—'}</div>
                        ${obs}
                    </div>
                    <div class="aj-ajuste-qtd">${fmtNumSign(qtdAssinada)} LT</div>
                </div>
            `;
        }).join('');
    }

    // -------------------- Mensagens --------------------
    function msgError(el, txt) {
        el.textContent = txt;
        el.className = 'aj-form-msg is-error';
        el.hidden = false;
    }

    function msgSuccess(el, txt) {
        el.textContent = txt;
        el.className = 'aj-form-msg is-success';
        el.hidden = false;
    }

    // -------------------- Boot --------------------
    document.addEventListener('DOMContentLoaded', () => {
        setupTabs();
        setupTypeaheadCaixas();
        setupTypeaheadCombustivel();
        setupFormCaixas();
        setupFormCombustivel();
        carregarCaixas();  // carrega só a aba inicial
    });
})();
