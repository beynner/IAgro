window.ComercialFinanceiro = (function() {
    let STATE = { bruto: 0, liquido: 0, dadosNota: null, itens: [] };

    const abrir = async (nunota) => {
        const modal = document.getElementById('modalFaturamento');
        if (!modal) return;

        // 1. A BASE FÍSICA: Os produtos vêm da TOP 11 (Memória)
        let itensDaNota = (window.__COM_LIST_ROWS || []).filter(r => r.nunota == nunota);
        
        if (itensDaNota.length === 0) {
            // 🚀 FIX: Se a lista do fundo filtrou e sumiu com a nota, resgata do "cofre" do próprio Modal!
            if (STATE.itens && STATE.itens.length > 0 && STATE.itens[0].nunota == nunota) {
                itensDaNota = STATE.itens;
            } else {
                return;
            }
        }
        
        STATE.itens = itensDaNota;
        STATE.dadosNota = itensDaNota[0];
        document.getElementById('fechamentoParceiro').textContent = STATE.dadosNota.parceiro || '---';
        
        // Monta o subtítulo inicial com os dados da memória
        const memVale = window.ComercialUtils.toNumber(STATE.dadosNota.nunota_13);
        const memFin = window.ComercialUtils.toNumber(STATE.dadosNota.nufin);
        let subtitulo = `Pedido: ${nunota}`;
        if (memVale > 0) subtitulo += ` | Vale: ${memVale}`;
        if (memFin > 0) subtitulo += ` | Fin: ${memFin}`;
        document.getElementById('fechamentoPedido').textContent = subtitulo;
        
        // 🚀 FIX: Verifica se é uma atualização (modal já aberto) para evitar a "piscada"
        const isRefresh = modal.style.display === 'flex';
        modal.style.display = 'flex';

        const listClass = document.getElementById('listaFechamentoClass');
        const listDireto = document.getElementById('listaFechamentoDireto');
        
        // Só mostra a mensagem de "Buscando..." se for a primeira vez abrindo
        if (!isRefresh) {
            listClass.innerHTML = '<tr><td colspan="5" class="txt-center val-sub">Buscando valores na TOP 13...</td></tr>';
            listDireto.innerHTML = '';
        }

        let totalBruto = 0;
        let temPendente = false;
        let htmlClass = '';
        let htmlDireto = '';

        // Pega o número do Vale (Se houver)
        const notaRef = itensDaNota.find(r => window.ComercialUtils.toNumber(r.nunota_13) > 0);
        const nunota13Ativo = notaRef ? window.ComercialUtils.toNumber(notaRef.nunota_13) : 0;

        let vlroutrosInicial = 0;
        let nufinAtivo = 0;
        if (nunota13Ativo > 0) {
            try {
                const resCab = await fetch(`/sankhya/comercial/api/detalhes-vale/?nunota_13=${nunota13Ativo}&lote=${STATE.dadosNota.codagregacao || ''}`);
                const dataCab = await resCab.json();
                vlroutrosInicial = window.ComercialUtils.toNumber(dataCab.vlroutros || 0);
                nufinAtivo = window.ComercialUtils.toNumber(dataCab.nufin || 0);
            } catch (e) { console.error("Erro ao carregar estado", e); }
        }
        STATE.dadosNota.nufin = nufinAtivo; // Guarda na memória se faturou
        
        // 🚀 Atualiza o subtítulo com os dados frescos da API
        let subtituloApi = `Pedido: ${nunota}`;
        if (nunota13Ativo > 0) subtituloApi += ` | Vale: ${nunota13Ativo}`;
        if (nufinAtivo > 0) subtituloApi += ` | Fin: ${nufinAtivo}`;
        document.getElementById('fechamentoPedido').textContent = subtituloApi;

        if (nufinAtivo > 0) {
            document.body.classList.add('vale-faturado');
        }
        
        // 2. MONTAGEM: Aplica a regra (Soma do vlrtot do mesmo lote da TOP 13)
        for (const item of itensDaNota) {
            const isClassificavel = item.geraproducao === 'S';
            const fabricante = item.fabricante || item.produto || 'PRODUTO';
            const pesoCx = window.ComercialUtils.toNumber(item.qtdfixada) || 20;
            const lote = item.codagregacao || '';
            
            let vlrTotal = 0;
            let vlrUnitDireto = 0;

            // Busca na TOP 13 filtrando pelo lote
            if (nunota13Ativo > 0) {
                try {
                    const resVale = await fetch(`/sankhya/comercial/api/detalhes-vale/?nunota_13=${nunota13Ativo}&lote=${lote}`);
                    const dataVale = await resVale.json();
                    
                    if (dataVale.ok && dataVale.itens) {
                        for (const it of dataVale.itens) {
                            if (!isClassificavel && String(it.codprod) !== String(item.codprod)) {
                                continue; 
                            }
                            vlrTotal += window.ComercialUtils.toNumber(it.vlrtot) || 0;
                            if (!isClassificavel) {
                                vlrUnitDireto = window.ComercialUtils.toNumber(it.vlrunit) || 0;
                            }
                        }
                    }
                } catch (e) { console.warn(`Erro ao buscar lote ${lote} na TOP 13`, e); }
            }

            totalBruto += vlrTotal;

            if (isClassificavel) {
                if (vlrTotal <= 0) temPendente = true;

                let kgFisicoTotal = 0;
                try {
                    const resBal = await fetch(`/sankhya/lote/consultar/?lote=${lote}&nunota_origem=${item.nunota}`);
                    const dataBal = await resBal.json();
                    if (dataBal.ok && dataBal.classificacoes) {
                        kgFisicoTotal = dataBal.classificacoes
                            .filter(c => window.ComercialUtils.toNumber(c.selecionado) !== 0)
                            .reduce((acc, curr) => acc + window.ComercialUtils.toNumber(curr.qtd), 0);
                    }
                } catch (e) { console.warn("Erro ao buscar balanço", e); }

                // 🚀 REGRA 1: Puxa a Qtde de Caixas diretamente da conferência da portaria
                const qtdConf = window.ComercialUtils.toNumber(item.qtdconferida || item.qtdneg) || 0;

                // Fallback de segurança para os quilos caso a API de classificação falhe/esteja vazia
                if (kgFisicoTotal === 0) {
                    const pesoIn = window.ComercialUtils.toNumber(item.peso || 1);
                    kgFisicoTotal = qtdConf * pesoIn;
                }

                // 🚀 REGRA 3: Cálculos de Preço Unitário separados e exatos
                const custoCx = qtdConf > 0 ? (vlrTotal / qtdConf) : 0;
                const custoKg = kgFisicoTotal > 0 ? (vlrTotal / kgFisicoTotal) : 0;

                htmlClass += `
                    <tr>
                        <td class="val-main">${fabricante}</td>
                        <td class="txt-right">
                            <div class="val-main">${window.ComercialUtils.formatQty(qtdConf, 2) || '0.00'} cx</div>
                            <div class="val-sub">${window.ComercialUtils.formatQty(kgFisicoTotal) || '0.00'} kg</div>
                        </td>
                        <td class="txt-right">
                            <div class="val-main">R$ ${custoCx.toFixed(2) || '0.00'}/cx</div>
                            <div class="val-sub">R$ ${custoKg.toFixed(2) || '0.00'}/kg</div>
                        </td>
                        <td class="txt-right">
                            <div class="val-main">R$ ${vlrTotal.toLocaleString('pt-BR', {minimumFractionDigits:2})}</div>
                        </td>
                        <td class="txt-center"><span class="status-dot ${vlrTotal > 0 ? 'verde' : 'vermelho'}"></span></td>
                    </tr>`;

            } else {
                // ... bloco dos não classificáveis continua inalterado ...
                const qtd = window.ComercialUtils.toNumber(item.qtdconferida) || 0; 
                const pesoIn = window.ComercialUtils.toNumber(item.peso) || 0;
                const unidade = (item.codvol || 'un').toLowerCase();
                
                const vlrUnit = qtd > 0 ? (vlrTotal / qtd) : 0;
                
                const isFaturado = nufinAtivo > 0;

                const campoEditavel = isFaturado ? 
                    `<span>${vlrUnit.toFixed(2)}</span>` :
                    `<span class="editable" style="cursor:pointer;" onclick="window.ComercialFinanceiro.editarPreco(${item.nunota}, ${item.codprod}, ${nunota13Ativo}, this)">${vlrUnit.toFixed(2)}</span>`;
                if (vlrUnit <= 0 || vlrTotal <= 0) temPendente = true;

                let htmlQtde = '';
                let htmlVlr = '';

                if (['cx', 'sc'].includes(unidade) && pesoIn > 0) {
                    const totalKg = qtd * pesoIn;
                    const custoKg = totalKg > 0 ? (vlrTotal / totalKg) : 0;

                    htmlQtde = `
                        <div class="val-main">${window.ComercialUtils.formatQty(qtd, 2) || '0.00'} ${unidade}</div>
                        <div class="val-sub">${window.ComercialUtils.formatQty(totalKg) || '0.00'} kg</div>`;
                    
                    htmlVlr = `
                        <div class="val-main">R$ ${campoEditavel}/${unidade}</div>
                        <div class="val-sub">R$ ${custoKg.toFixed(2) || '0.00'}/kg</div>`;
                } else {
                    htmlQtde = `<div class="val-main">${window.ComercialUtils.formatQty(qtd) || '0'} ${unidade}</div>`;
                    htmlVlr = `<div class="val-main">R$ ${campoEditavel}/${unidade}</div>`;
                }

                htmlDireto += `
                    <tr>
                        <td class="val-main">${fabricante}</td>
                        <td class="txt-right">${htmlQtde}</td>
                        <td class="txt-right">${htmlVlr}</td>
                        <td class="txt-right">
                            <div class="val-main">R$ ${vlrTotal.toLocaleString('pt-BR', {minimumFractionDigits:2})}</div>
                        </td>
                        <td class="txt-center"><span class="status-dot ${vlrTotal > 0 && vlrUnit > 0 ? 'verde' : 'vermelho'}"></span></td>
                    </tr>`;
            }
        }

        listClass.innerHTML = htmlClass || '<tr><td colspan="5" class="txt-center val-sub" style="padding: 15px;">Nenhum produto classificável</td></tr>';
        listDireto.innerHTML = htmlDireto || '<tr><td colspan="5" class="txt-center val-sub" style="padding: 15px;">Nenhum produto direto</td></tr>';

        STATE.bruto = totalBruto;
        document.getElementById('vlrBrutoFechamento').textContent = `R$ ${totalBruto.toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;
        document.getElementById('btnEfetivarFaturamento').disabled = temPendente;
        
        const checkInss = document.getElementById('chkInss');
        checkInss.checked = vlroutrosInicial > 0;
        checkInss.onchange = () => window.ComercialFinanceiro.toggleInss(nunota13Ativo);

        // --- CONTROLE DO CARIMBO ---
        const carimbo = document.getElementById('carimboFaturado');
        if (carimbo) {
            carimbo.style.display = nufinAtivo > 0 ? 'block' : 'none';
        }

        // CONFIGURAÇÃO DA GANGORRA DOS BOTÕES
        const btnEfetivar = document.getElementById('btnEfetivarFaturamento');
        
        // 🚀 VERIFICAÇÃO DE BAIXA NO FINANCEIRO (O mesmo que fizemos na tela principal)
        const isPago = window.ComercialUtils.toNumber(STATE.dadosNota.qtd_baixados) > 0;

        if (nufinAtivo > 0) {
            btnEfetivar.textContent = "DESFATURAR";
            
            if (isPago) {
                // TRAVADO (Título já pago)
                btnEfetivar.style.backgroundColor = "#9ca3af";
                btnEfetivar.style.color = "#ffffff";
                btnEfetivar.style.cursor = "not-allowed";
                btnEfetivar.disabled = true;
                btnEfetivar.title = "Não é possível desfaturar: Título já baixado no financeiro.";
                btnEfetivar.onclick = null;
            } else {
                // LIBERADO (Faturado, mas ainda não pago)
                btnEfetivar.style.backgroundColor = "#ef4444";
                btnEfetivar.style.color = "#ffffff";
                btnEfetivar.style.cursor = "pointer";
                btnEfetivar.disabled = false;
                btnEfetivar.title = "";
                btnEfetivar.onclick = () => window.ComercialFinanceiro.desfaturar(nunota13Ativo);
            }
        } else {
            // MODO FATURAR
            btnEfetivar.textContent = "FATURAR";
            btnEfetivar.style.backgroundColor = ""; 
            btnEfetivar.style.color = "";
            btnEfetivar.style.cursor = temPendente ? "not-allowed" : "pointer";
            btnEfetivar.disabled = temPendente;
            btnEfetivar.title = temPendente ? "Existem produtos sem preço definido." : "";
            btnEfetivar.onclick = () => window.ComercialFinanceiro.faturar();
        }

        recalcularLiquido();
    };

    const editarPreco = (nunotaOrigem, codprod, nunota13, spanElement) => {
        if (STATE.dadosNota && STATE.dadosNota.nufin > 0) {
            window.ComercialUtils.mostrarToast("Vale faturado. Desfature para editar preços.", "aviso");
            return;
        }

        const valorAtual = spanElement.innerText.trim();
        const input = document.createElement('input');
        input.type = 'text';
        input.value = valorAtual;
        input.className = 'preco-input';
        input.style.width = '60px';
        input.style.textAlign = 'right';

        spanElement.style.display = 'none';
        spanElement.parentNode.insertBefore(input, spanElement);
        input.focus();
        input.select();

        const salvar = async () => {
            const novoPreco = window.ComercialUtils.toNumber(input.value);
            if (isNaN(novoPreco) || novoPreco < 0) {
                input.remove(); spanElement.style.display = 'inline'; return;
            }

            input.disabled = true;
            try {
                const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
                const res = await fetch('/sankhya/comercial/api/atualizar-preco-modalFaturamento/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify({ nunota_origem: nunotaOrigem, codprod: codprod, nunota_13: nunota13, preco: novoPreco })
                });
                
                const data = await res.json();
                if (!data.ok) throw new Error(data.error);
                
                window.ComercialUtils.mostrarToast("Preço salvo com sucesso!", "sucesso");
                
                // 🚀 FIX: Ensina a memória do Javascript que o Vale agora existe!
                if (data.nunota_13 && window.__COM_LIST_ROWS) {
                    window.__COM_LIST_ROWS.forEach(r => {
                        if (r.nunota == nunotaOrigem) r.nunota_13 = data.nunota_13;
                    });
                }
                
                // Recarrega o modal silenciosamente e atualiza a linha de trás
                abrir(nunotaOrigem);
                const linhaSel = document.querySelector('tr.lista-item-row.row--sel');
                if (linhaSel) linhaSel.click();

            } catch (e) {
                window.ComercialUtils.mostrarToast(e.message, "erro");
                input.remove(); spanElement.style.display = 'inline';
            }
        };

        input.addEventListener('blur', salvar);
        input.addEventListener('keydown', (e) => { if (e.key === 'Enter') input.blur(); });
    };

    // --- INÍCIO DO NOVO CÓDIGO ---
    const toggleInss = async (nunota13) => {
        const isChecked = document.getElementById('chkInss').checked;
        const valorDesconto = isChecked ? (STATE.bruto * 0.0163) : 0;
        
        try {
            const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
            const res = await fetch('/sankhya/comercial/api/atualizar-desconto-inss/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ nunota_13: nunota13, valor: valorDesconto })
            });
            
            const data = await res.json();
            if (!data.ok) throw new Error(data.error);

            window.ComercialUtils.mostrarToast(isChecked ? "Desconto INSS aplicado!" : "Desconto removido!", "sucesso");
            recalcularLiquido();
            
        } catch (e) {
            window.ComercialUtils.mostrarToast("Erro ao salvar desconto: " + e.message, "erro");
            document.getElementById('chkInss').checked = !isChecked; 
        }
    };
    // --- FIM DO NOVO CÓDIGO ---

    const recalcularLiquido = () => {
        const isChecked = document.getElementById('chkInss').checked;
        
        // 🚀 FIX: Arredondamento para 2 casas decimais (padrão monetário)
        // Usamos Math.round com multiplicador 100 para garantir que 235.515 vire 235.52
        const inss = isChecked ? Math.round((STATE.bruto * 0.0163) * 100) / 100 : 0;
        
        // O líquido deve ser a subtração exata dos dois valores já arredondados
        STATE.liquido = Math.round((STATE.bruto - inss) * 100) / 100;

        document.getElementById('vlrInssFechamento').textContent = `R$ ${inss.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        document.getElementById('vlrLiquidoFechamento').textContent = `R$ ${STATE.liquido.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    };

    const faturar = async () => {
        const nunota13 = STATE.dadosNota.nunota_13;
        if (!nunota13) return window.ComercialUtils.mostrarToast("Erro: Vale não gerado.", "erro");

        if (!confirm(`Confirmar faturamento e geração de financeiro de R$ ${STATE.liquido.toLocaleString('pt-BR', {minimumFractionDigits: 2})}?`)) return;

        const btn = document.getElementById('btnEfetivarFaturamento');
        btn.disabled = true; btn.textContent = "PROCESSANDO...";

        try {
            const lote = STATE.dadosNota.codagregacao || 'S/L';
            const historico = `Faturamento via painel SIG(Sistema Integrado de Gestão) - Vale ${STATE.dadosNota.nunota}`.substring(0, 255);
            const usaInss = document.getElementById('chkInss').checked;
            const valorInss = usaInss ? (STATE.bruto * 0.0163) : 0;

            const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
            const res = await fetch('/sankhya/comercial/api/efetivar-faturamento/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ 
                    nunota_13: nunota13, 
                    descontar_inss: usaInss,
                    historico: historico,
                    vlrinss: valorInss,
                    vlr_forcar_liquido: STATE.liquido, // 🚀 Manda o Líquido Exato (ex: 757.45)
                    vlr_forcar_bruto: STATE.bruto      // 🚀 Manda o Bruto Exato (ex: 767.90)
                })
            });

            const data = await res.json();
            if (!data.ok) throw new Error(data.error);

            window.ComercialUtils.mostrarToast("Financeiro gerado com sucesso!", "sucesso");
            
            STATE.dadosNota.nufin = data.nufin || 1; // Atualiza a memória
            
            // 1. Recarrega o modal (usando await para não atropelar)
            await abrir(STATE.dadosNota.nunota); 
            
            // 2. Atualiza TODOS os painéis do fundo para aplicar as travas
            if (window.ComercialEntrada) window.ComercialEntrada.preencher(STATE.dadosNota);
            if (window.ComercialClassificacao) {
                window.ComercialClassificacao.preencher(STATE.dadosNota).then(pesos => {
                    if (window.ComercialDistribuicao) window.ComercialDistribuicao.preencher(STATE.dadosNota, pesos);
                });
            }
            
            // 3. Atualiza a lista lateral
            if (window.ComercialFiltros && window.ComercialFiltros.atualizar) {
                window.ComercialFiltros.atualizar();
            }

        } catch (e) {
            window.ComercialUtils.mostrarToast("Falha ao faturar: " + e.message, "erro");
            btn.disabled = false; btn.textContent = "FATURAR";
        }
    };

    // --- NOVA FUNÇÃO DESFATURAR ---
    const desfaturar = async (nunota13) => {
        if (!confirm("Atenção: Isso excluirá o título financeiro para permitir novas edições. Deseja continuar?")) return;

        const btn = document.getElementById('btnEfetivarFaturamento');
        btn.disabled = true; btn.textContent = "EXCLUINDO...";

        try {
            const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
            const res = await fetch('/sankhya/comercial/api/desfaturar-vale/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ nunota_13: nunota13 })
            });

            const data = await res.json();
            if (!data.ok) throw new Error(data.error);

            window.ComercialUtils.mostrarToast("Vale reaberto para edição!", "sucesso");
            
            STATE.dadosNota.nufin = 0; // Limpa a memória
            STATE.dadosNota.qtd_baixados = 0; // Garante destravamento completo
            
            // 1. Recarrega o modal (usando await para não atropelar)
            await abrir(STATE.dadosNota.nunota); 
            
            // 2. Atualiza TODOS os painéis do fundo para remover as travas e o carimbo
            if (window.ComercialEntrada) window.ComercialEntrada.preencher(STATE.dadosNota);
            if (window.ComercialClassificacao) {
                window.ComercialClassificacao.preencher(STATE.dadosNota).then(pesos => {
                    if (window.ComercialDistribuicao) window.ComercialDistribuicao.preencher(STATE.dadosNota, pesos);
                });
            }
            
            // 3. Atualiza a lista lateral
            if (window.ComercialFiltros && window.ComercialFiltros.atualizar) {
                window.ComercialFiltros.atualizar();
            }

        } catch (e) {
            window.ComercialUtils.mostrarToast(e.message, "erro");
            btn.disabled = false; btn.textContent = "DESFATURAR";
        }
    };

    const fechar = () => {
        document.getElementById('modalFaturamento').style.display = 'none';
    };

    const getItens = () => STATE.itens;
    return { abrir, editarPreco, toggleInss, recalcularLiquido, faturar, desfaturar, fechar, getItens };
})();