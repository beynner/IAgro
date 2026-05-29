/* =============================================================================
   Logística — Rotas de entrega (Mai/2026 — schema persistente — 2026-05-29)
   ---------------------------------------------------------------------------
   Dados reais via REST:
     GET  /sankhya/logistica/api/viagens/
     GET  /sankhya/logistica/api/parceiros/?tipo=N
     GET  /sankhya/logistica/api/veiculos/
     POST /sankhya/logistica/api/viagem/criar/
     POST /sankhya/logistica/api/viagem/<id>/editar/
     POST /sankhya/logistica/api/viagem/<id>/excluir/
     GET  /sankhya/logistica/api/viagem/<id>/ficha-pdf/  (PDF inline)
   ============================================================================= */

(function () {
    'use strict';

    // IDs dos tipos cadastrados em AD_TIPO_PARCEIRO (seed)
    const TIPO_CLIENTE   = 1;
    const TIPO_MOTORISTA = 4;
    const TIPO_AJUDANTE  = 5;

    // CSRF helper
    function getCsrf() {
        if (window.IAgro && IAgro.getCookie) return IAgro.getCookie('csrftoken');
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    async function apiGet(url) {
        const r = await fetch(url, { credentials: 'same-origin' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    }

    async function apiPost(url, body) {
        const r = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf(),
            },
            body: JSON.stringify(body || {}),
        });
        const data = await r.json().catch(function () { return { ok: false, error: 'HTTP ' + r.status }; });
        if (!r.ok && data && data.ok === undefined) data.ok = false;
        return data;
    }

    // -------------------------------------------------------------------------
    // MOCK DATA
    // -------------------------------------------------------------------------
    const HOJE = new Date().toISOString().slice(0, 10);
    const ONTEM = (function () {
        const d = new Date(); d.setDate(d.getDate() - 1);
        return d.toISOString().slice(0, 10);
    })();
    const AMANHA = (function () {
        const d = new Date(); d.setDate(d.getDate() + 1);
        return d.toISOString().slice(0, 10);
    })();

    // VEICULOS — populados via apiCarregarVeiculos() no boot. Mantém estrutura
    // {codveiculo, placa, modelo} pra compatibilidade com código existente.
    // Mock inicial é fallback se backend falhar.
    let VEICULOS_MOCK = [
        { codveiculo: 1, placa: 'JFO-5H79', modelo: 'MB 2544' },
        { codveiculo: 2, placa: 'OVT-0B50', modelo: 'VW 24.280' },
        { codveiculo: 3, placa: 'OVT-0B51', modelo: 'VW 24.280' },
        { codveiculo: 4, placa: 'PBW-0D02', modelo: 'MB ACCELO 1016' },
        { codveiculo: 5, placa: 'RER-2B08', modelo: 'FORD CARGO 816' },
        { codveiculo: 6, placa: 'NLM-6688', modelo: 'FIAT STRADA' },
        { codveiculo: 7, placa: 'GHF-1234', modelo: 'VW DELIVERY 9.170' },
        { codveiculo: 8, placa: 'XYZ-7890', modelo: 'IVECO TECTOR' },
    ];

    // PARCEIROS — populados via apiCarregarParceiros() no boot.
    // Estrutura: {codparc, nome, razao, tipo} ('CLIENTE'/'MOTORISTA'/'AJUDANTE').
    // Mock inicial é fallback de demo se backend falhar.
    let PARCEIROS_MOCK = [
        // Clientes (destinos)
        { codparc: 240, nome: 'ASSAI SIA',                   tipo: 'CLIENTE' },
        { codparc: 244, nome: 'ASSAI ASA NORTE',             tipo: 'CLIENTE' },
        { codparc: 245, nome: 'ASSAI ASA SUL',               tipo: 'CLIENTE' },
        { codparc: 251, nome: 'ASSAI CEILANDIA',             tipo: 'CLIENTE' },
        { codparc: 252, nome: 'ASSAI TAGUATINGA',            tipo: 'CLIENTE' },
        { codparc: 253, nome: 'ASSAI VALPARAISO',            tipo: 'CLIENTE' },
        { codparc: 211, nome: 'ASSAI PALMAS TEOTONIO',       tipo: 'CLIENTE' },
        { codparc: 212, nome: 'ASSAI PALMAS CESAMAR',        tipo: 'CLIENTE' },
        { codparc: 213, nome: 'ASSAI ARAGUAINA',             tipo: 'CLIENTE' },
        { codparc: 270, nome: 'VERDI ASA SUL',               tipo: 'CLIENTE' },
        { codparc: 271, nome: 'VERDI ASA NORTE',             tipo: 'CLIENTE' },
        { codparc: 272, nome: 'VERDI LAGO SUL',              tipo: 'CLIENTE' },
        { codparc: 313, nome: 'ECONOMART BARREIRAS',         tipo: 'CLIENTE' },
        { codparc: 314, nome: 'ECONOMART LEM',               tipo: 'CLIENTE' },
        { codparc: 350, nome: 'NA HORTA',                    tipo: 'CLIENTE' },
        { codparc: 401, nome: 'EXAL LUNDIN',                 tipo: 'CLIENTE' },
        { codparc: 402, nome: 'EXAL AURA SERRA GRANDE',      tipo: 'CLIENTE' },
        { codparc: 510, nome: 'JC ANAPOLIS',                 tipo: 'CLIENTE' },
        { codparc: 511, nome: 'JC GOIANIA',                  tipo: 'CLIENTE' },
        // Motoristas
        { codparc: 800, nome: 'VICENTE',         razao: 'VICENTE SOARES',    tipo: 'MOTORISTA' },
        { codparc: 801, nome: 'ALAN',            razao: 'ALAN FERREIRA',     tipo: 'MOTORISTA' },
        { codparc: 802, nome: 'HENRIQUE',        razao: 'HENRIQUE BATISTA',  tipo: 'MOTORISTA' },
        { codparc: 803, nome: 'ALVERI',          razao: 'ALVERI SANTOS',     tipo: 'MOTORISTA' },
        { codparc: 804, nome: 'WELINGTON',       razao: 'WELINGTON COSTA',   tipo: 'MOTORISTA' },
        { codparc: 805, nome: 'CARLOS',          razao: 'CARLOS OLIVEIRA',   tipo: 'MOTORISTA' },
        { codparc: 806, nome: 'ROBERTO',         razao: 'ROBERTO ANDRADE',   tipo: 'MOTORISTA' },
        { codparc: 807, nome: 'JOSÉ MENDES',     razao: 'JOSE MENDES',       tipo: 'MOTORISTA' },
        // Ajudantes
        { codparc: 900, nome: 'JULIANO',         razao: 'JULIANO PEREIRA',   tipo: 'AJUDANTE' },
        { codparc: 901, nome: 'PEDRO',           razao: 'PEDRO COSTA',       tipo: 'AJUDANTE' },
        { codparc: 902, nome: 'MARIA',           razao: 'MARIA SANTOS',      tipo: 'AJUDANTE' },
        { codparc: 903, nome: 'BRUNO',           razao: 'BRUNO LIMA',        tipo: 'AJUDANTE' },
        { codparc: 904, nome: 'FELIPE',          razao: 'FELIPE SOUZA',      tipo: 'AJUDANTE' },
        { codparc: 905, nome: 'ANDERSON',        razao: 'ANDERSON DIAS',     tipo: 'AJUDANTE' },
        { codparc: 906, nome: 'PAULO HENRIQUE',  razao: 'PAULO HENRIQUE',    tipo: 'AJUDANTE' },
        { codparc: 907, nome: 'LUCAS',           razao: 'LUCAS PEREIRA',     tipo: 'AJUDANTE' },
        { codparc: 908, nome: 'TIAGO',           razao: 'TIAGO MENDES',      tipo: 'AJUDANTE' },
    ];

    function parceirosPorTipo(tipo) {
        return PARCEIROS_MOCK.filter(function (p) { return p.tipo === tipo; });
    }

    function buscarParceiro(codparc) {
        return PARCEIROS_MOCK.find(function (p) { return p.codparc === codparc; }) || null;
    }

    function buscarVeiculo(codveiculo) {
        return VEICULOS_MOCK.find(function (v) { return v.codveiculo === codveiculo; }) || null;
    }

    // ROTAS — populadas via apiCarregarViagens() no boot.
    // Mock vazio inicialmente; preenchido após fetch /viagens/.
    let MOCK_ROTAS = [];

    // Mock fallback — só usado se backend falhar completamente
    const MOCK_ROTAS_FALLBACK = [
        {
            id: 1, num_viagem: 3043,
            data: HOJE, hora_saida: '06:00',
            codveiculo: 1,
            codparc_motorista: 800,  // VICENTE
            ajudantes: [900],         // JULIANO
            destinos: [
                { ordem: 1, codparc: 240, qtd_caixas: 120, obs: '' },
                { ordem: 2, codparc: 244, qtd_caixas: 90, obs: 'entregar antes 9h' },
            ],
            observacao: 'Carro tanqueado ontem. Documentação no porta-luvas.',
        },
        {
            id: 2, num_viagem: 3044,
            data: HOJE, hora_saida: '05:30',
            codveiculo: 2,
            codparc_motorista: 801,  // ALAN
            ajudantes: [901, 902],
            destinos: [
                { ordem: 1, codparc: 270, qtd_caixas: 60, obs: '' },
                { ordem: 2, codparc: 271, qtd_caixas: 80, obs: '' },
                { ordem: 3, codparc: 272, qtd_caixas: 50, obs: 'recolher caixas vazias' },
            ],
            observacao: 'Verdi DF — rotina semanal.',
        },
        {
            id: 3, num_viagem: 3045,
            data: HOJE, hora_saida: '05:30',
            codveiculo: 3,
            codparc_motorista: 802,  // HENRIQUE
            ajudantes: [900],         // JULIANO
            destinos: [
                { ordem: 1, codparc: 240, qtd_caixas: 75, obs: '' },
                { ordem: 2, codparc: 244, qtd_caixas: 50, obs: '' },
            ],
            observacao: 'Cê tá doido!!!',
        },
        {
            id: 4, num_viagem: 3046,
            data: HOJE, hora_saida: '04:00',
            codveiculo: 4,
            codparc_motorista: 803,  // ALVERI
            ajudantes: [903, 904],
            destinos: [
                { ordem: 1, codparc: 211, qtd_caixas: 130, obs: '' },
                { ordem: 2, codparc: 212, qtd_caixas: 110, obs: 'descarregar pela rampa lateral' },
            ],
            observacao: 'Saída antes do amanhecer. Café preparado na cozinha.',
        },
        {
            id: 5, num_viagem: 3047,
            data: HOJE, hora_saida: '02:30',
            codveiculo: 5,
            codparc_motorista: 804,  // WELINGTON
            ajudantes: [905, 906, 907],
            destinos: [
                { ordem: 1, codparc: 313, qtd_caixas: 220, obs: '' },
                { ordem: 2, codparc: 314, qtd_caixas: 180, obs: '' },
            ],
            observacao: 'Viagem longa pra Bahia. Combustível 70%.',
        },
        {
            id: 6, num_viagem: 3042,
            data: ONTEM, hora_saida: '06:30',
            codveiculo: 6,
            codparc_motorista: 805,  // CARLOS
            ajudantes: [908],
            destinos: [
                { ordem: 1, codparc: 350, qtd_caixas: 35, obs: '' },
                { ordem: 2, codparc: 270, qtd_caixas: 40, obs: '' },
            ],
            observacao: '',
        },
        {
            id: 7, num_viagem: 3048,
            data: AMANHA, hora_saida: '07:00',
            codveiculo: 7,
            codparc_motorista: 806,  // ROBERTO
            ajudantes: [901, 904],
            destinos: [
                { ordem: 1, codparc: 401, qtd_caixas: 60, obs: '' },
                { ordem: 2, codparc: 402, qtd_caixas: 70, obs: '' },
                { ordem: 3, codparc: 510, qtd_caixas: 95, obs: 'preferir saída sul' },
            ],
            observacao: 'Rota Goiás — incluir Exal e JC no mesmo trajeto.',
        },
    ];

    let proximoId = 100;          // legacy — mock fallback usa; backend retorna ID via sequence
    let proximoNumViagem = 1;     // backend retorna em response.proximo_num_viagem

    // -------------------------------------------------------------------------
    // API CLIENT (backend real, schema persistente)
    // -------------------------------------------------------------------------

    function normalizarViagem(v) {
        // Mapeia campos do backend pro formato interno usado pelo JS
        return {
            id: v.id,
            num_viagem: v.num_viagem,
            data: v.data_viagem,
            hora_saida: v.hora_saida,
            codveiculo: v.codveiculo,
            codparc_motorista: v.codparc_motorista,
            observacao: v.observacao || '',
            ajudantes: (v.ajudantes || []).map(function (a) { return a.codparc; }),
            destinos: (v.destinos || []).map(function (d) {
                return {
                    id: d.id,
                    ordem: d.ordem,
                    codparc: d.codparc,
                    qtd_caixas: d.qtd_caixas,
                    obs: d.observacao || '',
                };
            }),
        };
    }

    async function apiCarregarViagens(filtros) {
        const params = new URLSearchParams();
        if (filtros && filtros.data_de)            params.set('data_de', filtros.data_de);
        if (filtros && filtros.data_ate)           params.set('data_ate', filtros.data_ate);
        if (filtros && filtros.codparc_motorista)  params.set('codparc_motorista', filtros.codparc_motorista);
        if (filtros && filtros.codveiculo)         params.set('codveiculo', filtros.codveiculo);
        if (filtros && filtros.q)                  params.set('q', filtros.q);
        params.set('limite', '300');
        const data = await apiGet('/sankhya/logistica/api/viagens/?' + params.toString());
        if (!data.ok) throw new Error(data.error || 'Falha ao carregar viagens');
        if (data.proximo_num_viagem) proximoNumViagem = data.proximo_num_viagem;
        return (data.viagens || []).map(normalizarViagem);
    }

    async function apiCarregarParceiros(tipoId) {
        const data = await apiGet('/sankhya/logistica/api/parceiros/?tipo=' + tipoId + '&limite=500');
        if (!data.ok) throw new Error(data.error || 'Falha ao carregar parceiros');
        return data.parceiros || [];
    }

    async function apiCarregarVeiculos() {
        const data = await apiGet('/sankhya/logistica/api/veiculos/?limite=300');
        if (!data.ok) throw new Error(data.error || 'Falha ao carregar veículos');
        return data.veiculos || [];
    }

    function payloadParaBackend(p) {
        // Converte campos internos do JS pro formato do backend.
        return {
            data_viagem: p.data,
            hora_saida: p.hora_saida,
            codveiculo: p.codveiculo,
            codparc_motorista: p.codparc_motorista,
            observacao: p.observacao || '',
            destinos: (p.destinos || []).map(function (d) {
                return {
                    codparc: d.codparc,
                    qtd_caixas: d.qtd_caixas,
                    observacao: d.obs || '',
                };
            }),
            ajudantes: p.ajudantes || [],
        };
    }

    async function apiCriarViagem(payload) {
        const body = payloadParaBackend(payload);
        return apiPost('/sankhya/logistica/api/viagem/criar/', body);
    }

    async function apiEditarViagem(viagemId, payload) {
        const body = payloadParaBackend(payload);
        return apiPost('/sankhya/logistica/api/viagem/' + viagemId + '/editar/', body);
    }

    async function apiExcluirViagem(viagemId, motivo) {
        return apiPost('/sankhya/logistica/api/viagem/' + viagemId + '/excluir/', { motivo: motivo || '' });
    }

    function filtrosEstado() {
        return {
            data_de: ESTADO.filtroDataIni || '',
            data_ate: ESTADO.filtroDataFim || ESTADO.filtroDataIni || '',
            codparc_motorista: ESTADO.filtroCodparcMotorista || 0,
            codveiculo: ESTADO.filtroCodveiculo || 0,
            q: (ESTADO.filtroBusca || '').trim(),
        };
    }

    let _refetchTimer = null;
    let _refetchToken = 0;
    function aplicarFiltrosBackend(opts) {
        const debounceMs = (opts && typeof opts.debounceMs === 'number') ? opts.debounceMs : 250;
        if (_refetchTimer) clearTimeout(_refetchTimer);
        _refetchTimer = setTimeout(async function () {
            const meuToken = ++_refetchToken;
            try {
                const rotas = await apiCarregarViagens(filtrosEstado());
                if (meuToken !== _refetchToken) return;   // resposta obsoleta — descarta
                MOCK_ROTAS = rotas;
                renderTudo();
            } catch (e) {
                if (meuToken !== _refetchToken) return;
                console.error('Falha ao filtrar viagens:', e);
                if (window.IAgro && IAgro.showToast) {
                    IAgro.showToast('Erro ao filtrar: ' + e.message, 'error');
                }
            }
        }, debounceMs);
    }

    async function recarregarDadosBackend() {
        try {
            const [veics, motoristas, clientes, ajudantes, rotas] = await Promise.all([
                apiCarregarVeiculos(),
                apiCarregarParceiros(TIPO_MOTORISTA),
                apiCarregarParceiros(TIPO_CLIENTE),
                apiCarregarParceiros(TIPO_AJUDANTE),
                apiCarregarViagens(filtrosEstado()),
            ]);

            VEICULOS_MOCK = veics.map(function (v) {
                return {
                    codveiculo: v.codveiculo,
                    placa: v.placa,
                    modelo: v.marcamodelo || '',
                };
            });

            PARCEIROS_MOCK = [];
            motoristas.forEach(function (m) {
                PARCEIROS_MOCK.push({
                    codparc: m.codparc, nome: m.nomeparc, razao: m.razaosocial || '', tipo: 'MOTORISTA',
                });
            });
            clientes.forEach(function (c) {
                PARCEIROS_MOCK.push({
                    codparc: c.codparc, nome: c.nomeparc, razao: c.razaosocial || '', tipo: 'CLIENTE',
                });
            });
            ajudantes.forEach(function (a) {
                PARCEIROS_MOCK.push({
                    codparc: a.codparc, nome: a.nomeparc, razao: a.razaosocial || '', tipo: 'AJUDANTE',
                });
            });

            MOCK_ROTAS = rotas;
            return { ok: true };
        } catch (e) {
            console.error('Falha ao carregar dados do backend:', e);
            if (window.IAgro && IAgro.showToast) {
                IAgro.showToast('Erro carregando dados do servidor: ' + e.message, 'error');
            }
            return { ok: false, error: e.message };
        }
    }

    // -------------------------------------------------------------------------
    // ESTADO
    // -------------------------------------------------------------------------
    const ESTADO = {
        filtroDataIni: HOJE,
        filtroDataFim: HOJE,
        filtroBusca: '',
        filtroCodparcMotorista: 0,
        filtroCodveiculo: 0,
        rotaEditandoId: null,
        // edição corrente do modal
        ajudantesEdit: [],   // array de codparc
        destinosEdit: [],    // array de { ordem, codparc, qtd_caixas, obs }
    };

    // -------------------------------------------------------------------------
    // HELPERS
    // -------------------------------------------------------------------------
    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function normalizar(s) {
        return (s || '').toString().toLowerCase()
            .normalize('NFD').replace(/[̀-ͯ]/g, '');
    }

    function fmtDataBR(iso) {
        if (!iso) return '—';
        const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
        if (!m) return iso;
        return `${m[3]}/${m[2]}/${m[1]}`;
    }

    function fmtDataExtenso(iso) {
        if (!iso) return '—';
        const d = new Date(iso + 'T12:00:00');
        if (isNaN(d.getTime())) return iso;
        const dias = ['domingo', 'segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado'];
        return dias[d.getDay()] + ', ' + fmtDataBR(iso);
    }

    function nomeMotorista(r) {
        if (!r.codparc_motorista) return '—';
        const p = buscarParceiro(r.codparc_motorista);
        return p ? p.nome : ('parc ' + r.codparc_motorista);
    }

    function nomeAjudantes(r) {
        if (!r.ajudantes || !r.ajudantes.length) return '';
        return r.ajudantes.map(function (codparc) {
            const p = buscarParceiro(codparc);
            return p ? p.nome : ('parc ' + codparc);
        }).join(', ');
    }

    function nomeDestino(codparc) {
        const p = buscarParceiro(codparc);
        return p ? p.nome : '—';
    }

    function placaModelo(r) {
        const v = buscarVeiculo(r.codveiculo);
        if (v) return { placa: v.placa, modelo: v.modelo };
        return { placa: '—', modelo: '—' };
    }

    function totalCaixas(r) {
        if (!r.destinos) return 0;
        return r.destinos.reduce(function (sum, d) { return sum + (d.qtd_caixas || 0); }, 0);
    }

    function mostrarToast(msg, tipo) {
        if (window.IAgro && IAgro.showToast) IAgro.showToast(msg, tipo || 'info');
    }

    // -------------------------------------------------------------------------
    // FILTRAGEM
    // -------------------------------------------------------------------------
    // Backend já entrega a lista filtrada por ESTADO. Aqui só ordena.
    function rotasFiltradas() {
        return MOCK_ROTAS.slice().sort(function (a, b) {
            if (a.data !== b.data) return a.data < b.data ? 1 : -1;
            return (a.hora_saida || '').localeCompare(b.hora_saida || '');
        });
    }

    // -------------------------------------------------------------------------
    // RENDER
    // -------------------------------------------------------------------------
    function atualizarResumo() {
        const lista = rotasFiltradas();
        const total = lista.length;
        const caixas = lista.reduce(function (s, r) { return s + totalCaixas(r); }, 0);
        const destinos = lista.reduce(function (s, r) { return s + (r.destinos || []).length; }, 0);
        const motoristas = new Set();
        lista.forEach(function (r) { if (r.codparc_motorista) motoristas.add(r.codparc_motorista); });

        document.getElementById('lgResumoTotal').textContent = total;
        document.getElementById('lgResumoCaixas').textContent = caixas.toLocaleString('pt-BR');
        document.getElementById('lgResumoDestinos').textContent = destinos;
        document.getElementById('lgResumoMotoristas').textContent = motoristas.size;

        document.getElementById('lgRotasContador').textContent = total + (total === 1 ? ' viagem' : ' viagens');
    }

    function renderLista() {
        const container = document.getElementById('lgRotasLista');
        const lista = rotasFiltradas();

        if (!lista.length) {
            container.innerHTML = '<div class="lg-empty">Nenhuma viagem encontrada com os filtros atuais.</div>';
            return;
        }

        container.innerHTML = lista.map(function (r) {
            const pm = placaModelo(r);
            const motorista = nomeMotorista(r);
            const ajudantes = nomeAjudantes(r);
            const total = totalCaixas(r);

            // Render dos primeiros 3 destinos + "+N mais"
            const destinos = r.destinos || [];
            const visiveis = destinos.slice(0, 3);
            const restantes = destinos.length - 3;

            const linhasDest = visiveis.map(function (d, i) {
                return `
                    <div class="lg-card-destino-linha">
                        <span class="lg-card-destino-cliente">${i + 1}. ${escapeHtml(nomeDestino(d.codparc))}</span>
                        <span class="lg-card-destino-qtd">${d.qtd_caixas}cx</span>
                    </div>
                `;
            }).join('');

            const maisLinha = restantes > 0
                ? `<div class="lg-card-destinos-mais">+ ${restantes} ${restantes === 1 ? 'destino' : 'destinos'}</div>`
                : '';

            return `
                <div class="lg-card" data-id="${r.id}">
                    <div class="lg-card-numviagem">
                        <span class="lg-card-numviagem-label">Viagem</span>
                        <span class="lg-card-numviagem-valor">${r.num_viagem}</span>
                    </div>
                    <div class="lg-card-cabecalho">
                        <span class="lg-card-placa">${escapeHtml(pm.placa)}</span>
                        <span class="lg-card-modelo">${escapeHtml(pm.modelo)}</span>
                        <span class="lg-card-datahora">${fmtDataBR(r.data)} · ${escapeHtml(r.hora_saida)}</span>
                    </div>
                    <div class="lg-card-detalhe">
                        <span class="lg-card-tag"><i class="ph ph-steering-wheel"></i> ${escapeHtml(motorista)}</span>
                        ${ajudantes ? '<span class="lg-card-tag"><i class="ph ph-users"></i>' + escapeHtml(ajudantes) + '</span>' : ''}
                    </div>
                    <div class="lg-card-destinos">
                        <span class="lg-card-destinos-titulo">Destinos (${destinos.length})</span>
                        ${linhasDest}
                        ${maisLinha}
                    </div>
                    <div class="lg-card-direita">
                        <span class="lg-card-qtd">${total}<small>caixas</small></span>
                        <button type="button" class="lg-card-imprimir" data-id="${r.id}" title="Ficha de impressão" aria-label="Ficha">
                            <i class="ph ph-printer"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        // Click no card abre edição (mas não no botão imprimir)
        container.querySelectorAll('.lg-card').forEach(function (card) {
            card.addEventListener('click', function (e) {
                const btn = e.target.closest('.lg-card-imprimir');
                if (btn) {
                    e.stopPropagation();
                    const id = parseInt(btn.dataset.id, 10);
                    abrirFicha(id);
                    return;
                }
                const id = parseInt(card.dataset.id, 10);
                abrirModalEditar(id);
            });
        });
    }

    function preencherFiltrosSelects() {
        const motoSel = document.getElementById('lgFiltroMotorista');
        const veicSel = document.getElementById('lgFiltroVeiculo');
        if (motoSel) {
            const ms = parceirosPorTipo('MOTORISTA')
                .slice().sort(function (a, b) { return a.nome.localeCompare(b.nome); });
            motoSel.innerHTML = '<option value="">Todos</option>' + ms.map(function (p) {
                return `<option value="${p.codparc}">${escapeHtml(p.nome)}</option>`;
            }).join('');
        }
        if (veicSel) {
            veicSel.innerHTML = '<option value="">Todos</option>' + VEICULOS_MOCK.map(function (v) {
                return `<option value="${v.codveiculo}">${escapeHtml(v.placa)} — ${escapeHtml(v.modelo)}</option>`;
            }).join('');
        }
    }

    function renderTudo() {
        atualizarResumo();
        renderLista();
    }

    // -------------------------------------------------------------------------
    // MODAL NOVA / EDITAR
    // -------------------------------------------------------------------------
    function abrirModalNova() {
        ESTADO.rotaEditandoId = null;
        ESTADO.ajudantesEdit = [];
        ESTADO.destinosEdit = [];

        document.getElementById('lgRotaModalTitulo').textContent = 'Nova viagem';
        document.getElementById('lgRotaModalNumViagem').textContent = '#' + proximoNumViagem + ' (próximo)';
        document.getElementById('lgRotaSalvarLabel').textContent = 'Confirmar viagem';
        document.getElementById('lgRotaExcluir').hidden = true;
        document.getElementById('lgRotaImprimir').hidden = true;

        document.getElementById('lgRotaVeiculo').value = '';
        document.getElementById('lgRotaCodVeiculo').value = '';
        document.getElementById('lgRotaData').value = HOJE;
        document.getElementById('lgRotaHora').value = '06:00';
        document.getElementById('lgRotaMotorista').value = '';
        document.getElementById('lgRotaCodMotorista').value = '';
        document.getElementById('lgRotaAjudanteInput').value = '';
        document.getElementById('lgRotaObs').value = '';
        renderChipsAjudantes();
        renderDestinosEdit();
        limparMsg();

        abrirOverlay();
    }

    function abrirModalEditar(id) {
        const r = MOCK_ROTAS.find(function (x) { return x.id === id; });
        if (!r) return;

        ESTADO.rotaEditandoId = id;
        ESTADO.ajudantesEdit = (r.ajudantes || []).slice();
        ESTADO.destinosEdit = (r.destinos || []).map(function (d) {
            return { ordem: d.ordem, codparc: d.codparc, qtd_caixas: d.qtd_caixas, obs: d.obs || '' };
        });

        document.getElementById('lgRotaModalTitulo').textContent = 'Editar viagem';
        document.getElementById('lgRotaModalNumViagem').textContent = '#' + r.num_viagem;
        document.getElementById('lgRotaSalvarLabel').textContent = 'Salvar alterações';
        document.getElementById('lgRotaExcluir').hidden = false;
        document.getElementById('lgRotaImprimir').hidden = false;

        const pm = placaModelo(r);
        document.getElementById('lgRotaVeiculo').value = pm.placa + ' — ' + pm.modelo;
        document.getElementById('lgRotaCodVeiculo').value = r.codveiculo || '';
        document.getElementById('lgRotaData').value = r.data;
        document.getElementById('lgRotaHora').value = r.hora_saida;
        document.getElementById('lgRotaMotorista').value = nomeMotorista(r);
        document.getElementById('lgRotaCodMotorista').value = r.codparc_motorista || '';
        document.getElementById('lgRotaAjudanteInput').value = '';
        document.getElementById('lgRotaObs').value = r.observacao || '';
        renderChipsAjudantes();
        renderDestinosEdit();
        limparMsg();

        abrirOverlay();
    }

    function abrirOverlay() {
        const overlay = document.getElementById('lgRotaModal');
        overlay.classList.remove('hidden');
        overlay.setAttribute('aria-hidden', 'false');
    }

    function fecharOverlay() {
        const overlay = document.getElementById('lgRotaModal');
        overlay.classList.add('hidden');
        overlay.setAttribute('aria-hidden', 'true');
    }

    function renderChipsAjudantes() {
        const container = document.getElementById('lgRotaAjudantesChips');
        if (!container) return;
        if (!ESTADO.ajudantesEdit.length) {
            container.innerHTML = '';
            return;
        }
        container.innerHTML = ESTADO.ajudantesEdit.map(function (codparc, idx) {
            const p = buscarParceiro(codparc);
            const nome = p ? p.nome : ('parc ' + codparc);
            return `
                <span class="lg-chip-pessoa">
                    ${escapeHtml(nome)}
                    <button type="button" class="lg-chip-remove" data-idx="${idx}" aria-label="Remover">×</button>
                </span>
            `;
        }).join('');
        container.querySelectorAll('.lg-chip-remove').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const idx = parseInt(btn.dataset.idx, 10);
                ESTADO.ajudantesEdit.splice(idx, 1);
                renderChipsAjudantes();
            });
        });
    }

    function renderDestinosEdit() {
        const container = document.getElementById('lgRotaDestinosLista');
        if (!container) return;

        if (!ESTADO.destinosEdit.length) {
            container.innerHTML = '<div class="lg-destinos-edit-empty">Adicione pelo menos um destino abaixo.</div>';
            atualizarTotalDestinos();
            return;
        }

        container.innerHTML = ESTADO.destinosEdit.map(function (d, idx) {
            const nome = d.codparc ? nomeDestino(d.codparc) : '';
            return `
                <div class="lg-destino-linha" data-idx="${idx}">
                    <div class="lg-destino-ordem">${idx + 1}</div>
                    <div class="lg-destino-cliente-wrap">
                        <input type="text" class="lg-destino-cliente-input" placeholder="Buscar cliente…"
                               value="${escapeHtml(nome)}" data-idx="${idx}" autocomplete="off">
                        <div class="dropdown-abs lg-destino-cliente-dd" data-idx="${idx}"></div>
                    </div>
                    <input type="number" class="lg-destino-qtd" min="0" step="1" placeholder="0"
                           value="${d.qtd_caixas || 0}" data-idx="${idx}">
                    <button type="button" class="lg-destino-remover" data-idx="${idx}" aria-label="Remover destino">
                        <i class="ph ph-trash"></i>
                    </button>
                </div>
            `;
        }).join('');

        // Bind dos inputs de cliente (typeahead) e qtd
        container.querySelectorAll('.lg-destino-cliente-input').forEach(function (inp) {
            const idx = parseInt(inp.dataset.idx, 10);
            const dd = container.querySelector('.lg-destino-cliente-dd[data-idx="' + idx + '"]');
            setupTypeaheadClienteEditavel(inp, dd, idx);
        });

        container.querySelectorAll('.lg-destino-qtd').forEach(function (inp) {
            inp.addEventListener('input', function () {
                const idx = parseInt(inp.dataset.idx, 10);
                ESTADO.destinosEdit[idx].qtd_caixas = parseInt(inp.value, 10) || 0;
                atualizarTotalDestinos();
            });
        });

        container.querySelectorAll('.lg-destino-remover').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const idx = parseInt(btn.dataset.idx, 10);
                ESTADO.destinosEdit.splice(idx, 1);
                renderDestinosEdit();
            });
        });

        atualizarTotalDestinos();
    }

    function setupTypeaheadClienteEditavel(input, dropdown, idx) {
        function buscar() {
            const termo = normalizar(input.value);
            const clientes = parceirosPorTipo('CLIENTE');
            const results = clientes.filter(function (p) {
                return normalizar(p.nome).indexOf(termo) >= 0;
            }).slice(0, 8);

            if (!results.length) {
                dropdown.innerHTML = '<div class="dd-item dd-empty">Nenhum cliente</div>';
            } else {
                dropdown.innerHTML = results.map(function (p) {
                    return `<div class="dd-item" data-cod="${p.codparc}" data-nome="${escapeHtml(p.nome)}">
                        ${escapeHtml(p.nome)}
                    </div>`;
                }).join('');
            }
            dropdown.style.display = 'block';

            dropdown.querySelectorAll('.dd-item[data-cod]').forEach(function (item) {
                item.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    const cp = parseInt(item.dataset.cod, 10);
                    ESTADO.destinosEdit[idx].codparc = cp;
                    input.value = item.dataset.nome;
                    dropdown.style.display = 'none';
                });
            });
        }
        input.addEventListener('input', buscar);
        input.addEventListener('focus', buscar);
        input.addEventListener('blur', function () {
            setTimeout(function () { dropdown.style.display = 'none'; }, 200);
        });
    }

    function atualizarTotalDestinos() {
        const total = ESTADO.destinosEdit.reduce(function (s, d) { return s + (d.qtd_caixas || 0); }, 0);
        const el = document.getElementById('lgRotaDestinosTotal');
        if (el) el.textContent = total.toLocaleString('pt-BR');
    }

    function adicionarDestino() {
        ESTADO.destinosEdit.push({
            ordem: ESTADO.destinosEdit.length + 1,
            codparc: 0,
            qtd_caixas: 0,
            obs: '',
        });
        renderDestinosEdit();
    }

    function setMsg(texto, tipo) {
        const el = document.getElementById('lgRotaMsg');
        el.textContent = texto;
        el.hidden = false;
        el.classList.remove('lg-form-msg--success');
        if (tipo === 'success') el.classList.add('lg-form-msg--success');
    }

    function limparMsg() {
        const el = document.getElementById('lgRotaMsg');
        el.textContent = '';
        el.hidden = true;
    }

    function coletarPayload() {
        const codveiculo = parseInt(document.getElementById('lgRotaCodVeiculo').value, 10) || 0;
        const data = document.getElementById('lgRotaData').value;
        const hora = document.getElementById('lgRotaHora').value;
        const codparc_motorista = parseInt(document.getElementById('lgRotaCodMotorista').value, 10) || 0;
        const observacao = document.getElementById('lgRotaObs').value.trim();

        if (!codveiculo) return { erro: 'Escolha um caminhão pelo typeahead.' };
        if (!data) return { erro: 'Informe a data.' };
        if (!hora) return { erro: 'Informe a hora de saída.' };
        if (!codparc_motorista) return { erro: 'Escolha um motorista (parceiro tipo MOTORISTA).' };
        if (!ESTADO.destinosEdit.length) return { erro: 'Adicione pelo menos um destino.' };

        // Valida destinos
        const destinos = [];
        for (let i = 0; i < ESTADO.destinosEdit.length; i++) {
            const d = ESTADO.destinosEdit[i];
            if (!d.codparc) return { erro: 'Destino #' + (i + 1) + ' sem cliente selecionado.' };
            if (!d.qtd_caixas || d.qtd_caixas <= 0) return { erro: 'Destino #' + (i + 1) + ' precisa ter qtd > 0.' };
            destinos.push({ ordem: i + 1, codparc: d.codparc, qtd_caixas: d.qtd_caixas, obs: d.obs || '' });
        }

        return {
            ok: true,
            codveiculo: codveiculo,
            data: data,
            hora_saida: hora,
            codparc_motorista: codparc_motorista,
            ajudantes: ESTADO.ajudantesEdit.slice(),
            destinos: destinos,
            observacao: observacao,
        };
    }

    async function salvarRota() {
        const payload = coletarPayload();
        if (payload.erro) { setMsg(payload.erro, 'error'); return; }
        delete payload.ok;

        const btn = document.getElementById('lgRotaSalvar');
        if (btn) btn.disabled = true;
        setMsg('Salvando...', 'info');

        try {
            let resp;
            if (ESTADO.rotaEditandoId) {
                resp = await apiEditarViagem(ESTADO.rotaEditandoId, payload);
            } else {
                resp = await apiCriarViagem(payload);
            }

            if (!resp.ok) {
                setMsg(resp.error || 'Falha ao salvar.', 'error');
                if (btn) btn.disabled = false;
                return;
            }

            const numFinal = resp.num_viagem;
            const tipoAcao = ESTADO.rotaEditandoId ? 'atualizada' : 'criada';
            mostrarToast('Viagem #' + numFinal + ' ' + tipoAcao + '.', 'success');

            await recarregarDadosBackend();
            fecharOverlay();
            renderTudo();
        } catch (e) {
            setMsg(e.message || 'Falha de comunicação.', 'error');
            if (btn) btn.disabled = false;
        }
    }

    function excluirRota() {
        if (!ESTADO.rotaEditandoId) return;
        const r = MOCK_ROTAS.find(function (x) { return x.id === ESTADO.rotaEditandoId; });
        if (!r) return;

        const confirmar = window.IAgro && IAgro.confirmarAcao
            ? IAgro.confirmarAcao({
                titulo: 'Excluir viagem',
                mensagem: 'Confirmar exclusão da viagem #' + r.num_viagem + ' (' + fmtDataBR(r.data) + ')?',
                tipo: 'perigo',
            })
            : Promise.resolve(window.confirm('Excluir esta viagem?'));

        Promise.resolve(confirmar).then(async function (ok) {
            if (!ok) return;
            try {
                const resp = await apiExcluirViagem(ESTADO.rotaEditandoId, '');
                if (!resp.ok) {
                    mostrarToast('Erro ao excluir: ' + (resp.error || 'desconhecido'), 'error');
                    return;
                }
                await recarregarDadosBackend();
                fecharOverlay();
                renderTudo();
                mostrarToast('Viagem excluída.', 'success');
            } catch (e) {
                mostrarToast('Falha: ' + e.message, 'error');
            }
        });
    }

    // -------------------------------------------------------------------------
    // FICHA DE IMPRESSÃO
    // -------------------------------------------------------------------------
    function abrirFicha(id) {
        const r = MOCK_ROTAS.find(function (x) { return x.id === id; });
        if (!r) return;
        window._lgFichaUltimaId = id;   // guardado pra botão Imprimir saber qual rota baixar
        renderFicha(r);
        const overlay = document.getElementById('lgFichaModal');
        overlay.classList.remove('hidden');
        overlay.setAttribute('aria-hidden', 'false');
    }

    function fecharFicha() {
        const overlay = document.getElementById('lgFichaModal');
        overlay.classList.add('hidden');
        overlay.setAttribute('aria-hidden', 'true');
    }

    function renderFicha(r) {
        const pm = placaModelo(r);
        const motorista = nomeMotorista(r);
        const ajudantes = nomeAjudantes(r) || '—';
        const total = totalCaixas(r);

        const destinosHTML = (r.destinos || []).map(function (d) {
            const obsHtml = d.obs ? `<small class="lg-ficha-destino-obs">${escapeHtml(d.obs)}</small>` : '';
            return `
                <li>
                    <span class="lg-ficha-destino-arrow">&gt;</span>
                    <span>
                        <span class="lg-ficha-destino-nome">${escapeHtml(nomeDestino(d.codparc))}</span>
                        ${obsHtml}
                    </span>
                    <span class="lg-ficha-destino-qtd">${d.qtd_caixas} cx</span>
                </li>
            `;
        }).join('');

        const html = `
            <header class="lg-ficha-cabecalho">
                <div class="lg-ficha-titulo">ROTA</div>
                <div class="lg-ficha-numviagem">VIAGEM Nº ${r.num_viagem}</div>
            </header>

            <div class="lg-ficha-data-bloco">
                <span class="lg-ficha-data-extenso">${fmtDataExtenso(r.data)}</span>
                <span class="lg-ficha-saida">
                    Saída às <span class="lg-ficha-saida-hora">${escapeHtml(r.hora_saida)}</span>
                </span>
            </div>

            <div class="lg-ficha-pessoas">
                <div class="lg-ficha-linha">
                    <span class="lg-ficha-linha-label">Motorista</span>
                    <span class="lg-ficha-motorista">${escapeHtml(motorista)}</span>
                </div>
                <div class="lg-ficha-linha">
                    <span class="lg-ficha-linha-label">Ajudante(s)</span>
                    <span class="lg-ficha-ajudantes">${escapeHtml(ajudantes)}</span>
                </div>
            </div>

            <div class="lg-ficha-placa">
                <div class="lg-ficha-placa-valor">${escapeHtml(pm.placa)}</div>
                <div class="lg-ficha-placa-modelo">${escapeHtml(pm.modelo)}</div>
            </div>

            <div class="lg-ficha-destinos">
                <div class="lg-ficha-destinos-titulo">Destinos:</div>
                <ol class="lg-ficha-destinos-lista">${destinosHTML}</ol>
            </div>

            <div class="lg-ficha-total">
                <span>Total de caixas:</span>
                <span class="lg-ficha-total-valor">${total}</span>
            </div>

            <div class="lg-ficha-obs">
                <div class="lg-ficha-obs-titulo">Observação:</div>
                <div class="lg-ficha-obs-texto">${escapeHtml(r.observacao || '')}</div>
            </div>

            <div class="lg-ficha-rodape">IAgro · Logística</div>
        `;

        document.getElementById('lgFichaPaper').innerHTML = html;
    }

    // -------------------------------------------------------------------------
    // TYPEAHEADS GENÉRICOS
    // -------------------------------------------------------------------------
    function attachTypeaheadParceiro(inputId, hiddenId, ddId, tipo, onSelect) {
        const input = document.getElementById(inputId);
        const hidden = document.getElementById(hiddenId);
        const dropdown = document.getElementById(ddId);
        if (!input || !dropdown) return;

        function buscar() {
            const termo = normalizar(input.value);
            const results = parceirosPorTipo(tipo).filter(function (p) {
                return normalizar(p.nome + ' ' + (p.razao || '')).indexOf(termo) >= 0;
            }).slice(0, 10);

            if (!results.length) {
                dropdown.innerHTML = '<div class="dd-item dd-empty">Nenhum parceiro</div>';
            } else {
                dropdown.innerHTML = results.map(function (p) {
                    const sub = p.razao ? `<small style="display:block;color:#6b7280;font-size:11px">${escapeHtml(p.razao)}</small>` : '';
                    return `<div class="dd-item" data-cod="${p.codparc}" data-nome="${escapeHtml(p.nome)}">
                        <strong>${escapeHtml(p.nome)}</strong>
                        ${sub}
                    </div>`;
                }).join('');
            }
            dropdown.style.display = 'block';

            dropdown.querySelectorAll('.dd-item[data-cod]').forEach(function (item) {
                item.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    const cp = parseInt(item.dataset.cod, 10);
                    if (hidden) hidden.value = cp;
                    input.value = item.dataset.nome;
                    dropdown.style.display = 'none';
                    if (onSelect) onSelect(cp);
                });
            });
        }
        input.addEventListener('input', buscar);
        input.addEventListener('focus', buscar);
        input.addEventListener('blur', function () {
            setTimeout(function () { dropdown.style.display = 'none'; }, 200);
        });
    }

    function setupTypeaheadVeiculo() {
        const input = document.getElementById('lgRotaVeiculo');
        const hidden = document.getElementById('lgRotaCodVeiculo');
        const dropdown = document.getElementById('lgRotaVeiculoDropdown');
        if (!input || !dropdown) return;

        function buscar() {
            const termo = normalizar(input.value);
            const results = VEICULOS_MOCK.filter(function (v) {
                return normalizar(v.placa + ' ' + v.modelo).indexOf(termo) >= 0;
            }).slice(0, 8);

            if (!results.length) {
                dropdown.innerHTML = '<div class="dd-item dd-empty">Nenhum veículo</div>';
            } else {
                dropdown.innerHTML = results.map(function (v) {
                    return `<div class="dd-item" data-cod="${v.codveiculo}" data-placa="${v.placa}" data-modelo="${v.modelo}">
                        <strong>${v.placa}</strong> — ${v.modelo}
                    </div>`;
                }).join('');
            }
            dropdown.style.display = 'block';
            dropdown.querySelectorAll('.dd-item[data-cod]').forEach(function (item) {
                item.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    input.value = item.dataset.placa + ' — ' + item.dataset.modelo;
                    hidden.value = item.dataset.cod;
                    dropdown.style.display = 'none';
                });
            });
        }
        input.addEventListener('input', buscar);
        input.addEventListener('focus', buscar);
        input.addEventListener('blur', function () {
            setTimeout(function () { dropdown.style.display = 'none'; }, 200);
        });
    }

    function setupAjudanteTypeahead() {
        const input = document.getElementById('lgRotaAjudanteInput');
        const dropdown = document.getElementById('lgRotaAjudanteDropdown');
        if (!input || !dropdown) return;

        function buscar() {
            const termo = normalizar(input.value);
            const disponiveis = parceirosPorTipo('AJUDANTE').filter(function (p) {
                return ESTADO.ajudantesEdit.indexOf(p.codparc) < 0;
            });
            const results = disponiveis.filter(function (p) {
                return normalizar(p.nome).indexOf(termo) >= 0;
            }).slice(0, 8);

            if (!results.length) {
                dropdown.innerHTML = '<div class="dd-item dd-empty">Nenhum ajudante disponível</div>';
            } else {
                dropdown.innerHTML = results.map(function (p) {
                    return `<div class="dd-item" data-cod="${p.codparc}" data-nome="${escapeHtml(p.nome)}">
                        ${escapeHtml(p.nome)}
                    </div>`;
                }).join('');
            }
            dropdown.style.display = 'block';
            dropdown.querySelectorAll('.dd-item[data-cod]').forEach(function (item) {
                item.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    const cp = parseInt(item.dataset.cod, 10);
                    if (ESTADO.ajudantesEdit.indexOf(cp) < 0) {
                        ESTADO.ajudantesEdit.push(cp);
                        renderChipsAjudantes();
                    }
                    input.value = '';
                    dropdown.style.display = 'none';
                });
            });
        }
        input.addEventListener('input', buscar);
        input.addEventListener('focus', buscar);
        input.addEventListener('blur', function () {
            setTimeout(function () { dropdown.style.display = 'none'; }, 200);
        });
    }

    // -------------------------------------------------------------------------
    // SETUP — FILTROS
    // -------------------------------------------------------------------------
    function setupFiltros() {
        const dataIni = document.getElementById('lgDataIni');
        const dataFim = document.getElementById('lgDataFim');
        const busca = document.getElementById('lgBusca');
        const motoSel = document.getElementById('lgFiltroMotorista');
        const veicSel = document.getElementById('lgFiltroVeiculo');

        dataIni.value = ESTADO.filtroDataIni;
        dataFim.value = ESTADO.filtroDataFim;

        // Replicação dataIni → dataFim (sempre, paridade com convenção iOS Safari)
        const replicarDataFim = function () {
            const v = dataIni.value;
            if (v) dataFim.value = v;
        };
        // change: aplica estado + dispara refetch. input: só replica (sem refetch a cada keystroke)
        dataIni.addEventListener('input', replicarDataFim);
        dataIni.addEventListener('change', function () {
            replicarDataFim();
            ESTADO.filtroDataIni = dataIni.value;
            ESTADO.filtroDataFim = dataFim.value;
            aplicarFiltrosBackend();
        });

        dataFim.addEventListener('change', function () {
            ESTADO.filtroDataFim = dataFim.value;
            aplicarFiltrosBackend();
        });

        const shift = function (delta) {
            let d = dataIni.value ? new Date(dataIni.value + 'T12:00:00') : new Date();
            if (isNaN(d.getTime())) d = new Date();
            d.setDate(d.getDate() + delta);
            const iso = d.toISOString().slice(0, 10);
            dataIni.value = iso;
            dataFim.value = iso;
            ESTADO.filtroDataIni = iso;
            ESTADO.filtroDataFim = iso;
            aplicarFiltrosBackend({ debounceMs: 0 });
        };
        document.getElementById('lgPrevDay').addEventListener('click', function () { shift(-1); });
        document.getElementById('lgNextDay').addEventListener('click', function () { shift(1); });

        busca.addEventListener('input', function () {
            ESTADO.filtroBusca = busca.value;
            aplicarFiltrosBackend({ debounceMs: 350 });
        });

        motoSel.addEventListener('change', function () {
            ESTADO.filtroCodparcMotorista = parseInt(motoSel.value, 10) || 0;
            aplicarFiltrosBackend({ debounceMs: 0 });
        });
        veicSel.addEventListener('change', function () {
            ESTADO.filtroCodveiculo = parseInt(veicSel.value, 10) || 0;
            aplicarFiltrosBackend({ debounceMs: 0 });
        });

        document.getElementById('lgLimparFiltros').addEventListener('click', function () {
            ESTADO.filtroDataIni = HOJE;
            ESTADO.filtroDataFim = HOJE;
            ESTADO.filtroBusca = '';
            ESTADO.filtroCodparcMotorista = 0;
            ESTADO.filtroCodveiculo = 0;
            dataIni.value = HOJE;
            dataFim.value = HOJE;
            busca.value = '';
            motoSel.value = '';
            veicSel.value = '';
            aplicarFiltrosBackend({ debounceMs: 0 });
        });
    }

    // -------------------------------------------------------------------------
    // BOOT
    // -------------------------------------------------------------------------
    document.addEventListener('DOMContentLoaded', function () {
        const btnNova = document.getElementById('btnNovaRota');
        if (btnNova) btnNova.addEventListener('click', abrirModalNova);

        const btnRefresh = document.getElementById('lgBtnRefresh');
        if (btnRefresh) btnRefresh.addEventListener('click', async function () {
            btnRefresh.classList.add('is-loading');
            try {
                const r = await recarregarDadosBackend();
                renderTudo();
                if (r.ok) mostrarToast('Lista atualizada.', 'info');
            } finally {
                btnRefresh.classList.remove('is-loading');
            }
        });

        // Modal — fechar
        document.querySelectorAll('#lgRotaModal [data-modal-close]').forEach(function (el) {
            el.addEventListener('click', fecharOverlay);
        });

        // Modal — backdrop click
        const overlay = document.getElementById('lgRotaModal');
        if (overlay) {
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) fecharOverlay();
            });
        }

        document.getElementById('lgRotaSalvar').addEventListener('click', salvarRota);
        document.getElementById('lgRotaExcluir').addEventListener('click', excluirRota);
        document.getElementById('lgRotaImprimir').addEventListener('click', function () {
            if (ESTADO.rotaEditandoId) abrirFicha(ESTADO.rotaEditandoId);
        });

        // Destinos — adicionar
        document.getElementById('lgRotaAddDestino').addEventListener('click', adicionarDestino);

        // Ficha — fechar + imprimir
        document.querySelectorAll('#lgFichaModal [data-modal-close]').forEach(function (el) {
            el.addEventListener('click', fecharFicha);
        });
        const fichaOverlay = document.getElementById('lgFichaModal');
        if (fichaOverlay) {
            fichaOverlay.addEventListener('click', function (e) {
                if (e.target === fichaOverlay) fecharFicha();
            });
        }
        document.getElementById('lgFichaImprimirBtn').addEventListener('click', function () {
            // PDF reportlab — abre em aba nova pra operador imprimir/baixar
            const id = ESTADO.rotaEditandoId || (window._lgFichaUltimaId || 0);
            if (id) {
                window.open('/sankhya/logistica/api/viagem/' + id + '/ficha-pdf/', '_blank');
            } else {
                window.print();   // fallback se não tem ID (rota local sem persistir)
            }
        });

        // Esc fecha
        document.addEventListener('keydown', function (e) {
            if (e.key !== 'Escape') return;
            const ficha = document.getElementById('lgFichaModal');
            const editor = document.getElementById('lgRotaModal');
            if (ficha && !ficha.classList.contains('hidden')) { fecharFicha(); return; }
            if (editor && !editor.classList.contains('hidden')) fecharOverlay();
        });

        setupTypeaheadVeiculo();
        attachTypeaheadParceiro('lgRotaMotorista', 'lgRotaCodMotorista', 'lgRotaMotoristaDropdown', 'MOTORISTA');
        setupAjudanteTypeahead();
        setupFiltros();
        renderTudo();

        // Carrega dados do backend e re-renderiza (assíncrono — UI aparece com mock fallback enquanto carrega)
        recarregarDadosBackend().then(function () {
            preencherFiltrosSelects();
            renderTudo();
        });
    });

    // Expor helpers pra mobile + camada de API
    window.LogisticaMock = {
        getRotas: function () { return MOCK_ROTAS; },
        getParceiros: function () { return PARCEIROS_MOCK; },
        getVeiculos: function () { return VEICULOS_MOCK; },
        parceirosPorTipo: parceirosPorTipo,
        buscarParceiro: buscarParceiro,
        buscarVeiculo: buscarVeiculo,
        // Métodos legacy mantidos pra compat com mobile (operam em memória local).
        // Mobile deve preferir LogisticaApi pra persistir.
        addRota: function (r) {
            MOCK_ROTAS.unshift(Object.assign({ id: proximoId++, num_viagem: proximoNumViagem++ }, r));
        },
        atualizarRota: function (id, dados) {
            const idx = MOCK_ROTAS.findIndex(function (x) { return x.id === id; });
            if (idx >= 0) MOCK_ROTAS[idx] = Object.assign({}, MOCK_ROTAS[idx], dados);
        },
        removerRota: function (id) {
            MOCK_ROTAS = MOCK_ROTAS.filter(function (x) { return x.id !== id; });
        },
        proximoNumViagem: function () { return proximoNumViagem; },
        rerenderDesktop: renderTudo,
        nomeMotorista: nomeMotorista,
        nomeAjudantes: nomeAjudantes,
        nomeDestino: nomeDestino,
        placaModelo: placaModelo,
        totalCaixas: totalCaixas,
        fmtDataBR: fmtDataBR,
        fmtDataExtenso: fmtDataExtenso,
    };

    // API de persistência real (preferida sobre LogisticaMock pra escrita)
    window.LogisticaApi = {
        criarViagem: apiCriarViagem,
        editarViagem: apiEditarViagem,
        excluirViagem: apiExcluirViagem,
        carregarViagens: apiCarregarViagens,
        carregarParceiros: apiCarregarParceiros,
        carregarVeiculos: apiCarregarVeiculos,
        recarregarTudo: recarregarDadosBackend,
        fichaPdfUrl: function (viagemId) {
            return '/sankhya/logistica/api/viagem/' + viagemId + '/ficha-pdf/';
        },
    };
})();
