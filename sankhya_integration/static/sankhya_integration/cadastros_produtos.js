/* ============================================================
   CADASTROS → PRODUTOS (Mai/2026) — view-only
   ============================================================ */
(function () {
    'use strict';

    const H = window.CadHelpers || {};

    const STATE = {
        produtos: [],
        selecionado: null,
        filtros: { busca: '', usoprod: '', mostrar_inativos: false },
        carregando: false,
    };

    const $ = function (id) { return document.getElementById(id); };

    const USO_LABEL = { V: 'V — Venda', R: 'R — Revenda', C: 'C — Consumo' };

    function descUso(u) {
        if (!u) return '—';
        return USO_LABEL[u] || u;
    }

    async function carregar() {
        if (STATE.carregando) return;
        STATE.carregando = true;
        const lista = $('prodLista');
        if (lista && !STATE.produtos.length) {
            lista.innerHTML = '<div class="cad-lista-empty">Carregando…</div>';
        }

        const params = new URLSearchParams();
        if (STATE.filtros.busca) params.set('busca', STATE.filtros.busca);
        if (STATE.filtros.usoprod) params.set('usoprod', STATE.filtros.usoprod);
        if (STATE.filtros.mostrar_inativos) params.set('mostrar_inativos', 'true');
        params.set('limite', '200');

        try {
            const resp = await fetch('/sankhya/cadastros/api/produtos/listar/?' + params.toString());
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                H.showToast(data.error || 'Falha ao listar produtos.', 'error');
                renderLista([], 0);
                return;
            }
            STATE.produtos = data.produtos || [];
            renderLista(STATE.produtos, data.total || 0);
        } catch (e) {
            console.error(e);
            H.showToast('Erro de comunicação ao listar produtos.', 'error');
            renderLista([], 0);
        } finally {
            STATE.carregando = false;
        }
    }

    function renderLista(produtos, total) {
        const lista = $('prodLista');
        const contador = $('prodContador');
        if (!lista) return;

        if (contador) {
            const mostrando = produtos.length;
            contador.textContent = mostrando === total
                ? total + ' produto' + (total === 1 ? '' : 's')
                : mostrando + ' de ' + total;
        }

        if (!produtos.length) {
            lista.innerHTML = '<div class="cad-lista-empty">Nenhum produto encontrado com os filtros atuais.</div>';
            return;
        }

        lista.innerHTML = produtos.map(function (p) {
            const isActive = STATE.selecionado && STATE.selecionado.codprod === p.codprod;
            const corAvatar = H.corDoHash(p.descrprod || String(p.codprod));
            const badges = [];
            if (!p.ativo) badges.push('<span class="cad-badge cad-badge--inativo">INATIVO</span>');
            if (p.usoprod) badges.push('<span class="cad-badge cad-badge--info">' + p.usoprod + '</span>');

            return '<div class="cad-item ' + (isActive ? 'is-active' : '') + '" data-codprod="' + p.codprod + '">'
                 + '<div class="cad-item-avatar" style="background:' + corAvatar + ';">'
                 +   H.escapeHtml(H.iniciais(p.descrprod))
                 + '</div>'
                 + '<div class="cad-item-info">'
                 +   '<div class="cad-item-nome">' + H.escapeHtml(p.descrprod) + '</div>'
                 +   '<div class="cad-item-meta">#' + p.codprod + ' · ' + H.escapeHtml(p.codvol || '—') + ' · ' + H.escapeHtml(p.descrgrupoprod || ('Grupo ' + (p.codgrupoprod || '?'))) + '</div>'
                 + '</div>'
                 + '<div class="cad-item-badges">' + badges.join('') + '</div>'
                 + '</div>';
        }).join('');

        lista.querySelectorAll('.cad-item').forEach(function (el) {
            el.addEventListener('click', function () {
                const cod = parseInt(el.dataset.codprod, 10);
                selecionar(cod);
            });
        });
    }

    async function selecionar(codprod) {
        try {
            const resp = await fetch('/sankhya/cadastros/api/produtos/' + codprod + '/');
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                H.showToast(data.error || 'Falha ao carregar produto.', 'error');
                return;
            }
            STATE.selecionado = data.produto;
            renderDetalhe(data.produto);
            const lista = $('prodLista');
            if (lista) {
                lista.querySelectorAll('.cad-item').forEach(function (el) {
                    el.classList.toggle('is-active', parseInt(el.dataset.codprod, 10) === codprod);
                });
            }
        } catch (e) {
            console.error(e);
            H.showToast('Erro de comunicação ao carregar produto.', 'error');
        }
    }

    function renderDetalhe(p) {
        $('prodDetalheVazio').hidden = true;
        $('prodDetalheCard').hidden = false;

        const cor = H.corDoHash(p.descrprod || String(p.codprod));
        const avatar = $('prodDetalheAvatar');
        if (avatar) {
            avatar.textContent = H.iniciais(p.descrprod);
            avatar.style.background = cor;
        }

        $('prodDetalheNome').textContent   = p.descrprod || '—';
        $('prodDetalheCodigo').textContent = p.codprod;

        const badgesEl = $('prodDetalheBadges');
        const badges = [];
        badges.push(p.ativo
            ? '<span class="cad-badge cad-badge--ativo">ATIVO</span>'
            : '<span class="cad-badge cad-badge--inativo">INATIVO</span>');
        if (p.codvol) badges.push('<span class="cad-badge cad-badge--info">' + H.escapeHtml(p.codvol) + '</span>');
        badgesEl.innerHTML = badges.join('');

        $('prodFldDesc').textContent = p.descrprod || '—';
        $('prodFldFab').textContent  = p.fabricante || '—';
        $('prodFldVol').textContent  = p.codvol || '—';
        $('prodFldUso').textContent  = descUso(p.usoprod);

        const grupo = (p.codgrupoprod !== null && p.codgrupoprod !== undefined)
            ? (p.codgrupoprod + (p.descrgrupoprod ? ' — ' + p.descrgrupoprod : ''))
            : '—';
        $('prodFldGrupo').textContent = grupo;
        $('prodFldRef').textContent   = p.referencia || '—';
        $('prodFldSel').textContent   = p.selecionado || '—';

        // Volumes alternativos
        const volWrap = $('prodFldVolumes');
        if (!p.volumes || !p.volumes.length) {
            volWrap.innerHTML = '<div class="cad-pills-empty">Sem volumes alternativos cadastrados (TGFVOA).</div>';
        } else {
            volWrap.innerHTML =
                '<table class="cad-tabela">'
                + '<thead><tr>'
                +   '<th>CODVOL</th><th>Operação</th><th class="num">Qtd</th>'
                +   '<th>Cód. barras</th><th>Ativo</th>'
                + '</tr></thead><tbody>'
                + p.volumes.map(function (v) {
                    const op = v.divmult === 'D' ? 'Divide' : 'Multiplica';
                    return '<tr>'
                         + '<td>' + H.escapeHtml(v.codvol) + '</td>'
                         + '<td>' + op + '</td>'
                         + '<td class="num">' + H.fmtNumeroBR(v.quantidade, 3) + '</td>'
                         + '<td>' + H.escapeHtml(v.codbarra || '—') + '</td>'
                         + '<td>' + (v.ativo ? 'S' : 'N') + '</td>'
                         + '</tr>';
                }).join('')
                + '</tbody></table>';
        }
    }

    function bind() {
        $('prodBusca').addEventListener('input', H.debounce(function () {
            STATE.filtros.busca = $('prodBusca').value.trim();
            carregar();
        }, 400));
        $('prodFiltroUso').addEventListener('change', function () {
            STATE.filtros.usoprod = $('prodFiltroUso').value;
            carregar();
        });
        $('prodMostrarInativos').addEventListener('change', function () {
            STATE.filtros.mostrar_inativos = $('prodMostrarInativos').checked;
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
