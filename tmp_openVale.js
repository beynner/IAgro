async function openValeResumo(nunota){
        console.log('[DEBUG] 🚀 openValeResumo chamada com nunota:', nunota);
        const t0Performance = performance.now();
        
        // 🚀 OTIMIZAÇÃO: Cache de seletores DOM no início
        const els = {
          spinner: document.getElementById('loadingSpinner'),
          modal: document.getElementById('modalFaturamento'),
          title: document.getElementById('valeResumoTitle'),
          classBody: document.getElementById('valeClassBody'),
          outrosBody: document.getElementById('valeOutrosBody'),
          totalEl: document.getElementById('valeResumoTotal'),
          btnGerarVale: document.getElementById('btnGerarVale'),
          pedidoEl: document.getElementById('valeResumoPedido'),
          pedidoNumEl: document.getElementById('valeResumoPedidoNum'),
          valeEl: document.getElementById('valeResumoVale'),
          valeNumEl: document.getElementById('valeResumoValeNum')
        };
        // Expor referências locais para evitar problemas de closure dentro de helpers
        const classBody = els.classBody;
        const outrosBody = els.outrosBody;
        
        // Mostrar spinner
        if(els.spinner) els.spinner.style.display = 'flex';
        
        try{
          // 🚀 OTIMIZAÇÃO: Remover reload automático - usar dados já carregados
          // O reload só será feito quando necessário (após save, delete, etc)
          const t2 = performance.now();
          
          // 🔥 ARMAZENAR NUNOTA no botão para evitar closure problem
          if(els.btnGerarVale){
            els.btnGerarVale.setAttribute('data-nunota-atual', String(nunota));
          }
          
          if(!els.modal || !els.title || !els.classBody || !els.outrosBody || !els.totalEl) {
            console.error('[ERROR] Elementos do modal não encontrados!');
            if(els.spinner) els.spinner.style.display = 'none';
            return;
          }
          
          // 🔥 Armazenar NUNOTA atual globalmente para verificações de faturamento
          window.__CURRENT_VALE_NUNOTA = nunota;
          
          // 🔥 CRÍTICO: Armazenar NUNOTA do PEDIDO (TOP 11) para usar no auto-save
          window.__CURRENT_PEDIDO_NUNOTA = nunota;
          
          // 🚀 CRÍTICO: Buscar NUNOTA do vale (TOP 13) para exibir dados corretos
          const pedidoRows = (window.__COM_LIST_ROWS||[]).filter(r=> String(r.nunota||'') === String(nunota||''));
          console.log('[DEBUG] Linhas do pedido filtradas:', pedidoRows.length);
          
          // Buscar nunota_13 (vale) nos dados do pedido
          let nunota13 = pedidoRows[0]?.nunota_13 || '';
          if(!nunota13){
            const itemComVale = pedidoRows.find(r => r.nunota_13);
            if(itemComVale) nunota13 = itemComVale.nunota_13;
          }
          
          // 🔥 CRÍTICO: Armazenar NUNOTA do VALE (TOP 13) para usar no auto-save
          window.__CURRENT_VALE_NUNOTA_TOP13 = nunota13 || null;
          console.log('[MODAL] 🔥 NUNOTAs armazenados - PEDIDO:', window.__CURRENT_PEDIDO_NUNOTA, 'VALE:', window.__CURRENT_VALE_NUNOTA_TOP13);
          
          // 🔥 Carregar VLROUTROS (desconto INSS) do vale
          const vlroutros = pedidoRows[0]?.vlroutros || 0;
          const checkboxINSS = document.getElementById('valeDescontaINSS');
          if(checkboxINSS){
            if(vlroutros > 0){
              checkboxINSS.checked = true;
              console.log('[MODAL] ✅ INSS carregado de VLROUTROS:', vlroutros);
            } else {
              checkboxINSS.checked = false;
            }
          }
          
          // 🔥 Se tem vale, BUSCAR ITENS DO VALE DO BACKEND (não estão em cache)
          let rows = pedidoRows;
          if(nunota13){
            console.log('[DEBUG] 🔍 Buscando itens do vale', nunota13, 'do backend...');
            try {
              const resp = await fetch(`/sankhya/comercial/api/itens_vale/?nunota=${nunota13}`);
              if(resp.ok){
                const valeData = await resp.json();
                if(valeData.items && valeData.items.length > 0){
                  rows = valeData.items;
                  console.log('[DEBUG] ✅ Itens do vale carregados:', rows.length);
                } else {
                  console.warn('[DEBUG] ⚠️ Vale sem itens, usando pedido');
                }
              } else {
                console.error('[DEBUG] ❌ Erro ao buscar vale:', resp.status);
              }
            } catch(e){
              console.error('[DEBUG] ❌ Erro na requisição do vale:', e);
            }
          }

          // 🔁 Normalizar quantidades para preservar a visualização em CX (pré-faturamento)
          const normalizeNumber = (value) => {
            const n = Number(value);
            return Number.isFinite(n) ? n : null;
          };
          const normalizeUnit = (value) => {
            if(value === null || value === undefined) return '';
            try {
              return String(value).trim().toUpperCase();
            } catch (err) {
              return '';
            }
          };
          const makeFullKey = (obj) => {
            const codprod = normalizeNumber(obj?.codprod) ?? 0;
            const codag = normalizeUnit(obj?.codagregacao || obj?.lote);
            const classKey = obj?.classificavel === false ? 'N' : 'C';
            return `${codprod}#${codag}#${classKey}`;
          };
          const makePartialKey = (obj) => {
            const codprod = normalizeNumber(obj?.codprod) ?? 0;
            const classKey = obj?.classificavel === false ? 'N' : 'C';
            return `${codprod}#${classKey}`;
          };
          const bucketsFull = new Map();
          const bucketsPartial = new Map();
          const pushBucket = (map, key, value) => {
            if(!map.has(key)){
              map.set(key, []);
            }
            map.get(key).push(value);
          };
          (pedidoRows || []).forEach(pr => {
            pushBucket(bucketsFull, makeFullKey(pr), pr);
            pushBucket(bucketsPartial, makePartialKey(pr), pr);
          });
          const consumedSeqs = new Set();
          const takeFromBucket = (map, key) => {
            const arr = map.get(key);
            if(!arr || !arr.length) return null;
            while(arr.length){
              const candidate = arr.shift();
              if(!candidate) continue;
              const seqKey = `${candidate?.nunota ?? 'P'}#${candidate?.sequencia ?? ''}#${normalizeUnit(candidate?.codagregacao || candidate?.lote)}#${candidate?.codprod ?? 0}`;
              if(consumedSeqs.has(seqKey)){
                continue;
              }
              consumedSeqs.add(seqKey);
              return candidate;
            }
            return null;
          };
          const normalizeRows = (sourceRows) => {
            return (sourceRows || []).map(item => {
              const pedidoRef = takeFromBucket(bucketsFull, makeFullKey(item))
                || takeFromBucket(bucketsPartial, makePartialKey(item))
                || null;
              let fator = normalizeNumber(item?.fator_conversao);
              const fatorPedido = normalizeNumber(pedidoRef?.fator_conversao);
              if(!fator && fatorPedido){
                fator = fatorPedido;
              }
              if(fator && fator <= 0){
                fator = null;
              }
              let baseQty = normalizeNumber(item?.qtdneg_base);
              if(baseQty === null && pedidoRef){
                baseQty = normalizeNumber(pedidoRef?.qtdneg_base);
              }
              let displayQty = normalizeNumber(item?.qtdneg);
              const pedidoQty = normalizeNumber(pedidoRef?.qtdneg);
              if(pedidoQty !== null){
                displayQty = pedidoQty;
              } else if(displayQty === null && baseQty !== null && fator){
                displayQty = baseQty / fator;
              }
              if(baseQty === null){
                if(displayQty !== null && fator){
                  baseQty = displayQty * fator;
                } else if(displayQty !== null){
                  baseQty = displayQty;
                }
              }
              if(displayQty === null){
                if(baseQty !== null && fator){
                  displayQty = baseQty / fator;
                } else if(baseQty !== null){
                  displayQty = baseQty;
                } else {
                  displayQty = 0;
                }
              }
              const unitPedido = normalizeUnit(pedidoRef?.codvol);
              let unit = normalizeUnit(item?.codvol);
              if(unitPedido){
                unit = unitPedido;
              }
              displayQty = Number(displayQty);
              if(!Number.isFinite(displayQty)){
                displayQty = 0;
              }
              if(baseQty === null || baseQty === undefined){
                baseQty = displayQty;
              }
              baseQty = Number(baseQty);
              if(!Number.isFinite(baseQty)){
                baseQty = 0;
              }
              return {
                ...item,
                qtdneg: displayQty,
                qtdneg_base: baseQty,
                fator_conversao: fator ?? null,
                codvol: unit || null
              };
            });
          };

          rows = normalizeRows(rows);
          
          console.log('[DEBUG] NUNOTA usado para modal:', nunota13 || nunota, 'Linhas filtradas:', rows.length);
          
          const parc = pedidoRows[0]?.parceiro || '';
          
          // Armazenar fabricante do primeiro produto para uso na impressão
          const fabricanteProduto = pedidoRows[0]?.produto || 'N/A';
          window.__CURRENT_FABRICANTE = fabricanteProduto;
          console.log('[DEBUG] Fabricante armazenado:', fabricanteProduto);
          
          // 🚀 Atualizar título: só o parceiro (usando cache)
          els.title.textContent = parc || 'Parceiro';
          
          console.log('[MODAL PEDIDO] Elementos:', {
            pedidoEl: !!els.pedidoEl,
            pedidoNumEl: !!els.pedidoNumEl,
            nunota: nunota
          });
          
          // Pedido = NUNOTA atual (TOP 11) - SEMPRE mostrar
          if(els.pedidoEl && els.pedidoNumEl && nunota){
            els.pedidoNumEl.textContent = nunota;
            els.pedidoEl.style.display = 'block';
            console.log('[VALE MODAL] ✅ Pedido exibido:', nunota, 'display:', els.pedidoEl.style.display);
          } else {
            console.log('[VALE MODAL] ❌ Pedido não exibido - elementos ou nunota faltando');
          }
          
          // Vale (TOP 13) - buscar se existe NUNOTA relacionado
          if(els.valeEl && els.valeNumEl){
            // Usar nunota13 já declarado acima
            
            if(nunota13){
              els.valeNumEl.textContent = nunota13;
              els.valeEl.style.display = 'block';
            } else {
              els.valeNumEl.textContent = '—';
              els.valeEl.style.display = 'none';
            }
          }
          
          // 🚀 OTIMIZAÇÃO: Criar formatadores UMA VEZ (fora do loop)
          const moneyFormatter = new Intl.NumberFormat('pt-BR', {style:'decimal', minimumFractionDigits:2, maximumFractionDigits:2});
          const qtyFormatter = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 0}); // 0 casas decimais
          
          const fmtMoney = (n)=> {
            if(isNaN(n)) return '<span class="valor-monetario"><span class="cifrao">R$</span> 0,00</span>';
            const formatted = moneyFormatter.format(n);
            return `<span class="valor-monetario"><span class="cifrao">R$</span> ${formatted}</span>`;
          };
          const fmtQty = (n)=> isNaN(n) ? '0' : qtyFormatter.format(Number(n||0));
          
          const classifs = rows.filter(r=> window.__isClassificavelItem(r));
          const nclass = rows.filter(r=> window.__isNaoClassificavelItem(r));
          
          // Usar nunota13 já declarado no início da função
          console.log('[MODAL] NUNOTA do pedido (TOP 11):', nunota, '| NUNOTA do vale (TOP 13):', nunota13);
          
          // 🚀 Calcular totais de KG e CX dos itens classificáveis do pedido
          let totalKgFromItems = 0;
          let totalCxFromItems = 0;
          
          // 🔥 IMPORTANTE: Buscar fator de conversão do PEDIDO (pedidoRows) porque o vale vem em KG sem fator
          const fatorConversaoPedido = (() => {
            const candidate = (pedidoRows || []).find(r => Number(r?.fator_conversao || 0) > 0)
              || (rows || []).find(r => Number(r?.fator_conversao || 0) > 0);
            const valor = Number(candidate?.fator_conversao || 0);
            return Number.isFinite(valor) && valor > 0 ? valor : 22;
          })(); // Default 22kg/cx se nada informado
          console.log('[MODAL] Fator conversão do pedido:', fatorConversaoPedido, 'pedidoRows[0]:', pedidoRows[0]);
          
          // Somar QTDNEG de todos os classificáveis
          classifs.forEach((r, idx) => {
            const qtd = Number(r.qtdneg || 0);
            const unit = ((r.codvol || '') + '').toUpperCase();
            // 🔥 CORRIGIDO: Usar fator do pedido se o item não tiver (null, 0, ou undefined)
            const fatorItem = r.fator_conversao;
            const fatorConv = (fatorItem != null && fatorItem > 0) ? Number(fatorItem) : fatorConversaoPedido;
            
            console.log(`[MODAL] Item ${idx}: qtd=${qtd} unit=${unit} fatorItem=${fatorItem} fatorUsado=${fatorConv}`);
            
            if(unit === 'CX'){
              totalCxFromItems += qtd;
              totalKgFromItems += qtd * fatorConv; // CX * kg_por_cx = kg_total
            } else if(unit === 'KG'){
              totalKgFromItems += qtd;
              totalCxFromItems += (fatorConv > 0 ? qtd / fatorConv : 0); // kg / kg_por_cx = cx
              console.log(`[MODAL] Convertendo KG→CX: ${qtd}kg ÷ ${fatorConv} = ${qtd / fatorConv}cx`);
            }
          });
          
          console.log('[MODAL] Totais calculados - CX:', totalCxFromItems, 'KG:', totalKgFromItems);
          
          // Classificáveis: exibir RESUMO CONSOLIDADO por FABRICANTE (não detalhar Extra/Médio)
          let totalVlrClassif = 0;  // 🔥 Declarar ANTES do bloco if
          
          if(classifs.length){
            // Agrupar por FABRICANTE e somar valores
            const fabricantesMap = {};
            
            classifs.forEach((r) => {
              // Usar FABRICANTE se disponível, senão extrair nome base do produto
              let fabricante = r.fabricante;
              
              if (!fabricante || fabricante.trim() === '') {
                // Extrair nome do produto removendo EXTRA, MÉDIO, MEDIO, etc
                const produtoNome = (r.produto || '').toUpperCase();
                fabricante = produtoNome
                  .replace(/\s+(EXTRA|MEDIO|MÉDIO|MEDIA|MÉDIA)\s*$/i, '')
                  .replace(/\s+(EXTRA|MEDIO|MÉDIO|MEDIA|MÉDIA)\s+/i, ' ')
                  .trim();
                
                // Se ainda estiver vazio, usar o nome completo
                if (!fabricante) {
                  fabricante = r.produto || 'Produto';
                }
              }
              
              if (!fabricantesMap[fabricante]) {
                fabricantesMap[fabricante] = {
                  fabricante: fabricante,
                  qtdKg: 0,
                  qtdCx: 0,
                  vlrtot: 0,
                  items: []
                };
              }
              
              const unit = ((r.codvol || '') + '').toUpperCase();
              const fatorItem = r.fator_conversao;
              const fatorConv = (fatorItem != null && Number(fatorItem) > 0) ? Number(fatorItem) : fatorConversaoPedido;
              let qtdEntrada = Number(r.qtdneg || 0);
              let qtdKg = qtdEntrada;
              let qtdCx = 0;
              
              if(unit === 'CX'){
                qtdCx = qtdEntrada;
                qtdKg = qtdEntrada * fatorConv;
              }else if(unit === 'KG'){
                qtdKg = qtdEntrada;
                qtdCx = fatorConv > 0 ? qtdEntrada / fatorConv : 0;
              }
              
              fabricantesMap[fabricante].qtdKg += qtdKg;
              fabricantesMap[fabricante].qtdCx += qtdCx;
              fabricantesMap[fabricante].vlrtot += Number(r.vlrtot || 0);
              fabricantesMap[fabricante].items.push(r);
            });
            
            // 💰 CALCULAR TOTAL DOS CLASSIFICÁVEIS ANTES de gerar HTML
            Object.values(fabricantesMap).forEach(fab => {
              totalVlrClassif += fab.vlrtot;
            });
            
            console.log('[MODAL] 💰 Total Classificáveis calculado:', totalVlrClassif);
            
            // Gerar HTML do resumo consolidado
            const classRowsHtml = Object.values(fabricantesMap).map((fab) => {
              const prod = fab.fabricante;
              const qtdKg = fab.qtdKg;
              const qtdCx = fab.qtdCx;
              const vlrtot = fab.vlrtot;
              
              const qtdeDisplay = `<div style="line-height:1.3;">
                <div style="font-size:.85rem; color:#334155;">${fmtQty(qtdKg)}<span style="color:#64748b; font-size:.7rem; margin-left:2px;">kg</span></div>
                <div style="font-size:.8rem; color:#64748b;">${fmtQty(qtdCx)}<span style="color:#94a3b8; font-size:.7rem; margin-left:2px;">cx</span></div>
              </div>`;
              
              // Calcular preço médio
              const precoKg = (vlrtot > 0 && qtdKg > 0) ? (vlrtot / qtdKg) : 0;
              const precoCx = (vlrtot > 0 && qtdCx > 0) ? (vlrtot / qtdCx) : 0;
              
              let vlrUnitDisplay = '—';
              if(precoKg > 0 || precoCx > 0){
                vlrUnitDisplay = `<div style="line-height:1.3;">
                  <div style="font-size:.85rem; color:#334155;">${precoKg > 0 ? fmtMoney(precoKg) : '—'}<span style="color:#64748b; font-size:.7rem;">/kg</span></div>
                  <div style="font-size:12.8px; color:#64748b;">${precoCx > 0 ? fmtMoney(precoCx) : '—'}<span style="color:#94a3b8; font-size:.7rem;">/cx</span></div>
                </div>`;
              }
              
              const statusOk = vlrtot > 0;
              const status = statusOk
                ? `<span title="OK" style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#16a34a;"></span>`
                : `<span title="Pendente" style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#dc2626;"></span>`;
              
              // Link para abrir o primeiro item do fabricante
              const primeiroItem = fab.items[0];
              const nunItem = Number(primeiroItem.nunota || nunota);
              const seqItem = Number(primeiroItem.sequencia || 0);
              
              const abrir = (nunItem && seqItem) ? `
                <a class="eye-open" href="/sankhya/comercial/?sel_nunota=${nunItem}&sel_seq=${seqItem}" target="_blank" rel="noopener" data-nun="${nunItem}" data-seq="${seqItem}" style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;color:#94a3b8;text-decoration:none;">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                  </svg>
                </a>` : '';
              
              return `
                <tr data-fabricante="${prod}">
                  <td title="${prod.replace(/\"/g,'&quot;')}" style="padding:6px 8px; border-bottom:1px solid #e5e7eb;">${prod}</td>
                  <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${qtdeDisplay}</td>
                  <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${vlrUnitDisplay}</td>
                  <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${vlrtot > 0 ? fmtMoney(vlrtot) : '—'}</td>
                  <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:left;">${status}</td>
                  <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${abrir}</td>
                </tr>`;
            }).join('');
            
            els.classBody.innerHTML = classRowsHtml;
          }else{
            els.classBody.innerHTML = '<tr><td colspan="6" style="padding:8px; color:#64748b;">—</td></tr>';
          }
          // Não Classificáveis: com preço
          if(nclass.length){
            els.outrosBody.innerHTML = nclass.map((r, idx)=>{
              const prod = r.produto||'';
              const unit = ((r.codvol||'')+'').toUpperCase();
              const q = Number(r.qtdneg||0);
              let qBase = r.qtdneg_base;
              if(qBase === undefined || qBase === null){
                const fatorCalc = Number(r.fator_conversao || 0);
                qBase = fatorCalc > 0 ? q * fatorCalc : q;
              }
              qBase = Number(qBase);
              if(!Number.isFinite(qBase)){
                qBase = 0;
              }
              const id = `vop_${idx}_${Date.now()}`;
              const vlrtot = Number(r.vlrtot||0) || 0;
              // Calcular preço por unidade (CX) = VLRTOT / QTDNEG
              const preco = (q > 0 && vlrtot > 0) ? (vlrtot / q) : 0;
              const total = vlrtot;
              const codprod = Number(r.codprod||0);
              const lote = String(r.codagregacao||r.lote||'');
              return `<tr data-idx="${idx}" data-q="${q}" data-q-base="${qBase}" data-unit="${unit}" data-nun="${Number(r.nunota||0)}" data-seq="${Number(r.sequencia||0)}" data-codprod="${codprod}" data-lote="${lote}">
                <td title="${prod.replace(/\"/g,'&quot;')}" style="padding:6px 8px; border-bottom:1px solid #e5e7eb;">${prod}</td>
                <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${fmtQty(q)}${unit?`<span style='color:#64748b; font-size:.72rem; margin-left:2px;'>${unit.toLowerCase()}</span>`:''}</td>
                <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">
                  <div contenteditable="true" class="vop-price" data-idx="${idx}" id="${id}" style="outline:none; min-width:90px; display:inline-block; text-align:right; font-size:.85rem; color:#374151;">${preco>0 ? fmtMoney(preco) : '<span style="color:#94a3b8;">R$ 0,00</span>'}</div>
                </td>
                <td class="vop-total" style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${total>0 ? fmtMoney(total) : '—'}</td>
              </tr>`;
            }).join('');
          }else{
            els.outrosBody.innerHTML = '<tr><td colspan="4" style="padding:8px; color:#64748b;">—</td></tr>';
          }
          
          // 💰 Calcular e atualizar Total do Vale
          let totalVlrNaoClassif = 0;
          nclass.forEach(r => {
            const vlr = Number(r.vlrtot || 0);
            totalVlrNaoClassif += vlr;
            console.log('[MODAL] 💰 Item Não Classificável:', r.produto, 'VLRTOT:', vlr);
          });
          
          const totalGeral = totalVlrClassif + totalVlrNaoClassif;
          console.log('[MODAL] 💰 ========== TOTAIS FINAIS ==========');
          console.log('[MODAL] 💰 Classificáveis:', totalVlrClassif);
          console.log('[MODAL] 💰 Não Classificáveis:', totalVlrNaoClassif);
          console.log('[MODAL] 💰 TOTAL GERAL:', totalGeral);
          console.log('[MODAL] 💰 =====================================');
          
          if(els.totalEl){
            const textoFormatado = fmtMoney(totalGeral);
            console.log('[MODAL] 💰 Atualizando display com:', textoFormatado);
            els.totalEl.innerHTML = textoFormatado;  // Usar innerHTML ao invés de textContent
            // Armazenar o total original para cálculo do INSS
            els.totalEl.setAttribute('data-total-original', totalGeral);
            // Aplicar desconto INSS após garantir que modal está visível
            setTimeout(() => {
              if(typeof window.__aplicarDescontoINSS === 'function'){
                window.__aplicarDescontoINSS();
              }
            const calcNaoClassifMetrics = (item)=>{
              const q = Number(item?.qtdneg || 0);
              const vlrtotRaw = Number(item?.vlrtot || 0);
              const precoInicial = Number(item?.preco_inicial || 0);
              let preco = (Number.isFinite(precoInicial) && precoInicial > 0) ? precoInicial : 0;
              if(!(preco > 0)){
                const fallback = (q > 0 && vlrtotRaw > 0) ? (vlrtotRaw / q) : 0;
                if(Number.isFinite(fallback) && fallback > 0){
                  preco = fallback;
                }
              }
              preco = Number.isFinite(preco) ? Number(preco.toFixed(6)) : 0;
              const total = (preco > 0 && q > 0)
                ? Number((preco * q).toFixed(2))
                : (Number.isFinite(vlrtotRaw) ? Number(vlrtotRaw.toFixed(2)) : 0);
              return { preco, total, qtd: q, vlrtotRaw };
            };
            }, 0);
          } else {
            console.error('[MODAL] ❌ Elemento totalEl não encontrado!');
          }
          
          // Validar status: habilitar GERAR VALE apenas se todos classificáveis tiverem status verde (VLRTOT > 0)
          if(els.btnGerarVale){
            const todosVerdes = classifs.every(r=> Number(r.vlrtot||0) > 0);
            if(todosVerdes){
              els.btnGerarVale.disabled = false;
              els.btnGerarVale.style.opacity = '1';
              els.btnGerarVale.style.cursor = 'pointer';
              els.btnGerarVale.title = '';
            }else{
              els.btnGerarVale.disabled = true;
                const metrics = calcNaoClassifMetrics(r);
                r.__calc_nao_classif = metrics;
                const preco = metrics.preco;
                const total = metrics.total;
          }
          
          const t3 = performance.now();
          console.log(`[MODAL] ⚡ Tabelas renderizadas em ${(t3-t2).toFixed(0)}ms`);
          
          // 🔥 Verificar estado do vale (NUFIN, NURENEG, VLRBAIXA)
          const nufinBadge = document.getElementById('valeResumoNufinBadge');
          const nufinNum = document.getElementById('valeResumoNufinNum');
          const btnFaturar = document.getElementById('valeResumoFaturar');
          const btnDesfaturar = document.getElementById('valeResumoDesfaturar');
          const statusBanner = document.getElementById('valeResumoStatusBanner');
          const statusBannerFaturado = document.getElementById('statusBannerFaturado');
          const statusBannerBloqueado = document.getElementById('statusBannerBloqueado');
          const bannerMotivoBloqueio = document.getElementById('bannerMotivoBloqueio');
          const marcaDagua = document.getElementById('modalMarcaDagua');
          
          // Buscar dados do primeiro item (todos têm os mesmos dados financeiros)
          const primeiroItem = rows.length > 0 ? rows[0] : null;
              const baseMetrics = r.__calc_nao_classif || calcNaoClassifMetrics(r);
              const vlr = Number(baseMetrics?.total || 0);
              totalVlrNaoClassif += vlr;
              console.log('[MODAL] 💰 Item Não Classificável:', r.produto, 'Total exibido:', vlr, 'VLRTOT original:', r.vlrtot);
          const bloqueado = primeiroItem?.bloqueado_financeiro || false;
          
          console.log('[MODAL] Estado Financeiro:', { 
            nufin: nufinExistente, 
            nureneg, 
            vlrbaixa, 
            bloqueado 
          });
          
          // Resetar todos os elementos
          if(statusBanner) statusBanner.style.display = 'none';
          if(statusBannerFaturado) statusBannerFaturado.style.display = 'none';
          if(statusBannerBloqueado) statusBannerBloqueado.style.display = 'none';
          if(marcaDagua) marcaDagua.style.display = 'none';
          if(nufinBadge) nufinBadge.style.display = 'none';
          if(btnFaturar) btnFaturar.style.display = 'inline-block';
          if(btnDesfaturar) btnDesfaturar.style.display = 'none';
          
          // ESTADO 1: Não faturado (sem NUFIN)
          if(!nufinExistente){
            console.log('[MODAL] Estado: NÃO FATURADO');
            // Botões: FATURAR visível, DESFATURAR oculto
            if(btnFaturar){
              btnFaturar.style.display = 'inline-block';
              btnFaturar.disabled = false;
              btnFaturar.style.opacity = '1';
              btnFaturar.style.cursor = 'pointer';
              btnFaturar.style.background = '#fff';
              btnFaturar.style.borderColor = '#16a34a';
              btnFaturar.textContent = 'FATURAR';
            }
            // Habilitar checkbox INSS
            const checkboxINSS = document.getElementById('valeDescontaINSS');
            if(checkboxINSS){
              checkboxINSS.disabled = false;
              checkboxINSS.style.cursor = 'pointer';
              checkboxINSS.style.opacity = '1';
            }
            // Campos editáveis (padrão, sem bloqueios)
          }
          // ESTADO 2: Faturado livre (tem NUFIN, mas sem NURENEG/VLRBAIXA)
          else if(nufinExistente && !bloqueado){
            console.log('[MODAL] Estado: FATURADO LIVRE (pode desfaturar)');
            
            // Mostrar badge NUFIN
            if(nufinBadge){
              nufinBadge.style.display = 'inline-block';
              if(nufinNum) nufinNum.textContent = String(nufinExistente);
            }
            
            // Banner verde REMOVIDO (conforme solicitação)
            // if(statusBanner) statusBanner.style.display = 'block';
            // if(statusBannerFaturado){
            //   statusBannerFaturado.style.display = 'block';
            // }
            
            // Mostrar marca d'água sutil
            if(marcaDagua) marcaDagua.style.display = 'block';
            
            // Botões: FATURAR oculto, DESFATURAR visível
            if(btnFaturar) btnFaturar.style.display = 'none';
            if(btnDesfaturar){
              btnDesfaturar.style.display = 'inline-block';
              btnDesfaturar.disabled = false;
            }
            
            // 🔒 Desabilitar checkbox INSS quando faturado
            const checkboxINSS = document.getElementById('valeDescontaINSS');
            if(checkboxINSS){
              checkboxINSS.disabled = true;
              checkboxINSS.style.cursor = 'not-allowed';
              checkboxINSS.style.opacity = '0.5';
            }
            
            // 🔒 Bloquear TODOS os campos (usando cache para melhor performance)
            const editables = els.outrosBody.querySelectorAll('[contenteditable]');
            for(let i = 0; i < editables.length; i++){
              const inp = editables[i];
              inp.setAttribute('contenteditable', 'false');
              inp.style.cssText = 'opacity:0.6;cursor:not-allowed;background:#f3f4f6;pointer-events:none;user-select:none;';
              inp.title = 'Não é possível editar vale faturado';
            }
          }
          // ESTADO 3 ou 4: Bloqueado (tem NURENEG ou VLRBAIXA)
          else if(bloqueado){
            console.log('[MODAL] Estado: BLOQUEADO pelo Financeiro');
            
            // Mostrar badge NUFIN
            if(nufinBadge){
              nufinBadge.style.display = 'inline-block';
              if(nufinNum) nufinNum.textContent = String(nufinExistente);
            }
            
            // Mostrar banner vermelho
            if(statusBanner) statusBanner.style.display = 'block';
            if(statusBannerBloqueado){
              statusBannerBloqueado.style.display = 'block';
              if(bannerMotivoBloqueio){
                bannerMotivoBloqueio.textContent = 'BLOQUEADO - Existe negociação com o setor FINANCEIRO!!!';
              }
            }

            if(marcaDagua){
              marcaDagua.style.display = 'block';
            }
            
            // Botões: Ambos ocultos
            if(btnFaturar) btnFaturar.style.display = 'none';
            if(btnDesfaturar) btnDesfaturar.style.display = 'none';
            
            // 🔒 Desabilitar checkbox INSS quando bloqueado
            const checkboxINSS = document.getElementById('valeDescontaINSS');
            if(checkboxINSS){
              checkboxINSS.disabled = true;
              checkboxINSS.style.cursor = 'not-allowed';
              checkboxINSS.style.opacity = '0.5';
            }
            
            // 🔒 Bloquear TODOS os campos (usando cache para melhor performance)
            const editables = els.outrosBody.querySelectorAll('[contenteditable]');
            for(let i = 0; i < editables.length; i++){
              const inp = editables[i];
              inp.setAttribute('contenteditable', 'false');
              inp.style.cssText = 'opacity:0.6;cursor:not-allowed;background:#f3f4f6;pointer-events:none;user-select:none;';
              inp.title = 'Vale bloqueado pelo Financeiro';
            }
          }
          
          // 🔥 Bloquear botões "Zerar Negociação" e "Salvar" se vale estiver faturado
          const btnResetMain = document.getElementById('dist-btn-reset');
          const btnSaveMain = document.getElementById('dist-btn-save');
          const lockIcon = document.getElementById('lockIconContainer');
          
          if(nufinExistente){
            // Vale faturado - bloquear botões do painel principal
            console.log('[MODAL] Vale faturado - bloqueando botões Zerar e Salvar');
            
            // Mostrar ícone de cadeado
            if(lockIcon) lockIcon.style.display = 'inline-block';
            
            if(btnResetMain){
              btnResetMain.disabled = true;
              btnResetMain.style.opacity = '0.3';
              btnResetMain.style.cursor = 'not-allowed';
              btnResetMain.title = 'Não é possível zerar negociação de vale faturado';
            }
            
            if(btnSaveMain){
              btnSaveMain.disabled = true;
              btnSaveMain.style.opacity = '0.3';
              btnSaveMain.style.cursor = 'not-allowed';
              btnSaveMain.title = 'Não é possível salvar vale faturado';
            }
          } else {
            // Vale não faturado - reativar botões (se não estiver em modo projeção)
            console.log('[MODAL] Vale não faturado - verificando estado dos botões');
            
            // Ocultar ícone de cadeado
            if(lockIcon) lockIcon.style.display = 'none';
            
            // Respeitar o estado do toggle (projeção vs real)
            const modoAtual = window.__VALOR_TOTAL_MODE || 'projecao';
            const podeEditar = modoAtual === 'real';
            
            if(btnResetMain){
              btnResetMain.disabled = !podeEditar;
              btnResetMain.style.opacity = podeEditar ? '0.8' : '0.4';
              btnResetMain.style.cursor = podeEditar ? 'pointer' : 'not-allowed';
              btnResetMain.title = podeEditar ? '' : 'Disponível apenas no modo Real';
            }
            
            if(btnSaveMain){
              btnSaveMain.disabled = !podeEditar;
              btnSaveMain.style.opacity = podeEditar ? '0.85' : '0.4';
              btnSaveMain.style.cursor = podeEditar ? 'pointer' : 'not-allowed';
              btnSaveMain.title = podeEditar ? '' : 'Disponível apenas no modo Real';
            }
          }
          
          // 🚀 Ocultar spinner e mostrar modal
          if(els.spinner) els.spinner.style.display = 'none';
          els.modal.style.display = 'flex';
          // Tooltip de distribuição no ícone olho (usa estado corrente de distribuição)
          const ensureDistTooltip = () => {
            let tip = document.getElementById('distEyeTooltip');
            if(!tip){
              tip = document.createElement('div');
              tip.id = 'distEyeTooltip';
              tip.style.position = 'fixed';
              tip.style.display = 'none';
              tip.style.zIndex = '3000';
              tip.style.background = '#fff';
              tip.style.border = '1px solid #e5e7eb';
              tip.style.borderRadius = '10px';
              tip.style.boxShadow = '0 8px 28px rgba(2,6,23,.15)';
              tip.style.padding = '8px 10px';
              tip.style.minWidth = '260px';
              document.body.appendChild(tip);
            }
            return tip;
          };
          const renderTipContent = () => {
            const st = window.__DIST_STATE || {};
            const ex = (st.categorias && st.categorias.extra) || {};
            const md = (st.categorias && st.categorias.medio) || {};
            const hasData = [ex.kg, ex.cxEq, ex.custoKg, ex.custoCx, ex.custoTotal, md.kg, md.cxEq, md.custoKg, md.custoCx, md.custoTotal]
              .some(v => Number(v||0) > 0);
            if(!hasData){
              return `<div style="padding:6px 8px; color:#64748b;">Sem dados!</div>`;
            }
            const fmtNum = (n, d=0) => Number(n||0).toLocaleString('pt-BR',{ maximumFractionDigits: d });
            const fmtMoney = (n) => new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(n||0));
            const row = (label, kg, cx, kgCost, cxCost, total) => `
              <div style="display:grid;grid-template-columns:1fr auto;gap:6px;margin:4px 0">
                <div style="font-weight:700;color:#0f172a">${label}</div>
                <div style="text-align:right;color:#475569">${fmtNum(kg,0)} kg · ${fmtNum(cx,0)} cx</div>
                <div style="grid-column:1 / -1;display:flex;justify-content:space-between;color:#64748b;font-size:.85em">
                  <span>Custo/kg</span><span>${fmtMoney(kgCost)}</span>
                </div>
                <div style="grid-column:1 / -1;display:flex;justify-content:space-between;color:#64748b;font-size:.85em">
                  <span>Custo/cx</span><span>${fmtMoney(cxCost)}</span>
                </div>
                <div style="grid-column:1 / -1;display:flex;justify-content:space-between;font-weight:700;color:#0a3392">
                  <span>Total</span><span>${fmtMoney(total)}</span>
                </div>
              </div>`;
            return `
              <div style="font-size:.9rem">
                ${row('EXTRA', ex.kg, ex.cxEq, ex.custoKg, ex.custoCx, ex.custoTotal)}
                <div style="border-top:1px solid #e5e7eb;margin:6px 0"></div>
                ${row('MÉDIO', md.kg, md.cxEq, md.custoKg, md.custoCx, md.custoTotal)}
              </div>`;
          };
          const tip = ensureDistTooltip();
          const attachEyeHover = (container) => {
            const eyes = container.querySelectorAll('a.eye-open');
            for(let i = 0; i < eyes.length; i++){
              const a = eyes[i];
              a.addEventListener('mouseenter', (e)=>{
                tip.innerHTML = renderTipContent();
                tip.style.display = 'block';
                const r = a.getBoundingClientRect();
                tip.style.left = (r.right + 8) + 'px';
                tip.style.top = Math.max(8, r.top - 6) + 'px';
              });
              a.addEventListener('mouseleave', ()=>{ tip.style.display = 'none'; tip.innerHTML = ''; });
            }
          };
          attachEyeHover(els.classBody);
          
          const t4 = performance.now();
          console.log(`[MODAL] ⚡ Event listeners em ${(t4-t3).toFixed(0)}ms`);
          
          // cálculo total
          const parsePT = (text) => {
            if(!text) return NaN;
            const cleaned = text.toString().trim().replace(/[^0-9,\.]/g, '').replace(/\.(?=\d{3}(\D|$))/g, '').replace(',', '.');
            const n = Number(cleaned); return isFinite(n) ? n : NaN;
          };
          function recompute(){
            let sum = 0;
            let classTotal = 0;
            let outrosTotal = 0;
            
            // 💰 Soma dos classificáveis: usar o array de dados diretamente
            // (não usar as linhas HTML porque estão agrupadas por FABRICANTE)
            classifs.forEach(item => {
              classTotal += Number(item.vlrtot || 0);
            });
            console.log('[RECOMPUTE] 💰 Classificáveis somados:', classifs.length, 'itens, total:', classTotal);
            
            // soma dos não classificáveis: calcular dinamicamente
            const trs = Array.from(els.outrosBody.querySelectorAll('tr'));
            trs.forEach((tr, i)=>{
              const q = Number(tr.getAttribute('data-q')||'0');
              const editableDiv = tr.querySelector('.vop-price');
              const p = parsePT(editableDiv?.textContent||'');
              const precoBaseAttr = parseFloat(tr.getAttribute('data-preco-base') || '0');
              const totalBaseAttr = parseFloat(tr.getAttribute('data-total-base') || '0');
              const precoBase = Number.isFinite(precoBaseAttr) ? Number(precoBaseAttr.toFixed(6)) : 0;
              const precoDigitado = Number.isFinite(p) ? Number(p.toFixed(6)) : 0;
              const precoAtual = precoDigitado > 0 ? precoDigitado : (precoBase > 0 ? precoBase : 0);
              let t = 0;
              if(Number.isFinite(q) && q > 0 && precoAtual > 0){
                t = Number((precoAtual * q).toFixed(2));
              } else if(Number.isFinite(totalBaseAttr) && totalBaseAttr > 0){
                t = Number((totalBaseAttr).toFixed(2));
              }
              const cell = tr.querySelector('.vop-total');
              if(!isNaN(precoAtual) && precoAtual > 0){
                tr.setAttribute('data-preco-edit', precoAtual.toFixed(6));
              } else {
                tr.removeAttribute('data-preco-edit');
              }
              if(!isNaN(t) && t > 0){
                tr.setAttribute('data-total-edit', t.toFixed(2));
              } else {
                tr.removeAttribute('data-total-edit');
              }
              if(cell) cell.innerHTML = fmtMoney(t > 0 ? t : 0);
              outrosTotal += (Number.isFinite(t) ? t : 0);
            });
            
            sum = classTotal + outrosTotal;
            console.log('[RECOMPUTE] Classificáveis:', fmtMoney(classTotal), 'Outros:', fmtMoney(outrosTotal), 'TOTAL:', fmtMoney(sum));
            els.totalEl.innerHTML = fmtMoney(sum);
            
            // 🔄 Atualizar o valor bruto original e recalcular INSS
            els.totalEl.setAttribute('data-total-original', sum);
            if(typeof window.__aplicarDescontoINSS === 'function') {
              window.__aplicarDescontoINSS();
            }
            
            // NÃO atualizar o card Distribuição quando estamos no modal de faturamento
            // O modal deve apenas calcular seu próprio total, não interferir nos cards externos
          }
          els.outrosBody.addEventListener('input', (ev)=>{ 
            if(ev.target && (ev.target.classList.contains('vop-price') || ev.target.classList.contains('vop-preco-inicial'))) {
              // 🔒 BLOQUEAR se vale faturado
              if(ev.target.getAttribute('contenteditable') === 'false'){
                ev.preventDefault();
                ev.stopPropagation();
                return false;
              }
              recompute(); 
            }
          });
          els.outrosBody.addEventListener('beforeinput', (ev)=>{
            if(ev.target && (ev.target.classList.contains('vop-price') || ev.target.classList.contains('vop-preco-inicial'))){
              // 🔒 BLOQUEAR edição se vale faturado
              if(ev.target.getAttribute('contenteditable') === 'false'){
                console.log('[MODAL] ⛔ Edição bloqueada - vale faturado');
                ev.preventDefault();
                return false;
              }
            }
          }, true);
          els.outrosBody.addEventListener('paste', (ev)=>{
            if(ev.target && (ev.target.classList.contains('vop-price') || ev.target.classList.contains('vop-preco-inicial'))){
              // 🔒 BLOQUEAR paste se vale faturado
              if(ev.target.getAttribute('contenteditable') === 'false'){
                console.log('[MODAL] ⛔ Paste bloqueado - vale faturado');
                ev.preventDefault();
                return false;
              }
            }
          }, true);
          els.outrosBody.addEventListener('click', (ev)=>{
            // 🔒 Alertar usuário se tentar clicar em campo bloqueado
            const target = ev.target;
            if(target && (target.classList.contains('vop-price') || target.classList.contains('vop-preco-inicial'))){
              if(target.getAttribute('contenteditable') === 'false'){
                console.log('[MODAL] ⛔ Clique bloqueado - vale faturado');
                // Mostrar feedback visual sutil (sem alert irritante)
                target.style.animation = 'shake 0.3s';
                setTimeout(() => { target.style.animation = ''; }, 300);
              }
            }
          });
          els.outrosBody.addEventListener('blur', (ev)=>{
            if(ev.target && ev.target.classList.contains('vop-price')){
              // 🔒 BLOQUEAR se vale faturado
              if(ev.target.getAttribute('contenteditable') === 'false'){
                return false;
              }
              // Reformatar ao perder foco
              const editableDiv = ev.target;
              const val = parsePT(editableDiv.textContent||'');
              if(val>0){
                editableDiv.innerHTML = fmtMoney(val);
              }
            }
          }, true);
          
          const t5 = performance.now();
          console.log(`[MODAL] ⚡ Event listeners registrados em ${(t5-t4).toFixed(0)}ms`);
          
          // ========================================
          // CLASSIFICÁVEIS: Event listeners REMOVIDOS
          // Tabela agora é somente leitura (display vlrKg/vlrCx)
          // ========================================
          
          /* COMENTADO: Classificáveis não são mais editáveis
          classBody.addEventListener('input', (ev)=>{ 
            if(ev.target && ev.target.classList.contains('vcl-preco-inicial')) {
              recompute(); 
            }
          });
          
          classBody.addEventListener('focus', (ev)=>{
            if(ev.target && ev.target.classList.contains('vcl-preco-inicial')){
              const editableDiv = ev.target;
              setTimeout(() => {
                const range = document.createRange();
                range.selectNodeContents(editableDiv);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
              }, 0);
            }
          }, true);
          
          classBody.addEventListener('keydown', (ev)=>{
            if(ev.target && ev.target.classList.contains('vcl-preco-inicial')){
              if(ev.key === 'Enter'){
                ev.preventDefault();
                ev.target.blur();
                const currentTr = ev.target.closest('tr');
                if(currentTr){
                  let nextTr = currentTr.nextElementSibling;
                  if(nextTr){
                    const nextField = nextTr.querySelector('.vcl-preco-inicial');
                    if(nextField){
                      setTimeout(() => nextField.focus(), 50);
                    }
                  }
                }
              }
            }
          }, true);
          
          classBody.addEventListener('blur', async (ev)=>{
            if(ev.target && ev.target.classList.contains('vcl-preco-inicial')){
              const editableDiv = ev.target;
              const tr = editableDiv.closest('tr');
              if(!tr) return;
              
              const nunota_val = Number(tr.getAttribute('data-nun') || 0);
              const seq_val = Number(tr.getAttribute('data-seq') || 0);
              const val = parsePT(editableDiv.textContent||'');
              
              if(val>0){
                editableDiv.innerHTML = fmtMoney(val);
                
                if(nunota_val && seq_val){
                  const itemData = window.__COM_LIST_ROWS?.find(r => 
                    Number(r.nunota||0) === nunota_val && 
                    Number(r.sequencia||0) === seq_val
                  );
                  
                  if(!itemData){
                    console.error('[MODAL AUTO-SAVE] Item não encontrado no cache');
                    return;
                  }
                  
                  const codprod = Number(itemData.codprod || 0);
                  const codagregacao = String(itemData.codagregacao || itemData.lote || '');
                  const qtdneg = Number(itemData.qtdneg || 0);
                  
                  if(!codprod || !codagregacao){
                    console.error('[MODAL AUTO-SAVE] CODPROD ou LOTE não disponível');
                    return;
                  }
                  
                  if(qtdneg === 0){
                    console.error('[MODAL AUTO-SAVE] QTDNEG = 0, impossível calcular');
                    alert('Erro: Quantidade não pode ser zero');
                    return;
                  }
                  
                  const vlrtot = val * qtdneg;
                  
                  try{
                    const payload = { 
                      nunota_pedido: nunota_val, 
                      sequencia: seq_val, 
                      codprod: codprod,
                      codagregacao: codagregacao,
                      vlrtot: vlrtot,
                      is_classificavel: true
                    };
                    
                    console.log('[MODAL AUTO-SAVE CLASSIFICÁVEL] Salvando:', payload);
                    
                    const result = await AutoSaveQueue.add(payload);
                    
                    if(result.ok){
                      console.log('[MODAL AUTO-SAVE CLASSIFICÁVEL] ✅ Sucesso - NUNOTA_VALE:', result.nunota_vale, 'VLRNOTA_PEDIDO:', result.vlrnota_pedido, 'VLRUNIT:', result.vlrunit, 'VLRTOT:', vlrtot);
                      
                      if(itemData){
                        itemData.preco_inicial = result.vlrunit;
                        itemData.precobase = result.vlrunit;
                        itemData.vlrunit = result.vlrunit;
                        itemData.vlrtot = vlrtot;
                      }
                      
                      recompute();
                      
                    } else {
                      console.error('[MODAL AUTO-SAVE CLASSIFICÁVEL] ❌ Erro:', result.error || 'Erro desconhecido');
                      alert('Erro ao salvar: ' + (result.error || 'Erro desconhecido'));
                    }
                  } catch(err){
                    console.error('[MODAL AUTO-SAVE CLASSIFICÁVEL] ⚠️ Exceção:', err);
                    alert('Erro ao salvar: ' + err.message);
                  }
                }
              } else {
                editableDiv.innerHTML = '<span style="color:#94a3b8;">R$ 0,00</span>';
              }
            }
          }, true);
          */
          
          // Event listeners para itens NÃO CLASSIFICÁVEIS (salvar VLRUNIT no banco)
          els.outrosBody.addEventListener('focus', (ev)=>{
            if(ev.target && ev.target.classList.contains('vop-price')){
              const editableDiv = ev.target;
              
              // Sempre selecionar todo o conteúdo (funciona tanto para valores zerados quanto preenchidos)
              setTimeout(() => {
                const range = document.createRange();
                range.selectNodeContents(editableDiv);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
              }, 0);
            }
          }, true);
          
          els.outrosBody.addEventListener('keydown', (ev)=>{
            if(ev.target && ev.target.classList.contains('vop-price')){
              if(ev.key === 'Enter'){
                ev.preventDefault();
                ev.target.blur(); // Aciona o salvamento
                
                // Encontrar próximo campo editável
                const currentTr = ev.target.closest('tr');
                if(currentTr){
                  let nextTr = currentTr.nextElementSibling;
                  if(nextTr){
                    const nextField = nextTr.querySelector('.vop-price');
                    if(nextField){
                      setTimeout(() => nextField.focus(), 50);
                    }
                  }
                }
              }
            }
          }, true);
          
          els.outrosBody.addEventListener('input', (ev)=>{ 
            if(ev.target && ev.target.classList.contains('vop-price')) {
              // Atualizar Total dinamicamente
              const tr = ev.target.closest('tr');
              if(tr){
                const qtd = Number(tr.getAttribute('data-q') || 0);
                const val = parsePT(ev.target.textContent || '');
                const totalCell = tr.querySelector('.vop-total');
                if(totalCell && val > 0){
                  const total = qtd * val;
                  totalCell.innerHTML = fmtMoney(total);
                }
              }
              recompute(); 
            }
          });
          
          els.outrosBody.addEventListener('blur', async (ev)=>{
            if(ev.target && ev.target.classList.contains('vop-price')){
              // 🔒 BLOQUEAR se vale faturado
              if(ev.target.getAttribute('contenteditable') === 'false'){
                console.log('[MODAL AUTO-SAVE] ⛔ Bloqueado - vale faturado');
                return false;
              }
              
              const editableDiv = ev.target;
              const tr = editableDiv.closest('tr');
              if(!tr) return;
              
              const nunota_val = Number(tr.getAttribute('data-nun') || 0);
              const seq_val = Number(tr.getAttribute('data-seq') || 0);
              const qtd = Number(tr.getAttribute('data-q') || 0);
              const val = parsePT(editableDiv.textContent || '');
              
              // Reformatar ao perder foco
              if(val > 0){
                editableDiv.innerHTML = fmtMoney(val);
                
                // Auto-salvar usando novo endpoint (NÃO CLASSIFICÁVEL)
                if(nunota_val && seq_val){
                  // 🔥 CRÍTICO: Buscar dados da própria TR (data-attributes) ao invés do cache
                  // Isso funciona mesmo quando o modal mostra itens do VALE que não estão no cache
                  const codprod = Number(tr.getAttribute('data-codprod') || 0);
                  const codagregacao = String(tr.getAttribute('data-lote') || '');
                  const qtdneg_item = Number(tr.getAttribute('data-q') || 0);
                  
                  // Log de diagnóstico
                  console.log('[MODAL AUTO-SAVE NÃO CLASSIFICÁVEL] Dados da TR:', {
                    nunota: nunota_val,
                    sequencia: seq_val,
                    codprod: codprod,
                    lote: codagregacao,
                    qtdneg: qtdneg_item,
                    preco_digitado: val
                  });
                  
                  if(!codprod){
                    console.error('[MODAL AUTO-SAVE] CODPROD não disponível');
                    alert('Erro: Código do produto não identificado');
                    return;
                  }
                  
                  if(!codagregacao){
                    console.warn('[MODAL AUTO-SAVE] ⚠️ LOTE vazio, continuando mesmo assim');
                  }
                  
                  if(qtdneg_item === 0){
                    console.error('[MODAL AUTO-SAVE] QTDNEG = 0, impossível calcular');
                    alert('Erro: Quantidade não pode ser zero');
                    return;
                  }
                  
                  // Calcular VLRTOT a partir do valor digitado (que é tratado como preço unitário)
                  const vlrtot_calculado = val * qtdneg_item;
                  
                  // 🔥 CRÍTICO: Usar NUNOTA do PEDIDO (não do vale) para atualizar corretamente
                  // Se o modal está mostrando itens do VALE, data-nun terá o NUNOTA do vale
                  // Precisamos buscar o NUNOTA do PEDIDO que foi armazenado globalmente
                  const nunota_pedido_real = window.__CURRENT_PEDIDO_NUNOTA || nunota_val;
                  
                  // Buscar sequencia do item no PEDIDO (pode ser diferente da sequencia no vale)
                  // Para isso, precisamos do mapeamento codprod+lote -> sequencia do pedido
                  let seq_pedido = seq_val; // default: usar mesma sequencia
                  
                  // Tentar encontrar item correspondente no cache do pedido
                  if(window.__COM_LIST_ROWS){
                    const itemPedido = window.__COM_LIST_ROWS.find(r => 
                      Number(r.nunota||0) === Number(nunota_pedido_real||0) && 
                      Number(r.codprod||0) === codprod &&
                      String(r.codagregacao||r.lote||'').toUpperCase() === codagregacao.toUpperCase()
                    );
                    if(itemPedido){
                      seq_pedido = Number(itemPedido.sequencia || seq_val);
                      console.log('[MODAL AUTO-SAVE] Item encontrado no pedido - SEQ_PEDIDO:', seq_pedido);
                    } else {
                      console.warn('[MODAL AUTO-SAVE] ⚠️ Item não encontrado no pedido, usando SEQ:', seq_val);
                    }
                  }
                  
                  try{
                    const payload = { 
                      nunota_pedido: nunota_pedido_real, 
                      sequencia: seq_pedido, 
                      codprod: codprod,
                      codagregacao: codagregacao,
                      vlrtot: vlrtot_calculado,
                      is_classificavel: false
                    };
                    
                    console.log('[MODAL AUTO-SAVE NÃO CLASSIFICÁVEL] Salvando:', payload);
                    
                    const result = await AutoSaveQueue.add(payload);
                    
                    if(result.ok){
                      console.log('[MODAL AUTO-SAVE NÃO CLASSIFICÁVEL] ✅ Sucesso - NUNOTA_VALE:', result.nunota_vale, 'VLRNOTA_PEDIDO:', result.vlrnota_pedido, 'VLRNOTA_VALE:', result.vlrnota_vale, 'VLRUNIT:', result.vlrunit, 'VLRTOT:', vlrtot_calculado);
                      
                      // Atualizar cache do PEDIDO (não do vale)
                      if(window.__COM_LIST_ROWS){
                        const itemPedido = window.__COM_LIST_ROWS.find(r => 
                          Number(r.nunota||0) === Number(nunota_pedido_real||0) && 
                          Number(r.sequencia||0) === seq_pedido
                        );
                        if(itemPedido){
                          itemPedido.vlrunit = result.vlrunit;
                          itemPedido.vlrtot = vlrtot_calculado;
                          console.log('[MODAL AUTO-SAVE] Cache do PEDIDO atualizado - NUNOTA:', nunota_pedido_real, 'SEQ:', seq_pedido);
                        } else {
                          console.log('[MODAL AUTO-SAVE] Item do pedido não está no cache');
                        }
                      }
                      
                      // Atualizar Total na UI
                      const totalCell = tr.querySelector('.vop-total');
                      if(totalCell){
                        totalCell.innerHTML = fmtMoney(vlrtot_calculado);
                      }
                      
                    } else {
                      console.error('[MODAL AUTO-SAVE NÃO CLASSIFICÁVEL] ❌ Erro:', result.error || 'Erro desconhecido');
                      alert('Erro ao salvar: ' + (result.error || 'Erro desconhecido'));
                    }
                  } catch(err){
                    console.error('[MODAL AUTO-SAVE NÃO CLASSIFICÁVEL] ⚠️ Exceção:', err);
                    alert('Erro ao salvar: ' + err.message);
                  }
                }
              } else {
                editableDiv.innerHTML = '<span style="color:#94a3b8;">R$ 0,00</span>';
              }
            }
          }, true);
          
          recompute();
          // Close handlers
          document.getElementById('valeResumoClose')?.addEventListener('click', ()=>{ 
            els.modal.style.display='none'; 
            window.__GERANDO_VALE = false; // Limpar flag ao fechar
            // Limpar display do vale para não mostrar dados antigos
            const valeEl = document.getElementById('valeResumoVale');
            if(valeEl) valeEl.style.display = 'none';
            console.log('[MODAL] Modal fechado, flag __GERANDO_VALE resetada e dados limpos');
          });
          els.modal.addEventListener('click', (ev)=>{ 
            if(ev.target === els.modal) {
              els.modal.style.display='none'; 
              window.__GERANDO_VALE = false; // Limpar flag ao fechar
              // Limpar display do vale para não mostrar dados antigos
              const valeEl = document.getElementById('valeResumoVale');
              if(valeEl) valeEl.style.display = 'none';
              console.log('[MODAL] Modal fechado (click fora), flag __GERANDO_VALE resetada e dados limpos');
            }
          });

          // Botão de impressão
          // Botão de impressão no rodapé
          document.getElementById('valeResumoFooterPrint')?.addEventListener('click', ()=>{
            printVale();
          });

          // Event listener para o checkbox INSS (função já definida no início)
          document.getElementById('valeDescontaINSS')?.addEventListener('change', async function(){
            window.__aplicarDescontoINSS();
            
            // 💾 Salvar VLROUTROS no backend
            const checkbox = this;
            const nunotaVale = window.__CURRENT_VALE_NUNOTA_TOP13;
            
            if(!nunotaVale){
              console.warn('[INSS SAVE] ⚠️ NUNOTA do vale não encontrado');
              return;
            }
            
            // Calcular valor do desconto INSS
            const totalEl = document.getElementById('valeResumoTotal');
            const totalOriginal = parseFloat(totalEl?.getAttribute('data-total-original') || '0');
            const vlroutros = checkbox.checked ? (totalOriginal * 0.015) : 0;
            
            console.log('[INSS SAVE] 💾 Salvando VLROUTROS:', vlroutros, 'para vale:', nunotaVale);
            
            try {
              const response = await window.__postJSON('/sankhya/comercial/vale/update_vlroutros/', {
                nunota: nunotaVale,
                vlroutros: vlroutros
              });
              
              if(response.ok){
                console.log('[INSS SAVE] ✅ VLROUTROS salvo com sucesso');
                // Atualizar cache local
                if(window.__COM_LIST_ROWS){
                  window.__COM_LIST_ROWS.forEach(row => {
                    if(String(row.nunota) === String(nunotaVale)){
                      row.vlroutros = vlroutros;
                    }
                  });
                }
              } else {
                console.error('[INSS SAVE] ❌ Erro ao salvar VLROUTROS:', response);
                window.showToast('Erro ao salvar desconto INSS', 'error');
              }
            } catch(e){
              console.error('[INSS SAVE] ❌ Exceção ao salvar VLROUTROS:', e);
              window.showToast('Erro ao salvar desconto INSS', 'error');
            }
          });

          // =========================
          // AutoSaveQueue (client-side queue para evitar requisições concorrentes)
          // =========================
          (function(window){
            // � Lote de loading do botão FATURAR durante auto-save
            let pendingSavesCount = 0;
            
            function updateFaturarSpinner(){
              const btn = document.getElementById('valeResumoFaturar');
              if(!btn) return;
              
              if(pendingSavesCount > 0){
                // Mostrar loading e desabilitar botão
                btn.disabled = true;
                btn.style.opacity = '0.6';
                btn.style.cursor = 'not-allowed';
                btn.title = `Salvando alterações... (${pendingSavesCount} pendente${pendingSavesCount > 1 ? 's' : ''})`;
                btn.textContent = '🔄 SALVANDO...';
              } else {
                // Restaurar estado normal
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.style.cursor = 'pointer';
                btn.title = '';
                btn.textContent = 'FATURAR';
              }
            }
            
            const AutoSaveQueue = (function(){
              const queue = [];
              let inFlight = false;
              const RETRIES = 3;

              function sleep(ms){ return new Promise(r=>setTimeout(r, ms)); }

              async function process(){
                if(inFlight) return;
                inFlight = true;
                while(queue.length){
                  const job = queue.shift();
                  try{
                    const res = await window.__postJSON('/sankhya/comercial/modal/auto-save/', job.payload);
                    job.resolve(res);
                    pendingSavesCount--;
                    updateFaturarSpinner();
                  }catch(err){
                    job.attempt = (job.attempt||0) + 1;
                    if(job.attempt <= RETRIES){
                      const backoff = 150 * Math.pow(2, job.attempt);
                      await sleep(backoff);
                      queue.unshift(job);
                    } else {
                      job.reject(err);
                      pendingSavesCount--;
                      updateFaturarSpinner();
                    }
                  }
                }
                inFlight = false;
              }

              return {
                add(payload){
                  pendingSavesCount++;
                  updateFaturarSpinner();
                  return new Promise((resolve, reject) => {
                    queue.push({ payload, resolve, reject, attempt: 0 });
                    // slight debounce to allow quick successive edits to queue
                    setTimeout(process, 30);
                  });
                },
                getPendingCount(){ return pendingSavesCount; }
              };
            })();
            window.AutoSaveQueue = AutoSaveQueue;
          })(window);

          // Salvar/Faturar emit
          // Build payload with sequences for precise updates (inclui preco_inicial para ambas tabelas)
          const buildValeItems = () => {
            const items = [];
            const nunotaPedido = Number(window.__CURRENT_PEDIDO_NUNOTA || nunota || 0);
            const cacheRows = Array.isArray(window.__COM_LIST_ROWS) ? window.__COM_LIST_ROWS : [];

            const pedidoIndex = new Map();
            if(nunotaPedido && cacheRows.length){
              cacheRows.forEach(row => {
                if(Number(row?.nunota || 0) !== nunotaPedido){
                  return;
                }
                const codprod = Number(row?.codprod || 0);
                if(!codprod){
                  return;
                }
                const lote = String(row?.codagregacao || row?.lote || '').trim().toUpperCase();
                const key = `${codprod}#${lote}`;
                if(!pedidoIndex.has(key)){
                  pedidoIndex.set(key, Number(row?.sequencia || 0));
                }
              });
            }

            const resolveSeqForPedido = (tr, seqAttr) => {
              if(!tr){
                return seqAttr;
              }
              const seqOriginal = Number(seqAttr || 0);
              if(!nunotaPedido){
                return seqOriginal;
              }
              const nunotaLinha = Number(tr.getAttribute('data-nun') || 0);
              if(!nunotaLinha || nunotaLinha === nunotaPedido){
                return seqOriginal;
              }
              const codprod = Number(tr.getAttribute('data-codprod') || 0);
              if(!codprod){
                return seqOriginal;
              }
              const lote = String(tr.getAttribute('data-lote') || '').trim().toUpperCase();
              const key = `${codprod}#${lote}`;
              if(pedidoIndex.has(key)){
                const mappedSeq = Number(pedidoIndex.get(key) || 0);
                if(mappedSeq){
                  if(mappedSeq !== seqOriginal){
                  console.log('[FATURAR] 🔄 Mapeando sequência do vale para pedido', {
                    seqVale: seqOriginal,
                    seqPedido: mappedSeq,
                    codprod,
                    lote,
                    nunotaPedido,
                    nunotaVale: nunotaLinha,
                  });
                  }
                  return mappedSeq;
                }
              }
              console.warn('[FATURAR] ⚠️ Sequência do pedido não encontrada; item será ignorado no payload', {
                seqOriginal,
                codprod,
                lote,
                nunotaPedido,
                nunotaLinha,
              });
              return 0;
            };

            // Classificáveis: só preco_inicial (usando contenteditable)
            Array.from(els.classBody.querySelectorAll('tr')).forEach(tr => {
              const rawSeq = Number(tr.getAttribute('data-seq')||'0');
              const seq = resolveSeqForPedido(tr, rawSeq);
              const editableDiv = tr.querySelector('.vcl-preco-inicial');
              const p0 = parsePT(editableDiv?.textContent||'');
              if(seq){
                items.push({
                  sequencia: seq,
                  preco_inicial: isNaN(p0) ? null : p0,
                });
              }
            });

            // Não Classificáveis: preco_inicial (opcional) + preco (VLRUNIT) - usando contenteditable
            Array.from(els.outrosBody.querySelectorAll('tr')).forEach((tr)=>{
              const rawSeq = Number(tr.getAttribute('data-seq')||'0');
              const seq = resolveSeqForPedido(tr, rawSeq);
              const editableDiv = tr.querySelector('.vop-price');
              const p = parsePT(editableDiv?.textContent||'');
              if(seq){
                items.push({
                  sequencia: seq,
                  preco: isNaN(p) ? null : p,
                });
              }
            });
            return items;
          };

          // Remover listener antigo se existir
          const btnGerar = document.getElementById('btnGerarVale');
          if(btnGerar){
            // Clonar e substituir para remover todos os listeners
            const newBtn = btnGerar.cloneNode(true);
            btnGerar.parentNode.replaceChild(newBtn, btnGerar);
            console.log('[MODAL] Event listeners do botão GERAR VALE removidos');
          }

          document.getElementById('btnGerarVale')?.addEventListener('click', async function gerarValeHandler(){
            // ⚠️ PROTEÇÃO: Impedir múltiplas execuções simultâneas
            if(window.__GERANDO_VALE){
              console.warn('[GERAR VALE] ⚠️ Geração já em andamento, ignorando clique duplicado');
              return;
            }
            window.__GERANDO_VALE = true;
            
            // 🔥 CRÍTICO: Ler NUNOTA do atributo data-nunota-atual do botão
            const btn = document.getElementById('btnGerarVale');
            const nunota_atual = btn ? Number(btn.getAttribute('data-nunota-atual') || '0') : 0;
            console.log('[GERAR VALE] NUNOTA lida do botão:', nunota_atual);
            
            if(!nunota_atual){
              console.error('[GERAR VALE] ❌ NUNOTA não encontrada no botão!');
              window.__GERANDO_VALE = false;
              alert('❌ Erro: NUNOTA não identificada. Feche e abra o modal novamente.');
              return;
            }
            
            // Validação: verificar se TODOS os itens têm preço salvo (vlrtot > 0)
            const rows = (window.__COM_LIST_ROWS||[]).filter(r=> String(r.nunota||'') === String(nunota_atual||''));
            const todosVerdes = rows.every(r=> Number(r.vlrtot||0) > 0);
            
            if(!todosVerdes){
              window.__GERANDO_VALE = false;
              alert('❌ Não é possível gerar vale!\n\nTodos os produtos devem ter negociação salva (vlrtot > 0).\n\nVerifique se todos os itens foram processados.');
              return;
            }
            
            // Separar itens classificáveis e não classificáveis
            const classifs = rows.filter(r=> window.__isClassificavelItem(r));
            const naoClassifs = rows.filter(r=> window.__isNaoClassificavelItem(r));
            
            console.log(`[GERAR VALE] Total: ${rows.length} itens | Classificáveis: ${classifs.length} | Não classificáveis: ${naoClassifs.length}`);

                        // Garantir que totais reflitam as edições do usuário antes de montar o payload
                        try{
                          if(typeof recompute === 'function'){
                            recompute();
                          }
                        }catch(err){
                          console.warn('[GERAR VALE] Aviso: falha ao recomputar totais antes de gerar vale:', err);
                        }

                        const roundTo = (num, decimals = 2)=>{
                          if(!Number.isFinite(num)) return 0;
                          const factor = Math.pow(10, decimals);
                          return Math.round(num * factor) / factor;
                        };
            
            const items = [];
            
            // 1. Processar itens CLASSIFICÁVEIS (geram EXTRA + MEDIO com distribuição)
            for(const item of classifs){
              const codprod = Number(item.codprod || 0);
              const sequencia = Number(item.sequencia || 0);
              const codvol = String(item.codvol || 'CX').toUpperCase();
              const codagregacao = String(item.codagregacao || '');
              const vlrtot = Number(item.vlrtot || 0);
              
              // Buscar quantidades da classificação via API
              const lote = codagregacao;
              let extra_cx = 0, extra_total = 0, medio_cx = 0, medio_total = 0;
              
              try {
                // Buscar classificação
                const respClass = await fetch(`/sankhya/classificacao/resumo/?lote=${encodeURIComponent(lote)}`);
                if(!respClass.ok) throw new Error('Erro ao buscar classificação');
                
                const dataClass = await respClass.json();
                
                if(dataClass && dataClass.ok && Array.isArray(dataClass.linhas) && dataClass.linhas.length > 0){
                  const linhas = dataClass.linhas;
                  
                  console.log(`[GERAR VALE] Classificação encontrada para lote ${lote}:`, linhas);
                  
                  // Separar EXTRA e MEDIO/MÉDIA
                  let extraLine = linhas.find(l => {
                    const prod = (l.produto || '').toUpperCase();
                    console.log(`[GERAR VALE] Verificando se "${prod}" é EXTRA:`, prod.includes('EXTRA'));
                    return prod.includes('EXTRA');
                  });
                  
                  let medioLine = linhas.find(l => {
                    const prod = (l.produto || '').toUpperCase();
                    const isMedio = prod.includes('MEDIO') || prod.includes('MÉDIO') || prod.includes('MÉDIA') || prod.includes('MEDIA');
                    console.log(`[GERAR VALE] Verificando se "${prod}" é MEDIO:`, isMedio);
                    return isMedio;
                  });
                  
                  // FALLBACK: Se não encontrou EXTRA nem MÉDIO, buscar produto sem "IN NATURA"
                  if(!extraLine && !medioLine) {
                    console.log('[GERAR VALE] FALLBACK - Não encontrou EXTRA nem MÉDIO, buscando produto genérico...');
                    
                    // Pegar nome do produto original e remover "IN NATURA", "INNATURA", "INATURA"
                    const prodOriginal = (item.produto || '').toUpperCase();
                    const prodBase = prodOriginal
                      .replace(/IN\s*NATURA/gi, '')
                      .replace(/INNATURA/gi, '')
                      .replace(/INATURA/gi, '')
                      .trim();
                    
                    console.log(`[GERAR VALE] Produto original: "${prodOriginal}" → Base: "${prodBase}"`);
                    
                    // Buscar linha que contenha o nome base
                    extraLine = linhas.find(l => {
                      const classifNome = (l.produto || '').toUpperCase().trim();
                      const match = classifNome.includes(prodBase) || prodBase.includes(classifNome);
                      if(match) {
                        console.log(`[GERAR VALE] ✅ MATCH encontrado: "${l.produto}" será tratado como EXTRA`);
                      }
                      return match;
                    });
                    
                    if(extraLine) {
                      console.log(`[GERAR VALE] Produto "${prodOriginal}" → Usando "${extraLine.produto}" como EXTRA (sem divisão)`);
                    } else {
                      console.warn(`[GERAR VALE] ⚠️ Nenhuma linha encontrada para produto "${prodOriginal}"`);
                    }
                  }
                  
                  console.log(`[GERAR VALE] Extra line encontrada:`, extraLine);
                  console.log(`[GERAR VALE] Medio line encontrada:`, medioLine);
                  
                  const extraKg = Number(extraLine?.kg || 0);
                  const extraCx = Number(extraLine?.cx || 0);
                  const medioKg = Number(medioLine?.kg || 0);
                  const medioCx = Number(medioLine?.cx || 0);
                  
                  console.log(`[GERAR VALE] Classificação do lote ${lote}:`, {
                    linhas,
                    extra: { kg: extraKg, cx: extraCx },
                    medio: { kg: medioKg, cx: medioCx }
                  });
                  
                  // Calcular distribuição usando VLRTOT e a mesma lógica do cenário 2
                  // Fórmula: valorTotal = (extraKg × X) + (medioKg × X/2)
                  //         X = valorTotal / (extraKg + medioKg/2)
                  
                  if(extraKg > 0 || medioKg > 0){
                    const divisor = extraKg + (medioKg / 2);
                    
                    if(divisor > 0){
                      // Custo por kg do Extra
                      const extraCustoKg = vlrtot / divisor;
                      const extraCustoTotal = extraKg * extraCustoKg;
                      
                      // Médio = metade do custo do Extra
                      const medioCustoKg = extraCustoKg / 2;
                      const medioCustoTotal = medioKg * medioCustoKg;
                      
                      extra_cx = extraCx;
                      extra_total = extraCustoTotal;
                      medio_cx = medioCx;
                      medio_total = medioCustoTotal;
                      
                      console.log(`[GERAR VALE] Item ${codprod} (seq ${sequencia}) - CALCULADO:`, {
                        vlrtot,
                        extraKg, extraCx, extraCustoKg: extraCustoKg.toFixed(2), extraCustoTotal: extraCustoTotal.toFixed(2),
                        medioKg, medioCx, medioCustoKg: medioCustoKg.toFixed(2), medioCustoTotal: medioCustoTotal.toFixed(2),
                        soma: (extraCustoTotal + medioCustoTotal).toFixed(2)
                      });
                    }
                  }
                } else {
                  console.warn(`[GERAR VALE] Classificação não encontrada para lote ${lote}`);
                }
              } catch(err) {
                console.error(`[GERAR VALE] Erro ao buscar classificação do item ${codprod}:`, err);
              }
              
              console.log(`[GERAR VALE] Item CLASSIFICÁVEL ${codprod} (seq ${sequencia}):`, {
                extra_cx, extra_total, medio_cx, medio_total, codagregacao
              });
              
              items.push({
                tipo: 'classificavel',
                codprod: codprod,
                sequencia_origem: sequencia,
                extra_cx: extra_cx,
                extra_total: extra_total,
                medio_cx: medio_cx,
                medio_total: medio_total,
                codvol: codvol,
                codagregacao: codagregacao
              });
            }
            
            // 2. Processar itens NÃO CLASSIFICÁVEIS (duplicam o produto original com valores atualizados)
            naoClassifs.forEach((item, idx)=>{
              const codprod = Number(item.codprod || 0);
              const sequencia = Number(item.sequencia || 0);
              const qtdneg = Number(item.qtdneg || 0);
              const codvol = String(item.codvol || 'CX').toUpperCase();
              const codagregacao = String(item.codagregacao || '');
              const nunotaLinha = Number(item.nunota || nunota_atual || 0);

              const selector = `#valeOutrosBody tr[data-nun="${nunotaLinha}"][data-seq="${sequencia}"][data-codprod="${codprod}"][data-lote="${codagregacao}"]`;
              const tr = document.querySelector(selector) || document.querySelector(`#valeOutrosBody tr[data-idx="${idx}"]`);
              const priceFromDom = tr ? parsePT(tr.querySelector('.vop-price')?.textContent || '') : NaN;
              const attrPrecoEdit = tr ? parseFloat(tr.getAttribute('data-preco-edit') || '0') : NaN;
              const attrPrecoBase = tr ? parseFloat(tr.getAttribute('data-preco-base') || '0') : NaN;
              const attrTotalEdit = tr ? parseFloat(tr.getAttribute('data-total-edit') || '0') : NaN;
              const attrTotalBase = tr ? parseFloat(tr.getAttribute('data-total-base') || '0') : NaN;

              const precoCandidates = [priceFromDom, attrPrecoEdit, attrPrecoBase, Number(item.__calc_nao_classif?.preco), Number(item.preco_inicial || 0), (qtdneg > 0 ? Number(item.vlrtot || 0) / qtdneg : NaN)];
              let precoAtual = 0;
              for(const candidate of precoCandidates){
                if(Number.isFinite(candidate) && candidate > 0){
                  precoAtual = roundTo(candidate, 6);
                  break;
                }
              }

              let vlrtotAtual = 0;
              if(precoAtual > 0 && Number.isFinite(qtdneg) && qtdneg > 0){
                vlrtotAtual = roundTo(precoAtual * qtdneg, 2);
              }
              if(!(vlrtotAtual > 0)){
                const totalCandidates = [attrTotalEdit, attrTotalBase, Number(item.__calc_nao_classif?.total || 0), Number(item.vlrtot || 0)];
                for(const candidate of totalCandidates){
                  if(Number.isFinite(candidate) && candidate > 0){
                    vlrtotAtual = roundTo(candidate, 2);
                    break;
                  }
                }
              }
              if(!(precoAtual > 0) && vlrtotAtual > 0 && Number.isFinite(qtdneg) && qtdneg > 0){
                precoAtual = roundTo(vlrtotAtual / qtdneg, 6);
              }

              // Persistir valores consolidados nos atributos do DOM para uso posterior
              if(tr){
                if(precoAtual > 0){
                  tr.setAttribute('data-preco-edit', precoAtual.toFixed(6));
                } else {
                  tr.removeAttribute('data-preco-edit');
                }
                if(vlrtotAtual > 0){
                  tr.setAttribute('data-total-edit', vlrtotAtual.toFixed(2));
                } else {
                  tr.removeAttribute('data-total-edit');
                }
                const totalCell = tr.querySelector('.vop-total');
                if(totalCell){
                  totalCell.innerHTML = fmtMoney(vlrtotAtual > 0 ? vlrtotAtual : 0);
                }
                const priceCell = tr.querySelector('.vop-price');
                if(priceCell){
                  priceCell.innerHTML = precoAtual > 0 ? fmtMoney(precoAtual) : '<span style="color:#94a3b8;">R$ 0,00</span>';
                }
              }

              item.vlrunit = precoAtual;
              item.vlrtot = vlrtotAtual;
              item.__calc_nao_classif = { preco: item.vlrunit, total: item.vlrtot };

              console.log(`[GERAR VALE] Item NÃO CLASSIFICÁVEL ${codprod} (seq ${sequencia}):`, {
                qtdneg,
                vlrunit: item.vlrunit,
                vlrtot: item.vlrtot,
                codvol,
                codagregacao
              });

              items.push({
                tipo: 'nao_classificavel',
                codprod,
                sequencia_origem: sequencia,
                qtdneg,
                vlrunit: item.vlrunit,
                vlrtot: item.vlrtot,
                codvol,
                codagregacao
              });
            });
            
            if(items.length === 0){
              alert('❌ Nenhum item encontrado para gerar o vale!');
              return;
            }
            
            console.log('[GERAR VALE] Payload completo:', { nunota_origem: Number(nunota_atual), items });
            
            // Desabilitar botão e mostrar loading
            const btnGV = document.getElementById('btnGerarVale');
            const btnOrigText = btnGV?.textContent;
            if(btnGV){
              btnGV.disabled = true;
              btnGV.textContent = 'GERANDO...';
              btnGV.style.opacity = '0.6';
            }
            
            try{
              const res = await window.__postJSON('/sankhya/comercial/vale/gerar/', { 
                nunota_origem: Number(nunota_atual), 
                items 
              });
              
              if(res.ok){
                const valeNum = res.body?.nunota_13 || '';
                const itemsCriados = res.body?.items_criados || 0;
                
                // Limpar flag ANTES de fechar modal
                window.__GERANDO_VALE = false;
                
                alert(`✅ Vale criado com sucesso!\n\nNUNOTA: ${valeNum}\nItens criados: ${itemsCriados}`); 
                els.modal.style.display = 'none';
                
                // Atualizar lista para refletir o vale gerado (force reload com cache-busting)
                if(typeof loadLista === 'function') {
                  console.log('[GERAR VALE] Forçando reload da lista...');
                  loadLista();
                }
              }else{
                // Verifica se é um erro de vale duplicado
                if(res.body?.vale_existente){
                  const valeNum = res.body.vale_existente;
                  const msg = `⚠️ Este pedido já possui um vale gerado:\n\nVale NUNOTA: ${valeNum}\n\nNão é possível gerar outro vale para o mesmo pedido.`;
                  alert(msg);
                }else{
                  alert('❌ Falha ao gerar vale:\n\n' + (res.body?.error || 'erro desconhecido'));
                }
              }
            }catch(e){ 
              console.error('[GERAR VALE] Erro:', e);
              alert('❌ Erro ao gerar vale:\n\n' + e); 
            }finally{
              // Restaurar botão e liberar flag
              if(btnGV){
                btnGV.disabled = false;
                btnGV.textContent = btnOrigText;
                btnGV.style.opacity = '1';
              }
              window.__GERANDO_VALE = false;
            }
          });
          
          // 🔥 Event listener: Botão FATURAR
          // Remover listeners anteriores para evitar duplicação
          const btnFaturarEl = document.getElementById('valeResumoFaturar');
          const btnFaturarClone = btnFaturarEl.cloneNode(true);
          btnFaturarEl.parentNode.replaceChild(btnFaturarClone, btnFaturarEl);
          
          btnFaturarClone.addEventListener('click', async ()=>{
            // 🔥 CRÍTICO: Verificar se há saves pendentes antes de faturar
            const pendingSaves = window.AutoSaveQueue?.getPendingCount() || 0;
            if(pendingSaves > 0){
              alert(`⏳ Aguarde!\n\nHá ${pendingSaves} salvamento${pendingSaves > 1 ? 's' : ''} em andamento.\n\nPor favor, aguarde a conclusão antes de faturar.`);
              console.warn('[FATURAR] ⚠️ Bloqueado - Saves pendentes:', pendingSaves);
              return;
            }
            
            const nunotaPedido = Number(window.__CURRENT_PEDIDO_NUNOTA || nunota || 0);
            const items = buildValeItems();
            console.log('[FATURAR] Iniciando faturamento...', { nunotaTela: nunota, nunotaPedido, items });

            if(!nunotaPedido){
              alert('Não foi possível identificar o pedido para faturamento. Feche e abra o modal novamente.');
              console.error('[FATURAR] ❌ NUNOTA do pedido não identificado', { nunotaTela: nunota, nunotaPedido });
              return;
            }
            try{
              // Desabilitar botão para evitar duplicação
              btnFaturarClone.disabled = true;
              btnFaturarClone.style.opacity = '0.5';
              btnFaturarClone.style.cursor = 'not-allowed';
              btnFaturarClone.textContent = 'FATURANDO...';

              const res = await window.__postJSON('/sankhya/comercial/vale/save/', { nunota: nunotaPedido, items, faturar: true });
              console.log('[FATURAR] Resposta recebida:', res);
              
              if(res.ok){
                if(Array.isArray(res.body?.warnings) && res.body.warnings.length){
                  window.showToast(`Faturado com avisos:\n${res.body.warnings.join('\n')}`, 'warning');
                }
                // Mostrar NUFIN no badge se foi criado
                if(res.body?.financeiro?.criado && res.body.financeiro.nufin){
                  const badge = document.getElementById('valeResumoNufinBadge');
                  const nufinNum = document.getElementById('valeResumoNufinNum');
                  const marcaDagua = document.getElementById('modalMarcaDagua');
                  const btnDesfaturarAtual = document.getElementById('valeResumoDesfaturar');
                  
                  console.log('[FATURAR] ✅ NUFIN criado:', res.body.financeiro.nufin, 'Valor:', res.body.financeiro.vlrdesdob, 'Venc:', res.body.financeiro.dtvenc);
                  
                  // Atualizar badge NUFIN
                  if(badge && nufinNum){
                    nufinNum.textContent = res.body.financeiro.nufin;
                    badge.style.display = 'inline-block';
                  }
                  
                  // 🎨 Mostrar marca d'água
                  if(marcaDagua){
                    marcaDagua.style.display = 'block';
                  }
                  
                  // 🗑️ Trocar botão FATURAR por DESFATURAR
                  if(btnFaturarClone && btnDesfaturarAtual){
                    btnFaturarClone.style.display = 'none';
                    btnDesfaturarAtual.style.display = 'inline-flex';
                    btnDesfaturarAtual.disabled = false;
                    btnDesfaturarAtual.style.opacity = '1';
                    btnDesfaturarAtual.style.cursor = 'pointer';
                  }
                  
                  // 🔒 Bloquear todos os campos (otimizado)
                  console.log('[FATURAR] 🔒 Bloqueando campos editáveis...');
                  const editablesOutros = document.querySelectorAll('#valeOutrosBody .vop-price');
                  console.log('[FATURAR] 🔒 Encontrados', editablesOutros.length, 'campos editáveis');
                  for(let i = 0; i < editablesOutros.length; i++){
                    const inp = editablesOutros[i];
                    inp.setAttribute('contenteditable', 'false');
                    inp.style.opacity = '0.6';
                    inp.style.cursor = 'not-allowed';
                    inp.style.background = '#f3f4f6';
                    inp.style.pointerEvents = 'none';
                    inp.style.userSelect = 'none';
                    inp.title = 'Não é possível editar vale faturado';
                    console.log('[FATURAR] 🔒 Campo bloqueado:', inp.id || inp.className);
                  }
                  console.log('[FATURAR] ✅ Bloqueio concluído');
                  
                  // 🔒 Bloquear checkbox INSS
                  const checkboxINSS = document.getElementById('valeDescontaINSS');
                  if(checkboxINSS){
                    checkboxINSS.disabled = true;
                    checkboxINSS.style.cursor = 'not-allowed';
                    checkboxINSS.style.opacity = '0.5';
                  }
                  
                  // 🔒 Bloquear botões "Zerar Negociação" e "Salvar" do painel principal
                  const btnResetMain = document.getElementById('dist-btn-reset');
                  const btnSaveMain = document.getElementById('dist-btn-save');
                  const lockIcon = document.getElementById('lockIconContainer');
                  
                  // Mostrar ícone de cadeado
                  if(lockIcon) lockIcon.style.display = 'inline-block';
                  
                  if(btnResetMain){
                    btnResetMain.disabled = true;
                    btnResetMain.style.opacity = '0.3';
                    btnResetMain.style.cursor = 'not-allowed';
                    btnResetMain.title = 'Não é possível zerar negociação de vale faturado';
                  }
                  
                  if(btnSaveMain){
                    btnSaveMain.disabled = true;
                    btnSaveMain.style.opacity = '0.3';
                    btnSaveMain.style.cursor = 'not-allowed';
                    btnSaveMain.title = 'Não é possível salvar vale faturado';
                  }
                  
                  window.showToast('✅ Vale faturado com sucesso!', 'success');
                  // Atualizar cor/estado na lista imediatamente
                  try{
                    const nunStr = String(nunota);
                    const headers = Array.from(document.querySelectorAll('#listaBody tr.vale-header'));
                    const found = headers.find(h => (h.querySelector('.vale-head-nun')?.textContent||'').trim() === nunStr);
                    if(found){
                      found.classList.remove('vale--aberto');
                      found.classList.add('vale--faturado');
                      found.setAttribute('data-status','faturado');
                    } else {
                      // Se não encontrou o header correspondente, forçar reload
                      if(typeof loadLista === 'function') loadLista();
                    }
                  }catch(e){ console.error('[FATURAR] Falha ao atualizar cor na lista:', e); }
                }else{
                  console.log('[FATURAR] Financeiro não criado ou sem NUFIN:', res.body?.financeiro);
                  window.showToast('✅ Vale faturado com sucesso!', 'success');
                }
              }else{
                // Reabilitar em caso de erro
                const body = res.body || {};
                const errors = Array.isArray(body.errors) ? body.errors.filter(Boolean) : [];
                const warnings = Array.isArray(body.warnings) ? body.warnings.filter(Boolean) : [];
                const fallbackError = body.error || 'erro desconhecido';
                const lines = errors.length ? errors : [fallbackError];
                let message = 'Falha ao faturar:\n\n' + lines.map(msg => `• ${msg}`).join('\n');
                if(warnings.length){
                  message += '\n\nAvisos:\n' + warnings.map(msg => `• ${msg}`).join('\n');
                }
                console.error('[FATURAR] Erro ao faturar:', { response: res, errors, warnings });
                alert(message);
                btnFaturarClone.disabled = false;
                btnFaturarClone.style.opacity = '1';
                btnFaturarClone.style.cursor = 'pointer';
                btnFaturarClone.textContent = 'FATURAR';
              }
            }catch(e){
              console.error('[FATURAR] Exceção ao faturar:', e);
              alert('Erro ao faturar: ' + e);
              // Reabilitar em caso de exceção
              btnFaturarClone.disabled = false;
              btnFaturarClone.style.opacity = '1';
              btnFaturarClone.style.cursor = 'pointer';
              btnFaturarClone.textContent = 'FATURAR';
            }
          });
          
          // 🗑️ Event listener: Botão DESFATURAR
          // Remover listeners anteriores para evitar duplicação
          const btnDesfaturarEl = document.getElementById('valeResumoDesfaturar');
          const btnDesfaturarClone = btnDesfaturarEl.cloneNode(true);
          btnDesfaturarEl.parentNode.replaceChild(btnDesfaturarClone, btnDesfaturarEl);
          
          console.log('[MODAL] Registrando handler DESFATURAR (clone)');
          // Defensive delegated tracer in case listener is not invoked for any reason
          document.addEventListener('click', (ev)=>{
            try{
              const t = ev.target.closest && ev.target.closest('#valeResumoDesfaturar');
              if(t){ console.log('[MODAL] Click delegated detected on #valeResumoDesfaturar', t); }
            }catch(_){ }
          });

          btnDesfaturarClone.addEventListener('click', async ()=>{            // Confirmação
            console.log('[DESFATURAR] handler (clone) invoked');
            const confirma = confirm(
              '⚠️ ATENÇÃO!\n\n' +
              'Isso irá DELETAR o registro financeiro (TGFFIN) e reabrir o vale para edição.\n\n' +
              'Deseja continuar?'
            );
            
            if(!confirma) return;
            
            try{
              // Desabilitar botão durante a operação
              const btnEl = document.getElementById('valeResumoDesfaturar') || btnDesfaturarClone;
              console.log('[DESFATURAR] iniciando desfaturar - btnEl:', btnEl);
              if(btnEl){ btnEl.disabled = true; btnEl.textContent = 'DESFATURANDO...'; btnEl.style.opacity = '0.5'; }
              
              // Buscar NUFIN do primeiro item (todos têm o mesmo)
              const primeiroItem = rows.length > 0 ? rows[0] : null;
              let nufinParaDesfaturar = primeiroItem?.nufin || null;
              
              if(!nufinParaDesfaturar){
                console.warn('[DESFATURAR] NUFIN não encontrado no primeiroItem, tentando buscar no cache e servidor');
                // tentativa adicional: procurar em cache por qualquer item com nufin
                let fallbackNufin = null;
                try{ fallbackNufin = (window.__COM_LIST_ROWS||[]).find(r=> r && r.nunota && (String(r.nunota) === String(window.__CURRENT_VALE_NUNOTA)) && r.nufin)?.nufin || null; }catch(_){ }
                if(fallbackNufin){
                  console.log('[DESFATURAR] NUFIN encontrado via fallback cache:', fallbackNufin);
                  nufinParaDesfaturar = fallbackNufin;
                } else {
                  // Fallback: pedir ao servidor os itens do vale para obter NUFIN de forma confiável
                  try{
                    console.log('[DESFATURAR] Fazendo fallback ao servidor: GET /sankhya/comercial/api/itens_vale/?nunota=' + window.__CURRENT_VALE_NUNOTA);
                    const resp = await fetch(`/sankhya/comercial/api/itens_vale/?nunota=${encodeURIComponent(window.__CURRENT_VALE_NUNOTA)}`, { method: 'GET', headers: { 'Accept': 'application/json' }});
                    if(resp && resp.ok){
                      const body = await resp.json();
                      if(body && body.items && body.items.length > 0){
                        const first = body.items[0];
                        if(first && first.nufin){
                          console.log('[DESFATURAR] NUFIN encontrado via servidor:', first.nufin);
                          nufinParaDesfaturar = first.nufin;
                        } else {
                          console.log('[DESFATURAR] Servidor respondeu, mas sem NUFIN nos items:', body);
                        }
                      } else {
                        console.log('[DESFATURAR] Servidor respondeu sem items:', body);
                      }
                    } else {
                      console.warn('[DESFATURAR] Falha ao consultar servidor para NUFIN, status:', resp && resp.status);
                    }
                  }catch(err){
                    console.error('[DESFATURAR] Erro no fetch fallback para NUFIN:', err);
                  }
                }
              }
              if(!nufinParaDesfaturar){
                console.warn('[DESFATURAR] Ainda sem NUFIN após cache+server fallback; tentando extrair do DOM (badge)');
                try{
                  const badgeNumEl = document.getElementById('valeResumoNufinNum');
                  const badgeEl = document.getElementById('valeResumoNufinBadge');
                  if(badgeNumEl && badgeEl && badgeEl.style && badgeEl.style.display !== 'none'){
                    const txt = (badgeNumEl.textContent || '').trim();
                    const m = txt.match(/(\d+)/);
                    if(m){
                      nufinParaDesfaturar = Number(m[1]);
                      console.log('[DESFATURAR] NUFIN extraído do badge DOM:', nufinParaDesfaturar);
                    } else {
                      console.log('[DESFATURAR] badge presente mas não contém número:', txt);
                    }
                  } else {
                    // Tentar buscar qualquer elemento contendo 'NUFIN' no modal
                    const modal = document.getElementById('modalFaturamento');
                    if(modal){
                      const found = modal.querySelector("*[id*='Nufin']") || modal.querySelector("span:contains('NUFIN')");
                      // querySelector with :contains is not standard — fallback to scanning text nodes
                      if(!found){
                        // scan for nodes that include 'NUFIN' text
                        const walker = document.createTreeWalker(modal, NodeFilter.SHOW_TEXT, null, false);
                        let node;
                        while((node = walker.nextNode())){
                          if(node.nodeValue && node.nodeValue.toUpperCase().includes('NUFIN')){
                            const m2 = node.nodeValue.match(/(\d{4,})/);
                            if(m2){ nufinParaDesfaturar = Number(m2[1]); console.log('[DESFATURAR] NUFIN extraído via text walker:', nufinParaDesfaturar); break; }
                          }
                        }
                      }
                    }
                  }
                }catch(e){ console.error('[DESFATURAR] Falha ao extrair NUFIN do DOM:', e); }

                if(!nufinParaDesfaturar){
                  window.showToast('❌ NUFIN não encontrado', 'error');
                  const btnEl2 = document.getElementById('valeResumoDesfaturar') || btnDesfaturarClone;
                  if(btnEl2){ btnEl2.disabled = false; btnEl2.textContent = '🗑️ DESFATURAR'; btnEl2.style.opacity = '1'; }
                  return;
                }
              }
              
              console.log('[DESFATURAR] Enviando NUFIN:', nufinParaDesfaturar);
              
              const res = await window.__postJSON('/sankhya/comercial/vale/desfaturar/', { 
                nufin: Number(nufinParaDesfaturar)
              });
              
              console.log('[DESFATURAR] Resposta:', res);
              
              if(res.ok && res.body?.ok){
                window.showToast('✅ Vale desfaturado com sucesso!', 'success');
                
                // 🔥 Atualizar estado local para refletir desfaturamento
                // Limpar NUFIN dos dados em cache
                if(window.__COM_LIST_ROWS){
                  const nunotaAtual = window.__CURRENT_VALE_NUNOTA;
                  window.__COM_LIST_ROWS.forEach(row => {
                    if(String(row.nunota) === String(nunotaAtual)){
                      row.nufin = null;
                      row.nureneg = null;
                      row.vlrbaixa = null;
                      row.bloqueado_financeiro = false;
                    }
                  });
                  console.log('[DESFATURAR] Cache atualizado - NUFIN removido');
                }
                
                // 🔓 Reativar botões "Zerar Negociação" e "Salvar"
                const btnResetMain = document.getElementById('dist-btn-reset');
                const btnSaveMain = document.getElementById('dist-btn-save');
                const lockIcon = document.getElementById('lockIconContainer');
                
                // Ocultar ícone de cadeado
                if(lockIcon) lockIcon.style.display = 'none';
                
                // Verificar modo atual (projeção vs real)
                const modoAtual = window.__VALOR_TOTAL_MODE || 'projecao';
                const podeEditar = modoAtual === 'real';
                
                if(btnResetMain){
                  btnResetMain.disabled = !podeEditar;
                  btnResetMain.style.opacity = podeEditar ? '0.8' : '0.4';
                  btnResetMain.style.cursor = podeEditar ? 'pointer' : 'not-allowed';
                  btnResetMain.title = podeEditar ? '' : 'Disponível apenas no modo Real';
                }
                
                if(btnSaveMain){
                  btnSaveMain.disabled = !podeEditar;
                  btnSaveMain.style.opacity = podeEditar ? '0.85' : '0.4';
                  btnSaveMain.style.cursor = podeEditar ? 'pointer' : 'not-allowed';
                  btnSaveMain.title = podeEditar ? '' : 'Disponível apenas no modo Real';
                }
                
                console.log('[DESFATURAR] Botões reativados - Modo:', modoAtual, 'Pode editar:', podeEditar);

                // Restaurar UI do modal para estado NÃO-FATURADO:
                try{
                  // Remover marca d'água
                  const marcaDagua = document.getElementById('modalMarcaDagua');
                  if(marcaDagua) marcaDagua.style.display = 'none';

                  // Esconder badge NUFIN e resetar número
                  const nufinBadge = document.getElementById('valeResumoNufinBadge');
                  const nufinNum = document.getElementById('valeResumoNufinNum');
                  if(nufinBadge) nufinBadge.style.display = 'none';
                  if(nufinNum) nufinNum.textContent = '—';

                  // Mostrar botão FATURAR e esconder DESFATURAR (se existem)
                  const btnFaturarNow = document.getElementById('valeResumoFaturar');
                  const btnDesfNow = document.getElementById('valeResumoDesfaturar');
                  if(btnFaturarNow){ btnFaturarNow.style.display = 'inline-block'; btnFaturarNow.disabled = false; btnFaturarNow.textContent = 'FATURAR'; btnFaturarNow.style.opacity = '1'; btnFaturarNow.style.cursor = 'pointer'; }
                  if(btnDesfNow){ btnDesfNow.style.display = 'none'; btnDesfNow.disabled = false; btnDesfNow.textContent = '🗑️ DESFATURAR'; btnDesfNow.style.opacity = '1'; }

                  // 🔓 Reabilitar campos editáveis do modal (remoção do bloqueio aplicado ao faturar)
                  console.log('[DESFATURAR] 🔓 Desbloqueando campos editáveis...');
                  const editablesOutros = document.querySelectorAll('#valeOutrosBody .vop-price');
                  console.log('[DESFATURAR] 🔓 Encontrados', editablesOutros.length, 'campos editáveis');
                  for(let i = 0; i < editablesOutros.length; i++){
                    const inp = editablesOutros[i];
                    try{ 
                      inp.setAttribute('contenteditable','true'); 
                      inp.style.opacity = '1';
                      inp.style.cursor = 'text';
                      inp.style.background = '';
                      inp.style.pointerEvents = '';
                      inp.style.userSelect = '';
                      inp.removeAttribute('title');
                      console.log('[DESFATURAR] 🔓 Campo desbloqueado:', inp.id || inp.className);
                    }catch(_){ }
                  }
                  console.log('[DESFATURAR] ✅ Desbloqueio concluído');

                  // 🔓 Reabilitar checkbox INSS
                  const checkboxINSS = document.getElementById('valeDescontaINSS');
                  if(checkboxINSS){
                    checkboxINSS.disabled = false;
                    checkboxINSS.style.cursor = 'pointer';
                    checkboxINSS.style.opacity = '1';
                  }

                  // Ocultar ícone de cadeado se presente
                  const lockIcon = document.getElementById('lockIconContainer');
                  if(lockIcon) lockIcon.style.display = 'none';
                }catch(e){ console.error('[DESFATURAR] Falha ao restaurar UI do modal:', e); }

                // NÃO fechar modal automaticamente após desfaturar — manter aberto para revisão pelo usuário
                // Atualizar lista (preferimos reload para garantir consistência)
                try{
                  const nunStr = String(nunota);
                  const headers = Array.from(document.querySelectorAll('#listaBody tr.vale-header'));
                  const found = headers.find(h => (h.querySelector('.vale-head-nun')?.textContent||'').trim() === nunStr);
                  if(found){
                    found.classList.remove('vale--faturado');
                    found.classList.add('vale--aberto');
                    found.setAttribute('data-status','aberto');
                  }
                }catch(e){ console.error('[DESFATURAR] Falha ao ajustar cor local:', e); }
                // Recarregar lista para garantir estado completo atualizado no UI
                await window.loadLista?.();
              } else {
                const erro = res.body?.error || 'Erro ao desfaturar';
                window.showToast(`❌ ${erro}`, 'error');
                // Reabilitar botão
                btnDesfaturarClone.disabled = false;
                btnDesfaturarClone.textContent = '🗑️ DESFATURAR';
                btnDesfaturarClone.style.opacity = '1';
              }
            }catch(e){
              console.error('[DESFATURAR] Exceção:', e);
              window.showToast(`❌ Erro ao desfaturar: ${e.message}`, 'error');
              // Reabilitar botão
              btnDesfaturarClone.disabled = false;
              btnDesfaturarClone.textContent = '🗑️ DESFATURAR';
              btnDesfaturarClone.style.opacity = '1';
            }
          });
        }catch(err){
          console.error('[ERROR] openValeResumo falhou:', err);
          alert('Erro ao abrir modal: ' + err.message);
        }finally{
          // 🚀 Log de performance e ocultar spinner
          const t1Performance = performance.now();
          const tempoTotal = (t1Performance - t0Performance).toFixed(0);
          console.log(`[MODAL] ⚡ Modal aberto em ${tempoTotal}ms`);
          
          // Garantir que spinner seja ocultado mesmo em caso de erro
          if(els.spinner) els.spinner.style.display = 'none';
        }
      }

      