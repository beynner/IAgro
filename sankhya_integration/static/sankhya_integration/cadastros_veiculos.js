/* ============================================================
   CADASTROS → VEÍCULOS (Mai/2026) — view-only
   ============================================================ */
(function () {
    'use strict';

    const H = window.CadHelpers || {};

    const STATE = {
        veiculos: [],
        selecionado: null,
        filtros: { busca: '', proprio: '', mostrar_inativos: false },
        carregando: false,
    };

    const $ = function (id) { return document.getElementById(id); };

    const COMB_LABEL = {
        D: 'D — Diesel', G: 'G — Gasolina', F: 'F — Flex',
        E: 'E — Etanol', N: 'N — GNV', '': '—',
    };

    function descComb(c) {
        if (!c) return '—';
        return COMB_LABEL[c] || c;
    }

    function descProprio(p) {
        if (p === 'S') return 'S — Próprio (frota / maquinário)';
        if (p === 'N') return 'N — Terceiro (freteiro / cooperado)';
        return p || '—';
    }

    async function carregar() {
        if (STATE.carregando) return;
        STATE.carregando = true;
        const lista = $('veiLista');
        if (lista && !STATE.veiculos.length) {
            lista.innerHTML = '<div class="cad-lista-empty">Carregando…</div>';
        }

        const params = new URLSearchParams();
        if (STATE.filtros.busca) params.set('busca', STATE.filtros.busca);
        if (STATE.filtros.proprio) params.set('proprio', STATE.filtros.proprio);
        if (STATE.filtros.mostrar_inativos) params.set('mostrar_inativos', 'true');
        params.set('limite', '200');

        try {
            const resp = await fetch('/sankhya/cadastros/api/veiculos/listar/?' + params.toString());
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                H.showToast(data.error || 'Falha ao listar veículos.', 'error');
                renderLista([], 0);
                return;
            }
            STATE.veiculos = data.veiculos || [];
            renderLista(STATE.veiculos, data.total || 0);
        } catch (e) {
            console.error(e);
            H.showToast('Erro de comunicação ao listar veículos.', 'error');
            renderLista([], 0);
        } finally {
            STATE.carregando = false;
        }
    }

    function renderLista(veiculos, total) {
        const lista = $('veiLista');
        const contador = $('veiContador');
        if (!lista) return;

        if (contador) {
            const mostrando = veiculos.length;
            contador.textContent = mostrando === total
                ? total + ' veículo' + (total === 1 ? '' : 's')
                : mostrando + ' de ' + total;
        }

        if (!veiculos.length) {
            lista.innerHTML = '<div class="cad-lista-empty">Nenhum veículo encontrado com os filtros atuais.</div>';
            return;
        }

        lista.innerHTML = veiculos.map(function (v) {
            const isActive = STATE.selecionado && STATE.selecionado.codveiculo === v.codveiculo;
            const corAvatar = H.corDoHash(v.placa || String(v.codveiculo));
            const badges = [];
            if (!v.ativo) badges.push('<span class="cad-badge cad-badge--inativo">INATIVO</span>');
            if (v.proprio === 'N') badges.push('<span class="cad-badge cad-badge--warning">TERCEIRO</span>');
            if (v.combustivel) badges.push('<span class="cad-badge cad-badge--info">' + v.combustivel + '</span>');

            return '<div class="cad-item ' + (isActive ? 'is-active' : '') + '" data-codveiculo="' + v.codveiculo + '">'
                 + '<div class="cad-item-avatar" style="background:' + corAvatar + ';">'
                 +   '<i class="ph ph-truck" style="font-size:14px;"></i>'
                 + '</div>'
                 + '<div class="cad-item-info">'
                 +   '<div class="cad-item-nome">' + H.escapeHtml(v.placa || '—') + ' · ' + H.escapeHtml(v.marcamodelo || '—') + '</div>'
                 +   '<div class="cad-item-meta">#' + v.codveiculo + ' · ' + H.escapeHtml(v.especietipo || '—') + ' · ' + H.escapeHtml(v.nomeparc || '—') + '</div>'
                 + '</div>'
                 + '<div class="cad-item-badges">' + badges.join('') + '</div>'
                 + '</div>';
        }).join('');

        lista.querySelectorAll('.cad-item').forEach(function (el) {
            el.addEventListener('click', function () {
                const cod = parseInt(el.dataset.codveiculo, 10);
                selecionar(cod);
            });
        });
    }

    async function selecionar(codveiculo) {
        try {
            const resp = await fetch('/sankhya/cadastros/api/veiculos/' + codveiculo + '/');
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                H.showToast(data.error || 'Falha ao carregar veículo.', 'error');
                return;
            }
            STATE.selecionado = data.veiculo;
            renderDetalhe(data.veiculo);
            const lista = $('veiLista');
            if (lista) {
                lista.querySelectorAll('.cad-item').forEach(function (el) {
                    el.classList.toggle('is-active', parseInt(el.dataset.codveiculo, 10) === codveiculo);
                });
            }
        } catch (e) {
            console.error(e);
            H.showToast('Erro de comunicação ao carregar veículo.', 'error');
        }
    }

    function renderDetalhe(v) {
        $('veiDetalheVazio').hidden = true;
        $('veiDetalheCard').hidden = false;

        const cor = H.corDoHash(v.placa || String(v.codveiculo));
        const avatar = $('veiDetalheAvatar');
        if (avatar) {
            avatar.innerHTML = '<i class="ph ph-truck" style="font-size:22px;"></i>';
            avatar.style.background = cor;
        }

        $('veiDetalheNome').textContent   = (v.placa || '—') + ' · ' + (v.marcamodelo || '—');
        $('veiDetalheCodigo').textContent = v.codveiculo;

        const badgesEl = $('veiDetalheBadges');
        const badges = [];
        badges.push(v.ativo
            ? '<span class="cad-badge cad-badge--ativo">ATIVO</span>'
            : '<span class="cad-badge cad-badge--inativo">INATIVO</span>');
        badges.push(v.proprio === 'S'
            ? '<span class="cad-badge cad-badge--primary">PRÓPRIO</span>'
            : '<span class="cad-badge cad-badge--warning">TERCEIRO</span>');
        if (v.combustivel) badges.push('<span class="cad-badge cad-badge--info">' + v.combustivel + '</span>');
        badgesEl.innerHTML = badges.join('');

        $('veiFldPlaca').textContent  = v.placa || '—';
        $('veiFldModelo').textContent = v.marcamodelo || '—';
        $('veiFldTipo').textContent   = v.especietipo || '—';
        $('veiFldCor').textContent    = v.cor || '—';

        const anoFab = v.anofab || v.ano || '';
        const anoMod = v.anomod || '';
        $('veiFldAno').textContent =
            (anoFab || anoMod) ? ((anoFab || '?') + ' / ' + (anoMod || '?')) : '—';

        $('veiFldChassi').textContent  = v.chassi || '—';
        $('veiFldRenavam').textContent = v.renavam || '—';

        $('veiFldProprio').textContent = descProprio(v.proprio);
        $('veiFldParc').textContent = (v.codparc !== null && v.codparc !== undefined)
            ? ('#' + v.codparc + ' · ' + (v.nomeparc || '—'))
            : '—';
        $('veiFldComb').textContent = descComb(v.combustivel);
        $('veiFldCap').textContent  = (v.capacidade !== null && v.capacidade !== undefined)
            ? H.fmtNumeroBR(v.capacidade, 2) + ' LT'
            : '—';

        $('veiFldCencus').textContent = (v.codcencus !== null && v.codcencus !== undefined)
            ? ('#' + v.codcencus + (v.descrcencus ? ' · ' + v.descrcencus : ''))
            : '—';

        $('veiFldObs').textContent = v.obs || v.observacao || '—';
    }

    function bind() {
        $('veiBusca').addEventListener('input', H.debounce(function () {
            STATE.filtros.busca = $('veiBusca').value.trim();
            carregar();
        }, 400));
        $('veiFiltroProprio').addEventListener('change', function () {
            STATE.filtros.proprio = $('veiFiltroProprio').value;
            carregar();
        });
        $('veiMostrarInativos').addEventListener('change', function () {
            STATE.filtros.mostrar_inativos = $('veiMostrarInativos').checked;
            carregar();
        });
    }

    document.addEventListener('DOMContentLoaded', async function () {
        bind();
        // Swipe-to-back: configurado automaticamente pelo base.html via
        // IAgro.setupSwipeBackAuto() + MAPA_VOLTA_PADRAO.
        await carregar();
    });
})();
