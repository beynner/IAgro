/* =============================================================================
   Controle de Caixas — frontend (Mai/2026)
   - Aba Saldo: lista clientes c/ saldo > 0; click abre timeline
   - Aba Produtos: lista AD_PRODUTO_CAIXA
   - Modais: lançar coleta (B1) + cadastrar produto-caixa (B3) → hoje retornam 501
   ============================================================================= */

(function () {
    'use strict';

    const $  = (sel, ctx = document) => ctx.querySelector(sel);
    const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

    // Estado global da tela
    const state = {
        clientes:        [],
        clienteAtivo:    null,    // codparc selecionado
        incluirZerados:  false,
        buscaQ:          '',
        carregadoSaldo:  false,
        timelineDias:    90,
    };

    // ---------------------------------------------------------------- Helpers

    function fmtNum(n) {
        return new Intl.NumberFormat('pt-BR').format(Number(n) || 0);
    }

    function fmtData(iso) {
        if (!iso) return '—';
        const [y, m, d] = iso.split('-');
        return `${d}/${m}/${y.slice(2)}`;
    }

    function setLoading(btn, on) {
        if (!btn) return;
        btn.classList.toggle('is-loading', !!on);
        btn.disabled = !!on;
    }

    function showToast(msg, tipo = 'info') {
        if (window.IAgro && window.IAgro.showToast) {
            window.IAgro.showToast(msg, tipo);
        } else {
            alert(msg);
        }
    }

    // ---------------------------------------------------------- Refresh

    function setupRefresh() {
        $('#cxBtnRefresh').addEventListener('click', async () => {
            // =================================================================
            // !!! TEMPORÁRIO Mai/2026 — REMOVER QUANDO IAGRO VIRAR FLUXO ÚNICO
            //
            // Hoje 99% das vendas TGFITE TOP 35/37 chegam com PESO=0
            // (faturadas direto no Sankhya, sem passar pelo Rastreio).
            // O endpoint faz backfill via moda da TOP 26 antes de recarregar
            // o saldo — garante que vendas novas ganhem peso a cada refresh.
            //
            // PARA REMOVER (quando IAgro virar fluxo único):
            // basta excluir o bloco abaixo, deixando só as 2 linhas finais
            // de carregarSaldo/carregarProdutos.
            // =================================================================
            setLoading($('#cxBtnRefresh'), true);
            mostrarBannerProcessando('Processando pesos das notas…');
            try {
                const resp = await window.IAgro.postJSON('/sankhya/caixas/api/refresh-pesos/', {});
                const body = resp.body || {};
                if (body.ok && body.linhas_atualizadas > 0) {
                    showToast(`${body.linhas_atualizadas} vendas atualizadas com peso.`, 'success');
                }
            } catch (err) {
                // backfill é "best effort" — se falhar, segue pra recarregar
                console.warn('Refresh pesos falhou:', err);
            } finally {
                esconderBannerProcessando();
            }
            // =================================================================
            // -- FIM DO BLOCO TEMPORÁRIO --
            // =================================================================

            carregarSaldo(true);
        });
    }

    // ---------------------------------------------------------------- Banner
    // Banner sticky no topo do .cx-layout durante operações longas
    // (refresh-pesos pode demorar segundos a minutos)
    function mostrarBannerProcessando(msg) {
        let banner = $('#cxBannerProcessando');
        if (!banner) {
            banner = document.createElement('div');
            banner.id = 'cxBannerProcessando';
            banner.className = 'cx-banner-processando';
            banner.innerHTML = `
                <i class="ph ph-circle-notch" aria-hidden="true"></i>
                <span class="cx-banner-msg"></span>
            `;
            const layout = $('.cx-layout');
            if (layout) layout.insertBefore(banner, layout.firstChild);
        }
        banner.querySelector('.cx-banner-msg').textContent = msg;
        banner.classList.add('is-visible');
    }
    function esconderBannerProcessando() {
        const banner = $('#cxBannerProcessando');
        if (banner) banner.classList.remove('is-visible');
    }

    // ---------------------------------------------------- Aba SALDO — lista

    async function carregarSaldo(forcar = false) {
        if (state.carregadoSaldo && !forcar) return;
        const lista = $('#cxClientesLista');
        lista.innerHTML = '<div class="cx-empty">Carregando…</div>';
        setLoading($('#cxBtnRefresh'), true);

        const params = new URLSearchParams();
        params.set('apenas_saldo_positivo', state.incluirZerados ? 'false' : 'true');
        if (state.buscaQ) params.set('q', state.buscaQ);

        try {
            const resp = await fetch(`/sankhya/caixas/api/saldo/?${params.toString()}`, {
                headers: { 'Accept': 'application/json' },
            });
            const data = await resp.json();
            if (!data.ok) throw new Error(data.error || 'Falha ao carregar saldo');

            state.clientes = data.linhas || [];
            state.carregadoSaldo = true;
            renderClientes();
            atualizarResumo(data);
        } catch (err) {
            lista.innerHTML = `<div class="cx-erro">${err.message}</div>`;
            console.error('carregarSaldo', err);
        } finally {
            setLoading($('#cxBtnRefresh'), false);
        }
    }

    function atualizarResumo(data) {
        $('#cxResumoEmCampo').textContent  = fmtNum(data.total_caixas || 0);
        $('#cxResumoClientes').textContent = fmtNum(data.total_clientes || 0);

        // Quebradas / perdidas — agrega das linhas (filtro client-side dos 30 dias
        // não é trivial sem outra query; por enquanto soma total do snapshot).
        let q = 0, p = 0;
        for (const l of state.clientes) {
            q += l.caixas_quebradas || 0;
            p += l.caixas_perdidas  || 0;
        }
        $('#cxResumoQuebradas').textContent = fmtNum(q);
        $('#cxResumoPerdidas').textContent  = fmtNum(p);
    }

    function renderClientes() {
        const lista = $('#cxClientesLista');
        if (state.clientes.length === 0) {
            lista.innerHTML = '<div class="cx-empty">Nenhum cliente com caixa em campo.</div>';
            $('#cxClientesContador').textContent = '0';
            return;
        }
        $('#cxClientesContador').textContent = `${state.clientes.length} cliente${state.clientes.length === 1 ? '' : 's'}`;

        const html = state.clientes.map(c => {
            const zero = c.saldo === 0 ? 'cx-cliente-saldo--zero' : '';
            const ativo = c.codparc === state.clienteAtivo ? 'is-active' : '';
            const ultUltima = c.ultima_saida || c.ultima_coleta || '—';
            return `
                <div class="cx-cliente-card ${ativo}" data-codparc="${c.codparc}">
                    <div class="cx-cliente-info">
                        <div class="cx-cliente-nome" title="${escapeHtml(c.nomeparc)}">${escapeHtml(c.nomeparc)}</div>
                        <div class="cx-cliente-meta">${c.codparc} · última mov: ${fmtData(ultUltima)}</div>
                    </div>
                    <div class="cx-cliente-saldo ${zero}">${fmtNum(c.saldo)}</div>
                </div>
            `;
        }).join('');
        lista.innerHTML = html;

        $$('.cx-cliente-card', lista).forEach(card => {
            card.addEventListener('click', () => {
                const cp = parseInt(card.dataset.codparc, 10);
                selecionarCliente(cp);
            });
        });
    }

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ----------------------------------------------- Aba SALDO — detalhe/timeline

    async function selecionarCliente(codparc) {
        state.clienteAtivo = codparc;
        $$('.cx-cliente-card').forEach(c => {
            c.classList.toggle('is-active', parseInt(c.dataset.codparc, 10) === codparc);
        });

        const cliente = state.clientes.find(c => c.codparc === codparc);
        if (!cliente) return;

        $('#cxDetalheVazio').hidden = true;
        $('#cxDetalheCard').hidden  = false;
        $('#cxDetalheNome').textContent     = cliente.nomeparc;
        $('#cxDetalheCodparc').textContent  = `CODPARC ${cliente.codparc}`;
        $('#cxDetalheSaldo').textContent    = fmtNum(cliente.saldo);
        $('#cxStatEnviadas').textContent    = fmtNum(cliente.caixas_enviadas);
        $('#cxStatColetadas').textContent   = fmtNum(cliente.caixas_coletadas);
        $('#cxStatQuebradas').textContent   = fmtNum(cliente.caixas_quebradas);
        $('#cxStatPerdidas').textContent    = fmtNum(cliente.caixas_perdidas);

        const tl = $('#cxTimeline');
        tl.innerHTML = '<div class="cx-empty">Carregando timeline…</div>';
        $('#cxTimelineDias').textContent = state.timelineDias;

        try {
            const resp = await fetch(`/sankhya/caixas/api/timeline/${codparc}/?dias=${state.timelineDias}`);
            const data = await resp.json();
            if (!data.ok) throw new Error(data.error || 'Falha ao carregar timeline');
            renderTimeline(data.eventos || []);
        } catch (err) {
            tl.innerHTML = `<div class="cx-erro">${err.message}</div>`;
            console.error('selecionarCliente timeline', err);
        }
    }

    function renderTimeline(eventos) {
        const tl = $('#cxTimeline');
        if (eventos.length === 0) {
            tl.innerHTML = '<div class="cx-empty">Sem eventos no período.</div>';
            return;
        }

        const mapaTipo = {
            'VIAGEM':        { classe: 'cx-evento--viagem',    icone: 'ph-truck',            label: 'Viagem' },
            'COLETA':        { classe: 'cx-evento--coleta',    icone: 'ph-arrow-down-left',  label: 'Coleta' },
            'QUEBRA':        { classe: 'cx-evento--quebra',    icone: 'ph-warning',          label: 'Quebra' },
            'PERDA':         { classe: 'cx-evento--perda',     icone: 'ph-x-circle',         label: 'Perda' },
            'AJUSTE_SALDO':  { classe: 'cx-evento--ajuste',    icone: 'ph-pencil-simple',    label: 'Ajuste de saldo' },
            // Legado (eventos pre-2026-05-29 — só renderiza se aparecerem):
            'SAIDA':         { classe: 'cx-evento--saida',     icone: 'ph-arrow-up-right',   label: 'Saída (legado)' },
            'DEVOLUCAO':     { classe: 'cx-evento--devolucao', icone: 'ph-arrow-down-left',  label: 'Devolução (legado)' },
        };

        const html = eventos.map(e => {
            const m = mapaTipo[e.tipo] || { classe: '', icone: 'ph-circle', label: e.tipo };
            const estornadoCls = e.estornado ? 'cx-evento--estornado' : '';
            const data = fmtData(e.data);

            let infoExtra = '';
            if (e.tipo === 'VIAGEM' && e.num_viagem) {
                const tituloViagem = `Viagem #${e.num_viagem}`;
                const detalhe = e.descricao ? ` — ${escapeHtml(e.descricao)}` : '';
                infoExtra = `<div class="cx-evento-desc">${escapeHtml(tituloViagem)}${detalhe}</div>`;
                if (e.observacao) {
                    infoExtra += `<div class="cx-evento-obs">${escapeHtml(e.observacao)}</div>`;
                }
            } else if (e.nunota) {
                const notaLbl = e.numnota ? `Nota ${e.numnota}` : `NUNOTA ${e.nunota}`;
                infoExtra = `<div class="cx-evento-desc">${escapeHtml(notaLbl)}${e.descricao ? ' — ' + escapeHtml(e.descricao) : ''}</div>`;
            } else if (e.observacao) {
                infoExtra = `<div class="cx-evento-desc">${escapeHtml(e.observacao)}</div>`;
            }
            const usuario = (e.tipo === 'COLETA' && e.motorista_nome)
                ? ` · Motorista: ${escapeHtml(e.motorista_nome)}`
                : (e.nomeusu ? ` · por ${escapeHtml(e.nomeusu)}` : '');
            const estornadoBadge = e.estornado ? ' <small style="color:#dc2626">(estornado)</small>' : '';

            // AJUSTE_SALDO mostra sinal real da qtd (pode ser + ou −).
            // VIAGEM/SAIDA é + (sai do nosso estoque, soma saldo em campo).
            // Outros tipos (COLETA/QUEBRA/PERDA/DEVOLUCAO) descontam saldo → −.
            let sinal, qtdExibida;
            if (e.tipo === 'AJUSTE_SALDO') {
                qtdExibida = Math.abs(e.qtd_caixas);
                sinal = e.qtd_caixas >= 0 ? '+' : '−';
            } else if (e.tipo === 'VIAGEM' || e.tipo === 'SAIDA') {
                qtdExibida = e.qtd_caixas;
                sinal = '+';
            } else {
                qtdExibida = e.qtd_caixas;
                sinal = '−';
            }

            // Botão estornar só em eventos manuais (têm id_coleta) e não estornados
            const podeEstornar = e.id_coleta && !e.estornado;
            const btnEstornar = podeEstornar
                ? `<button type="button" class="cx-btn-estornar" data-id="${e.id_coleta}" title="Estornar este lançamento">
                       <i class="ph ph-arrow-counter-clockwise"></i>
                   </button>`
                : '';

            return `
                <div class="cx-evento ${m.classe} ${estornadoCls}">
                    <div class="cx-evento-icone"><i class="ph ${m.icone}"></i></div>
                    <div class="cx-evento-corpo">
                        <div class="cx-evento-tit">${m.label}${estornadoBadge} <small>${data}${usuario}</small></div>
                        ${infoExtra}
                    </div>
                    <div class="cx-evento-qtd">${sinal}${fmtNum(qtdExibida)}</div>
                    ${btnEstornar}
                </div>
            `;
        }).join('');
        tl.innerHTML = html;

        // Bind dos botões de estorno
        tl.querySelectorAll('.cx-btn-estornar').forEach(btn => {
            btn.addEventListener('click', async (ev) => {
                ev.stopPropagation();
                const id = parseInt(btn.dataset.id, 10);
                await estornarColeta(id);
            });
        });
    }

    async function estornarColeta(idColeta) {
        let motivo = '';
        if (window.IAgro && window.IAgro.confirmarAcao) {
            const ok = await window.IAgro.confirmarAcao({
                titulo:   'Estornar coleta',
                mensagem: 'Esta coleta vai ser marcada como estornada. O saldo do cliente sobe novamente. Audit preservado. Tem certeza?',
                tipo:     'aviso',
            });
            if (!ok) return;
            motivo = prompt('Motivo do estorno (opcional, mas recomendado):', 'Lançamento incorreto') || 'Estornado pelo operador';
        } else {
            if (!confirm('Estornar esta coleta?')) return;
            motivo = prompt('Motivo do estorno:', 'Lançamento incorreto') || 'Estornado pelo operador';
        }

        try {
            const resp = await window.IAgro.postJSON(
                `/sankhya/caixas/api/coleta/${idColeta}/estornar/`,
                { motivo_estorno: motivo },
            );
            const body = resp.body || {};
            if (!resp.ok || !body.ok) {
                showToast(body.error || `Erro HTTP ${resp.status}`, 'error');
                return;
            }
            showToast('Coleta estornada.', 'success');
            carregarSaldo(true);
            if (state.clienteAtivo) selecionarCliente(state.clienteAtivo);
        } catch (err) {
            showToast('Falha de comunicação: ' + err.message, 'error');
        }
    }

    // ----------------------------------------- Aba SALDO — busca + filtro

    function setupFiltros() {
        const debounce = (fn, ms) => {
            let t;
            return (...args) => {
                clearTimeout(t);
                t = setTimeout(() => fn(...args), ms);
            };
        };

        const buscaInput = $('#cxBusca');
        const aplicarBusca = debounce(() => {
            state.buscaQ = buscaInput.value.trim();
            carregarSaldo(true);
        }, 400);
        buscaInput.addEventListener('input', aplicarBusca);

        $('#cxIncluirZerados').addEventListener('change', e => {
            state.incluirZerados = e.target.checked;
            carregarSaldo(true);
        });
    }

    // ------------------------------------- Modal Lançar coleta (B1 stub)

    function setupModalColeta() {
        const modal = $('#cxColetaModal');
        const abrir = (codparc = null, nomeparc = null, motivoPre = 'COLETA') => {
            $('#cxColetaForm').reset();
            $('#cxColetaMsg').hidden = true;
            // Default data = hoje
            $('#cxColetaData').valueAsDate = new Date();
            if (codparc) {
                $('#cxColetaCliente').value = nomeparc || '';
                $('#cxColetaCodparc').value = codparc;
            }
            // Pré-seleciona motivo (default COLETA)
            const r = document.querySelector(`input[name="motivo"][value="${motivoPre}"]`);
            if (r) r.checked = true;
            modal.classList.remove('hidden');
            modal.setAttribute('aria-hidden', 'false');
        };
        const fechar = () => {
            modal.classList.add('hidden');
            modal.setAttribute('aria-hidden', 'true');
        };

        $('#btnLancarColeta').addEventListener('click', () => {
            // Se um cliente está selecionado, pré-preenche
            if (state.clienteAtivo) {
                const c = state.clientes.find(x => x.codparc === state.clienteAtivo);
                abrir(state.clienteAtivo, c ? c.nomeparc : '', 'COLETA');
            } else {
                abrir(null, null, 'COLETA');
            }
        });
        $('#cxBtnColetaCliente').addEventListener('click', () => {
            const c = state.clientes.find(x => x.codparc === state.clienteAtivo);
            abrir(state.clienteAtivo, c ? c.nomeparc : '', 'COLETA');
        });

        modal.querySelectorAll('[data-modal-close]').forEach(b => b.addEventListener('click', fechar));
        modal.addEventListener('click', e => {
            if (e.target === modal) fechar();
        });

        // Typeahead de parceiro (B1 vai precisar de fato — por enquanto stub bloqueia)
        if (window.IAgro && window.IAgro.attachTypeahead) {
            window.IAgro.attachTypeahead({
                inputId:    'cxColetaCliente',
                hiddenId:   'cxColetaCodparc',
                dropdownId: 'cxColetaClienteDropdown',
                url:        '/sankhya/parceiros/search/',
                pickItems:  (data) => data.results || [],
                pickCod:    (it) => it.codparc,
                pickDescr:  (it) => it.nomeparc,
                renderItem: (it) => `${it.codparc} — ${it.nomeparc}`,
            });

            // Typeahead Motorista (AD_PARCEIRO_TIPO tipo=4) — mesma fonte da Logística
            window.IAgro.attachTypeahead({
                inputId:    'cxColetaMotorista',
                hiddenId:   'cxColetaMotoristaCodparc',
                dropdownId: 'cxColetaMotoristaDropdown',
                url:        '/sankhya/logistica/api/parceiros/?tipo=4',
                pickItems:  (data) => data.parceiros || [],
                pickCod:    (it) => it.codparc,
                pickDescr:  (it) => it.nomeparc,
                renderItem: (it) => `${it.codparc} — ${it.nomeparc}`,
            });
        }

        // Visibilidade condicional do campo Motorista (só em COLETA)
        const aplicarVisibilidadeMotorista = () => {
            const motivo = (document.querySelector('input[name="motivo"]:checked') || {}).value || 'COLETA';
            const wrap   = $('#cxColetaMotoristaWrap');
            const ehColeta = motivo === 'COLETA';
            if (wrap) wrap.style.display = ehColeta ? '' : 'none';
            if (!ehColeta) {
                $('#cxColetaMotorista').value = '';
                $('#cxColetaMotoristaCodparc').value = '';
            }
        };
        document.querySelectorAll('input[name="motivo"]').forEach(r => {
            r.addEventListener('change', aplicarVisibilidadeMotorista);
        });
        // Inicializa visibilidade ao abrir modal
        aplicarVisibilidadeMotorista();

        $('#cxColetaSalvar').addEventListener('click', async () => {
            const msgEl = $('#cxColetaMsg');
            const codparc = parseInt($('#cxColetaCodparc').value || '0', 10);
            const qtdRaw  = $('#cxColetaQtd').value;
            const qtd     = parseInt(qtdRaw || '0', 10);
            const data    = $('#cxColetaData').value;
            const motivo  = (document.querySelector('input[name="motivo"]:checked') || {}).value || 'COLETA';
            const obs     = $('#cxColetaObs').value.trim();

            if (!codparc || !data) {
                msgEl.textContent = 'Cliente e data são obrigatórios.';
                msgEl.className = 'cx-form-msg is-error';
                msgEl.hidden = false;
                return;
            }
            if (isNaN(qtd) || qtd < 1) {
                msgEl.textContent = 'Quantidade deve ser > 0.';
                msgEl.className = 'cx-form-msg is-error';
                msgEl.hidden = false;
                return;
            }

            try {
                const resp = await window.IAgro.postJSON('/sankhya/caixas/api/coleta/criar/', {
                    codparc, qtd_caixas: qtd, data_coleta: data, motivo, observacao: obs,
                });
                const body = resp.body || {};
                if (!resp.ok || !body.ok) {
                    msgEl.textContent = body.error || `Erro HTTP ${resp.status}`;
                    msgEl.className = 'cx-form-msg is-error';
                    msgEl.hidden = false;
                    return;
                }
                showToast('Coleta lançada.', 'success');
                fechar();
                carregarSaldo(true);
                if (state.clienteAtivo) selecionarCliente(state.clienteAtivo);
            } catch (err) {
                msgEl.textContent = 'Falha de comunicação: ' + err.message;
                msgEl.className = 'cx-form-msg is-error';
                msgEl.hidden = false;
            }
        });
    }

    // ------------------------------------------------------- Boot

    document.addEventListener('DOMContentLoaded', () => {
        setupRefresh();
        setupFiltros();
        setupModalColeta();
        carregarSaldo(true);
    });
})();
