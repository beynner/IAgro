/* ============================================================
   CADASTROS → PARCEIROS (Mai/2026) — view-only
   Pattern idêntico ao módulo Usuários (listar + detalhe).
   ============================================================ */
(function () {
    'use strict';

    const H = window.CadHelpers || {};

    const STATE = {
        parceiros: [],
        selecionado: null,
        tipos: [],
        filtros: { busca: '', tipo_id: '', mostrar_inativos: false },
        carregando: false,
    };

    const $ = function (id) { return document.getElementById(id); };

    // ===== Tipos (1 chamada no boot) =====
    async function carregarTipos() {
        try {
            const resp = await fetch('/sankhya/logistica/api/tipos-parceiro/');
            const data = await resp.json();
            if (!resp.ok || !data.ok) return;
            STATE.tipos = data.tipos || [];
            const sel = $('parFiltroTipo');
            if (sel) {
                const atual = sel.value;
                sel.innerHTML = '<option value="">Todos os tipos</option>'
                    + STATE.tipos.map(function (t) {
                        return '<option value="' + t.id + '">'
                             + H.escapeHtml(t.descricao || t.codigo)
                             + '</option>';
                    }).join('');
                sel.value = atual;
            }
        } catch (e) {
            console.warn('Falha ao carregar tipos de parceiro', e);
        }
    }

    // ===== Listagem =====
    async function carregar() {
        if (STATE.carregando) return;
        STATE.carregando = true;
        const lista = $('parLista');
        if (lista && !STATE.parceiros.length) {
            lista.innerHTML = '<div class="cad-lista-empty">Carregando…</div>';
        }

        const params = new URLSearchParams();
        if (STATE.filtros.busca) params.set('busca', STATE.filtros.busca);
        if (STATE.filtros.tipo_id) params.set('tipo_id', STATE.filtros.tipo_id);
        if (STATE.filtros.mostrar_inativos) params.set('mostrar_inativos', 'true');
        params.set('limite', '200');

        try {
            const resp = await fetch('/sankhya/cadastros/api/parceiros/listar/?' + params.toString());
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                H.showToast(data.error || 'Falha ao listar parceiros.', 'error');
                renderLista([], 0);
                return;
            }
            STATE.parceiros = data.parceiros || [];
            renderLista(STATE.parceiros, data.total || 0);
        } catch (e) {
            console.error(e);
            H.showToast('Erro de comunicação ao listar parceiros.', 'error');
            renderLista([], 0);
        } finally {
            STATE.carregando = false;
        }
    }

    function renderLista(parceiros, total) {
        const lista = $('parLista');
        const contador = $('parContador');
        if (!lista) return;

        if (contador) {
            const mostrando = parceiros.length;
            contador.textContent = mostrando === total
                ? total + ' parceiro' + (total === 1 ? '' : 's')
                : mostrando + ' de ' + total;
        }

        if (!parceiros.length) {
            lista.innerHTML = '<div class="cad-lista-empty">Nenhum parceiro encontrado com os filtros atuais.</div>';
            return;
        }

        lista.innerHTML = parceiros.map(function (p) {
            const isActive = STATE.selecionado && STATE.selecionado.codparc === p.codparc;
            const corAvatar = H.corDoHash(p.nomeparc || String(p.codparc));
            const badges = [];
            if (!p.ativo) badges.push('<span class="cad-badge cad-badge--inativo">INATIVO</span>');
            if (p.qtd_tipos > 0) badges.push('<span class="cad-badge cad-badge--info">' + p.qtd_tipos + ' tipo' + (p.qtd_tipos > 1 ? 's' : '') + '</span>');

            return '<div class="cad-item ' + (isActive ? 'is-active' : '') + '" data-codparc="' + p.codparc + '">'
                 + '<div class="cad-item-avatar" style="background:' + corAvatar + ';">'
                 +   H.escapeHtml(H.iniciais(p.nomeparc))
                 + '</div>'
                 + '<div class="cad-item-info">'
                 +   '<div class="cad-item-nome">' + H.escapeHtml(p.nomeparc) + '</div>'
                 +   '<div class="cad-item-meta">#' + p.codparc + ' · ' + H.escapeHtml(p.razaosocial || '—') + '</div>'
                 + '</div>'
                 + '<div class="cad-item-badges">' + badges.join('') + '</div>'
                 + '</div>';
        }).join('');

        lista.querySelectorAll('.cad-item').forEach(function (el) {
            el.addEventListener('click', function () {
                const cod = parseInt(el.dataset.codparc, 10);
                selecionar(cod);
            });
        });
    }

    // ===== Detalhe =====
    async function selecionar(codparc) {
        try {
            const resp = await fetch('/sankhya/cadastros/api/parceiros/' + codparc + '/');
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                H.showToast(data.error || 'Falha ao carregar parceiro.', 'error');
                return;
            }
            STATE.selecionado = data.parceiro;
            renderDetalhe(data.parceiro);
            const lista = $('parLista');
            if (lista) {
                lista.querySelectorAll('.cad-item').forEach(function (el) {
                    el.classList.toggle('is-active', parseInt(el.dataset.codparc, 10) === codparc);
                });
            }
        } catch (e) {
            console.error(e);
            H.showToast('Erro de comunicação ao carregar parceiro.', 'error');
        }
    }

    function renderDetalhe(p) {
        $('parDetalheVazio').hidden = true;
        $('parDetalheCard').hidden = false;

        const cor = H.corDoHash(p.nomeparc || String(p.codparc));
        const avatar = $('parDetalheAvatar');
        if (avatar) {
            avatar.textContent = H.iniciais(p.nomeparc);
            avatar.style.background = cor;
        }

        $('parDetalheNome').textContent   = p.nomeparc || '—';
        $('parDetalheCodigo').textContent = p.codparc;

        const badgesEl = $('parDetalheBadges');
        const badges = [];
        badges.push(p.ativo
            ? '<span class="cad-badge cad-badge--ativo">ATIVO</span>'
            : '<span class="cad-badge cad-badge--inativo">INATIVO</span>');
        if (p.codtab !== null && p.codtab !== undefined) {
            badges.push('<span class="cad-badge cad-badge--info">Tabela ' + p.codtab + '</span>');
        }
        badgesEl.innerHTML = badges.join('');

        $('parFldNome').textContent  = p.nomeparc || '—';
        $('parFldRazao').textContent = p.razaosocial || '—';
        $('parFldCgc').textContent   = H.fmtCpfCnpj(p.cgc_cpf) || '—';
        $('parFldIE').textContent    = p.identinscestad || '—';
        $('parFldCodtab').textContent = (p.codtab !== null && p.codtab !== undefined) ? p.codtab : '—';

        $('parFldEmail').textContent = p.email || '—';
        $('parFldTel').textContent   = p.telefone || '—';
        $('parFldFax').textContent   = p.fax || '—';

        // Tipos
        const tiposEl = $('parFldTipos');
        if (!p.tipos || !p.tipos.length) {
            tiposEl.innerHTML = '<li class="cad-pills-empty">Sem tipos cadastrados em AD_PARCEIRO_TIPO.</li>';
        } else {
            tiposEl.innerHTML = p.tipos.map(function (t) {
                return '<li class="cad-pill">' + H.escapeHtml(t.descricao || t.codigo) + '</li>';
            }).join('');
        }
    }

    // ===== Bind =====
    function bind() {
        $('parBusca').addEventListener('input', H.debounce(function () {
            STATE.filtros.busca = $('parBusca').value.trim();
            carregar();
        }, 400));
        $('parFiltroTipo').addEventListener('change', function () {
            STATE.filtros.tipo_id = $('parFiltroTipo').value;
            carregar();
        });
        $('parMostrarInativos').addEventListener('change', function () {
            STATE.filtros.mostrar_inativos = $('parMostrarInativos').checked;
            carregar();
        });
    }

    document.addEventListener('DOMContentLoaded', async function () {
        bind();
        // Swipe-to-back: configurado automaticamente pelo base.html via
        // IAgro.setupSwipeBackAuto() + MAPA_VOLTA_PADRAO.
        await carregarTipos();
        await carregar();
    });
})();
