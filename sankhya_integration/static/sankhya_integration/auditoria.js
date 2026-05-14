// auditoria.js — Tela de Auditoria Universal (Mai/2026 — Lote A)
// Carrega eventos paginados de AD_AUDITORIA_GERAL com filtros + modal diff.

(function () {
    'use strict';

    const URL_LISTAR  = '/sankhya/api/auditoria/listar/';
    const URL_FILTROS = '/sankhya/api/auditoria/filtros/';

    const PAGINA_SIZE = 50;

    // Estado
    let offset    = 0;
    let total     = 0;
    let inFlight  = false;
    let filtrosAtivos = {};

    // =========================================================
    // HELPERS
    // =========================================================
    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function formatDt(s) {
        if (!s) return '—';
        const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/);
        if (!m) return s;
        return `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}`;
    }

    function compactarJson(obj) {
        if (obj == null) return '—';
        if (obj && obj._raw) return obj._raw;
        return JSON.stringify(obj, null, 2);
    }

    function diferencaChaves(antes, depois) {
        // Marca em amarelo as chaves cujo valor mudou entre antes/depois
        if (!antes || !depois || typeof antes !== 'object' || typeof depois !== 'object') {
            return new Set();
        }
        const diff = new Set();
        const todas = new Set([...Object.keys(antes), ...Object.keys(depois)]);
        for (const k of todas) {
            const va = JSON.stringify(antes[k]);
            const vd = JSON.stringify(depois[k]);
            if (va !== vd) diff.add(k);
        }
        return diff;
    }

    // =========================================================
    // DIFF INTELIGENTE (Mai/2026 — v2)
    // Achatamento + normalização de chaves pra detectar mudanças
    // mesmo quando antes/depois têm formatos diferentes (snapshot
    // completo do banco vs payload flat do operador).
    // =========================================================

    // Prefixos comuns que podem aparecer nas chaves dos snapshots
    // (estrutura aninhada do banco — ex: requisicao.HODOMETRO_KM).
    // Quando comparando, removemos esses prefixos da chave pra
    // alinhar com os payloads "flat" do payload do operador.
    const PREFIXOS_REMOVIVEIS = ['requisicao.', 'cab.', 'cabecalho.', 'fin.', 'financeiro.'];

    // Aliases pra forma canonical. TUDO que aparecer no `chave: valor`
    // do dicionário vira o `valor` ao normalizar — então `qtdneg`, `qtdvol`
    // e o payload `qtd` ficam todos na mesma chave `qtd` e o diff casa.
    // Adicione novos aliases aqui conforme aparecerem campos com nomes
    // diferentes pro mesmo conceito.
    const ALIASES = {
        // Quantidade — banco usa QTDNEG no item e QTDVOL no cabeçalho;
        // payload do operador usa `qtd`. Tudo vira `qtd`.
        'qtdneg':       'qtd',
        'qtdvol':       'qtd',
        // Valores — banco às vezes usa VLRTOT (total da linha), payload usa vlrunit
        'vlrtot':       'vlrunit',
        // Volume / unidade
        'codvolparc':   'codvol',
        // Audit fields que aparecem em níveis diferentes — mesma semântica
        'qtd_atribuida': 'qtd',
    };

    function _flatten(obj, prefix = '') {
        const out = {};
        if (!obj || typeof obj !== 'object') return out;
        for (const [k, v] of Object.entries(obj)) {
            const key = prefix ? `${prefix}.${k}` : k;
            if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
                Object.assign(out, _flatten(v, key));
            } else if (Array.isArray(v)) {
                // Lista (ex: itens[]) — guarda como string descritiva.
                // Diff de array é complicado e geralmente ruidoso; mostramos
                // apenas a quantidade pra dar contexto.
                out[key] = `(${v.length} item${v.length === 1 ? '' : 'ns'})`;
            } else {
                out[key] = v;
            }
        }
        return out;
    }

    function _normalizarChave(caminho) {
        // Pega só o último segmento (descarta hierarquia tipo
        // `requisicao.HODOMETRO_KM` ou `itens.0.QTDNEG`) — porque o payload
        // do operador é flat e o snapshot do banco é hierárquico, e queremos
        // que ambos batam pela semântica do campo, não pelo caminho.
        const limpo = caminho.toLowerCase().replace(/\.\d+(\.|$)/g, '.');
        const partes = limpo.split('.');
        let ultimo = partes[partes.length - 1] || '';
        // Aplica alias pra forma canonical (qtdneg/qtdvol → qtd, etc)
        if (ALIASES[ultimo]) ultimo = ALIASES[ultimo];
        return ultimo;
    }

    function _equivalentes(a, b) {
        // Compara dois valores ignorando number-vs-string e null-vs-undefined
        if (a === b) return true;
        if (a == null && b == null) return true;
        if (a == null || b == null) return false;
        // Trata números como strings pra comparar 100 vs "100"
        const sa = typeof a === 'object' ? JSON.stringify(a) : String(a).trim();
        const sb = typeof b === 'object' ? JSON.stringify(b) : String(b).trim();
        if (sa === sb) return true;
        // Equivalência numérica
        const na = parseFloat(sa);
        const nb = parseFloat(sb);
        if (!isNaN(na) && !isNaN(nb) && na === nb) return true;
        return false;
    }

    function _formatarValor(v) {
        if (v === null || v === undefined || v === '') return null;
        if (typeof v === 'boolean') return v ? 'sim' : 'não';
        if (typeof v === 'number') {
            // Heurística: se for inteiro, mostra inteiro; senão até 4 casas
            return Number.isInteger(v) ? String(v) : v.toLocaleString('pt-BR', { maximumFractionDigits: 4 });
        }
        if (typeof v === 'object') return JSON.stringify(v);
        return String(v);
    }

    /**
     * Calcula o diff "humano" entre antes e depois.
     * Retorna lista ordenada de {campo, antes, depois, tipo}, onde tipo é
     * 'alterado', 'adicionado' ou 'removido'. Filtra ruído (NUNOTA igual,
     * metadados de audit como NOMEUSU/CRIADO_EM, etc).
     */
    function gerarDiffSimples(antes, depois) {
        const fa = _flatten(antes || {});
        const fd = _flatten(depois || {});

        const antesVazio  = Object.keys(fa).length === 0;
        const depoisVazio = Object.keys(fd).length === 0;
        const ehUpdate    = !antesVazio && !depoisVazio;

        // Indexa por chave normalizada.
        // Estratégia de desempate (várias chaves cruas viram a mesma canonical):
        //   - mantém o último valor não-vazio (null/undefined/'' perdem pra
        //     valor real). Isso resolve casos como `qtdvol: 200` (cab) vs
        //     `itens.0.qtdneg: 200` (item) — ambos viram `qtd`, valor 200.
        function _indexar(flat) {
            const idx = {};
            for (const [caminho, valor] of Object.entries(flat)) {
                const norm = _normalizarChave(caminho);
                if (!norm) continue;
                const ja = idx[norm];
                const valorVazio = valor === null || valor === undefined || valor === '';
                if (!ja) {
                    idx[norm] = { caminho, valor };
                } else {
                    const jaVazio = ja.valor === null || ja.valor === undefined || ja.valor === '';
                    // Substitui se o anterior era vazio e o novo não é (ganha o último não-vazio)
                    if (jaVazio && !valorVazio) idx[norm] = { caminho, valor };
                }
            }
            return idx;
        }

        const idxA = _indexar(fa);
        const idxD = _indexar(fd);

        // Chaves que ignoramos (ruído do audit + metadados Sankhya).
        // Como o IGNORAR é checado APÓS normalização, aqui as chaves
        // estão na forma canonical (ex: qtdvol já foi mapeado pra qtd).
        const IGNORAR = new Set([
            'id', 'criado_em', 'nomeusu', 'codusu', 'dtalter',
            'descrprod', 'nomeparc', 'placa', 'marcamodelo',
            'especietipo', 'proprio', 'combustivel', 'codgrupoprod',
            'vlrnota', 'vlrtot', 'numnota',
            'veiculo_descricao', 'fornecedor_descricao',
            'itens', 'requisicao',  // estruturas-pai (já achatadas)
        ]);

        const diff = [];
        const todas = new Set([...Object.keys(idxA), ...Object.keys(idxD)]);

        for (const k of todas) {
            if (IGNORAR.has(k)) continue;
            const a = idxA[k];
            const d = idxD[k];
            const va = a ? a.valor : undefined;
            const vd = d ? d.valor : undefined;

            // Pula valores equivalentes
            if (_equivalentes(va, vd)) continue;

            const aVazio = va === null || va === undefined || va === '';
            const dVazio = vd === null || vd === undefined || vd === '';
            if (aVazio && dVazio) continue;

            let tipo;
            if (ehUpdate) {
                // Em UPDATE, só mostra campos que existem nos DOIS lados — campos
                // que só aparecem num lado costumam ser ausência do payload
                // (não mudança real). Pra ver isso, abre o JSON técnico embaixo.
                if (!a || !d) continue;
                tipo = 'alterado';
            } else if (antesVazio) {
                tipo = 'adicionado';   // CRIAR
            } else {
                tipo = 'removido';     // EXCLUIR (snapshot_depois vazio)
            }

            diff.push({
                campo:  k.toUpperCase(),
                antes:  va,
                depois: vd,
                tipo,
            });
        }

        // Ordena: alterados primeiro, depois adicionados, depois removidos.
        // Dentro do grupo, alfabético.
        const ordemTipo = { alterado: 0, adicionado: 1, removido: 2 };
        diff.sort((x, y) => {
            const ot = (ordemTipo[x.tipo] || 3) - (ordemTipo[y.tipo] || 3);
            if (ot !== 0) return ot;
            return x.campo.localeCompare(y.campo);
        });

        return diff;
    }

    function renderResumoMudancas(antes, depois) {
        const tbody = document.getElementById('auditResumoBody');
        const vazio = document.getElementById('auditResumoVazio');
        const count = document.getElementById('auditResumoCount');
        if (!tbody) return;

        const diff = gerarDiffSimples(antes, depois);
        tbody.innerHTML = '';

        if (diff.length === 0) {
            count.textContent = '0';
            vazio.hidden = false;
            return;
        }

        vazio.hidden = true;
        count.textContent = `${diff.length} campo${diff.length === 1 ? '' : 's'}`;

        for (const d of diff) {
            const tr = document.createElement('tr');
            const valA = _formatarValor(d.antes);
            const valD = _formatarValor(d.depois);
            const cellA = valA === null
                ? `<span class="val-vazio">vazio</span>`
                : `<span class="val-antes">${escapeHtml(valA)}</span>`;
            const cellD = valD === null
                ? `<span class="val-vazio">vazio</span>`
                : `<span class="val-depois">${escapeHtml(valD)}</span>`;
            tr.innerHTML = `
                <td class="col-campo">${escapeHtml(d.campo)}<span class="badge-tipo" data-tipo="${d.tipo}">${d.tipo}</span></td>
                <td class="col-antes">${cellA}</td>
                <td class="col-arrow">→</td>
                <td class="col-depois">${cellD}</td>
            `;
            tbody.appendChild(tr);
        }
    }

    function renderJsonComDiff(obj, chavesDiferentes, lado) {
        if (obj == null) return '—';
        if (obj._raw) return escapeHtml(obj._raw);
        const linhas = JSON.stringify(obj, null, 2).split('\n');
        return linhas.map(linha => {
            const m = linha.match(/^(\s*)"([^"]+)":\s*(.+?)(,?)$/);
            if (!m) return escapeHtml(linha);
            const [_, indent, chave, valor, virg] = m;
            const ehDif = chavesDiferentes.has(chave);
            const corClasse = ehDif
                ? `diff-key-mudou`
                : '';
            const corValor = ehDif
                ? (lado === 'antes' ? 'diff-val-antes' : 'diff-val-depois')
                : '';
            return `${escapeHtml(indent)}<span class="${corClasse}">"${escapeHtml(chave)}"</span>: <span class="${corValor}">${escapeHtml(valor)}</span>${virg}`;
        }).join('\n');
    }

    function lerFiltrosForm() {
        return {
            busca:       document.getElementById('fltBusca').value.trim(),
            registro_id: document.getElementById('fltRegistroId').value.trim(),
            modulo:      document.getElementById('fltModulo').value,
            operacao:    document.getElementById('fltOperacao').value,
            codusu:      document.getElementById('fltUsuario').value,
            data_ini:    document.getElementById('fltDataIni').value,
            data_fim:    document.getElementById('fltDataFim').value,
        };
    }

    function montarQueryString(filtros, off) {
        const params = new URLSearchParams();
        for (const k of Object.keys(filtros)) {
            if (filtros[k]) params.set(k, filtros[k]);
        }
        params.set('limite', PAGINA_SIZE);
        params.set('offset', off);
        return params.toString();
    }

    // =========================================================
    // RENDER
    // =========================================================
    function renderChips(filtros) {
        const cont = document.getElementById('auditChips');
        cont.innerHTML = '';
        const labelDe = (k) => ({
            busca: 'Busca',
            registro_id: 'Registro',
            modulo: 'Módulo',
            operacao: 'Operação',
            codusu: 'Usuário',
            data_ini: 'De',
            data_fim: 'Até',
        })[k] || k;
        for (const k of Object.keys(filtros)) {
            const v = filtros[k];
            if (!v) continue;
            const chip = document.createElement('span');
            chip.className = 'audit-chip';
            chip.innerHTML = `${labelDe(k)}: <strong>${escapeHtml(v)}</strong>`;
            const x = document.createElement('button');
            x.className = 'audit-chip-remove';
            x.type = 'button';
            x.textContent = '×';
            x.addEventListener('click', () => {
                // Zera o campo correspondente e re-aplica
                const map = {
                    busca: 'fltBusca', registro_id: 'fltRegistroId',
                    modulo: 'fltModulo', operacao: 'fltOperacao',
                    codusu: 'fltUsuario',
                    data_ini: 'fltDataIni', data_fim: 'fltDataFim',
                };
                const el = document.getElementById(map[k]);
                if (el) el.value = '';
                aplicarFiltros();
            });
            chip.appendChild(x);
            cont.appendChild(chip);
        }
    }

    function renderEventos(registros, append) {
        const cont = document.getElementById('auditEvents');
        const vazio = document.getElementById('auditEmpty');

        if (!append) cont.innerHTML = '';

        if (!append && (!registros || registros.length === 0)) {
            vazio.textContent = 'Nenhum evento encontrado para esses filtros.';
            vazio.style.display = '';
            document.getElementById('auditPager').hidden = true;
            return;
        }
        vazio.style.display = 'none';

        registros.forEach(r => {
            const div = document.createElement('div');
            div.className = 'audit-event';
            div.setAttribute('role', 'button');
            div.tabIndex = 0;
            div.dataset.id = r.id;
            div.innerHTML = `
                <span class="audit-event-mod" data-mod="${escapeHtml(r.modulo)}">${escapeHtml(r.modulo)}</span>
                <span class="audit-event-op">${escapeHtml(r.operacao)}</span>
                <span class="audit-event-reg" title="${escapeHtml(r.tabela_alvo || '')}">${escapeHtml(r.registro_id || '—')}</span>
                <span class="audit-event-usr">
                    <span class="nome">${escapeHtml(r.nomeusu || ('Usuário ' + (r.codusu || '?')))}</span>
                    <span class="obs">${escapeHtml(r.observacao || '')}</span>
                </span>
                <span class="audit-event-dt">${escapeHtml(formatDt(r.dt))}</span>
            `;
            // Guarda o evento inteiro pro modal
            div._evento = r;
            div.addEventListener('click', () => abrirModal(r));
            div.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    abrirModal(r);
                }
            });
            cont.appendChild(div);
        });
    }

    function renderContador() {
        const el = document.getElementById('auditCounter');
        if (!el) return;
        if (!total) {
            el.textContent = '—';
        } else {
            const exibidos = Math.min(offset + PAGINA_SIZE, total);
            el.textContent = `${exibidos}/${total.toLocaleString('pt-BR')}`;
        }
    }

    // =========================================================
    // MODAL DETALHE
    // =========================================================
    function abrirModal(r) {
        const modal = document.getElementById('auditModal');
        const meta  = document.getElementById('auditModalMeta');
        const antes = document.getElementById('auditModalAntes');
        const depois = document.getElementById('auditModalDepois');

        document.getElementById('auditModalTitulo').textContent =
            `${r.modulo.toUpperCase()} · ${r.operacao} · ID ${r.id}`;

        meta.innerHTML = `
            <div><dt>Data/Hora</dt><dd>${escapeHtml(formatDt(r.dt))}</dd></div>
            <div><dt>Usuário</dt><dd>${escapeHtml(r.nomeusu || '')} ${r.codusu ? `(${r.codusu})` : ''}</dd></div>
            <div><dt>Tabela</dt><dd>${escapeHtml(r.tabela_alvo || '—')}</dd></div>
            <div><dt>Registro</dt><dd>${escapeHtml(r.registro_id || '—')}</dd></div>
            ${r.observacao ? `<div style="grid-column:1/-1"><dt>Observação</dt><dd>${escapeHtml(r.observacao)}</dd></div>` : ''}
        `;

        // Resumo amigável de mudanças no topo
        renderResumoMudancas(r.snapshot_antes, r.snapshot_depois);

        // JSON técnico completo embaixo (detalhe expansível)
        const diff = diferencaChaves(r.snapshot_antes, r.snapshot_depois);
        antes.innerHTML  = renderJsonComDiff(r.snapshot_antes, diff, 'antes');
        depois.innerHTML = renderJsonComDiff(r.snapshot_depois, diff, 'depois');

        modal.classList.remove('hidden');
    }

    function fecharModal() {
        document.getElementById('auditModal').classList.add('hidden');
    }

    // =========================================================
    // FETCH
    // =========================================================
    async function carregarFiltrosDistintos() {
        try {
            const resp = await fetch(URL_FILTROS, { credentials: 'same-origin' });
            const data = await resp.json();
            if (!data.ok) return;
            const popular = (id, valores) => {
                const sel = document.getElementById(id);
                while (sel.options.length > 1) sel.remove(1);
                valores.forEach(v => {
                    const o = document.createElement('option');
                    if (typeof v === 'object') {
                        o.value = v.codusu;
                        o.textContent = v.nomeusu;
                    } else {
                        o.value = v;
                        o.textContent = v;
                    }
                    sel.appendChild(o);
                });
            };
            popular('fltModulo',   data.modulos || []);
            popular('fltOperacao', data.operacoes || []);
            popular('fltUsuario',  data.usuarios || []);
        } catch (e) {
            console.error('[Auditoria] filtros:', e);
        }
    }

    async function carregar(append = false) {
        if (inFlight) return;
        inFlight = true;
        const btn = document.getElementById('btnAuditRefresh');
        if (btn) btn.classList.add('loading');

        try {
            const url = URL_LISTAR + '?' + montarQueryString(filtrosAtivos, offset);
            const resp = await fetch(url, { credentials: 'same-origin' });
            if (resp.status === 401) { window.location.reload(); return; }
            if (resp.status === 403) {
                document.getElementById('auditEvents').innerHTML = '';
                document.getElementById('auditEmpty').textContent = 'Acesso restrito.';
                document.getElementById('auditEmpty').style.display = '';
                return;
            }
            const data = await resp.json();
            if (!data.ok) {
                document.getElementById('auditEmpty').textContent = data.error || 'Erro ao carregar.';
                document.getElementById('auditEmpty').style.display = '';
                return;
            }
            total = data.total || 0;
            renderEventos(data.registros || [], append);
            renderContador();

            const pager = document.getElementById('auditPager');
            pager.hidden = !data.tem_mais;
        } catch (err) {
            console.error('[Auditoria]', err);
            document.getElementById('auditEmpty').textContent = 'Falha de conexão.';
            document.getElementById('auditEmpty').style.display = '';
        } finally {
            inFlight = false;
            if (btn) btn.classList.remove('loading');
        }
    }

    function aplicarFiltros() {
        filtrosAtivos = lerFiltrosForm();
        offset = 0;
        renderChips(filtrosAtivos);
        carregar(false);
    }

    function carregarMais() {
        offset += PAGINA_SIZE;
        carregar(true);
    }

    function limparFiltros() {
        ['fltBusca','fltRegistroId','fltModulo','fltOperacao','fltUsuario','fltDataIni','fltDataFim']
            .forEach(id => { document.getElementById(id).value = ''; });
        aplicarFiltros();
    }

    // =========================================================
    // BOOT
    // =========================================================
    document.addEventListener('DOMContentLoaded', () => {
        // Carga inicial dos filtros + primeira página
        carregarFiltrosDistintos();
        aplicarFiltros();

        // Botões
        document.getElementById('btnAuditAplicar').addEventListener('click', aplicarFiltros);
        document.getElementById('btnAuditLimpar').addEventListener('click', limparFiltros);
        document.getElementById('btnAuditRefresh').addEventListener('click', aplicarFiltros);
        document.getElementById('btnAuditMais').addEventListener('click', carregarMais);
        document.getElementById('btnAuditModalFechar').addEventListener('click', fecharModal);

        // Esc fecha modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') fecharModal();
        });

        // Click fora fecha modal
        document.getElementById('auditModal').addEventListener('click', (e) => {
            if (e.target.id === 'auditModal') fecharModal();
        });

        // Enter no input de busca também aplica filtros
        ['fltBusca','fltRegistroId'].forEach(id => {
            document.getElementById(id).addEventListener('keydown', (e) => {
                if (e.key === 'Enter') aplicarFiltros();
            });
        });
        // Selects e datas aplicam direto no change
        ['fltModulo','fltOperacao','fltUsuario','fltDataIni','fltDataFim'].forEach(id => {
            document.getElementById(id).addEventListener('change', aplicarFiltros);
        });
    });

})();
