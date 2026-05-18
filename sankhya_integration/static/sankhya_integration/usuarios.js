/* ============================================================
   MÓDULO USUÁRIOS (Mai/2026) — frontend
   Cat A: listagem + detalhe + dropdowns de grupos
   Cat B (pendente): cadastro/editar/inativar/grupos -> stubs 501
   ============================================================ */
(function () {
    'use strict';

    const STATE = {
        usuarios: [],
        usuarioSelecionado: null,
        grupos: [],
        filtros: {
            busca: '',
            codgrupo: '',
            // Default: só ativos. Toggle "Mostrar inativos" → inclui ambos.
            mostrarInativos: false,
        },
        carregando: false,
    };

    const $ = (id) => document.getElementById(id);

    // ===== Helpers =====
    function escapeHtml(s) {
        if (s === null || s === undefined) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function iniciais(nome) {
        if (!nome) return '?';
        const partes = String(nome).trim().split(/\s+/).filter(Boolean);
        if (!partes.length) return '?';
        if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
        return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
    }

    function corDoHash(str) {
        // hash simples pra avatar — mesmo nome sempre mesma cor
        let h = 0;
        for (let i = 0; i < str.length; i++) h = ((h << 5) - h) + str.charCodeAt(i);
        const cores = [
            '#5e7e4a', '#825e38', '#3b6ea5', '#a05a8a',
            '#7a6b48', '#5a807a', '#a05a3b', '#4a6b8a',
        ];
        return cores[Math.abs(h) % cores.length];
    }

    function showToast(msg, tipo) {
        if (window.IAgro && IAgro.showToast) {
            IAgro.showToast(msg, tipo || 'info');
        } else {
            console.log(`[${(tipo || 'info').toUpperCase()}] ${msg}`);
        }
    }

    // ===== Fetch de grupos (uma vez no boot) =====
    async function carregarGrupos() {
        try {
            const resp = await fetch('/sankhya/usuarios/api/grupos/');
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                console.warn('Falha ao carregar grupos', data);
                return;
            }
            STATE.grupos = data.grupos || [];
            // Popula select de filtro
            const selFiltro = $('usuFiltroGrupo');
            if (selFiltro) {
                const atual = selFiltro.value;
                selFiltro.innerHTML = '<option value="">Todos os grupos</option>'
                    + STATE.grupos.map(g =>
                        `<option value="${g.codgrupo}">${escapeHtml(g.codgrupo + ' — ' + g.nomegrupo)}</option>`
                    ).join('');
                selFiltro.value = atual;
            }
            // Popula select do formulário de cadastro
            const selCad = $('usuFormCodgrupo');
            if (selCad) {
                selCad.innerHTML = '<option value="">Selecione…</option>'
                    + STATE.grupos.map(g =>
                        `<option value="${g.codgrupo}">${escapeHtml(g.codgrupo + ' — ' + g.nomegrupo)}</option>`
                    ).join('');
            }
        } catch (e) {
            console.error('Erro ao carregar grupos', e);
        }
    }

    // ===== Fetch da lista =====
    async function carregarUsuarios() {
        if (STATE.carregando) return;
        STATE.carregando = true;

        const lista = $('usuLista');
        if (lista && !STATE.usuarios.length) {
            lista.innerHTML = '<div class="usu-lista-empty">Carregando…</div>';
        }

        const params = new URLSearchParams();
        if (STATE.filtros.busca) params.set('busca', STATE.filtros.busca);
        if (STATE.filtros.codgrupo) params.set('codgrupo', STATE.filtros.codgrupo);

        if (STATE.filtros.mostrarInativos) {
            // Inclui ativos + inativos na mesma lista
            params.set('apenas_ativos', 'false');
            params.set('apenas_inativos', 'false');
        } else {
            // Padrão: só ativos
            params.set('apenas_ativos', 'true');
        }

        params.set('limite', '200');

        try {
            const resp = await fetch('/sankhya/usuarios/api/listar/?' + params.toString());
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                showToast(data.error || 'Falha ao listar usuários.', 'error');
                renderLista([], 0);
                return;
            }
            STATE.usuarios = data.usuarios || [];
            renderLista(STATE.usuarios, data.total || 0);
        } catch (e) {
            console.error(e);
            showToast('Erro de comunicação ao listar usuários.', 'error');
            renderLista([], 0);
        } finally {
            STATE.carregando = false;
        }
    }

    function renderLista(usuarios, total) {
        const lista = $('usuLista');
        const contador = $('usuContador');
        if (!lista) return;

        if (contador) {
            const mostrando = usuarios.length;
            contador.textContent = mostrando === total
                ? `${total} usuário${total === 1 ? '' : 's'}`
                : `${mostrando} de ${total}`;
        }

        if (!usuarios.length) {
            lista.innerHTML = `
                <div class="usu-lista-empty">
                    Nenhum usuário encontrado com os filtros atuais.
                </div>
            `;
            return;
        }

        lista.innerHTML = usuarios.map(u => {
            const isActive = STATE.usuarioSelecionado && STATE.usuarioSelecionado.codusu === u.codusu;
            const corAvatar = corDoHash(u.nomeusu || '?');
            const badges = [];
            if (!u.ativo) badges.push('<span class="usu-badge usu-badge--inativo">INATIVO</span>');
            if (u.grupos_extras > 0) badges.push(`<span class="usu-badge usu-badge--grupos">+${u.grupos_extras} grupo${u.grupos_extras > 1 ? 's' : ''}</span>`);

            return `
                <div class="usu-item ${isActive ? 'is-active' : ''}" data-codusu="${u.codusu}">
                    <div class="usu-item-avatar" style="background:${corAvatar};">
                        ${escapeHtml(iniciais(u.nomeusu))}
                    </div>
                    <div class="usu-item-info">
                        <div class="usu-item-nome">${escapeHtml(u.nomeusu)}</div>
                        <div class="usu-item-meta">
                            ${escapeHtml(u.nomeusucplt || '—')} · ${escapeHtml(u.nomegrupo)}
                        </div>
                    </div>
                    <div class="usu-item-badges">
                        ${badges.join('')}
                    </div>
                </div>
            `;
        }).join('');

        // Bind clicks
        lista.querySelectorAll('.usu-item').forEach(el => {
            el.addEventListener('click', () => {
                const codusu = parseInt(el.dataset.codusu, 10);
                selecionarUsuario(codusu);
            });
        });
    }

    // ===== Detalhe =====
    async function selecionarUsuario(codusu) {
        try {
            const resp = await fetch(`/sankhya/usuarios/api/${codusu}/`);
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                showToast(data.error || 'Falha ao carregar usuário.', 'error');
                return;
            }
            STATE.usuarioSelecionado = data.usuario;
            renderDetalhe(data.usuario);
            // Marca item ativo na lista
            const lista = $('usuLista');
            if (lista) {
                lista.querySelectorAll('.usu-item').forEach(el => {
                    el.classList.toggle('is-active', parseInt(el.dataset.codusu, 10) === codusu);
                });
            }
        } catch (e) {
            console.error(e);
            showToast('Erro de comunicação ao carregar usuário.', 'error');
        }
    }

    function renderDetalhe(u) {
        $('usuDetalheVazio').hidden = true;
        $('usuDetalheCard').hidden = false;

        const corAvatar = corDoHash(u.nomeusu || '?');
        const avatar = $('usuDetalheAvatar');
        if (avatar) {
            avatar.textContent = iniciais(u.nomeusu);
            avatar.style.background = corAvatar;
        }

        $('usuDetalheNome').textContent  = u.nomeusucplt || u.nomeusu;
        $('usuDetalheLogin').textContent = u.nomeusu;

        // Badges
        const badgesEl = $('usuDetalheBadges');
        const badges = [];
        if (u.ativo) {
            badges.push('<span class="usu-badge usu-badge--ativo">ATIVO</span>');
        } else {
            badges.push('<span class="usu-badge usu-badge--inativo">INATIVO</span>');
        }
        if (!u.tem_senha) {
            badges.push('<span class="usu-badge usu-badge--sem-senha" title="Senha não definida no Sankhya — usuário não consegue logar até a TI definir">SEM SENHA</span>');
        }
        badgesEl.innerHTML = badges.join('');

        // Cards
        $('usuFldNome').textContent    = u.nomeusucplt || '—';
        $('usuFldEmail').textContent   = u.email || '—';
        $('usuFldCpf').textContent     = u.cpf || '—';
        $('usuFldLogin').textContent   = u.nomeusu;
        $('usuFldCodusu').textContent  = u.codusu;

        $('usuFldSituacao').innerHTML = u.ativo
            ? '<span style="color:#065f46;font-weight:600;">Ativo</span>'
            : '<span style="color:#991b1b;font-weight:600;">Inativo desde ' + escapeHtml(u.dtlimacesso || '—') + '</span>';
        $('usuFldSenha').innerHTML = u.tem_senha
            ? '<span style="color:#065f46;">Sim</span>'
            : '<span style="color:#92400e;font-weight:600;">⚠ Não — peça à TI</span>';
        $('usuFldUltimaSenha').textContent = u.dtultimasenha || '—';
        $('usuFldUltAcesso').textContent   = u.dtultacesso || 'Nunca';
        $('usuFldDtLimite').textContent    = u.dtlimacesso || 'Sem limite';

        $('usuGrupoPrincipal').textContent = `${u.codgrupo_principal} — ${u.nomegrupo_principal}`;

        // Grupos extras
        const extrasEl = $('usuGruposExtras');
        if (!u.grupos_extras || !u.grupos_extras.length) {
            extrasEl.innerHTML = '<li class="usu-grupos-empty">Sem grupos extras.</li>';
        } else {
            extrasEl.innerHTML = u.grupos_extras.map(g => `
                <li class="usu-grupos-extra-pill" data-codgrupo="${g.codgrupo}">
                    <span>${escapeHtml(g.codgrupo + ' — ' + g.nomegrupo)}</span>
                    <button type="button" class="btn-remover-grupo"
                            title="Remover grupo (encerra associação em ${escapeHtml(g.datainicio)})">
                        <i class="ph ph-x"></i>
                    </button>
                </li>
            `).join('');
            extrasEl.querySelectorAll('.btn-remover-grupo').forEach(btn => {
                btn.addEventListener('click', (ev) => {
                    const li = ev.currentTarget.closest('.usu-grupos-extra-pill');
                    const codgrupo = parseInt(li.dataset.codgrupo, 10);
                    confirmarRemoverGrupo(u.codusu, codgrupo);
                });
            });
        }

        // Ações (Reativar mostra só se inativo)
        $('usuBtnInativar').hidden = !u.ativo;
        $('usuBtnReativar').hidden = u.ativo;
    }

    // ===== Modais Cat B (stubs por enquanto) =====
    function abrirModal(id) {
        const m = $(id);
        if (m) m.classList.remove('hidden');
    }
    function fecharModal(id) {
        const m = $(id);
        if (m) m.classList.add('hidden');
    }

    function abrirModalCadastro(edicao) {
        const titulo = $('usuModalCadastroTitulo');
        const aviso = $('usuAvisoSenha');
        if (edicao && STATE.usuarioSelecionado) {
            const u = STATE.usuarioSelecionado;
            titulo.textContent = `Editar usuário — ${u.nomeusu}`;
            $('usuFormCodusu').value   = u.codusu;
            $('usuFormNomeusu').value  = u.nomeusu;
            $('usuFormNomeusu').disabled = true; // login não muda
            $('usuFormNomecplt').value = u.nomeusucplt || '';
            $('usuFormEmail').value    = u.email || '';
            $('usuFormCpf').value      = u.cpf || '';
            $('usuFormCodgrupo').value = u.codgrupo_principal;
            if (aviso) aviso.hidden = true;
        } else {
            titulo.textContent = 'Novo usuário';
            $('usuFormCodusu').value = '';
            $('usuFormNomeusu').value = '';
            $('usuFormNomeusu').disabled = false;
            $('usuFormNomecplt').value = '';
            $('usuFormEmail').value = '';
            $('usuFormCpf').value = '';
            $('usuFormCodgrupo').value = '';
            if (aviso) aviso.hidden = false;
        }
        $('usuMsgErroCadastro').hidden = true;
        $('usuMsgErroCadastro').textContent = '';
        abrirModal('usuModalCadastro');
        // Foca no primeiro campo editável
        setTimeout(() => {
            if (edicao) {
                $('usuFormNomecplt').focus();
            } else {
                $('usuFormNomeusu').focus();
            }
        }, 50);
    }

    async function salvarCadastro() {
        const codusu = $('usuFormCodusu').value;
        const nomeusu = $('usuFormNomeusu').value.trim();
        const nomeusucplt = $('usuFormNomecplt').value.trim();
        const email = $('usuFormEmail').value.trim();
        const cpf = $('usuFormCpf').value.trim();
        const codgrupo = $('usuFormCodgrupo').value;

        // Validação cliente
        if (!codusu && !nomeusu) {
            mostrarErroCadastro('Login obrigatório.');
            return;
        }
        if (!codgrupo) {
            mostrarErroCadastro('Selecione um grupo principal.');
            return;
        }
        if (cpf && !/^\d{11}$/.test(cpf)) {
            mostrarErroCadastro('CPF deve ter 11 dígitos numéricos (ou ficar em branco).');
            return;
        }

        const payload = { nomeusu, nomeusucplt, email, cpf, codgrupo: parseInt(codgrupo, 10) };
        const url = codusu
            ? `/sankhya/usuarios/api/${codusu}/editar/`
            : '/sankhya/usuarios/api/criar/';

        try {
            const resp = await IAgro.postJSON(url, payload);
            const data = resp.body || {};
            if (!resp.ok || !data.ok) {
                if (data.pendente_cat_b) {
                    showToast('Backend Cat B ainda não aprovado — operação simulada apenas.', 'warning');
                    mostrarErroCadastro('🚧 ' + (data.error || 'Aguardando aprovação do bloco Cat B.'));
                    return;
                }
                mostrarErroCadastro(data.error || 'Erro ao salvar.');
                return;
            }
            fecharModal('usuModalCadastro');
            showToast(codusu ? 'Usuário atualizado.' : 'Usuário criado.', 'success');
            await carregarUsuarios();
        } catch (e) {
            console.error(e);
            mostrarErroCadastro('Erro de comunicação.');
        }
    }

    function mostrarErroCadastro(msg) {
        const el = $('usuMsgErroCadastro');
        el.textContent = msg;
        el.hidden = false;
    }

    async function inativarUsuario() {
        if (!STATE.usuarioSelecionado) return;
        const u = STATE.usuarioSelecionado;
        const ok = await IAgro.confirmarAcao({
            titulo: 'Inativar usuário?',
            mensagem: `O acesso do usuário <strong>${escapeHtml(u.nomeusu)}</strong> será bloqueado a partir de hoje. A conta NÃO é deletada — pode ser reativada depois.`,
            tipo: 'aviso',
        });
        if (!ok) return;
        try {
            const resp = await IAgro.postJSON(`/sankhya/usuarios/api/${u.codusu}/inativar/`, {});
            const data = resp.body || {};
            if (!resp.ok || !data.ok) {
                if (data.pendente_cat_b) {
                    showToast('Inativar usuário (B3) aguardando aprovação Cat B.', 'warning');
                    return;
                }
                showToast(data.error || 'Falha ao inativar.', 'error');
                return;
            }
            showToast('Usuário inativado.', 'success');
            await carregarUsuarios();
            selecionarUsuario(u.codusu);
        } catch (e) {
            console.error(e);
            showToast('Erro de comunicação.', 'error');
        }
    }

    async function reativarUsuario() {
        if (!STATE.usuarioSelecionado) return;
        const u = STATE.usuarioSelecionado;
        const ok = await IAgro.confirmarAcao({
            titulo: 'Reativar usuário?',
            mensagem: `O usuário <strong>${escapeHtml(u.nomeusu)}</strong> volta a ter acesso ao sistema imediatamente.`,
            tipo: 'info',
        });
        if (!ok) return;
        try {
            const resp = await IAgro.postJSON(`/sankhya/usuarios/api/${u.codusu}/reativar/`, {});
            const data = resp.body || {};
            if (!resp.ok || !data.ok) {
                if (data.pendente_cat_b) {
                    showToast('Reativar usuário (B4) aguardando aprovação Cat B.', 'warning');
                    return;
                }
                showToast(data.error || 'Falha ao reativar.', 'error');
                return;
            }
            showToast('Usuário reativado.', 'success');
            await carregarUsuarios();
            selecionarUsuario(u.codusu);
        } catch (e) {
            console.error(e);
            showToast('Erro de comunicação.', 'error');
        }
    }

    function abrirModalAddGrupo() {
        if (!STATE.usuarioSelecionado) return;
        const u = STATE.usuarioSelecionado;
        $('usuAddGrupoUsuario').innerHTML = `Adicionar grupo extra ao usuário <strong>${escapeHtml(u.nomeusu)}</strong>:`;

        // Exclui grupos que o usuário já tem (principal + extras ativos)
        const jaTem = new Set([u.codgrupo_principal, ...u.grupos_extras.map(g => g.codgrupo)]);
        const disponiveis = STATE.grupos.filter(g => !jaTem.has(g.codgrupo));

        const sel = $('usuAddGrupoSelect');
        if (!disponiveis.length) {
            sel.innerHTML = '<option value="">— Usuário já está em todos os grupos —</option>';
        } else {
            sel.innerHTML = '<option value="">Selecione…</option>'
                + disponiveis.map(g =>
                    `<option value="${g.codgrupo}">${escapeHtml(g.codgrupo + ' — ' + g.nomegrupo)}</option>`
                ).join('');
        }

        $('usuMsgErroAddGrupo').hidden = true;
        abrirModal('usuModalAddGrupo');
    }

    async function confirmarAddGrupo() {
        if (!STATE.usuarioSelecionado) return;
        const u = STATE.usuarioSelecionado;
        const codgrupo = $('usuAddGrupoSelect').value;
        if (!codgrupo) {
            const el = $('usuMsgErroAddGrupo');
            el.textContent = 'Selecione um grupo.';
            el.hidden = false;
            return;
        }
        try {
            const resp = await IAgro.postJSON(
                `/sankhya/usuarios/api/${u.codusu}/grupo/adicionar/`,
                { codgrupo: parseInt(codgrupo, 10) }
            );
            const data = resp.body || {};
            if (!resp.ok || !data.ok) {
                const el = $('usuMsgErroAddGrupo');
                if (data.pendente_cat_b) {
                    el.textContent = '🚧 ' + data.error;
                } else {
                    el.textContent = data.error || 'Erro ao adicionar grupo.';
                }
                el.hidden = false;
                return;
            }
            fecharModal('usuModalAddGrupo');
            showToast('Grupo adicionado.', 'success');
            selecionarUsuario(u.codusu);
        } catch (e) {
            console.error(e);
            const el = $('usuMsgErroAddGrupo');
            el.textContent = 'Erro de comunicação.';
            el.hidden = false;
        }
    }

    async function confirmarRemoverGrupo(codusu, codgrupo) {
        const grupoNome = STATE.usuarioSelecionado.grupos_extras
            .find(g => g.codgrupo === codgrupo);
        const ok = await IAgro.confirmarAcao({
            titulo: 'Remover grupo?',
            mensagem: `Encerrar associação do grupo <strong>${escapeHtml(grupoNome ? grupoNome.nomegrupo : codgrupo)}</strong>? A entrada fica preservada em TSIGPU com DATAFIM=hoje (histórico).`,
            tipo: 'aviso',
        });
        if (!ok) return;
        try {
            const resp = await IAgro.postJSON(
                `/sankhya/usuarios/api/${codusu}/grupo/remover/`,
                { codgrupo }
            );
            const data = resp.body || {};
            if (!resp.ok || !data.ok) {
                if (data.pendente_cat_b) {
                    showToast('Remover grupo (B6) aguardando aprovação Cat B.', 'warning');
                    return;
                }
                showToast(data.error || 'Falha ao remover grupo.', 'error');
                return;
            }
            showToast('Grupo removido.', 'success');
            selecionarUsuario(codusu);
        } catch (e) {
            console.error(e);
            showToast('Erro de comunicação.', 'error');
        }
    }

    // ===== Bind de eventos =====
    function bind() {
        // Filtros
        const debounce = (window.IAgro && IAgro.debounce) || ((fn, ms) => {
            let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
        });
        $('usuBusca').addEventListener('input', debounce(() => {
            STATE.filtros.busca = $('usuBusca').value.trim();
            carregarUsuarios();
        }, 400));
        $('usuFiltroGrupo').addEventListener('change', () => {
            STATE.filtros.codgrupo = $('usuFiltroGrupo').value;
            carregarUsuarios();
        });
        $('usuMostrarInativos').addEventListener('change', () => {
            STATE.filtros.mostrarInativos = $('usuMostrarInativos').checked;
            carregarUsuarios();
        });

        // Botões do header e detalhe
        $('btnNovoUsuario').addEventListener('click', () => abrirModalCadastro(false));
        $('usuBtnEditar').addEventListener('click',   () => abrirModalCadastro(true));
        $('usuBtnInativar').addEventListener('click', inativarUsuario);
        $('usuBtnReativar').addEventListener('click', reativarUsuario);
        $('usuBtnAddGrupo').addEventListener('click', abrirModalAddGrupo);

        // Modais
        document.querySelectorAll('[data-fechar]').forEach(b => {
            b.addEventListener('click', () => {
                const tipo = b.dataset.fechar;
                if (tipo === 'cadastro') fecharModal('usuModalCadastro');
                if (tipo === 'addgrupo') fecharModal('usuModalAddGrupo');
            });
        });
        $('usuBtnSalvarCadastro').addEventListener('click', salvarCadastro);
        $('usuBtnConfirmarAddGrupo').addEventListener('click', confirmarAddGrupo);

        // Esc fecha modais
        document.addEventListener('keydown', (ev) => {
            if (ev.key === 'Escape') {
                fecharModal('usuModalCadastro');
                fecharModal('usuModalAddGrupo');
            }
        });
    }

    // ===== Boot =====
    document.addEventListener('DOMContentLoaded', async () => {
        bind();
        await carregarGrupos();
        await carregarUsuarios();
    });
})();
