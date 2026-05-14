/* ============================================================================
   Módulo Controle de Combustível — frontend
   Mai/2026 — entradas (TOP 10 + TGFFIN) + requisições (TOP 26 em aberto)
   ============================================================================ */
(function () {
    'use strict';

    // ---- Endpoints ----
    const URL_ESTOQUE        = '/sankhya/combustivel/api/estoque/';
    const URL_VEICULOS       = '/sankhya/combustivel/api/veiculos/';
    const URL_PRODUTOS       = '/sankhya/combustivel/api/produtos/';
    const URL_MOVIMENTACOES  = '/sankhya/combustivel/api/movimentacoes/';
    const URL_REQ_CRIAR      = '/sankhya/combustivel/api/requisicao/criar/';
    const URL_EXT_CRIAR      = '/sankhya/combustivel/api/abastecimento-externo/criar/';
    const URL_ENT_CRIAR      = '/sankhya/combustivel/api/entrada/criar/';
    const URL_CENCUS         = '/sankhya/cencus/search/';
    const URL_EMPRESAS       = '/sankhya/empresa/search/';
    const URL_PARCEIROS      = '/sankhya/parceiros/search/';
    const URL_NATUREZAS      = '/sankhya/natureza/search/';
    const URL_TIPVENDA       = '/sankhya/tipvenda/search/';

    // Defaults pré-preenchidos no modal de Nova Entrada/Requisição (Mai/2026):
    const DEFAULT_CODCENCUS  = 10100;     // COMERCIALIZAÇÃO
    const DEFAULT_CODNAT     = 30070200;  // COMBUSTÍVEL
    const DEFAULT_CODTIPVENDA = 11;       // Compra de combustível

    // =========================================================================
    // Helpers
    // =========================================================================

    function formatNumero(n, casas) {
        if (n === null || n === undefined || isNaN(n)) return '—';
        const c = casas !== undefined ? casas : 2;
        return Number(n).toLocaleString('pt-BR', { minimumFractionDigits: c, maximumFractionDigits: c });
    }

    function formatBRL(n) {
        if (n === null || n === undefined || isNaN(n) || n === 0) return '—';
        return Number(n).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function formatData(s) {
        if (!s) return '—';
        const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/);
        return m ? `${m[3]}/${m[2]}/${m[1]}` : s;
    }

    function hoje() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    }

    /**
     * Calcula consumo (km percorridos + km/L) entre abastecimentos
     * consecutivos do MESMO veículo. Funciona pra requisições internas e
     * externas (ambas têm hodometro_km na metadata da requisição).
     *
     * Estratégia: agrupa por codveiculo → ordena ASC por dtneg+nunota →
     * pra cada item idx>=1, km = hod[idx] - hod[idx-1] e consumo = km / qtd[idx-1]
     * (a qtd anterior foi consumida pra rodar até o atual). Retorna mapa
     * chave → {km_percorridos, kmlt} indexado por `${nunota}-${sequencia}`.
     */
    function _calcularConsumoMov(items) {
        const grupos = {};
        items.forEach(it => {
            const r = it.requisicao || {};
            const cv = r.codveiculo;
            const hod = parseFloat(r.hodometro_km);
            if (!cv || !hod || hod <= 0) return;
            if (!grupos[cv]) grupos[cv] = [];
            grupos[cv].push({
                chave: `${it.nunota}-${it.sequencia || 0}`,
                dtneg: it.dtneg || '',
                nunota: it.nunota,
                hod: hod,
                qtd: parseFloat(it.qtdneg_item) || 0,
            });
        });
        const out = {};
        Object.values(grupos).forEach(arr => {
            arr.sort((a, b) => {
                if (a.dtneg !== b.dtneg) return a.dtneg.localeCompare(b.dtneg);
                return a.nunota - b.nunota;
            });
            for (let i = 1; i < arr.length; i++) {
                const km = arr[i].hod - arr[i - 1].hod;
                const qtdAnt = arr[i - 1].qtd;
                if (km > 0) {
                    out[arr[i].chave] = {
                        km_percorridos: km,
                        kmlt: qtdAnt > 0 ? (km / qtdAnt) : null,
                    };
                }
            }
        });
        return out;
    }

    function classeTipo(tipo) {
        switch (tipo) {
            case 'INTERNA_FROTA':       return 'cb-badge cb-badge-frota';
            case 'INTERNA_MAQUINARIO':  return 'cb-badge cb-badge-maquina';
            case 'EXTERNA_FRETE':       return 'cb-badge cb-badge-frete';
            case 'EXTERNA_POSTO':       return 'cb-badge cb-badge-externo';
            default:                    return 'cb-badge';
        }
    }

    function rotuloTipo(tipo) {
        switch (tipo) {
            case 'INTERNA_FROTA':       return 'Frota';
            case 'INTERNA_MAQUINARIO':  return 'Máquina';
            case 'EXTERNA_FRETE':       return 'Freteiro';
            case 'EXTERNA_POSTO':       return '🌐 Externo';
            default:                    return '—';
        }
    }

    function classeStatus(st) {
        if (st === 'L') return 'cb-badge cb-status-conf';
        return 'cb-badge cb-status-aberto';
    }

    function rotuloStatus(st) {
        if (st === 'L') return 'Confirmada';
        if (st === 'E') return 'Excluída';
        return 'Aberta';
    }

    function classeMov(mov) {
        return mov === 'ENTRADA' ? 'cb-badge cb-status-conf' : 'cb-badge cb-status-aberto';
    }

    function rotuloMov(mov) {
        return mov === 'ENTRADA' ? '📥 Entrada' : '📋 Requisição';
    }

    // =========================================================================
    // Estoque
    // =========================================================================

    // Pinta as cores do nível e da classe do saldo conforme % cheio
    function _classesTanque(pct) {
        let fluido = 'cb-tanque-fluido--ok';
        let saldo = '';
        if (pct <= 0) {
            fluido = 'cb-tanque-fluido--zero';
            saldo = 'cb-tanque-saldo--crit';
        } else if (pct < 10) {
            fluido = 'cb-tanque-fluido--crit';
            saldo = 'cb-tanque-saldo--crit';
        } else if (pct < 30) {
            fluido = 'cb-tanque-fluido--aviso';
            saldo = 'cb-tanque-saldo--aviso';
        }
        return { fluido, saldo };
    }

    // Dispatcher: escolhe o renderizador conforme it.formato
    function renderTanqueSVG(it) {
        const formato = (it.formato || 'CILINDRO_HORIZONTAL').toUpperCase();
        if (formato === 'CAIXA_QUADRADA') return renderTanqueQuadradoSVG(it);
        return renderTanqueCilindricoSVG(it);
    }

    // Tanque cilíndrico horizontal (Diesel S10/S500). Largura proporcional à
    // capacidade via CSS var --cb-flex-grow. Altura fixa (preserveAspectRatio="none").
    function renderTanqueCilindricoSVG(it) {
        const pct = Math.max(0, Math.min(100, Number(it.percentual || 0)));
        const capacidade = Number(it.capacidade_lt || 0);
        const codvol = it.codvol || 'LT';
        const { fluido: cls, saldo: saldoCls } = _classesTanque(pct);

        // Coordenadas SVG do tanque cilíndrico horizontal.
        // viewBox: 0 0 300 120
        // - Corpo cilíndrico: rect de x=24 a x=276 (largura 252) com altura 80 (y=20 a 100)
        // - Elipses das extremidades dão o efeito 3D do cilindro
        const TANK_X = 24, TANK_Y = 20, TANK_W = 252, TANK_H = 80;
        const ELIPSE_RX = 10;  // raio horizontal das tampas (perspectiva)
        const fluidoH = (TANK_H * pct) / 100;
        const fluidoY = TANK_Y + (TANK_H - fluidoH);
        const clipId = `clip-tanque-${it.codprod}`;

        const saldoSvgCls = saldoCls.replace('cb-tanque-saldo--', 'cb-tanque-saldo-svg--');
        return `
            <div class="cb-tanque" style="--cb-flex-grow: ${capacidade || 1};"
                 title="Capacidade: ${formatNumero(capacidade, 0)} ${codvol}">
                <div class="cb-tanque-cabeca">
                    <p class="cb-tanque-nome">${it.descrprod || ('Produto ' + it.codprod)}</p>
                    <p class="cb-tanque-capacidade">capacidade ${formatNumero(capacidade, 0)} ${codvol}</p>
                </div>
                <div class="cb-tanque-svg">
                    <svg viewBox="0 0 300 120" preserveAspectRatio="none">
                        <defs>
                            <clipPath id="${clipId}">
                                <rect x="${TANK_X}" y="${TANK_Y}"
                                      width="${TANK_W}" height="${TANK_H}"/>
                            </clipPath>
                        </defs>

                        <!-- Corpo do cilindro -->
                        <rect x="${TANK_X}" y="${TANK_Y}"
                              width="${TANK_W}" height="${TANK_H}"
                              class="cb-tanque-corpo"/>

                        <!-- Fluido -->
                        <rect class="cb-tanque-fluido ${cls}"
                              x="${TANK_X}" y="${fluidoY}"
                              width="${TANK_W}" height="${fluidoH}"
                              clip-path="url(#${clipId})"/>

                        <!-- Tampas laterais (efeito 3D) -->
                        <ellipse cx="${TANK_X}" cy="${TANK_Y + TANK_H / 2}"
                                 rx="${ELIPSE_RX}" ry="${TANK_H / 2}"
                                 class="cb-tanque-elipse-frente"/>
                        <ellipse cx="${TANK_X + TANK_W}" cy="${TANK_Y + TANK_H / 2}"
                                 rx="${ELIPSE_RX}" ry="${TANK_H / 2}"
                                 class="cb-tanque-elipse-frente"/>

                        <!-- 2 anéis circunferenciais (efeito de cilindro segmentado/soldado) -->
                        <ellipse cx="${TANK_X + TANK_W / 3}" cy="${TANK_Y + TANK_H / 2}"
                                 rx="3" ry="${TANK_H / 2}" class="cb-tanque-anel"/>
                        <ellipse cx="${TANK_X + 2 * TANK_W / 3}" cy="${TANK_Y + TANK_H / 2}"
                                 rx="3" ry="${TANK_H / 2}" class="cb-tanque-anel"/>

                        <!-- Boca de inspeção / abastecimento no topo (centro) -->
                        <rect x="${TANK_X + TANK_W / 2 - 10}" y="${TANK_Y - 6}"
                              width="20" height="6" class="cb-tanque-valvula"/>
                        <rect x="${TANK_X + TANK_W / 2 - 4}" y="${TANK_Y - 12}"
                              width="8" height="6" class="cb-tanque-valvula"/>

                        <!-- Bujão de saída (cano lateral direito embaixo) -->
                        <rect x="${TANK_X + TANK_W}" y="${TANK_Y + TANK_H - 14}"
                              width="${ELIPSE_RX + 4}" height="5" class="cb-tanque-valvula"/>

                        <!-- Suportes em berço (trapézios apoiando o cilindro) -->
                        <path d="M ${TANK_X + 18} ${TANK_Y + TANK_H}
                                 L ${TANK_X + 8}  ${TANK_Y + TANK_H + 10}
                                 L ${TANK_X + 50} ${TANK_Y + TANK_H + 10}
                                 L ${TANK_X + 40} ${TANK_Y + TANK_H} Z"
                              class="cb-tanque-berco"/>
                        <path d="M ${TANK_X + TANK_W - 40} ${TANK_Y + TANK_H}
                                 L ${TANK_X + TANK_W - 50} ${TANK_Y + TANK_H + 10}
                                 L ${TANK_X + TANK_W - 8}  ${TANK_Y + TANK_H + 10}
                                 L ${TANK_X + TANK_W - 18} ${TANK_Y + TANK_H} Z"
                              class="cb-tanque-berco"/>

                        <!-- Linha do chão -->
                        <rect x="${TANK_X - 5}" y="${TANK_Y + TANK_H + 10}"
                              width="${TANK_W + 10}" height="2"
                              class="cb-tanque-base"/>
                    </svg>
                    <div class="cb-tanque-overlay">
                        <div class="cb-tanque-saldo-svg ${saldoSvgCls}">
                            ${formatNumero(it.qtd_disponivel, 0)} ${codvol}
                        </div>
                        <div class="cb-tanque-pct-svg">${pct.toFixed(0)}%</div>
                    </div>
                </div>
                <div class="cb-tanque-rodape">
                    <span class="cb-tanque-rodape-item cb-tanque-rodape-item--ent">
                        ↓ ent <strong>${formatNumero(it.qtd_entrada, 2)}</strong>
                    </span>
                    <span class="cb-tanque-rodape-item cb-tanque-rodape-item--sai">
                        ↑ sai <strong>${formatNumero(it.qtd_saida, 2)}</strong>
                    </span>
                </div>
            </div>
        `;
    }

    // Tanque quadrado tipo IBC/contêiner industrial (Arla 32). Proporção 1:1
    // visual (caixa) com estrutura interna (grade reforço + válvula inferior).
    function renderTanqueQuadradoSVG(it) {
        const pct = Math.max(0, Math.min(100, Number(it.percentual || 0)));
        const capacidade = Number(it.capacidade_lt || 0);
        const codvol = it.codvol || 'LT';
        const { fluido: cls, saldo: saldoCls } = _classesTanque(pct);

        // viewBox quadrado-ish (300x120 pra altura igual aos cilíndricos).
        // Caixa interna: x=80 a x=220 (largura 140), y=14 a y=114 (altura 100).
        const TANK_X = 80, TANK_Y = 14, TANK_W = 140, TANK_H = 100;
        const fluidoH = (TANK_H * pct) / 100;
        const fluidoY = TANK_Y + (TANK_H - fluidoH);
        const clipId = `clip-tanque-q-${it.codprod}`;

        // Grade de reforço (3 verticais + 3 horizontais)
        const grade = [];
        for (let i = 1; i <= 3; i++) {
            const x = TANK_X + (TANK_W * i / 4);
            grade.push(`<line x1="${x}" y1="${TANK_Y}" x2="${x}" y2="${TANK_Y + TANK_H}"
                          stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="2,2"/>`);
        }
        for (let i = 1; i <= 3; i++) {
            const y = TANK_Y + (TANK_H * i / 4);
            grade.push(`<line x1="${TANK_X}" y1="${y}" x2="${TANK_X + TANK_W}" y2="${y}"
                          stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="2,2"/>`);
        }

        const saldoSvgCls = saldoCls.replace('cb-tanque-saldo--', 'cb-tanque-saldo-svg--');
        return `
            <div class="cb-tanque" style="--cb-flex-grow: ${capacidade || 1};"
                 title="Capacidade: ${formatNumero(capacidade, 0)} ${codvol}">
                <div class="cb-tanque-cabeca">
                    <p class="cb-tanque-nome">${it.descrprod || ('Produto ' + it.codprod)}</p>
                    <p class="cb-tanque-capacidade">capacidade ${formatNumero(capacidade, 0)} ${codvol}</p>
                </div>
                <div class="cb-tanque-svg">
                    <svg viewBox="0 0 300 120" preserveAspectRatio="none">
                        <defs>
                            <clipPath id="${clipId}">
                                <rect x="${TANK_X}" y="${TANK_Y}"
                                      width="${TANK_W}" height="${TANK_H}" rx="3" ry="3"/>
                            </clipPath>
                        </defs>
                        <rect x="${TANK_X}" y="${TANK_Y}"
                              width="${TANK_W}" height="${TANK_H}"
                              rx="3" ry="3" class="cb-tanque-corpo"/>
                        <rect class="cb-tanque-fluido ${cls}"
                              x="${TANK_X}" y="${fluidoY}"
                              width="${TANK_W}" height="${fluidoH}"
                              clip-path="url(#${clipId})"/>
                        ${grade.join('')}
                        <rect x="${TANK_X + TANK_W / 2 - 12}" y="${TANK_Y - 8}"
                              width="24" height="8" class="cb-tanque-valvula"/>
                        <rect x="${TANK_X + TANK_W / 2 - 6}" y="${TANK_Y - 12}"
                              width="12" height="4" class="cb-tanque-valvula"/>
                        <rect x="${TANK_X + TANK_W - 6}" y="${TANK_Y + TANK_H - 14}"
                              width="12" height="6" class="cb-tanque-valvula"/>
                        <rect x="${TANK_X + TANK_W + 4}" y="${TANK_Y + TANK_H - 12}"
                              width="4" height="3" class="cb-tanque-valvula"/>
                        <rect x="${TANK_X - 6}" y="${TANK_Y + TANK_H}"
                              width="${TANK_W + 12}" height="6" class="cb-tanque-base"/>
                        <rect x="${TANK_X + 4}"             y="${TANK_Y + TANK_H + 6}" width="6" height="4" class="cb-tanque-base"/>
                        <rect x="${TANK_X + TANK_W / 2 - 3}" y="${TANK_Y + TANK_H + 6}" width="6" height="4" class="cb-tanque-base"/>
                        <rect x="${TANK_X + TANK_W - 10}"   y="${TANK_Y + TANK_H + 6}" width="6" height="4" class="cb-tanque-base"/>
                    </svg>
                    <div class="cb-tanque-overlay">
                        <div class="cb-tanque-saldo-svg ${saldoSvgCls}">
                            ${formatNumero(it.qtd_disponivel, 0)} ${codvol}
                        </div>
                        <div class="cb-tanque-pct-svg">${pct.toFixed(0)}%</div>
                    </div>
                </div>
                <div class="cb-tanque-rodape">
                    <span class="cb-tanque-rodape-item cb-tanque-rodape-item--ent">
                        ↓ ent <strong>${formatNumero(it.qtd_entrada, 2)}</strong>
                    </span>
                    <span class="cb-tanque-rodape-item cb-tanque-rodape-item--sai">
                        ↑ sai <strong>${formatNumero(it.qtd_saida, 2)}</strong>
                    </span>
                </div>
            </div>
        `;
    }

    async function carregarEstoque() {
        const wrap = document.getElementById('estoqueTanques');
        if (!wrap) return;
        wrap.innerHTML = '<div class="cb-empty" style="padding: 40px 14px;">Carregando…</div>';

        try {
            const resp = await fetch(URL_ESTOQUE, { credentials: 'same-origin' });
            const data = await resp.json();
            if (!data.ok) {
                wrap.innerHTML = `<div class="cb-empty" style="padding: 40px 14px;">${data.error || 'Falha ao carregar estoque.'}</div>`;
                return;
            }
            const items = data.items || [];
            if (items.length === 0) {
                wrap.innerHTML = '<div class="cb-empty" style="padding: 40px 14px;">Nenhum tanque mapeado. Verifique CAPACIDADE_TANQUE em oracle_conn.py.</div>';
                return;
            }
            wrap.innerHTML = items.map(renderTanqueSVG).join('');
        } catch (err) {
            wrap.innerHTML = '<div class="cb-empty" style="padding: 40px 14px;">Falha de conexão.</div>';
        }
    }

    // =========================================================================
    // Movimentações (entradas + requisições unificadas)
    // =========================================================================

    async function carregarMovimentacoes() {
        // Em modo detalhe de veículo, a tabela mostra abastecimentos daquele veículo;
        // re-uso o detalhe pra manter o filtro consistente com a área de veículos.
        if (veiculoDetalheCodvei) {
            return carregarDetalheVeiculo();
        }

        const tbody = document.getElementById('movimentacoesBody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="9" class="cb-empty">Carregando…</td></tr>';

        const params = new URLSearchParams();
        const mov    = document.getElementById('filtroMov').value;
        const status = document.getElementById('filtroStatus').value;
        const tipo   = document.getElementById('filtroTipo').value;
        if (mov)    params.set('mov', mov);
        if (status) params.set('status', status);
        if (tipo)   params.set('tipo', tipo);
        params.set('limit', '100');

        try {
            const resp = await fetch(`${URL_MOVIMENTACOES}?${params.toString()}`, { credentials: 'same-origin' });
            const data = await resp.json();
            if (!data.ok) {
                tbody.innerHTML = `<tr><td colspan="9" class="cb-empty">${data.error || 'Falha ao carregar.'}</td></tr>`;
                return;
            }
            const items = data.items || [];
            if (items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" class="cb-empty">Nenhuma movimentação encontrada com os filtros atuais.</td></tr>';
                return;
            }
            // Pré-cálculo de consumo: agrupa por veículo, ordena por data ASC,
            // calcula km percorridos e km/L entre abastecimentos consecutivos.
            // Indexa por chave única (nunota+sequencia) pra montar células na render.
            const consumoPorChave = _calcularConsumoMov(items);

            tbody.innerHTML = items.map(it => {
                const r = it.requisicao || {};
                const ehReq = it.tipo_movimento === 'REQUISICAO';
                const ehExterno = ehReq && r.tipo === 'EXTERNA_POSTO';
                const parceiroOuVei = ehReq
                    ? (r.placa || it.nomeparc || '—')
                    : (it.nomeparc || '—');
                const tooltipParcVei = ehReq
                    ? (r.marcamodelo ? `${r.placa} — ${r.marcamodelo}` : (it.nomeparc || ''))
                    : (it.nomeparc || '');

                // Badge MOV. — pra EXTERNA_POSTO, mostra só "🌐 EXTERNA" laranja
                // (em vez do par "📋 Requisição" + "🌐 Externo").
                let movLabel;
                if (ehExterno) {
                    movLabel = `<span class="cb-badge cb-badge-externo">🌐 EXTERNA</span>`;
                } else {
                    movLabel = `<span class="${classeMov(it.tipo_movimento)}">${rotuloMov(it.tipo_movimento)}</span>`;
                    if (ehReq && r.tipo) {
                        movLabel += ` <span class="${classeTipo(r.tipo)}" style="margin-left:4px;">${rotuloTipo(r.tipo)}</span>`;
                    }
                }

                // Botões de ação:
                // - REQUISICAO interna em aberto: editar + excluir
                // - EXTERNA_POSTO (qualquer STATUSNOTA, exceto E): editar + excluir
                //   (backend valida DHBAIXA do TGFFIN)
                // - ENTRADA (qualquer status != E): SÓ editar (excluir fica no modal)
                const podeReqInterna = ehReq && !ehExterno
                    && it.statusnota !== 'L' && it.statusnota !== 'E';
                const podeReqExterna = ehExterno && it.statusnota !== 'E';
                const podeReq = podeReqInterna || podeReqExterna;
                const podeEnt = !ehReq && it.statusnota !== 'E';
                const podeEditar = podeReq || podeEnt;
                const tipoAcao = ehReq ? 'req' : 'ent';
                const labelAcao = ehExterno ? 'externo' : (ehReq ? 'requisição' : 'entrada');
                const btnEditar = podeEditar ? `
                    <button class="cb-btn-acao cb-btn-acao--editar"
                            data-acao="editar" data-tipo="${tipoAcao}" data-nunota="${it.nunota}"
                            title="Editar ${labelAcao}">✏</button>` : '';
                // Lixeira em qualquer requisição (interna ou externa). Entrada exclui pelo modal.
                const btnExcluir = podeReq ? `
                    <button class="cb-btn-acao cb-btn-acao--excluir"
                            data-acao="excluir" data-tipo="${tipoAcao}" data-nunota="${it.nunota}"
                            data-resumo="${it.descrprod} · ${formatNumero(it.qtdneg_item, 2)} ${it.codvol || ''} · ${r.placa || ''}"
                            title="Excluir ${labelAcao}">🗑</button>` : '';
                const acoes = btnEditar + btnExcluir;

                // Total km + Média (só faz sentido em REQUISIÇÃO com veículo + hodômetro).
                // Externo também entra no cálculo (preenche o intervalo da viagem).
                const chave = `${it.nunota}-${it.sequencia || 0}`;
                const consumo = consumoPorChave[chave];
                const celKm = consumo
                    ? `<td class="cb-right">${formatNumero(consumo.km_percorridos, 0)} km</td>`
                    : '<td class="cb-right cb-muted">—</td>';
                const celMedia = consumo && consumo.kmlt
                    ? `<td class="cb-right cb-rel-consumo-destaque">${formatNumero(consumo.kmlt, 2)} km/L</td>`
                    : '<td class="cb-right cb-muted">—</td>';

                return `
                    <tr data-nunota="${it.nunota}" data-tipo="${it.tipo_movimento}">
                        <td>${movLabel}</td>
                        <td>${formatData(it.dtneg)}</td>
                        <td title="${tooltipParcVei}">${parceiroOuVei}</td>
                        <td title="${it.descrprod}">${it.descrprod || '—'}</td>
                        <td class="cb-right">${formatNumero(it.qtdneg_item, 2)} ${it.codvol || ''}</td>
                        <td class="cb-right">${formatBRL(it.vlrtot_item)}</td>
                        ${celKm}
                        ${celMedia}
                        <td class="cb-acoes-cell">${acoes}</td>
                    </tr>
                `;
            }).join('');

            // Delegação: liga editar/excluir nos botões da tabela
            // tipo='req' → requisição (handlers de Req)
            // tipo='ent' → entrada (handlers de Entrada)
            tbody.querySelectorAll('.cb-btn-acao').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const nunota = parseInt(btn.dataset.nunota, 10);
                    const tipo = btn.dataset.tipo || 'req';
                    const acao = btn.dataset.acao;
                    if (tipo === 'ent') {
                        if (acao === 'editar')  abrirModalEditarEntrada(nunota);
                        else if (acao === 'excluir') abrirModalExcluirEntrada(nunota, btn.dataset.resumo || '');
                    } else {
                        if (acao === 'editar')  abrirModalEditarReq(nunota);
                        else if (acao === 'excluir') abrirModalExcluirReq(nunota, btn.dataset.resumo || '');
                    }
                });
            });
        } catch (err) {
            tbody.innerHTML = '<tr><td colspan="9" class="cb-empty">Falha de conexão.</td></tr>';
        }
    }

    // =========================================================================
    // Modal Nova Requisição
    // =========================================================================

    let veiculoSelecionado = null;
    let produtoReqSelecionado = null;
    // Estado do modal: null = criação; int = NUNOTA em edição
    let requisicaoEditandoNunota = null;

    // Estado dos itens do EXTERNA_POSTO (Mai/2026 — 2026-05-13).
    // Estrutura idêntica ao entItens da Entrada — array de {_seq, codprod, descrprod, qtd, vlrunit}.
    let reqExtItens = [];
    let _reqExtSeq = 0;

    function _addItemReqExt(item) {
        _reqExtSeq += 1;
        reqExtItens.push({
            _seq: _reqExtSeq,
            codprod:   item ? item.codprod   : null,
            descrprod: item ? item.descrprod : '',
            qtd:       item ? item.qtd       : 0,
            vlrunit:   item ? item.vlrunit   : 0,
        });
        _renderReqExtItens();
    }

    function _removerItemReqExt(seq) {
        reqExtItens = reqExtItens.filter(it => it._seq !== seq);
        if (reqExtItens.length === 0) _addItemReqExt();
        _renderReqExtItens();
    }

    function _atualizarTotalReqExt() {
        let total = 0;
        reqExtItens.forEach(it => {
            const qt = parseFloat(it.qtd) || 0;
            const vu = parseFloat(it.vlrunit) || 0;
            total += qt * vu;
        });
        const lbl = document.getElementById('reqExtTotalCalculado');
        if (lbl) lbl.innerHTML = `Total da Nota: <strong>${formatBRL(total) || 'R$ 0,00'}</strong>`;
    }

    function _renderReqExtItens() {
        const tbody = document.getElementById('reqExtItensBody');
        if (!tbody) return;
        const sozinho = reqExtItens.length === 1;
        tbody.innerHTML = reqExtItens.map(it => {
            const idProdVis = `reqExtItemProd_${it._seq}`;
            const idProdCod = `reqExtItemProdCod_${it._seq}`;
            const idProdDD  = `reqExtItemProdDD_${it._seq}`;
            const idQtd     = `reqExtItemQtd_${it._seq}`;
            const idVlu     = `reqExtItemVlu_${it._seq}`;
            return `
            <tr data-seq="${it._seq}">
                <td style="position: relative;">
                    <input id="${idProdVis}" type="text" class="cb-input cb-input-reqext-prod"
                           data-seq="${it._seq}" autocomplete="off"
                           value="${it.codprod ? (it.codprod + ' — ' + (it.descrprod || '')) : ''}"
                           placeholder="Buscar combustível…" />
                    <input id="${idProdCod}" type="hidden" value="${it.codprod || ''}" />
                    <div id="${idProdDD}" class="cb-dropdown dropdown-abs"></div>
                </td>
                <td>
                    <input id="${idQtd}" type="number" class="cb-input cb-input-right cb-input-reqext-qtd"
                           data-seq="${it._seq}" step="0.01" min="0"
                           value="${it.qtd || ''}" placeholder="0,00" />
                </td>
                <td>
                    <input id="${idVlu}" type="number" class="cb-input cb-input-right cb-input-reqext-vlu"
                           data-seq="${it._seq}" step="0.0001" min="0"
                           value="${it.vlrunit || ''}" placeholder="0,0000" />
                </td>
                <td class="cb-item-total" data-seq="${it._seq}">
                    ${formatBRL((parseFloat(it.qtd) || 0) * (parseFloat(it.vlrunit) || 0)) || 'R$ 0,00'}
                </td>
                <td>
                    <button type="button" class="cb-item-remove" data-seq="${it._seq}"
                            ${sozinho ? 'disabled title="Pelo menos 1 item"' : 'title="Remover"'}>×</button>
                </td>
            </tr>`;
        }).join('');

        // Eventos qtd/vlrunit
        tbody.querySelectorAll('.cb-input-reqext-qtd, .cb-input-reqext-vlu').forEach(inp => {
            inp.addEventListener('input', (e) => {
                const seq = parseInt(e.target.dataset.seq, 10);
                const item = reqExtItens.find(it => it._seq === seq);
                if (!item) return;
                if (e.target.classList.contains('cb-input-reqext-qtd')) {
                    item.qtd = parseFloat(e.target.value) || 0;
                } else {
                    item.vlrunit = parseFloat(e.target.value) || 0;
                }
                const cell = tbody.querySelector(`.cb-item-total[data-seq="${seq}"]`);
                if (cell) {
                    cell.textContent = formatBRL(item.qtd * item.vlrunit) || 'R$ 0,00';
                }
                _atualizarTotalReqExt();
            });
        });
        tbody.querySelectorAll('.cb-item-remove').forEach(btn => {
            btn.addEventListener('click', () => {
                _removerItemReqExt(parseInt(btn.dataset.seq, 10));
            });
        });

        // Typeahead de produto por linha — IDs únicos (string)
        reqExtItens.forEach(it => {
            if (!window.IAgro || !IAgro.attachTypeahead) return;
            const seq = it._seq;
            IAgro.attachTypeahead({
                inputId:    `reqExtItemProd_${seq}`,
                hiddenId:   `reqExtItemProdCod_${seq}`,
                dropdownId: `reqExtItemProdDD_${seq}`,
                url: URL_PRODUTOS, limit: 30, debounceMs: 250, minChars: 0,
                positionFixed: true,
                pickItems: (data) => data.results || [],
                pickCod: (item) => item.codprod, pickDescr: (item) => item.descrprod,
                renderItem: (item) => `${item.codprod} — ${item.descrprod} <span style="color:#94a3b8;font-size:10px;">(${item.codvol})</span>`,
                onSelect: (cod, descr) => {
                    const i = reqExtItens.find(x => x._seq === seq);
                    if (i) {
                        i.codprod = parseInt(cod, 10);
                        i.descrprod = descr;
                    }
                },
                onClear: () => {
                    const i = reqExtItens.find(x => x._seq === seq);
                    if (i) { i.codprod = null; i.descrprod = ''; }
                },
            });
        });

        _atualizarTotalReqExt();
    }

    function _limparModalReq() {
        document.querySelector('input[name="cbTipo"][value="INTERNA_FROTA"]').checked = true;
        ['reqVeiculoVis','reqVeiculoCod','reqProdutoVis','reqProdutoCod','reqQtd',
         'reqVlrUnit','reqHodometroKm','reqHorimetroH','reqCencusVis','reqCencusCod','reqDocFrete','reqObs',
         'reqPostoVis','reqPostoCod','reqExternoDoc','reqExternoDtNeg','reqExternoDtVenc',
         'reqNaturezaVis','reqNaturezaCod','reqTipVendaVis','reqTipVendaCod']
            .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
        // Zera estado dos itens externos (multi-itens)
        reqExtItens = [];
        const bodyExt = document.getElementById('reqExtItensBody');
        if (bodyExt) bodyExt.innerHTML = '';
        const lblExtTot = document.getElementById('reqExtTotalCalculado');
        if (lblExtTot) lblExtTot.innerHTML = 'Total da Nota: <strong>R$ 0,00</strong>';

        // Defaults pré-selecionados (Mai/2026)
        document.getElementById('reqCencusCod').value  = DEFAULT_CODCENCUS;
        document.getElementById('reqCencusVis').value  = `${DEFAULT_CODCENCUS} — COMERCIALIZAÇÃO`;
        document.getElementById('reqNaturezaCod').value = DEFAULT_CODNAT;
        document.getElementById('reqNaturezaVis').value = `${DEFAULT_CODNAT} — COMBUSTÍVEL`;
        document.getElementById('reqTipVendaCod').value = DEFAULT_CODTIPVENDA;
        document.getElementById('reqTipVendaVis').value = `${DEFAULT_CODTIPVENDA} — A VISTA`;
        document.getElementById('reqVeiculoHint').textContent = '';
        document.getElementById('reqMensagem').textContent = '';
        document.getElementById('reqMensagem').className = 'cb-mensagem';
        veiculoSelecionado = null;
        produtoReqSelecionado = null;
    }

    function _atualizarHeaderModalReq() {
        const header = document.querySelector('#modalNovaReq .cb-modal-header strong');
        const btn = document.getElementById('btnConfirmarReq');
        if (requisicaoEditandoNunota) {
            if (header) header.textContent = `✏ Editar requisição NUNOTA ${requisicaoEditandoNunota}`;
            if (btn) btn.textContent = 'Salvar alterações';
        } else {
            if (header) header.textContent = 'Nova requisição de combustível';
            if (btn) btn.textContent = 'Salvar requisição';
        }
    }

    function abrirModalNovaReq() {
        const modal = document.getElementById('modalNovaReq');
        modal.classList.remove('hidden');
        requisicaoEditandoNunota = null;
        _limparModalReq();
        _atualizarHeaderModalReq();
        atualizarDocFreteVisivel();
        atualizarMedidorPorTipo();
        atualizarExternoVisivel();
        setTimeout(() => document.getElementById('reqVeiculoVis').focus(), 50);
    }

    async function abrirModalEditarReq(nunota) {
        const modal = document.getElementById('modalNovaReq');
        _limparModalReq();
        requisicaoEditandoNunota = nunota;
        _atualizarHeaderModalReq();
        modal.classList.remove('hidden');

        try {
            const resp = await fetch(`/sankhya/combustivel/api/requisicao/${nunota}/`,
                                     { credentials: 'same-origin' });
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                IAgro.showToast(data.error || 'Falha ao carregar requisição.', 'error');
                fecharModalNovaReq();
                return;
            }
            const cab = data.cabecalho || {};
            const req = data.requisicao || {};
            const itens = data.itens || [];
            const item = itens[0] || {};

            // Tipo
            const tipo = req.TIPO || 'INTERNA_FROTA';
            const radio = document.querySelector(`input[name="cbTipo"][value="${tipo}"]`);
            if (radio) radio.checked = true;
            atualizarDocFreteVisivel();
            atualizarMedidorPorTipo();
            atualizarExternoVisivel();

            // Posto + datas + doc (só relevantes em EXTERNA_POSTO)
            if (tipo === 'EXTERNA_POSTO') {
                if (req.CODPARC) {
                    document.getElementById('reqPostoCod').value = req.CODPARC;
                    document.getElementById('reqPostoVis').value =
                        `${req.CODPARC} — ${cab.NOMEPARC || ''}`;
                }
                if (req.DOC_FRETE_REF) {
                    document.getElementById('reqExternoDoc').value = req.DOC_FRETE_REF;
                }
                if (cab.DTNEG) {
                    const d = new Date(cab.DTNEG);
                    document.getElementById('reqExternoDtNeg').value = d.toISOString().slice(0, 10);
                }
                // DTVENC do TGFFIN: vamos buscar quando fechar o gap em B11; por ora,
                // deixa o operador re-informar se quiser mudar (default = data do abast.)
            }

            // Veículo
            if (req.CODVEICULO) {
                document.getElementById('reqVeiculoCod').value = req.CODVEICULO;
                const placa = req.PLACA || '';
                const modelo = req.MARCAMODELO || req.ESPECIETIPO || '';
                document.getElementById('reqVeiculoVis').value =
                    `${req.CODVEICULO} — ${placa}${modelo ? ' — ' + modelo : ''}`;
            }

            // Itens — popula conforme tipo (single vs multi)
            if (tipo === 'EXTERNA_POSTO') {
                // Multi-itens — popula tabela com todos os itens da nota.
                // Reseta o array completamente (atualizarExternoVisivel pode
                // ter adicionado 1 item vazio antes) e re-renderiza no final
                // como garantia visual.
                reqExtItens = [];
                _reqExtSeq = 0;
                itens.forEach(it => {
                    _reqExtSeq += 1;
                    reqExtItens.push({
                        _seq: _reqExtSeq,
                        codprod:   it.CODPROD,
                        descrprod: it.DESCRPROD,
                        qtd:       it.QTDNEG,
                        vlrunit:   it.VLRUNIT,
                    });
                });
                if (reqExtItens.length === 0) {
                    _reqExtSeq += 1;
                    reqExtItens.push({_seq: _reqExtSeq, codprod: null, descrprod: '', qtd: 0, vlrunit: 0});
                }
                // Render explícito final — garante DOM atualizado mesmo se
                // houve repaints intermediários durante o fluxo async.
                _renderReqExtItens();
            } else {
                // Single (interno) — popula form avulso
                if (item.CODPROD) {
                    document.getElementById('reqProdutoCod').value = item.CODPROD;
                    document.getElementById('reqProdutoVis').value =
                        `${item.CODPROD} — ${item.DESCRPROD || ''}`;
                }
                if (item.QTDNEG != null)  document.getElementById('reqQtd').value     = item.QTDNEG;
                if (item.VLRUNIT)         document.getElementById('reqVlrUnit').value = item.VLRUNIT;
            }

            // Medidores
            if (req.HODOMETRO_KM != null) document.getElementById('reqHodometroKm').value = req.HODOMETRO_KM;
            if (req.HORIMETRO_H  != null) document.getElementById('reqHorimetroH').value  = req.HORIMETRO_H;

            // Centro de Resultado
            if (cab.CODCENCUS) {
                document.getElementById('reqCencusCod').value = cab.CODCENCUS;
                document.getElementById('reqCencusVis').value = String(cab.CODCENCUS);
            }

            // Natureza (preenche se diferente do default)
            if (cab.CODNAT) {
                document.getElementById('reqNaturezaCod').value = cab.CODNAT;
                document.getElementById('reqNaturezaVis').value = String(cab.CODNAT);
            }

            // Doc frete + observação
            if (req.DOC_FRETE_REF) document.getElementById('reqDocFrete').value = req.DOC_FRETE_REF;
            if (cab.OBSERVACAO)    document.getElementById('reqObs').value      = cab.OBSERVACAO;
        } catch (err) {
            IAgro.showToast('Falha de conexão ao carregar requisição.', 'error');
            fecharModalNovaReq();
        }
    }

    function fecharModalNovaReq() {
        document.getElementById('modalNovaReq').classList.add('hidden');
    }

    function tipoSelecionado() {
        const r = document.querySelector('input[name="cbTipo"]:checked');
        return r ? r.value : 'INTERNA_FROTA';
    }

    function atualizarDocFreteVisivel() {
        const wrap = document.getElementById('reqDocFreteWrap');
        if (tipoSelecionado() === 'EXTERNA_FRETE') wrap.classList.remove('hidden');
        else wrap.classList.add('hidden');
    }

    function atualizarMedidorPorTipo() {
        const tipo = tipoSelecionado();
        const wrap = document.getElementById('reqMedidoresWrap');
        const asterHodo = wrap.querySelectorAll('.reqHodometroObrig');
        const asterHori = wrap.querySelectorAll('.reqHorimetroObrig');

        if (tipo === 'EXTERNA_FRETE') {
            wrap.classList.add('hidden');
            document.getElementById('reqHodometroKm').value = '';
            document.getElementById('reqHorimetroH').value = '';
            return;
        }
        wrap.classList.remove('hidden');
        // Hodômetro: obrigatório em INTERNA_FROTA e EXTERNA_POSTO; opcional em MAQUINARIO.
        // Horímetro: obrigatório SÓ em INTERNA_FROTA. EXTERNA_POSTO e MAQUINARIO = opcional.
        const hodoObrig = (tipo === 'INTERNA_FROTA' || tipo === 'EXTERNA_POSTO');
        const horiObrig = (tipo === 'INTERNA_FROTA');
        asterHodo.forEach(el => { el.style.display = hodoObrig ? '' : 'none'; });
        asterHori.forEach(el => { el.style.display = horiObrig ? '' : 'none'; });
    }

    function atualizarExternoVisivel() {
        const ehExterno = tipoSelecionado() === 'EXTERNA_POSTO';
        document.getElementById('reqPostoWrap').classList.toggle('hidden', !ehExterno);
        document.getElementById('reqExternoDocWrap').classList.toggle('hidden', !ehExterno);
        document.getElementById('reqExternoDatasWrap').classList.toggle('hidden', !ehExterno);
        document.getElementById('reqExternoAviso').classList.toggle('hidden', !ehExterno);

        // Multi-itens (Mai/2026 — 2026-05-13): externo usa tabela; internos
        // mantêm form single (Combustível + Qtd + Valor Unit. avulsos).
        const wrapItens = document.getElementById('reqItensExternoWrap');
        const wrapSingle = document.getElementById('reqProdutoSingleWrap');
        if (wrapSingle) wrapSingle.classList.toggle('hidden', ehExterno);
        if (wrapItens) wrapItens.classList.toggle('hidden', !ehExterno);
        document.getElementById('reqExtTotalWrap').classList.toggle('hidden', !ehExterno);

        // Quando entra em externo, garante 1 linha vazia na tabela e re-renderiza
        // forçado (cobre cenário de modal reaberto / troca de tipo com lista vazia).
        if (ehExterno && wrapItens) {
            if (reqExtItens.length === 0) {
                _addItemReqExt();
            } else {
                _renderReqExtItens();
            }
        }

        // Mai/2026: campo Valor Unit. (single, interno) é READONLY — puxa do
        // último abastecimento de estoque.
        const vlrUnitInp = document.getElementById('reqVlrUnit');
        if (vlrUnitInp) {
            vlrUnitInp.readOnly = true;
            vlrUnitInp.title = 'Preço travado — puxado do último abastecimento de estoque';
            vlrUnitInp.style.background = '#f1f5f9';
        }

        // Quando entra em externo, default datas = hoje (à vista)
        if (ehExterno) {
            const h = hoje();
            const dtNeg = document.getElementById('reqExternoDtNeg');
            const dtVenc = document.getElementById('reqExternoDtVenc');
            if (!dtNeg.value)  dtNeg.value  = h;
            if (!dtVenc.value) dtVenc.value = h;
        } else {
            document.getElementById('reqPostoVis').value = '';
            document.getElementById('reqPostoCod').value = '';
            document.getElementById('reqExternoDoc').value = '';
        }
    }

    function montarTypeaheadVeiculo() {
        if (!window.IAgro || !IAgro.attachTypeahead) return;
        IAgro.attachTypeahead({
            inputId:    'reqVeiculoVis',
            hiddenId:   'reqVeiculoCod',
            dropdownId: 'reqVeiculoDD',
            url:        URL_VEICULOS,
            limit:      30, debounceMs: 250, minChars: 0,
            extraQuery: () => `tipo=${tipoSelecionado()}`,
            pickItems:  (data) => data.results || [],
            pickCod:    (it) => it.codveiculo,
            pickDescr:  (it) => `${it.placa} — ${it.marcamodelo || it.especietipo || ''}`.trim(),
            pickExtra:  (it) => ({
                codparc:   it.codparc || '',
                nomeparc:  it.nomeparc || '',
                codcencus: it.codcencus || '',
                proprio:   it.proprio || '',
            }),
            renderItem: (it) => `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span><strong>${it.placa}</strong> — ${it.marcamodelo || it.especietipo || ''}</span>
                    <span style="font-size:10px; color:#94a3b8;">${it.proprio === 'S' ? 'Próprio' : 'Terceiro'}</span>
                </div>
            `,
            onSelect: (cod, descr, item) => {
                veiculoSelecionado = {
                    codveiculo: cod,
                    placa: item.dataset.descr || '',
                    nomeparc: item.dataset.nomeparc || '',
                    codcencus: item.dataset.codcencus || '',
                };
                if (veiculoSelecionado.codcencus) {
                    document.getElementById('reqCencusCod').value = veiculoSelecionado.codcencus;
                    document.getElementById('reqCencusVis').value = `${veiculoSelecionado.codcencus} (do veículo)`;
                }
                const hint = document.getElementById('reqVeiculoHint');
                hint.textContent = veiculoSelecionado.nomeparc ? `Parceiro: ${veiculoSelecionado.nomeparc}` : '';
            },
            onClear: () => {
                veiculoSelecionado = null;
                document.getElementById('reqVeiculoHint').textContent = '';
            },
        });
    }

    function montarTypeaheadProdutoReq() {
        if (!window.IAgro || !IAgro.attachTypeahead) return;
        IAgro.attachTypeahead({
            inputId: 'reqProdutoVis', hiddenId: 'reqProdutoCod', dropdownId: 'reqProdutoDD',
            url: URL_PRODUTOS, limit: 30, debounceMs: 250, minChars: 0,
            pickItems: (data) => data.results || [],
            pickCod: (it) => it.codprod, pickDescr: (it) => it.descrprod,
            renderItem: (it) => `${it.codprod} — ${it.descrprod} <span style="color:#94a3b8;font-size:10px;">(${it.codvol})</span>`,
            onSelect: (cod, descr) => {
                produtoReqSelecionado = { codprod: cod, descrprod: descr };
                // Mai/2026: puxa preço do último abastecimento (TOP 10) — só
                // em tipos internos, já que EXTERNA_POSTO tem preço do posto.
                _carregarUltimoPrecoReq(cod);
            },
            onClear: () => { produtoReqSelecionado = null; },
        });
    }

    async function _carregarUltimoPrecoReq(codprod) {
        // Só aplica em tipos internos (EXTERNA_POSTO tem preço informado pelo operador)
        if (tipoSelecionado() === 'EXTERNA_POSTO') return;
        if (!codprod) return;
        try {
            const r = await fetch(
                `/sankhya/combustivel/api/ultimo-preco/?codprod=${encodeURIComponent(codprod)}`,
                { credentials: 'same-origin' },
            );
            if (!r.ok) return;
            const j = await r.json();
            if (!j.ok) return;
            const vlu = parseFloat(j.vlrunit || 0);
            if (vlu > 0) {
                document.getElementById('reqVlrUnit').value = vlu.toFixed(4);
            }
        } catch (_) { /* ignora */ }
    }

    function montarTypeaheadCencusReq() {
        if (!window.IAgro || !IAgro.attachTypeahead) return;
        IAgro.attachTypeahead({
            inputId: 'reqCencusVis', hiddenId: 'reqCencusCod', dropdownId: 'reqCencusDD',
            url: URL_CENCUS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (data) => data.results || data.items || [],
            pickCod: (it) => it.cod || it.codcencus,
            pickDescr: (it) => it.descr || it.descrcencus || '',
        });
    }

    function montarTypeaheadNaturezaReq() {
        if (!window.IAgro || !IAgro.attachTypeahead) return;
        IAgro.attachTypeahead({
            inputId: 'reqNaturezaVis', hiddenId: 'reqNaturezaCod', dropdownId: 'reqNaturezaDD',
            url: URL_NATUREZAS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (data) => data.results || data.items || [],
            pickCod: (it) => it.cod || it.codnat,
            pickDescr: (it) => it.descr || it.descrnat || '',
        });
    }

    function montarTypeaheadTipVendaReq() {
        if (!window.IAgro || !IAgro.attachTypeahead) return;
        IAgro.attachTypeahead({
            inputId: 'reqTipVendaVis', hiddenId: 'reqTipVendaCod', dropdownId: 'reqTipVendaDD',
            url: URL_TIPVENDA, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (data) => data.results || data.items || [],
            pickCod: (it) => it.cod || it.codtipvenda,
            pickDescr: (it) => it.descr || it.descrtipvenda || '',
        });
    }

    function montarTypeaheadPostoReq() {
        if (!window.IAgro || !IAgro.attachTypeahead) return;
        IAgro.attachTypeahead({
            inputId: 'reqPostoVis', hiddenId: 'reqPostoCod', dropdownId: 'reqPostoDD',
            url: URL_PARCEIROS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (data) => data.results || data.items || [],
            pickCod: (it) => it.cod || it.codparc,
            pickDescr: (it) => it.descr || it.nomeparc || '',
        });
    }

    function validarReq() {
        const erros = [];
        const tipo = tipoSelecionado();
        const ehExterno = (tipo === 'EXTERNA_POSTO');

        if (!document.getElementById('reqVeiculoCod').value) erros.push('Selecione um veículo.');
        if (!document.getElementById('reqCencusCod').value) erros.push('Centro de resultado obrigatório.');

        if (ehExterno) {
            // Posto + hodômetro + datas
            if (!document.getElementById('reqPostoCod').value) erros.push('Selecione o posto/fornecedor.');
            const hod = parseFloat(document.getElementById('reqHodometroKm').value || '0');
            if (!hod || hod <= 0) erros.push('Hodômetro obrigatório no abastecimento externo (sem ele o consumo do veículo perde continuidade).');
            const dtn = document.getElementById('reqExternoDtNeg').value;
            const dtv = document.getElementById('reqExternoDtVenc').value;
            if (dtn && dtv && dtv < dtn) erros.push('Vencimento não pode ser anterior à data do abastecimento.');
            // Pelo menos 1 item completo na tabela
            const itensValidos = reqExtItens.filter(it =>
                it.codprod && (parseFloat(it.qtd) || 0) > 0 && (parseFloat(it.vlrunit) || 0) > 0);
            if (itensValidos.length === 0) {
                erros.push('Adicione ao menos 1 item com combustível, qtd e valor.');
            }
        } else {
            // Single-item (interno ou EXTERNA_FRETE)
            if (!document.getElementById('reqProdutoCod').value) erros.push('Selecione um combustível.');
            const qtd = parseFloat(document.getElementById('reqQtd').value || '0');
            if (!qtd || qtd <= 0) erros.push('Informe a quantidade.');
            if (tipo === 'EXTERNA_FRETE' && !document.getElementById('reqDocFrete').value.trim()) {
                erros.push('Documento do frete obrigatório.');
            }
            // Frota própria: hodômetro (km) E horímetro (h) AMBOS obrigatórios
            if (tipo === 'INTERNA_FROTA') {
                const hod = parseFloat(document.getElementById('reqHodometroKm').value || '0');
                const hor = parseFloat(document.getElementById('reqHorimetroH').value || '0');
                if (!hod || hod <= 0) erros.push('Hodômetro do veículo (km) obrigatório.');
                if (!hor || hor <= 0) erros.push('Horímetro da bomba (h) obrigatório.');
            }
        }
        return erros;
    }

    async function enviarRequisicao() {
        const msg = document.getElementById('reqMensagem');
        msg.textContent = ''; msg.className = 'cb-mensagem';
        const erros = validarReq();
        if (erros.length) { msg.textContent = erros.join(' '); return; }

        const tipo = tipoSelecionado();
        const ehExterno = (tipo === 'EXTERNA_POSTO');

        // Payload base — compartilhado entre interno e externo
        const payload = {
            codveiculo: parseInt(document.getElementById('reqVeiculoCod').value, 10),
            tipo: tipo,
            hodometro_km: parseFloat(document.getElementById('reqHodometroKm').value || '0') || null,
            horimetro_h:  parseFloat(document.getElementById('reqHorimetroH').value || '0') || null,
            codcencus: parseInt(document.getElementById('reqCencusCod').value, 10),
            codnat: parseInt(document.getElementById('reqNaturezaCod').value || '0', 10) || null,
            codtipvenda: parseInt(document.getElementById('reqTipVendaCod').value || '0', 10) || null,
            observacao: document.getElementById('reqObs').value.trim() || null,
        };
        if (ehExterno) {
            // Multi-itens — envia lista. Backend B8/B11 aceita itens=[...]
            payload.codparc = parseInt(document.getElementById('reqPostoCod').value, 10);
            payload.doc_frete_ref = document.getElementById('reqExternoDoc').value.trim() || null;
            payload.dtneg  = document.getElementById('reqExternoDtNeg').value || null;
            payload.dtvenc = document.getElementById('reqExternoDtVenc').value || null;
            payload.itens = reqExtItens
                .filter(it => it.codprod && (parseFloat(it.qtd) || 0) > 0 && (parseFloat(it.vlrunit) || 0) > 0)
                .map(it => ({
                    codprod: parseInt(it.codprod, 10),
                    qtd:     parseFloat(it.qtd),
                    vlrunit: parseFloat(it.vlrunit),
                }));
        } else {
            // Single-item — compat retro com fluxo interno atual
            payload.codprod = parseInt(document.getElementById('reqProdutoCod').value, 10);
            payload.qtd     = parseFloat(document.getElementById('reqQtd').value);
            payload.vlrunit = parseFloat(document.getElementById('reqVlrUnit').value || '0') || null;
            payload.doc_frete_ref = document.getElementById('reqDocFrete').value.trim() || null;
        }

        const btn = document.getElementById('btnConfirmarReq');
        btn.disabled = true; const txt0 = btn.textContent; btn.textContent = 'Enviando…';
        try {
            // Roteamento de endpoint:
            //  - edição: SEMPRE /requisicao/<n>/editar/ (a função service trata
            //    interno e externo, inclusive TGFFIN do externo)
            //  - criação interno: /requisicao/criar/
            //  - criação externo: /abastecimento-externo/criar/
            let url;
            if (requisicaoEditandoNunota) {
                url = `/sankhya/combustivel/api/requisicao/${requisicaoEditandoNunota}/editar/`;
            } else if (ehExterno) {
                url = URL_EXT_CRIAR;
            } else {
                url = URL_REQ_CRIAR;
            }
            const resp = await IAgro.postJSON(url, payload);
            const data = resp.body || {};
            if (!resp.ok || !data.ok) {
                msg.textContent = data.error || `Erro ${resp.status || 'desconhecido'}`;
                return;
            }
            const acao = requisicaoEditandoNunota ? 'atualizada' : 'criada';
            const extras = (ehExterno && data.nufin) ? ` · NUFIN ${data.nufin}` : '';
            IAgro.showToast(`Requisição NUNOTA ${data.nunota} ${acao}${extras}.`, 'success');
            fecharModalNovaReq();
            carregarMovimentacoes();
            carregarEstoque();
        } catch (err) {
            msg.textContent = 'Falha de conexão.';
        } finally {
            btn.disabled = false; btn.textContent = txt0;
        }
    }

    // =========================================================================
    // Veículos (área abaixo dos tanques)
    // Modo LISTA: toggle COM/MAQ + grid 2 colunas de cards com foto
    // Modo DETALHE: foto grande + relatório inline + filtra movimentações
    // =========================================================================

    const URL_RELATORIO = '/sankhya/combustivel/api/relatorio/consumo/';
    const STATIC_VEICULOS = '/static/sankhya_integration/img/veiculos/';
    const PREFS_KEY = 'iagro:combustivel:prefs:v1';

    // Estado
    let veiculosCarregados = [];      // todos os veículos próprios
    let veiculosFiltro = 'COM';        // COM | MAQ
    let veiculoDetalheCodvei = null;   // null = modo lista; int = modo detalhe
    let veiculoDetalhePeriodo = 30;    // dias

    // Heurística COM vs MAQ via ESPECIETIPO (Mai/2026 — TGFVEI.TIPOMEDICAO está NULL)
    const PALAVRAS_MAQ = ['TRATOR', 'COLHEIT', 'MAQUINA', 'PULVERIZ', 'ROCADEIR', 'ROÇADEIR', 'PLANTADEIR'];

    function classificarVeiculo(v) {
        const esp = String(v.especietipo || '').toUpperCase();
        for (const palavra of PALAVRAS_MAQ) {
            if (esp.indexOf(palavra) >= 0) return 'MAQ';
        }
        return 'COM';
    }

    function pathFotoVeiculo(placa, tamanho) {
        // Mai/2026: backend resolve a extensão (.jpg/.jpeg/.png/.webp) e cai
        // no _placeholder.svg se não achar nada.
        // tamanho = 'thumb' → backend redimensiona via Pillow + cacheia (lista 60×44 @ 2x)
        // tamanho = 'full' ou omitido → original em resolução máxima (detalhe/lightbox)
        if (!placa) return STATIC_VEICULOS + '_placeholder.svg';
        const p = String(placa).trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
        const qs = tamanho === 'thumb' ? '?size=thumb' : '';
        return `/sankhya/combustivel/api/veiculo-foto/${encodeURIComponent(p)}/${qs}`;
    }

    function _carregarPrefs() {
        try {
            const raw = localStorage.getItem(PREFS_KEY);
            if (raw) {
                const o = JSON.parse(raw);
                if (o && (o.veiculosFiltro === 'COM' || o.veiculosFiltro === 'MAQ')) {
                    veiculosFiltro = o.veiculosFiltro;
                }
            }
        } catch (e) { /* ignora */ }
    }

    function _salvarPrefs() {
        try {
            localStorage.setItem(PREFS_KEY, JSON.stringify({ veiculosFiltro }));
        } catch (e) { /* ignora */ }
    }

    async function carregarVeiculos() {
        const grid = document.getElementById('veiculosGrid');
        if (!grid) return;
        grid.innerHTML = '<div class="cb-empty" style="padding: 24px 14px;">Carregando…</div>';
        try {
            // Buscar todos os ativos (próprios + terceiros) — limite alto pra cobrir o cadastro
            const params = new URLSearchParams({ limit: '500' });
            const resp = await fetch(`${URL_VEICULOS}?${params.toString()}`,
                                     { credentials: 'same-origin' });
            const data = await resp.json();
            if (!data.ok) {
                grid.innerHTML = `<div class="cb-empty" style="padding: 24px 14px;">${data.error || 'Falha ao carregar veículos.'}</div>`;
                return;
            }
            veiculosCarregados = (data.results || []).map(v => ({
                ...v,
                _categoria: classificarVeiculo(v),
            }));
            renderVeiculosLista();
        } catch (err) {
            grid.innerHTML = '<div class="cb-empty" style="padding: 24px 14px;">Falha de conexão.</div>';
        }
    }

    function renderVeiculosLista() {
        const grid = document.getElementById('veiculosGrid');
        if (!grid) return;
        const lista = veiculosCarregados.filter(v => v._categoria === veiculosFiltro);
        if (lista.length === 0) {
            const rotulo = veiculosFiltro === 'MAQ' ? 'maquinário' : 'frota';
            grid.innerHTML = `<div class="cb-empty" style="padding: 24px 14px; grid-column: 1 / -1;">
                Nenhum veículo de ${rotulo} cadastrado.
            </div>`;
            return;
        }
        // Ordena por placa (alfabética)
        lista.sort((a, b) => String(a.placa || '').localeCompare(String(b.placa || '')));
        grid.innerHTML = lista.map(v => {
            // Lista usa thumb (240x180 cacheado via Pillow) — nítido em DPR 2.
            const fotoUrl = pathFotoVeiculo(v.placa, 'thumb');
            const placeholder = STATIC_VEICULOS + '_placeholder.svg';
            const propLabel = v.proprio === 'S' ? '' : ' (terceiro)';
            return `
                <div class="cb-veiculo-card" data-codveiculo="${v.codveiculo}" title="${v.placa || ''} — ${v.marcamodelo || v.especietipo || ''}">
                    <div class="cb-veiculo-foto"
                         style="background-image: url('${fotoUrl}'), url('${placeholder}');"></div>
                    <div class="cb-veiculo-info">
                        <div class="cb-veiculo-placa">${v.placa || '—'}</div>
                        <div class="cb-veiculo-modelo">${v.marcamodelo || v.especietipo || ''}</div>
                        <div class="cb-veiculo-tipo">${v.especietipo || ''}${propLabel}</div>
                    </div>
                </div>
            `;
        }).join('');
        // Delegação: click no card seleciona o veículo
        grid.querySelectorAll('.cb-veiculo-card').forEach(card => {
            card.addEventListener('click', () => {
                const cod = parseInt(card.dataset.codveiculo, 10);
                selecionarVeiculo(cod);
            });
        });
    }

    function _aplicarToggle(filtro) {
        if (filtro !== 'COM' && filtro !== 'MAQ') return;
        veiculosFiltro = filtro;
        _salvarPrefs();
        document.querySelectorAll('.cb-toggle-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.filtro === filtro);
        });
        renderVeiculosLista();
    }

    function _datasPeriodo(dias) {
        const fim = new Date();
        const ini = new Date(fim.getTime() - dias * 86400000);
        return {
            inicio: ini.toISOString().slice(0, 10),
            fim:    fim.toISOString().slice(0, 10),
        };
    }

    async function selecionarVeiculo(codveiculo) {
        veiculoDetalheCodvei = codveiculo;
        // Troca pra modo detalhe
        document.getElementById('veiculosListaWrap').classList.add('hidden');
        document.getElementById('veiculosDetalheWrap').classList.remove('hidden');
        await carregarDetalheVeiculo();
    }

    async function carregarDetalheVeiculo() {
        if (!veiculoDetalheCodvei) return;
        const { inicio, fim } = _datasPeriodo(veiculoDetalhePeriodo);
        const params = new URLSearchParams({
            codveiculo: String(veiculoDetalheCodvei),
            date_start: inicio,
            date_end:   fim,
        });

        const fotoEl   = document.getElementById('detFoto');
        const infoEl   = document.getElementById('detInfo');
        const resumoEl = document.getElementById('detResumo');
        infoEl.textContent = 'Carregando…';
        resumoEl.innerHTML = '';

        try {
            const resp = await fetch(`${URL_RELATORIO}?${params.toString()}`,
                                     { credentials: 'same-origin' });
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                infoEl.textContent = data.error || `Erro ${resp.status}`;
                return;
            }
            const v   = data.veiculo || {};
            const tot = data.totais  || {};
            const abast = data.abastecimentos || [];

            // Foto grande — click abre lightbox com imagem em resolução máxima
            const fotoUrl = pathFotoVeiculo(v.placa);
            const placeholder = STATIC_VEICULOS + '_placeholder.svg';
            fotoEl.style.backgroundImage = `url('${fotoUrl}'), url('${placeholder}')`;
            fotoEl.onclick = () => abrirLightboxVeiculo(
                v.placa,
                `${v.placa || ''} — ${v.marcamodelo || v.especietipo || ''}`.trim(),
            );

            // Info
            const propLabel = v.proprio === 'S' ? 'Próprio' : (v.proprio === 'N' ? 'Terceiro' : '');
            infoEl.innerHTML = `
                <div><span class="cb-detalhe-placa">${v.placa || '—'}</span> — ${v.marcamodelo || '—'}</div>
                <div class="cb-muted">
                    ${v.especietipo || ''}${propLabel ? ' · ' + propLabel : ''}${v.nomeparc ? ' · ' + v.nomeparc : ''}
                    · ${formatData(data.periodo.inicio)} a ${formatData(data.periodo.fim)}
                </div>
            `;

            // Resumo (cards de métricas)
            const consumoMedio = tot.consumo_medio_kmlt !== null && tot.consumo_medio_kmlt !== undefined
                ? formatNumero(tot.consumo_medio_kmlt, 2) + ' km/L'
                : (tot.consumo_medio_lth !== null && tot.consumo_medio_lth !== undefined
                    ? formatNumero(tot.consumo_medio_lth, 2) + ' L/h'
                    : '—');
            const distLabel = tot.km_total > 0
                ? formatNumero(tot.km_total, 0) + ' km'
                : (tot.h_total > 0 ? formatNumero(tot.h_total, 1) + ' h' : '—');
            resumoEl.innerHTML = `
                <div class="cb-detalhe-metric">
                    <div class="cb-detalhe-metric-label">Abastecimentos</div>
                    <div class="cb-detalhe-metric-valor">${tot.qtd_abastecimentos || 0}</div>
                </div>
                <div class="cb-detalhe-metric">
                    <div class="cb-detalhe-metric-label">Litros</div>
                    <div class="cb-detalhe-metric-valor">${formatNumero(tot.total_litros, 0)} LT</div>
                </div>
                <div class="cb-detalhe-metric">
                    <div class="cb-detalhe-metric-label">Distância</div>
                    <div class="cb-detalhe-metric-valor">${distLabel}</div>
                </div>
                <div class="cb-detalhe-metric cb-detalhe-metric--destaque">
                    <div class="cb-detalhe-metric-label">Consumo médio</div>
                    <div class="cb-detalhe-metric-valor">${consumoMedio}</div>
                </div>
                <div class="cb-detalhe-metric" style="grid-column: 1 / -1;">
                    <div class="cb-detalhe-metric-label">Valor total no período</div>
                    <div class="cb-detalhe-metric-valor">${formatBRL(tot.total_vlr) || 'R$ 0,00'}</div>
                </div>
            `;

            // Filtra as Movimentações pra mostrar só esses abastecimentos
            renderMovimentacoesDoVeiculo(v, abast);
        } catch (err) {
            infoEl.textContent = 'Falha de conexão.';
        }
    }

    function renderMovimentacoesDoVeiculo(v, abastecimentos) {
        const tbody = document.getElementById('movimentacoesBody');
        if (!tbody) return;
        if (!abastecimentos || abastecimentos.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="cb-empty">
                Sem abastecimentos para ${v.placa || 'este veículo'} no período.
            </td></tr>`;
            return;
        }
        // Cada abastecimento vira uma linha. Pode ser REQUISIÇÃO interna ou
        // EXTERNA_POSTO (ambas com hodômetro/consumo do veículo).
        // Mesma estrutura visual da listagem geral: 9 colunas.
        tbody.innerHTML = abastecimentos.map(a => {
            const ehExterno = a.tipo === 'EXTERNA_POSTO';
            const movLabel = ehExterno
                ? `<span class="cb-badge cb-badge-externo">🌐 EXTERNA</span>`
                : `<span class="${classeMov('REQUISICAO')}">${rotuloMov('REQUISICAO')}</span>`
                  + (a.tipo ? ` <span class="${classeTipo(a.tipo)}" style="margin-left:4px;">${rotuloTipo(a.tipo)}</span>` : '');
            const parceiroOuVei = v.placa || '—';
            // Externa pode editar/excluir mesmo com STATUSNOTA='L' (backend valida DHBAIXA)
            const podeEditar = ehExterno
                ? a.statusnota !== 'E'
                : (a.statusnota !== 'L' && a.statusnota !== 'E');
            const labelAcao = ehExterno ? 'externo' : 'requisição';
            const acoes = podeEditar ? `
                <button class="cb-btn-acao cb-btn-acao--editar"
                        data-acao="editar" data-nunota="${a.nunota}"
                        title="Editar ${labelAcao}">✏</button>
                <button class="cb-btn-acao cb-btn-acao--excluir"
                        data-acao="excluir" data-nunota="${a.nunota}"
                        data-resumo="${a.descrprod} · ${formatNumero(a.qtd, 2)} ${a.codvol || ''} · ${v.placa || ''}"
                        title="Excluir ${labelAcao}">🗑</button>` : '';

            // Total km + Média já vêm calculados pelo backend (consultar_consumo_por_veiculo)
            const celKm = (a.km_percorridos != null)
                ? `<td class="cb-right">${formatNumero(a.km_percorridos, 0)} km</td>`
                : '<td class="cb-right cb-muted">—</td>';
            const celMedia = (a.consumo_kmlt != null)
                ? `<td class="cb-right cb-rel-consumo-destaque">${formatNumero(a.consumo_kmlt, 2)} km/L</td>`
                : (a.consumo_lth != null
                    ? `<td class="cb-right cb-rel-consumo-destaque">${formatNumero(a.consumo_lth, 2)} L/h</td>`
                    : '<td class="cb-right cb-muted">—</td>');

            return `
                <tr data-nunota="${a.nunota}" data-tipo="REQUISICAO">
                    <td>${movLabel}</td>
                    <td>${formatData(a.dtneg)}</td>
                    <td title="${v.marcamodelo || ''}">${parceiroOuVei}</td>
                    <td title="${a.descrprod || ''}">${a.descrprod || '—'}</td>
                    <td class="cb-right">${formatNumero(a.qtd, 2)} ${a.codvol || ''}</td>
                    <td class="cb-right">${formatBRL(a.vlrtot)}</td>
                    ${celKm}
                    ${celMedia}
                    <td class="cb-acoes-cell">${acoes}</td>
                </tr>
            `;
        }).join('');

        // Delegação: liga editar/excluir nos botões da tabela. No relatório do
        // veículo só aparecem requisições (TOP 26), nunca entradas (TOP 10).
        tbody.querySelectorAll('.cb-btn-acao').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const nunota = parseInt(btn.dataset.nunota, 10);
                if (btn.dataset.acao === 'editar') abrirModalEditarReq(nunota);
                else if (btn.dataset.acao === 'excluir') abrirModalExcluirReq(nunota, btn.dataset.resumo || '');
            });
        });
    }

    // ===== Lightbox de foto do veículo (Mai/2026 - 2026-05-13) =====
    function abrirLightboxVeiculo(placa, descricao) {
        const lb = document.getElementById('cbLightbox');
        const img = document.getElementById('cbLightboxImg');
        const leg = document.getElementById('cbLightboxLegenda');
        if (!lb || !img) return;
        img.src = pathFotoVeiculo(placa);   // full resolution
        img.alt = descricao || placa || '';
        if (leg) leg.textContent = descricao || placa || '';
        lb.classList.remove('hidden');
        lb.setAttribute('aria-hidden', 'false');
    }

    function fecharLightboxVeiculo() {
        const lb = document.getElementById('cbLightbox');
        const img = document.getElementById('cbLightboxImg');
        if (!lb) return;
        lb.classList.add('hidden');
        lb.setAttribute('aria-hidden', 'true');
        if (img) img.src = '';   // libera memória
    }

    function voltarParaListaVeiculos() {
        veiculoDetalheCodvei = null;
        document.getElementById('veiculosDetalheWrap').classList.add('hidden');
        document.getElementById('veiculosListaWrap').classList.remove('hidden');
        // Limpa estados visuais do detalhe
        document.getElementById('detFoto').style.backgroundImage = '';
        document.getElementById('detInfo').innerHTML = '';
        document.getElementById('detResumo').innerHTML = '';
        // Volta lista de movimentações sem filtro
        carregarMovimentacoes();
    }

    // =========================================================================
    // Modal Excluir Requisição
    // =========================================================================

    let requisicaoExcluindoNunota = null;
    let entradaExcluindoNunota = null;   // Mai/2026 — exclusão de entrada reusa modal

    function abrirModalExcluirReq(nunota, resumo) {
        requisicaoExcluindoNunota = nunota;
        entradaExcluindoNunota = null;
        document.querySelector('#modalExcluirReq .cb-modal-header strong').textContent =
            '🗑 Excluir requisição';
        document.getElementById('excluirReqResumo').textContent =
            `NUNOTA ${nunota}${resumo ? ' · ' + resumo : ''}`;
        document.getElementById('excluirMotivo').value = '';
        document.getElementById('excluirMensagem').textContent = '';
        document.getElementById('excluirMensagem').className = 'cb-mensagem';
        document.getElementById('modalExcluirReq').classList.remove('hidden');
        setTimeout(() => document.getElementById('excluirMotivo').focus(), 50);
    }

    function abrirModalExcluirEntrada(nunota, resumo) {
        entradaExcluindoNunota = nunota;
        requisicaoExcluindoNunota = null;
        document.querySelector('#modalExcluirReq .cb-modal-header strong').textContent =
            '🗑 Excluir entrada (compra)';
        document.getElementById('excluirReqResumo').textContent =
            `NUNOTA ${nunota}${resumo ? ' · ' + resumo : ''}`;
        document.getElementById('excluirMotivo').value = '';
        document.getElementById('excluirMensagem').textContent = '';
        document.getElementById('excluirMensagem').className = 'cb-mensagem';
        document.getElementById('modalExcluirReq').classList.remove('hidden');
        setTimeout(() => document.getElementById('excluirMotivo').focus(), 50);
    }

    function fecharModalExcluirReq() {
        document.getElementById('modalExcluirReq').classList.add('hidden');
        requisicaoExcluindoNunota = null;
        entradaExcluindoNunota = null;
    }

    async function confirmarExcluirReq() {
        const msg = document.getElementById('excluirMensagem');
        msg.textContent = ''; msg.className = 'cb-mensagem';

        const motivo = (document.getElementById('excluirMotivo').value || '').trim();
        if (!motivo) {
            msg.textContent = 'Motivo é obrigatório.';
            return;
        }
        if (!requisicaoExcluindoNunota && !entradaExcluindoNunota) return;

        const btn = document.getElementById('btnConfirmarExcluir');
        btn.disabled = true; const txt0 = btn.textContent; btn.textContent = 'Excluindo…';
        try {
            const nunota = entradaExcluindoNunota || requisicaoExcluindoNunota;
            const tipoLabel = entradaExcluindoNunota ? 'Entrada' : 'Requisição';
            const url = entradaExcluindoNunota
                ? `/sankhya/combustivel/api/entrada/${nunota}/excluir/`
                : `/sankhya/combustivel/api/requisicao/${nunota}/excluir/`;
            const resp = await IAgro.postJSON(url, { motivo });
            const data = resp.body || {};
            if (!resp.ok || !data.ok) {
                msg.textContent = data.error || `Erro ${resp.status || 'desconhecido'}`;
                return;
            }
            IAgro.showToast(`${tipoLabel} NUNOTA ${data.nunota} excluída.`, 'success');
            fecharModalExcluirReq();
            carregarMovimentacoes();
            carregarEstoque();
        } catch (err) {
            msg.textContent = 'Falha de conexão.';
        } finally {
            btn.disabled = false; btn.textContent = txt0;
        }
    }

    // =========================================================================
    // Modal Nova Entrada
    // =========================================================================

    async function _preencherNomeEmpresaDefault(codemp) {
        // Busca o nome canônico da empresa via endpoint e preenche o campo visível
        // como "CODEMP — NOME". Não bloqueia a abertura do modal.
        try {
            const r = await fetch(`${URL_EMPRESAS}?q=${codemp}&limit=10`,
                                  { credentials: 'same-origin' });
            const d = await r.json();
            const items = d.results || d.items || [];
            const match = items.find(it =>
                String(it.cod || it.codemp) === String(codemp));
            const nome = match
                ? (match.descr || match.nomefantasia || match.razaosocial || '')
                : '';
            const inp = document.getElementById('entEmpresaVis');
            if (inp && nome) inp.value = `${codemp} — ${nome}`;
        } catch (_) { /* mantém só o código */ }
    }

    // Estado da edição da Entrada (Mai/2026 — multi-itens)
    let entItens = [];                 // [{codprod, descrprod, qtd, vlrunit, _seq}]
    let entEditandoNunota = null;      // null = criar; int = editar
    let _entSeq = 0;                   // contador interno para keys únicas

    function _addItemEntrada(item) {
        // item opcional: {codprod, descrprod, qtd, vlrunit}
        _entSeq += 1;
        entItens.push({
            _seq: _entSeq,
            codprod:    item ? item.codprod    : null,
            descrprod:  item ? item.descrprod  : '',
            qtd:        item ? item.qtd        : 0,
            vlrunit:    item ? item.vlrunit    : 0,
        });
        _renderEntItens();
    }

    function _removerItemEntrada(seq) {
        entItens = entItens.filter(it => it._seq !== seq);
        if (entItens.length === 0) _addItemEntrada();   // sempre ao menos 1 linha
        _renderEntItens();
    }

    function _atualizarTotalNota() {
        let total = 0;
        entItens.forEach(it => {
            const qt = parseFloat(it.qtd) || 0;
            const vu = parseFloat(it.vlrunit) || 0;
            total += qt * vu;
        });
        const lbl = document.getElementById('entTotalCalculado');
        if (lbl) lbl.innerHTML = `Total da Nota: <strong>${formatBRL(total) || 'R$ 0,00'}</strong>`;
    }

    function _renderEntItens() {
        const tbody = document.getElementById('entItensBody');
        if (!tbody) return;
        const sozinho = entItens.length === 1;
        // IDs únicos por linha — necessários porque IAgro.attachTypeahead espera
        // string (getElementById), não elemento. Sem ID único o helper não casa
        // o input/hidden/dropdown corretos.
        tbody.innerHTML = entItens.map(it => {
            const idProdVis = `entItemProd_${it._seq}`;
            const idProdCod = `entItemProdCod_${it._seq}`;
            const idProdDD  = `entItemProdDD_${it._seq}`;
            const idQtd     = `entItemQtd_${it._seq}`;
            const idVlu     = `entItemVlu_${it._seq}`;
            return `
            <tr data-seq="${it._seq}">
                <td style="position: relative;">
                    <input id="${idProdVis}" type="text" class="cb-input cb-input-item-prod"
                           data-seq="${it._seq}" autocomplete="off"
                           value="${it.codprod ? (it.codprod + ' — ' + (it.descrprod || '')) : ''}"
                           placeholder="Buscar combustível…" />
                    <input id="${idProdCod}" type="hidden" value="${it.codprod || ''}" />
                    <div id="${idProdDD}" class="cb-dropdown dropdown-abs"></div>
                </td>
                <td>
                    <input id="${idQtd}" type="number" class="cb-input cb-input-right cb-input-item-qtd"
                           data-seq="${it._seq}" step="0.01" min="0"
                           value="${it.qtd || ''}" placeholder="0,00" />
                </td>
                <td>
                    <input id="${idVlu}" type="number" class="cb-input cb-input-right cb-input-item-vlu"
                           data-seq="${it._seq}" step="0.0001" min="0"
                           value="${it.vlrunit || ''}" placeholder="0,0000" />
                </td>
                <td class="cb-item-total" data-seq="${it._seq}">
                    ${formatBRL((parseFloat(it.qtd) || 0) * (parseFloat(it.vlrunit) || 0)) || 'R$ 0,00'}
                </td>
                <td>
                    <button type="button" class="cb-item-remove" data-seq="${it._seq}"
                            ${sozinho ? 'disabled title="Pelo menos 1 item"' : 'title="Remover"'}>×</button>
                </td>
            </tr>`;
        }).join('');

        // Liga eventos de qtd/vlrunit (com recálculo da célula sem re-render)
        tbody.querySelectorAll('.cb-input-item-qtd, .cb-input-item-vlu').forEach(inp => {
            inp.addEventListener('input', (e) => {
                const seq = parseInt(e.target.dataset.seq, 10);
                const item = entItens.find(it => it._seq === seq);
                if (!item) return;
                if (e.target.classList.contains('cb-input-item-qtd')) {
                    item.qtd = parseFloat(e.target.value) || 0;
                } else {
                    item.vlrunit = parseFloat(e.target.value) || 0;
                }
                const cell = tbody.querySelector(`.cb-item-total[data-seq="${seq}"]`);
                if (cell) {
                    cell.textContent = formatBRL(item.qtd * item.vlrunit) || 'R$ 0,00';
                }
                _atualizarTotalNota();
            });
        });
        tbody.querySelectorAll('.cb-item-remove').forEach(btn => {
            btn.addEventListener('click', () => {
                _removerItemEntrada(parseInt(btn.dataset.seq, 10));
            });
        });

        // Typeahead de produto por linha — passa IDs únicos como string (não elementos!)
        entItens.forEach(it => {
            if (!window.IAgro || !IAgro.attachTypeahead) return;
            const seq = it._seq;
            IAgro.attachTypeahead({
                inputId:    `entItemProd_${seq}`,
                hiddenId:   `entItemProdCod_${seq}`,
                dropdownId: `entItemProdDD_${seq}`,
                url: URL_PRODUTOS, limit: 30, debounceMs: 250, minChars: 0,
                positionFixed: true,
                pickItems: (data) => data.results || [],
                pickCod: (item) => item.codprod, pickDescr: (item) => item.descrprod,
                renderItem: (item) => `${item.codprod} — ${item.descrprod} <span style="color:#94a3b8;font-size:10px;">(${item.codvol})</span>`,
                onSelect: (cod, descr) => {
                    const i = entItens.find(x => x._seq === seq);
                    if (i) {
                        i.codprod = parseInt(cod, 10);
                        i.descrprod = descr;
                    }
                },
                onClear: () => {
                    const i = entItens.find(x => x._seq === seq);
                    if (i) { i.codprod = null; i.descrprod = ''; }
                },
            });
        });

        _atualizarTotalNota();
    }

    function abrirModalNovaEntrada() {
        const modal = document.getElementById('modalNovaEntrada');
        modal.classList.remove('hidden');

        entEditandoNunota = null;
        entItens = [];
        _atualizarHeaderModalEnt();

        ['entEmpresaVis','entEmpresaCod','entFornecedorVis','entFornecedorCod',
         'entNumNota','entSerieNota',
         'entCencusVis','entCencusCod','entHistorico','entObs',
         'entNaturezaVis','entNaturezaCod','entTipVendaVis','entTipVendaCod']
            .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });

        // Defaults
        const h = hoje();
        document.getElementById('entDtNeg').value  = h;
        document.getElementById('entDtVenc').value = h;
        document.getElementById('entEmpresaCod').value = '1';
        document.getElementById('entEmpresaVis').value = '1';   // placeholder até nome carregar
        _preencherNomeEmpresaDefault(1);
        // Defaults pré-selecionados (Mai/2026)
        document.getElementById('entCencusCod').value  = DEFAULT_CODCENCUS;
        document.getElementById('entCencusVis').value  = `${DEFAULT_CODCENCUS} — COMERCIALIZAÇÃO`;
        document.getElementById('entNaturezaCod').value = DEFAULT_CODNAT;
        document.getElementById('entNaturezaVis').value = `${DEFAULT_CODNAT} — COMBUSTÍVEL`;
        document.getElementById('entTipVendaCod').value = DEFAULT_CODTIPVENDA;
        document.getElementById('entTipVendaVis').value = `${DEFAULT_CODTIPVENDA} — A VISTA`;

        // 1 item vazio inicial
        _addItemEntrada();
        document.getElementById('entTotalCalculado').innerHTML = 'Total: <strong>R$ 0,00</strong>';
        document.getElementById('entMensagem').textContent = '';
        document.getElementById('entMensagem').className = 'cb-mensagem';

        setTimeout(() => document.getElementById('entFornecedorVis').focus(), 50);
    }

    function fecharModalNovaEntrada() {
        document.getElementById('modalNovaEntrada').classList.add('hidden');
    }

    function _atualizarHeaderModalEnt() {
        const h = document.getElementById('entModalTitle');
        const btn = document.getElementById('btnConfirmarEntrada');
        const btnExcluir = document.getElementById('btnExcluirEntradaModal');
        if (entEditandoNunota) {
            if (h) h.textContent = `✏ Editar entrada NUNOTA ${entEditandoNunota}`;
            if (btn) btn.textContent = 'Salvar alterações';
            if (btnExcluir) btnExcluir.classList.remove('hidden');
        } else {
            if (h) h.textContent = '📥 Nova entrada de combustível (compra)';
            if (btn) btn.textContent = 'Salvar entrada';
            if (btnExcluir) btnExcluir.classList.add('hidden');
        }
    }

    async function abrirModalEditarEntrada(nunota) {
        const modal = document.getElementById('modalNovaEntrada');
        modal.classList.remove('hidden');
        entEditandoNunota = nunota;
        entItens = [];
        _atualizarHeaderModalEnt();

        // Limpa
        ['entEmpresaVis','entEmpresaCod','entFornecedorVis','entFornecedorCod',
         'entNumNota','entSerieNota',
         'entCencusVis','entCencusCod','entHistorico','entObs',
         'entNaturezaVis','entNaturezaCod','entTipVendaVis','entTipVendaCod',
         'entDtNeg','entDtVenc']
            .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
        _renderEntItens();
        document.getElementById('entMensagem').textContent = 'Carregando…';
        document.getElementById('entMensagem').className = 'cb-mensagem cb-mensagem-info';

        try {
            const resp = await fetch(`/sankhya/combustivel/api/entrada/${nunota}/`,
                                     { credentials: 'same-origin' });
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                document.getElementById('entMensagem').textContent =
                    data.error || 'Falha ao carregar entrada.';
                document.getElementById('entMensagem').className = 'cb-mensagem';
                return;
            }
            const cab = data.cabecalho || {};
            const fin = data.financeiro || {};
            const itens = data.itens || [];

            // Preenche cabeçalho
            if (cab.CODEMP) {
                document.getElementById('entEmpresaCod').value = cab.CODEMP;
                document.getElementById('entEmpresaVis').value = String(cab.CODEMP);
                _preencherNomeEmpresaDefault(cab.CODEMP);
            }
            if (cab.CODPARC) {
                document.getElementById('entFornecedorCod').value = cab.CODPARC;
                document.getElementById('entFornecedorVis').value =
                    `${cab.CODPARC} — ${cab.NOMEPARC || ''}`;
            }
            if (cab.NUMNOTA)   document.getElementById('entNumNota').value = cab.NUMNOTA;
            if (cab.SERIENOTA) document.getElementById('entSerieNota').value = cab.SERIENOTA;
            if (cab.DTNEG)     document.getElementById('entDtNeg').value  = cab.DTNEG;
            if (fin.DTVENC)    document.getElementById('entDtVenc').value = fin.DTVENC;
            else if (cab.DTNEG) document.getElementById('entDtVenc').value = cab.DTNEG;
            if (cab.CODCENCUS) {
                document.getElementById('entCencusCod').value = cab.CODCENCUS;
                document.getElementById('entCencusVis').value = String(cab.CODCENCUS);
            }
            if (cab.CODNAT) {
                document.getElementById('entNaturezaCod').value = cab.CODNAT;
                document.getElementById('entNaturezaVis').value = String(cab.CODNAT);
            }
            if (cab.CODTIPVENDA) {
                document.getElementById('entTipVendaCod').value = cab.CODTIPVENDA;
                document.getElementById('entTipVendaVis').value = String(cab.CODTIPVENDA);
            }
            if (fin.HISTORICO) document.getElementById('entHistorico').value = fin.HISTORICO;
            if (cab.OBSERVACAO) document.getElementById('entObs').value = cab.OBSERVACAO;

            // Itens — popula array e renderiza
            entItens = [];
            itens.forEach(it => _addItemEntrada({
                codprod:   it.CODPROD,
                descrprod: it.DESCRPROD,
                qtd:       it.QTDNEG,
                vlrunit:   it.VLRUNIT,
            }));
            if (entItens.length === 0) _addItemEntrada();

            document.getElementById('entMensagem').textContent = '';
            document.getElementById('entMensagem').className = 'cb-mensagem';
        } catch (err) {
            document.getElementById('entMensagem').textContent = 'Falha de conexão.';
            document.getElementById('entMensagem').className = 'cb-mensagem';
        }
    }

    function montarTypeaheadsEntrada() {
        if (!window.IAgro || !IAgro.attachTypeahead) return;

        // Empresa
        IAgro.attachTypeahead({
            inputId: 'entEmpresaVis', hiddenId: 'entEmpresaCod', dropdownId: 'entEmpresaDD',
            url: URL_EMPRESAS, limit: 30, debounceMs: 250, minChars: 0,
            pickItems: (data) => data.results || data.items || [],
            pickCod: (it) => it.cod || it.codemp,
            pickDescr: (it) => it.descr || it.nomefantasia || it.razaosocial || '',
        });

        // Fornecedor (typeahead de parceiros)
        IAgro.attachTypeahead({
            inputId: 'entFornecedorVis', hiddenId: 'entFornecedorCod', dropdownId: 'entFornecedorDD',
            url: URL_PARCEIROS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (data) => data.results || data.items || [],
            pickCod: (it) => it.cod || it.codparc,
            pickDescr: (it) => it.descr || it.nomeparc || '',
        });

        // (Mai/2026 — multi-itens) Typeahead de combustível agora é por linha
        // na tabela de itens, montado dinamicamente em _renderEntItens.

        // Centro de resultado
        IAgro.attachTypeahead({
            inputId: 'entCencusVis', hiddenId: 'entCencusCod', dropdownId: 'entCencusDD',
            url: URL_CENCUS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (data) => data.results || data.items || [],
            pickCod: (it) => it.cod || it.codcencus,
            pickDescr: (it) => it.descr || it.descrcencus || '',
        });

        // Natureza (CODNAT) — opcional. Default backend: 30070200 (combustíveis)
        IAgro.attachTypeahead({
            inputId: 'entNaturezaVis', hiddenId: 'entNaturezaCod', dropdownId: 'entNaturezaDD',
            url: URL_NATUREZAS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (data) => data.results || data.items || [],
            pickCod: (it) => it.cod || it.codnat,
            pickDescr: (it) => it.descr || it.descrnat || '',
        });

        // Tipo de Negociação (CODTIPVENDA) — opcional. Default 11.
        // onSelect dispara recálculo automático de DTVENC (BASEPRAZO do TGFTPV).
        IAgro.attachTypeahead({
            inputId: 'entTipVendaVis', hiddenId: 'entTipVendaCod', dropdownId: 'entTipVendaDD',
            url: URL_TIPVENDA, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (data) => data.results || data.items || [],
            pickCod: (it) => it.cod || it.codtipvenda,
            pickDescr: (it) => it.descr || it.descrtipvenda || '',
            onSelect: () => { if (window._cbRecalcularDtVenc) window._cbRecalcularDtVenc(); },
        });
    }

    function validarEntrada() {
        const erros = [];
        if (!document.getElementById('entEmpresaCod').value) erros.push('Empresa obrigatória.');
        if (!document.getElementById('entFornecedorCod').value) erros.push('Fornecedor obrigatório.');
        if (!document.getElementById('entCencusCod').value) erros.push('Centro de resultado obrigatório.');
        const numnota = parseInt(document.getElementById('entNumNota').value || '0', 10);
        if (!numnota || numnota <= 0) erros.push('Nº da Nota obrigatório.');
        const dtn = document.getElementById('entDtNeg').value;
        const dtv = document.getElementById('entDtVenc').value || dtn;
        if (dtv && dtn && dtv < dtn) erros.push('Vencimento não pode ser anterior à data da entrada.');
        // Pelo menos 1 item completo (com codprod, qtd > 0, vlrunit > 0)
        const itensValidos = entItens.filter(it =>
            it.codprod && (parseFloat(it.qtd) || 0) > 0 && (parseFloat(it.vlrunit) || 0) > 0);
        if (itensValidos.length === 0) {
            erros.push('Adicione pelo menos 1 item com combustível, qtd e valor.');
        }
        return erros;
    }

    async function enviarEntrada() {
        const msg = document.getElementById('entMensagem');
        msg.textContent = ''; msg.className = 'cb-mensagem';
        const erros = validarEntrada();
        if (erros.length) { msg.textContent = erros.join(' '); return; }

        const dtn = document.getElementById('entDtNeg').value || hoje();
        const dtv = document.getElementById('entDtVenc').value || dtn;

        // Monta lista de itens válidos
        const itens = entItens
            .filter(it => it.codprod && (parseFloat(it.qtd) || 0) > 0 && (parseFloat(it.vlrunit) || 0) > 0)
            .map(it => ({
                codprod: parseInt(it.codprod, 10),
                qtd:     parseFloat(it.qtd),
                vlrunit: parseFloat(it.vlrunit),
            }));

        const payload = {
            codemp:    parseInt(document.getElementById('entEmpresaCod').value, 10),
            codparc:   parseInt(document.getElementById('entFornecedorCod').value, 10),
            numnota:   parseInt(document.getElementById('entNumNota').value, 10),
            serienota: (document.getElementById('entSerieNota').value || '').trim() || null,
            itens:     itens,
            codcencus: parseInt(document.getElementById('entCencusCod').value, 10),
            codnat:    parseInt(document.getElementById('entNaturezaCod').value || '0', 10) || null,
            codtipvenda: parseInt(document.getElementById('entTipVendaCod').value || '0', 10) || null,
            dtneg:     dtn,
            dtvenc:    dtv,
            historico: document.getElementById('entHistorico').value.trim() || null,
            observacao: document.getElementById('entObs').value.trim() || null,
        };

        const btn = document.getElementById('btnConfirmarEntrada');
        btn.disabled = true; const txt0 = btn.textContent; btn.textContent = 'Enviando…';
        try {
            const url = entEditandoNunota
                ? `/sankhya/combustivel/api/entrada/${entEditandoNunota}/editar/`
                : URL_ENT_CRIAR;
            const resp = await IAgro.postJSON(url, payload);
            const data = resp.body || {};
            if (!resp.ok || !data.ok) {
                msg.textContent = data.error || `Erro ${resp.status || 'desconhecido'}`;
                return;
            }
            const acao = entEditandoNunota ? 'atualizada' : 'criada';
            const extras = data.nufin ? ` · NUFIN ${data.nufin}` : '';
            IAgro.showToast(
                `Entrada NUNOTA ${data.nunota} · NF ${data.numnota} (${data.qtd_itens || itens.length} itens) ${acao}${extras}.`,
                'success',
            );
            fecharModalNovaEntrada();
            carregarMovimentacoes();
            carregarEstoque();
        } catch (err) {
            msg.textContent = 'Falha de conexão.';
        } finally {
            btn.disabled = false; btn.textContent = txt0;
        }
    }

    // =========================================================================
    // Inicialização
    // =========================================================================

    function init() {
        document.getElementById('btnAtualizarEstoque').addEventListener('click', carregarEstoque);
        document.getElementById('btnAtualizarReqs').addEventListener('click', carregarMovimentacoes);
        document.getElementById('btnNovaRequisicao').addEventListener('click', abrirModalNovaReq);
        document.getElementById('btnNovaEntrada').addEventListener('click', abrirModalNovaEntrada);

        if (window.IAgro && IAgro.wireFilterAuto) {
            IAgro.wireFilterAuto(['filtroMov', 'filtroStatus', 'filtroTipo'], carregarMovimentacoes);
        } else {
            ['filtroMov','filtroStatus','filtroTipo'].forEach(id =>
                document.getElementById(id).addEventListener('change', carregarMovimentacoes));
        }

        // Modal Requisição
        document.getElementById('modalNovaReqFechar').addEventListener('click', fecharModalNovaReq);
        document.getElementById('btnCancelarReq').addEventListener('click', fecharModalNovaReq);
        document.getElementById('btnConfirmarReq').addEventListener('click', enviarRequisicao);
        document.querySelectorAll('input[name="cbTipo"]').forEach(r => {
            r.addEventListener('change', () => {
                atualizarDocFreteVisivel();
                atualizarMedidorPorTipo();
                atualizarExternoVisivel();
                document.getElementById('reqVeiculoVis').value = '';
                document.getElementById('reqVeiculoCod').value = '';
                document.getElementById('reqVeiculoHint').textContent = '';
                veiculoSelecionado = null;
            });
        });

        // Botão "+ Item" no modal de Requisição (só visível em EXTERNA_POSTO)
        const btnAddItemReqExt = document.getElementById('btnAddItemReqExt');
        if (btnAddItemReqExt) {
            btnAddItemReqExt.addEventListener('click', () => _addItemReqExt());
        }

        // Links rápidos pra parceiros frequentes do externo (Semear/Agromil)
        document.querySelectorAll('.cb-link-posto').forEach(a => {
            a.addEventListener('click', async (e) => {
                e.preventDefault();
                const cp = a.dataset.codparc;
                if (!cp) return;
                // Busca o nome canônico via endpoint e seta os campos
                try {
                    const resp = await fetch(`${URL_PARCEIROS}?q=${cp}&limit=5`,
                                             { credentials: 'same-origin' });
                    const data = await resp.json();
                    const items = data.results || data.items || [];
                    const match = items.find(it => String(it.cod || it.codparc) === String(cp));
                    const nome = match ? (match.descr || match.nomeparc || '') : '';
                    document.getElementById('reqPostoCod').value = cp;
                    document.getElementById('reqPostoVis').value = `${cp} — ${nome}`;
                } catch (_) {
                    document.getElementById('reqPostoCod').value = cp;
                    document.getElementById('reqPostoVis').value = String(cp);
                }
            });
        });

        // Modal Entrada
        document.getElementById('modalNovaEntradaFechar').addEventListener('click', fecharModalNovaEntrada);
        document.getElementById('btnCancelarEntrada').addEventListener('click', fecharModalNovaEntrada);
        document.getElementById('btnConfirmarEntrada').addEventListener('click', enviarEntrada);
        document.getElementById('btnAddItemEntrada').addEventListener('click', () => _addItemEntrada());

        // Botão Excluir Entrada (rodapé do modal de edição) — abre modal de
        // confirmação com motivo obrigatório. Reusa modal existente de excluir
        // requisição via abrirModalExcluirEntrada (distingue por flag interna).
        document.getElementById('btnExcluirEntradaModal').addEventListener('click', () => {
            if (!entEditandoNunota) return;
            const nunota = entEditandoNunota;
            // Monta resumo curto pra mostrar no modal de confirmação
            const numnota = (document.getElementById('entNumNota').value || '').trim();
            const fornecedor = (document.getElementById('entFornecedorVis').value || '').trim();
            const resumo = `NF ${numnota || '—'} · ${fornecedor || 'fornecedor'}`;
            // Fecha modal de edição antes pra evitar 2 modais sobrepostos
            fecharModalNovaEntrada();
            abrirModalExcluirEntrada(nunota, resumo);
        });

        // Auto-cálculo de DTVENC quando muda Tipo de Negociação ou Data Entrada.
        // Exposto em window._cbRecalcularDtVenc pra que o onSelect do typeahead
        // de tipo possa disparar (typeahead seta hidden programaticamente, sem
        // disparar event 'change').
        const _recalcularDtVenc = async () => {
            const codtipv = parseInt(document.getElementById('entTipVendaCod').value || '0', 10);
            const dtn = document.getElementById('entDtNeg').value;
            if (!codtipv || !dtn) return;
            try {
                const r = await fetch(`/sankhya/combustivel/api/prazo-tipvenda/?codtipvenda=${codtipv}`,
                                      { credentials: 'same-origin' });
                const j = await r.json();
                if (!j.ok) return;
                const prazo = parseInt(j.prazo_dias || 0, 10);
                const d = new Date(dtn);
                d.setDate(d.getDate() + prazo);
                const novaData = d.toISOString().slice(0, 10);
                document.getElementById('entDtVenc').value = novaData;
            } catch (_) { /* ignora */ }
        };
        window._cbRecalcularDtVenc = _recalcularDtVenc;
        document.getElementById('entDtNeg').addEventListener('change', _recalcularDtVenc);

        // Modal Excluir Requisição
        document.getElementById('modalExcluirReqFechar').addEventListener('click', fecharModalExcluirReq);
        document.getElementById('btnCancelarExcluir').addEventListener('click', fecharModalExcluirReq);
        document.getElementById('btnConfirmarExcluir').addEventListener('click', confirmarExcluirReq);

        // Lightbox da foto do veículo (Mai/2026 - 2026-05-13)
        // Fecha por: botão ×, click no overlay, tecla Esc
        const lbOverlay = document.getElementById('cbLightbox');
        const lbBtnFechar = document.getElementById('cbLightboxFechar');
        if (lbBtnFechar) lbBtnFechar.addEventListener('click', fecharLightboxVeiculo);
        if (lbOverlay) {
            lbOverlay.addEventListener('click', (e) => {
                // só fecha se clicou no overlay (não na imagem)
                if (e.target === lbOverlay) fecharLightboxVeiculo();
            });
        }
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && lbOverlay && !lbOverlay.classList.contains('hidden')) {
                fecharLightboxVeiculo();
            }
        });

        // Área de Veículos: toggle COM/MAQ + voltar + período
        _carregarPrefs();
        document.querySelectorAll('.cb-toggle-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filtro === veiculosFiltro);
            btn.addEventListener('click', () => _aplicarToggle(btn.dataset.filtro));
        });
        document.getElementById('btnVoltarVeiculos').addEventListener('click', voltarParaListaVeiculos);
        document.getElementById('detPeriodo').addEventListener('change', (e) => {
            veiculoDetalhePeriodo = parseInt(e.target.value, 10) || 30;
            carregarDetalheVeiculo();
        });

        // Typeaheads
        montarTypeaheadVeiculo();
        montarTypeaheadProdutoReq();
        montarTypeaheadCencusReq();
        montarTypeaheadNaturezaReq();
        montarTypeaheadTipVendaReq();
        montarTypeaheadPostoReq();
        montarTypeaheadsEntrada();

        // Carga inicial
        carregarEstoque();
        carregarMovimentacoes();
        carregarVeiculos();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
