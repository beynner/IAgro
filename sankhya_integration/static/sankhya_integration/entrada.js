;(function(){
    // Configuração centralizada de URLs
    const API_URLS = {
        ITEM_LIST: '/sankhya/item/list/',
        ITEM_SAVE: '/sankhya/item/save/',
        ITEM_PLAN: '/sankhya/item/plan/',
        ITEM_DELETE: '/sankhya/item/delete/',
        ITEM_FINALIZE: '/sankhya/item/finalize/',
        HEADER_UPDATE: '/sankhya/header/update/',
        HEADER_SAVE: '/sankhya/compras/central/salvar/',
        LOTE_SEARCH: '/sankhya/lote/search/',
        PROD_SEARCH: '/sankhya/produtos/search/',
        PARC_SEARCH: '/sankhya/parceiros/search/',
        TOP_SEARCH: '/sankhya/top/search/',
        NAT_SEARCH: '/sankhya/natureza/search/',
        CENCUS_SEARCH: '/sankhya/cencus/search/',
        VOL_SEARCH: '/sankhya/vol/search/',
        NOTA_DELETE: '/sankhya/nota/delete/',
        NOTA_CHECK_CLASS: '/sankhya/nota/check-classificacao/',
        NOTA_DIAGNOSE: '/sankhya/nota/diagnose/',
        CENTRAL_AJAX: '/sankhya/compras/central/'
    };

    // Utilitário para debounce (evita múltiplas chamadas enquanto digita)
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    }

    // Overlay controller shared across navigation points
    const IAOverlay = (()=>{
      const el = document.getElementById('pageOverlay');
      return {
        show(){ if(!el) return; el.classList.remove('hidden'); el.style.display = 'flex'; },
        hide(){ if(!el) return; el.classList.add('hidden'); setTimeout(()=>{ try{ el.style.display = 'none'; }catch(e){ console.warn('Overlay hide failed', e); } }, 280); }
      };
    })();
    try { window.IAOverlay = IAOverlay; } catch(e){ console.warn('IAOverlay export failed', e); }
    // Show overlay during navigation/refresh, hide after DOM ready (earlier)
    window.__IA_INITIAL_LOADING = true;
    document.addEventListener('DOMContentLoaded', function(){ try{ IAOverlay.hide(); }catch(e){ console.warn('DOMContentLoaded overlay hide failed', e); } });
    window.addEventListener('load', ()=>{ setTimeout(()=>{ try{ IAOverlay.hide(); window.__IA_INITIAL_LOADING = false; }catch(e){ console.warn('Load overlay hide failed', e); } }, 200); });
    window.addEventListener('beforeunload', ()=>{ try{ IAOverlay.show(); }catch(e){ console.warn('Beforeunload overlay show failed', e); } });
    window.addEventListener('pagehide', ()=>{ try{ IAOverlay.show(); }catch(e){ console.warn('Pagehide overlay show failed', e); } });

    const tbl = document.getElementById('notasTable');
    const listEl = document.getElementById('notasList');
    const panelItemsBody = document.getElementById('panelItemsBody');
    if (!tbl) return;
    // Helpers to render items into bottom panel
    
    function panelRenderEmpty(){ if(panelItemsBody) panelItemsBody.innerHTML = '<tr><td colspan="10" class="ia-muted">Nenhum item para a seleção.</td></tr>'; }
    
    function panelRenderRows(rows){
      if(!panelItemsBody) return;
      if(!rows || !rows.length){ panelRenderEmpty(); return; }
      let html = '';
      for(const it of rows){
        const ctrl = it.lote || '';
        const cod = (it.cod!=null? it.cod : '');
        const descr = it.descr || '';
        
        // ==========================================================================
        // LÓGICA DE VOLUME VIA CODVOLPARC (PAINEL INFERIOR)
        // ==========================================================================
        // Prioriza o CODVOLPARC (volume original). Se vazio, usa o codvol do estoque.
        const volExibicao = (it.codvolparc || it.codvol || '').trim().toLowerCase();

        const qtd = (it.qtd != null ? formatBR1(parseFloat(it.qtd)) : '');
        const peso = (it.peso != null ? formatBR1(parseFloat(it.peso)) : '');
        const classif = (it.classifica==null? '' : (it.classifica? 'Sim':'Não'));
        const totalKg = (it.total != null ? formatBR1(parseFloat(it.total)) : '');
        const vlt = (it.vlt!=null? it.vlt : '');
        const obs = it.obs || '';

        // Na montagem da linha, a coluna 4 usa o volExibicao
        html += `<tr><td>${ctrl}</td><td>${cod}</td><td>${descr}</td><td>${volExibicao}</td><td>${qtd}</td><td>${peso}</td><td>${classif}</td><td>${totalKg}</td><td>${vlt}</td><td>${obs}</td></tr>`;
      }
      panelItemsBody.innerHTML = html;
    }

    async function panelLoadItems(nunota){
      const resolved = normalizeNunota(nunota);
      if(!resolved){ panelRenderEmpty(); return; }
      // cache-first
      let j=null; try{ j = window.__ITEMS_CACHE && window.__ITEMS_CACHE[String(resolved)]; }catch(e){ console.debug('Cache access failed', e); }
      if(j && j.ok){ panelRenderRows(j.items || j.results || []); }
      // background fetch to refresh (and seed cache) if missing or for freshness
      try{
        const url = API_URLS.ITEM_LIST + '?nunota=' + encodeURIComponent(resolved);
        const r = await fetch(url, { credentials: 'same-origin' });
        let jj={}; try{ jj = await r.json(); }catch(e){ console.error('JSON parse failed', e); jj = {}; }
        if(jj && jj.ok){
          try{ window.__ITEMS_CACHE = window.__ITEMS_CACHE || {}; window.__ITEMS_CACHE[String(resolved)] = jj; }catch(e){ console.warn('Cache write failed', e); }
          // only re-render if the selected nunota is still the same
          const active = tbl.querySelector('tbody tr.row--click.row--active');
          const cur = active && active.dataset && active.dataset.nunota;
          if(String(cur) === String(resolved)) panelRenderRows(jj.items || jj.results || []);
        }
      }catch(e){ console.error('panelLoadItems fetch failed', e); }
    }

    let clickTimer = null;
    const CLICK_DELAY = 250; // ms
    // Items prefetch controls
    const ITEMS_PREFETCH = { inflight: Object.create(null), scheduled: Object.create(null) };
    
    function hasItemsInCache(nun){ try{ return !!(window.__ITEMS_CACHE && window.__ITEMS_CACHE[String(nun)] && window.__ITEMS_CACHE[String(nun)].ok); }catch(e){ console.debug('hasItemsInCache check failed', e); return false; } }
    
    async function prefetchItems(nun) {
    const resolved = (nun || '').trim();
    if (!resolved || resolved === 'undefined' || resolved === 'null') return; // Segurança extra
    if (hasItemsInCache(resolved)) return;
    if (ITEMS_PREFETCH.inflight[resolved]) return;

    ITEMS_PREFETCH.inflight[resolved] = true;
    try {
        const url = API_URLS.ITEM_LIST + '?nunota=' + encodeURIComponent(resolved);
        const r = await fetch(url, { credentials: 'same-origin' });
        
        // Se o servidor retornar 500, tratamos silenciosamente aqui
        if (!r.ok) {
            console.warn(`[Prefetch] Falha silenciosa para nota ${resolved}: Status ${r.status}`);
            return;
        }

        let j = {};
        try { j = await r.json(); } catch (e) { j = {}; }
        
        if (j && j.ok) {
            window.__ITEMS_CACHE = window.__ITEMS_CACHE || {};
            window.__ITEMS_CACHE[String(resolved)] = j;
        }
    } catch (e) {
        // Erros de rede ou abortos não devem poluir o console como erro crítico
        console.debug('[Prefetch] Abortado ou falha de conexão', e);
    } finally {
        delete ITEMS_PREFETCH.inflight[resolved];
    }
    }

    function schedulePrefetch(nun, delay){
      const resolved = (nun||'').trim(); if(!resolved) return;
      if (hasItemsInCache(resolved)) return;
      if (ITEMS_PREFETCH.scheduled[resolved]) return; // already scheduled
      ITEMS_PREFETCH.scheduled[resolved] = setTimeout(() => {
        try{ prefetchItems(resolved); }finally{ try{ clearTimeout(ITEMS_PREFETCH.scheduled[resolved]); }catch(e){ console.warn('clearTimeout failed', e); } delete ITEMS_PREFETCH.scheduled[resolved]; }
      }, typeof delay === 'number' ? delay : 150);
    }

    function updateDeleteBtn(){
      const btnDel = document.getElementById('btnDeleteNota');
      if (!btnDel) return;
      const hasActive = !!tbl.querySelector('tbody tr.row--click.row--active');
      if (hasActive) {
        btnDel.removeAttribute('disabled');
        btnDel.classList.add('danger');
      } else {
        btnDel.setAttribute('disabled','disabled');
        btnDel.classList.remove('danger');
      }
    }

    tbl.addEventListener('click', (e) => {
      const tr = e.target.closest('tr.row--click');
      if (!tr) return;
      // Realça imediatamente e habilita lixeira antes do reload
      Array.from(tbl.querySelectorAll('tbody tr.row--click')).forEach(r=>r.classList.remove('row--active'));
      tr.classList.add('row--active');
      updateDeleteBtn();
      if (clickTimer) clearTimeout(clickTimer);
      clickTimer = setTimeout(() => {
        // Clique simples: apenas seleciona e atualiza o card ITENS abaixo
        const nunota = tr.dataset.nunota;
        try { const url = new URL(window.location.href); url.searchParams.set('sel', nunota); window.history.replaceState({}, '', url.pathname + '?' + url.searchParams.toString()); } catch(e) { console.warn('History replaceState failed', e); }
        try{ panelLoadItems(nunota); }catch(err){ console.error('Falha ao carregar itens no painel', err); }
        clickTimer = null;
      }, CLICK_DELAY);
    });

    tbl.addEventListener('dblclick', (e) => {
      const tr = e.target.closest('tr[data-central-url]');
      if (!tr) return;
      if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; }
      const nunota = tr.dataset.nunota;
      if (!nunota) {
        // fallback: navigate to central
        window.location.href = tr.dataset.centralUrl;
        return;
      }
      // Dê preferência ao modal em-loco no duplo clique
      try{
        if (typeof openCabModalForEdit === 'function') openCabModalForEdit(nunota);
        if (typeof showItemsModal === 'function') showItemsModal(nunota);
        return;
      }catch(e){ console.error('Modal open failed', e); }
      // Fallback: navegar para a central
      try { IAOverlay.show(); window.location.href = `${API_URLS.CENTRAL_AJAX}?nunota=${encodeURIComponent(nunota)}`; } catch (e) { console.warn('Navigation failed', e); try{ IAOverlay.show(); }catch(e2){ console.warn('Overlay show failed', e2); } window.location.href = tr.dataset.centralUrl; }
    });

    // Navegação por teclado (setas) na lista de notas
    function getRows(){ return Array.from(tbl.querySelectorAll('tbody tr.row--click')); }
    
    function currentIndex(){
      const rows = getRows();
      if (!rows.length) return -1;
      const idx = rows.findIndex(r => r.classList.contains('row--active'));
      return idx >= 0 ? idx : 0;
    }
    
    function setActive(newIdx, triggerApply){
      const rows = getRows();
      if (!rows.length) return;
      newIdx = Math.max(0, Math.min(rows.length - 1, newIdx));
      const current = tbl.querySelector('tbody tr.row--active');
      const row = rows[newIdx];
      if (current === row) return; // nada a fazer
      rows.forEach(r => r.classList.remove('row--active'));
      row.classList.add('row--active');
      row.scrollIntoView({ block: 'nearest' });
      // Prefetch items for the active row to make dblclick instant
      try{ const nun = row && row.dataset && row.dataset.nunota; if(nun) schedulePrefetch(nun, 60); }catch(e){ console.debug('schedulePrefetch failed', e); }
      if (triggerApply) {
        applySelection();
      }
    }
    
    function applySelection(){
      const row = tbl.querySelector('tbody tr.row--active');
      if (!row) return;
      const nunota = row.dataset.nunota;
      // Atualiza URL sem recarregar para manter estado e atualizar itens do painel
      try { const url = new URL(window.location.href); url.searchParams.set('sel', nunota); window.history.replaceState({}, '', url.pathname + '?' + url.searchParams.toString()); } catch(e) { console.warn('History update failed', e); }
      try{ panelLoadItems(nunota); }catch(err){ console.error('applySelection panel load error', err); }
    }
    
    function isTypingTarget(el){
      const t = (el && el.tagName) ? el.tagName.toLowerCase() : '';
      return t === 'input' || t === 'textarea' || el.isContentEditable;
    }
    
    (listEl || document).addEventListener('keydown', (e) => {
      if (isTypingTarget(e.target)) return; // não interferir com inputs
      if (e.key === 'ArrowDown'){
        e.preventDefault();
        setActive(currentIndex() + 1, true); // aplica como clique simples
      } else if (e.key === 'ArrowUp'){
        e.preventDefault();
        setActive(currentIndex() - 1, true); // aplica como clique simples
      } else if (e.key === 'Enter'){
        e.preventDefault();
        applySelection();
      }
    });

    // Prefetch escalonado das primeiras notas para tornar o clique instantâneo
    try {
        const firstRows = getRows().slice(0, 4);
        firstRows.forEach((r, i) => {
            const nun = r?.dataset?.nunota;
            // i * 500ms dá tempo ao Oracle de responder cada uma sem enfileirar
            if (nun) schedulePrefetch(nun, 500 + (i * 500)); 
        });
    } catch (e) {
        console.debug('Initial prefetch failed', e);
    }

    // Auto-abrir modal de itens se nota foi recém-criada (parâmetro new=1)
    try {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('new') === '1') {
        const active = tbl.querySelector('tbody tr.row--click.row--active');
        if (active) {
          const nun = active.dataset.nunota;
          if (nun) {
            // Remover parâmetro 'new' da URL para evitar reabertura em refresh
            urlParams.delete('new');
            const cleanUrl = window.location.pathname + (urlParams.toString() ? '?' + urlParams.toString() : '');
            window.history.replaceState({}, '', cleanUrl);
            // Abrir modal de edição e itens para a nota recém-criada
            setTimeout(() => {
              if (typeof openCabModalForEdit === 'function') openCabModalForEdit(nun);
              if (typeof showItemsModal === 'function') showItemsModal(nun);
            }, 400); // pequeno delay para garantir que página carregou completamente
          }
        }
      }
    } catch(e) { console.warn('Auto-open modal failed', e); }

    // Hover-based prefetch to anticipate user choice
    tbl.addEventListener('mouseover', (e) => {
      const tr = e.target && e.target.closest ? e.target.closest('tr.row--click') : null;
      if (!tr) return;
      const nun = tr.dataset && tr.dataset.nunota; if (!nun) return;
      schedulePrefetch(nun, 120);
    });

    // Habilitar lixeira conforme seleção atual
    updateDeleteBtn();

    // Infinite scroll para 'Notas / Pedidos' — carrega 50 por página e anexa mais ao chegar no fim
    (function(){
      const list = document.getElementById('notasList');
      if(!list) return;
      let currentPage = Number(list.getAttribute('data-current-page')||1);
      let hasNext = list.getAttribute('data-has-next') === '1';
      const pageSize = Number(list.getAttribute('data-page-size')||50);
      let loading = false;
      const tbody = document.querySelector('#notasTable tbody');
      if(!tbody) return;
      const sentinel = document.createElement('tr');
      sentinel.id = 'notas-scroll-sentinel';
      sentinel.innerHTML = `<td colspan="3" class="ia-placeholder" style="text-align:center">Deslize para carregar mais...</td>`;
      tbody.appendChild(sentinel);
      async function fetchPage(page){
        try{
          loading = true;
          sentinel.querySelector('td').textContent = 'Carregando...';
          const fm = document.getElementById('filtersForm');
          const params = new URLSearchParams(new FormData(fm || document.createElement('form')));
          params.set('page', String(page));
          const url = window.location.pathname + '?' + params.toString();
          console.log('[notas] fetch page', page, 'url:', url);
          const res = await fetch(url, { credentials: 'same-origin' });
          console.log('[notas] response', res.status, res.ok);
          if(!res.ok) { hasNext = false; return []; }
          const txt = await res.text();
          const doc = new DOMParser().parseFromString(txt, 'text/html');
          // Prefer server-provided flag when available
          const listNode = doc.querySelector('#notasList');
          if (listNode && typeof listNode.dataset.hasNext !== 'undefined') {
            hasNext = listNode.dataset.hasNext === '1';
            console.log('[notas] server hasNext:', hasNext);
          }
          const newRows = doc.querySelectorAll('#notasTable tbody tr.row--click');
          const rows = Array.from(newRows);
          console.log('[notas] rows found:', rows.length);
          try {
            const rowNunotas = rows.map(r => r.dataset && r.dataset.nunota).filter(Boolean);
            console.log('[notas] nunotas sample:', rowNunotas.slice(0, 12));
            const tbodyHtml = (doc.querySelector('#notasTable tbody') || {}).innerHTML || '';
            console.log('[notas] returned tbody length:', tbodyHtml.length, 'snippet:', tbodyHtml.slice(0, 200));
          } catch (e) { console.warn('[notas] debug parse error', e); }
          // If server didn't provide hasNext, fall back to heuristic
          if (!listNode || typeof listNode.dataset.hasNext === 'undefined') {
            if (rows.length < pageSize) { hasNext = false; }
          }
          return rows;
        } catch(e){
          console.error('Erro ao carregar próxima página de notas', e);
          hasNext = false;
          return [];
        } finally {
          loading = false;
          sentinel.querySelector('td').textContent = hasNext ? 'Deslize para carregar mais...' : 'Fim da lista';
        }
      }
      const io = new IntersectionObserver(async (entries) => {
        for(const ent of entries){
          if(ent.isIntersecting && !loading && hasNext){
            const nextPage = currentPage + 1;
            const rows = await fetchPage(nextPage);
            if(rows && rows.length){
              // OTIMIZAÇÃO: Usar DocumentFragment para evitar múltiplos reflows
              const fragment = document.createDocumentFragment();
              rows.forEach(r => fragment.appendChild(r));
              tbody.insertBefore(fragment, sentinel);
              currentPage = nextPage;
            } else {
              hasNext = false;
              sentinel.querySelector('td').textContent = 'Fim da lista';
              io.disconnect();
            }
          }
        }
      }, { root: list, rootMargin: '200px', threshold: 0.1 });
      io.observe(sentinel);
    })();
    
    const getCookie = window.__getCookie || window.getCookie || function(name){
      const m = document.cookie.match(new RegExp('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)'));
      return m ? decodeURIComponent(m[2]) : null;
    };

    const postJSON = window.__postJSON || window.postJSON || async function(url, body){
      const csrftoken = getCookie('csrftoken');
      const headers = { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' };
      if (csrftoken) headers['X-CSRFToken'] = csrftoken;
      const r = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: headers, body: JSON.stringify(body) });
      let data = null;
      try{ data = await r.json(); }catch(e){ console.warn('postJSON parse failed', e); data = null; }
      return { ok: r.ok, status: r.status, statusText: r.statusText, body: data };
    };
    
    // Ação da lixeira: excluir a nota (TGFCAB) e itens (TGFITE)
    const btnDeleteNota = document.getElementById('btnDeleteNota');
    
    btnDeleteNota?.addEventListener('click', async ()=>{
      const active = tbl.querySelector('tbody tr.row--click.row--active');
      if (!active) return;
      const nun = active.getAttribute('data-nunota');
      
      // 1. FAZ A CHECAGEM USANDO A MESMA ROTA (Passando a flag apenas_checar)
      const checkRes = await postJSON(API_URLS.NOTA_DELETE, { nunota: parseInt(nun,10), apenas_checar: true });
      
      if (!checkRes.ok) {
          // Se esbarrou na trava, mostra o erro do Python e aborta!
          showToast(checkRes.body?.error || 'Erro de validação.', 'error');
          return; // 🛑 Para aqui, antes do confirm!
      }

      // 2. PASSOU NA TRAVA! Agora sim, pede a confirmação ao usuário
      const ok = confirm(`Confirma excluir a nota ${nun} e todos os itens?`);
      if (!ok) return;
      
      // 3. EXCLUI DE VERDADE (Sem a flag)
      const res = await postJSON(API_URLS.NOTA_DELETE, { nunota: parseInt(nun,10) });
      
      if (res.ok && (res.body?.deleted_cab || 0) > 0){
        showToast(`Nota ${nun} excluída com sucesso.`, 'success');
        setTimeout(() => {
          try {
            const url = new URL(window.location.href);
            url.searchParams.delete('sel');
            window.location.href = url.pathname + '?' + url.searchParams.toString();
          } catch(e){ window.location.reload(); }
        }, 1000);
      } else {
        if(handleValeLockedError(res)) return;
        showToast(res.body?.error || 'Falha ao excluir nota.', 'error');
      }
    });

    // Imprimir
    const btnPrint = document.getElementById('btnPrint');
    if (btnPrint && !btnPrint.disabled) {
      btnPrint.addEventListener('click', () => window.print());
    }

    // Limpar formulário sem aplicar filtros automaticamente
    const clearBtn = document.getElementById('btnClear');
    const btnUpdate = document.getElementById('btnUpdate');
    const form = document.getElementById('filtersForm');
    // Helper to trigger the filters form submission (preserves existing submit handler)
    
    if (btnUpdate) {
      btnUpdate.addEventListener('click', (e) => {
        e.preventDefault(); // Evita o comportamento padrão caso o botão esteja dentro de um form
        
        // Chama a tela de carregamento do sistema (feedback visual)
        try { IAOverlay.show(); } catch(err) {}
        
        // Recarrega a página mantendo os parâmetros atuais da URL (filtros)
        window.location.reload();
      });
    }

    function applyFilters(){
      try{
        const frm = document.getElementById('filtersForm'); if(!frm) return;
        try{ console.debug('applyFilters called'); }catch(e){ }
        // Prefer triggering the visible submit button so the existing submit handler runs
        const submitBtn = document.querySelector('button[form="filtersForm"][type="submit"]');
        if(submitBtn){ submitBtn.click(); return; }
        if(typeof frm.requestSubmit === 'function'){ frm.requestSubmit(); return; }
        frm.submit();
      }catch(e){ console.error('applyFilters error', e); }
    }

    /**
     * Mai/2026 — Renderiza chips de filtros ativos no #filtrosAtivosChips.
     * Lê os valores atuais dos campos (preenchidos pelo backend via params).
     * Click no × zera o(s) campo(s) correspondente(s) e chama applyFilters().
     * Roda 1x no boot — a página recarrega no submit, renderiza tudo de novo.
     */
    function renderChipsFiltrosEntrada(){
      const cont = document.getElementById('filtrosAtivosChips');
      if (!cont) return;
      cont.innerHTML = '';
      const chips = [];

      // Período (só mostra se != hoje em ambas as datas)
      const hoje = new Date().toISOString().split('T')[0];
      const ini = document.querySelector('input[name="start"]')?.value;
      const fim = document.querySelector('input[name="end"]')?.value;
      if (ini && fim && (ini !== hoje || fim !== hoje)) {
        const txt = ini === fim
          ? new Date(ini + 'T12:00:00').toLocaleDateString('pt-BR')
          : `${new Date(ini + 'T12:00:00').toLocaleDateString('pt-BR')} → ${new Date(fim + 'T12:00:00').toLocaleDateString('pt-BR')}`;
        chips.push({
          rotulo: 'Período', valor: txt,
          remover: () => {
            // Volta pra hoje em ambas
            const startEl = document.querySelector('input[name="start"]');
            const endEl   = document.querySelector('input[name="end"]');
            if (startEl) startEl.value = hoje;
            if (endEl)   endEl.value   = hoje;
            applyFilters();
          },
        });
      }

      // Pedido / Vale
      const nunota = document.querySelector('input[name="nunota_ini"]')?.value;
      if (nunota) chips.push({
        rotulo: 'Pedido', valor: nunota,
        remover: () => {
          const el = document.querySelector('input[name="nunota_ini"]');
          if (el) el.value = '';
          applyFilters();
        },
      });

      // Produto (Fabricante)
      const fab = document.getElementById('fabricanteHidden')?.value;
      if (fab) {
        const visivel = document.getElementById('prodSearch')?.value || fab;
        chips.push({
          rotulo: 'Produto', valor: visivel,
          remover: () => {
            document.getElementById('fabricanteHidden').value = '';
            const vis = document.getElementById('prodSearch');
            if (vis) vis.value = '';
            applyFilters();
          },
        });
      }

      // Parceiro
      const codparc = document.getElementById('codparc')?.value;
      if (codparc) {
        const visivel = document.getElementById('parcSearch')?.value || codparc;
        chips.push({
          rotulo: 'Parceiro', valor: visivel,
          remover: () => {
            document.getElementById('codparc').value = '';
            const vis = document.getElementById('parcSearch');
            if (vis) vis.value = '';
            applyFilters();
          },
        });
      }

      chips.forEach(chip => {
        const el = document.createElement('span');
        el.className = 'iagro-filtro-chip';
        el.innerHTML = `
          <span class="chip-rotulo">${chip.rotulo}:</span>
          <span class="chip-valor" title="${chip.valor}">${chip.valor}</span>
          <button type="button" class="chip-remover" title="Remover" aria-label="Remover">×</button>
        `;
        el.querySelector('.chip-remover').addEventListener('click', chip.remover);
        cont.appendChild(el);
      });
    }
    // Boot: render no carregamento da página
    try { renderChipsFiltrosEntrada(); } catch (e) { console.warn('renderChipsFiltrosEntrada falhou', e); }
    
    if (clearBtn && form) {
      clearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const inputs = form.querySelectorAll('input');
        inputs.forEach((inp) => {
          if (inp.type === 'hidden' || inp.type === 'text' || inp.type === 'number' || inp.type === 'date') {
            inp.value = '';
          }
        });
        // Campos específicos fora do padrão
        const parcHidden = document.getElementById('codparc');
        if (parcHidden) parcHidden.value = '';
        const parcVisible = document.getElementById('parcSearch');
        if (parcVisible) parcVisible.value = '';
        const fabricanteHidden = document.getElementById('fabricanteHidden');
        if (fabricanteHidden) fabricanteHidden.value = '';
        const prodVisible = document.getElementById('prodSearch');
        if (prodVisible) prodVisible.value = '';
        // After clearing visible and hidden fields, apply filters automatically
        try{ applyFilters(); }catch(e){ console.error('applyFilters failed', e); }
      });
    }

    // Ao aplicar, forçar page=1
    if (form) {
      form.addEventListener('submit', (ev) => {
        try{ // dump form values for debugging
          const data = {};
          new FormData(form).forEach((v,k)=>{ data[k]=v; });
          console.debug('filtersForm submit - values:', data);
        }catch(e){ console.debug('Form dump failed', e); }
        // Ensure pagination resets
        let pg = form.querySelector('input[name="page"]');
        if (!pg) {
          pg = document.createElement('input');
          pg.type = 'hidden';
          pg.name = 'page';
          form.appendChild(pg);
        }
        pg.value = '1';

        // Copy visible typeahead values into the hidden code inputs when appropriate
        try {
          // Mai/2026 — Fabricante (texto puro, igual ao Comercial).
          // Se operador só digitou sem selecionar no dropdown, copia o texto
          // visível pro hidden — backend filtra por LIKE %fabricante%.
          const prodVis = document.getElementById('prodSearch');
          const fabricanteHidden = document.getElementById('fabricanteHidden');
          if (prodVis && fabricanteHidden) {
            const raw = (prodVis.value || '').trim();
            if (raw && !fabricanteHidden.value) {
                fabricanteHidden.value = raw;
            }
          }
          
          // Partner
          const parcVis = document.getElementById('parcSearch');
          const parcHidden = document.getElementById('codparc');
          if (parcVis && parcHidden) {
            const rawp = (parcVis.value || '').trim();
            if ((!parcHidden.value || String(parcHidden.value).trim() === '') && rawp) {
              const mp = rawp.match(/^(\d+)/);
              if (mp && mp[1]) parcHidden.value = mp[1];
            }
          }
        } catch (e) { console.warn('Typeahead copy failed', e); }

        try{ IAOverlay.show(); }catch(e){ console.warn('Overlay show failed', e); }
      });
      // Replicar data inicial para data final ao digitar no primeiro campo
      try {
        const startDate = form.querySelector('input[name="start"]');
        const endDate = form.querySelector('input[name="end"]');
        if (startDate && endDate) {
          const syncEnd = () => {
            try{
              const val = startDate.value;
              // Check if date is defined and year is reasonable (>1000) to avoid triggering on partial year typing
              if (val && val.length === 10 && parseInt(val.split('-')[0], 10) > 1000){
                const prev = endDate.value || '';
                endDate.value = val;
                // If we changed the end date from empty to a value, apply filters.
                try{ if ((endDate.value || '').trim() && prev !== endDate.value) { applyFilters(); } }catch(e){ console.error('applyFilters failed', e); }
              }
            }catch(e){ console.warn('Date sync failed', e); }
          };
          startDate.addEventListener('change', syncEnd);

          // Quando o usuário preencher a segunda data (end) — aplicar filtros automaticamente
          endDate.addEventListener('change', () => {
            try{
              const v = (endDate.value || '').trim();
              if (v && v.length === 10 && parseInt(v.split('-')[0], 10) > 1000) { applyFilters(); }
            }catch(e){ console.error('applyFilters failed', e); }
          });

          // Date navigation buttons
          const btnPrev = document.getElementById('btnPrevDay');
          const btnNext = document.getElementById('btnNextDay');
          const shiftDate = (delta) => {
            try {
              let d = startDate.value ? new Date(startDate.value + 'T12:00:00') : new Date();
              if (isNaN(d.getTime())) d = new Date();
              d.setDate(d.getDate() + delta);
              const y = d.getFullYear();
              const m = String(d.getMonth() + 1).padStart(2, '0');
              const day = String(d.getDate()).padStart(2, '0');
              startDate.value = `${y}-${m}-${day}`;
              startDate.dispatchEvent(new Event('change'));
            } catch(e) { console.error(e); }
          };
          if(btnPrev) btnPrev.addEventListener('click', (e) => { e.preventDefault(); shiftDate(-1); });
          if(btnNext) btnNext.addEventListener('click', (e) => { e.preventDefault(); shiftDate(1); });
        }
      } catch (_) { }
      // ==============================================================================
      // FILTRO PEDIDO COM TEMPORIZADOR (Pesquisa Parcial e Manutenção de Foco)
      // ==============================================================================
      try {
        const form = document.getElementById('filtersForm');
        const pedidoInput = form ? form.querySelector('input[name="nunota_ini"]') : null;
        
        if (pedidoInput) {
          // Aumentado para 800ms para você ter tempo de digitar sem a tela piscar no meio
          pedidoInput.addEventListener('input', debounce(() => {
            try{
              // Injeta no sessionStorage quem causou o reload para devolvermos o foco
              sessionStorage.setItem('focusAfterReload', 'nunota_ini');
              applyFilters();
            }catch(e){ console.error('applyFilters failed', e); }
          }, 800));

          pedidoInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              try{ 
                sessionStorage.setItem('focusAfterReload', 'nunota_ini');
                applyFilters(); 
              }catch(err){}
            }
          });
        }

        // DEVOLVE O FOCO APÓS O RELOAD
        document.addEventListener("DOMContentLoaded", () => {
          if (sessionStorage.getItem('focusAfterReload') === 'nunota_ini') {
            const inputParaFocar = document.querySelector('input[name="nunota_ini"]');
            if (inputParaFocar) {
              inputParaFocar.focus();
              // Joga o cursor para o final do texto
              const val = inputParaFocar.value;
              inputParaFocar.value = '';
              inputParaFocar.value = val;
            }
            sessionStorage.removeItem('focusAfterReload');
          }
        });
      } catch (_) { }

      // Aplicar fallback de dias ao perder foco ou confirmar
      try {
        const daysInput = form.querySelector('input[name="days"]');
        if (daysInput) {
          const triggerDaysFilter = () => {
            try {
              const raw = (daysInput.value || '').trim();
              if (raw === '' || /^\d+$/.test(raw) || raw.toLowerCase() === 'all') {
                console.log('days blur/change -> applyFilters', raw);
                applyFilters();
              }
            } catch (e) { console.warn('Days filter failed', e); }
          };
          daysInput.addEventListener('blur', triggerDaysFilter);
          daysInput.addEventListener('change', triggerDaysFilter);
          daysInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              triggerDaysFilter();
            }
          });
        }

        // Buttons to quickly toggle 'days' filter
        try {
          const btnShowAll = document.getElementById('btnShowAll');
          const btnLast10 = document.getElementById('btnLast10');
          if (btnShowAll) {
            btnShowAll.addEventListener('click', () => {
              const fm = document.getElementById('filtersForm');
              if (!fm) return;
              let d = fm.querySelector('input[name="days"]');
              if (!d) { d = document.createElement('input'); d.type = 'hidden'; d.name = 'days'; fm.appendChild(d); }
              d.value = 'all';
              try{ applyFilters(); }catch(e){ console.warn('applyFilters failed, reloading', e); window.location.href = window.location.pathname + '?days=all'; }
            });
          }
          if (btnLast10) {
            btnLast10.addEventListener('click', () => {
              const fm = document.getElementById('filtersForm');
              if (!fm) return;
              let d = fm.querySelector('input[name="days"]');
              if (!d) { d = document.createElement('input'); d.type = 'hidden'; d.name = 'days'; fm.appendChild(d); }
              d.value = '10';
              try{ applyFilters(); }catch(e){ console.warn('applyFilters failed, reloading', e); window.location.href = window.location.pathname + '?days=10'; }
            });
          }
        } catch (_) { }
      } catch (_) { }
    }

    // Paginação preservando filtros
    function goToPage(targetPage){
      try {
        const url = new URL(window.location.href);
        url.searchParams.set('page', String(targetPage));
        try{ IAOverlay.show(); }catch(e){ console.warn('Overlay failed', e); }
        window.location.href = url.pathname + '?' + url.searchParams.toString();
      } catch (err) {
        const qs = window.location.search ? window.location.search + '&' : '?';
        try{ IAOverlay.show(); }catch(e){ console.warn('Overlay failed', e); }
        window.location.href = window.location.pathname + qs + 'page=' + encodeURIComponent(targetPage);
      }
    }
    
    const btnPrev = document.getElementById('btnPrev');
    if (btnPrev && !btnPrev.disabled) {
      btnPrev.addEventListener('click', () => goToPage(btnPrev.dataset.page));
    }
    
    const btnNext = document.getElementById('btnNext');
    if (btnNext && !btnNext.disabled) {
      btnNext.addEventListener('click', () => goToPage(btnNext.dataset.page));
    }

    // Helper: move focus to next focusable element
    function focusNext(el){
      try{
        const focusable = Array.from(document.querySelectorAll('input, select, textarea, button, [tabindex]'))
          .filter(x=> !x.disabled && x.tabIndex >= 0 && x.offsetParent !== null);
        const idx = focusable.indexOf(el);
        if (idx >= 0 && idx+1 < focusable.length){ focusable[idx+1].focus(); }
      }catch(e){ console.warn('focusNext failed', e); }
    }

    // ==============================================================================
    // TYPEAHEAD FILTROS (Parceiro e Produto)
    // ==============================================================================

    // 1. Typeahead Parceiro
    (function(){
      const parcInput = document.getElementById('parcSearch');
      const codparcInput = document.getElementById('codparc');
      const dropdown = document.getElementById('parcDropdown');
      if(!parcInput || !codparcInput || !dropdown) return;

      function hideDropdown() { dropdown.style.display = 'none'; dropdown.innerHTML=''; }
      function showDropdown(items) {
        if (!items || !items.length) { hideDropdown(); return; }
        dropdown.innerHTML = items.map((it,idx) => `<div class="dd-item typeahead-item${idx===0?' active':''}" data-cod="${it.codparc}" data-nome="${it.nomeparc}">${it.codparc} — ${it.nomeparc}</div>`).join('');
        dropdown.style.display = 'block';
      }
      function fetchPartners(q) {
        const url = `${API_URLS.PARC_SEARCH}?q=${encodeURIComponent(q)}&limit=10`;
        fetch(url).then(r => r.json()).then(data => showDropdown(data.results || [])).catch(() => hideDropdown());
      }
      parcInput.addEventListener('input', debounce((e) => {
        const raw = e.target.value.trim();
        if (raw) fetchPartners(raw); else hideDropdown();
      }, 400));
      parcInput.addEventListener('keydown', (e)=>{
        if (dropdown.style.display !== 'none'){
          if(e.key==='ArrowDown'){ e.preventDefault(); const items=Array.from(dropdown.querySelectorAll('.dd-item')); if(!items.length) return; const cur=items.findIndex(x=>x.classList.contains('active')); let nxt=(cur+1+items.length)%items.length; items.forEach(x=>x.classList.remove('active')); items[nxt].classList.add('active'); items[nxt].scrollIntoView({block:'nearest'}); return; }
          if(e.key==='ArrowUp'){ e.preventDefault(); const items=Array.from(dropdown.querySelectorAll('.dd-item')); if(!items.length) return; const cur=items.findIndex(x=>x.classList.contains('active')); let nxt=(cur-1+items.length)%items.length; items.forEach(x=>x.classList.remove('active')); items[nxt].classList.add('active'); items[nxt].scrollIntoView({block:'nearest'}); return; }
          if(e.key==='Enter' || e.key==='Tab'){ const el = dropdown.querySelector('.dd-item.active') || dropdown.querySelector('.dd-item'); if(el){ e.preventDefault(); codparcInput.value = el.dataset.cod; parcInput.value = `${el.dataset.cod} — ${el.dataset.nome}`; hideDropdown(); focusNext(parcInput); try{ applyFilters(); }catch(err){} } }
          if(e.key==='Escape'){ hideDropdown(); }
        }
      });
      dropdown.addEventListener('click', (e) => { const item = e.target.closest('.dd-item'); if (!item) return; codparcInput.value = item.dataset.cod; parcInput.value = `${item.dataset.cod} — ${item.dataset.nome}`; hideDropdown(); focusNext(parcInput); try{ applyFilters(); }catch(err){} });
      document.addEventListener('click', (e) => { if (!dropdown.contains(e.target) && e.target !== parcInput) hideDropdown(); });
    })();

    // 2. Typeahead Fabricante (campo rotulado "Produto" na UI, mas filtra por
    // FABRICANTE — Mai/2026 alinha com padrão do Comercial)
    (function(){
      const prodInput = document.getElementById('prodSearch');
      const prodHidden = document.getElementById('fabricanteHidden');
      const dropdown = document.getElementById('prodDropdown');
      if(!prodInput || !prodHidden || !dropdown) return;

      function hideDropdown() { dropdown.style.display = 'none'; dropdown.innerHTML=''; }
      function showDropdown(items) {
        if (!items || !items.length) { hideDropdown(); return; }
        dropdown.innerHTML = items.map((it, idx) => {
            const nome = (it.fabricante || it.descr || '').trim();
            return `<div class="dd-item typeahead-item${idx===0?' active':''}" data-descr="${nome}">${nome}</div>`;
        }).join('');
        dropdown.style.display = 'block';
      }
      function fetchProds(q) {
        // Endpoint retorna FABRICANTEs distintos (compartilha rota com produtos
        // via flag fabricante=1 — mesmo padrão do Comercial).
        const url = `${API_URLS.PROD_SEARCH}?q=${encodeURIComponent(q)}&limit=15&fabricante=1`;
        fetch(url)
          .then(r => r.json())
          .then(data => showDropdown(data.results || []))
          .catch(() => hideDropdown());
      }
      prodInput.addEventListener('input', debounce((e) => {
        const raw = e.target.value.trim();
        if (raw) fetchProds(raw); else hideDropdown();
      }, 400));
      prodInput.addEventListener('keydown', (e)=>{
        if (dropdown.style.display !== 'none'){
          if(e.key==='ArrowDown'){ e.preventDefault(); const items=Array.from(dropdown.querySelectorAll('.dd-item')); if(!items.length) return; const cur=items.findIndex(x=>x.classList.contains('active')); let nxt=(cur+1+items.length)%items.length; items.forEach(x=>x.classList.remove('active')); items[nxt].classList.add('active'); items[nxt].scrollIntoView({block:'nearest'}); return; }
          if(e.key==='ArrowUp'){ e.preventDefault(); const items=Array.from(dropdown.querySelectorAll('.dd-item')); if(!items.length) return; const cur=items.findIndex(x=>x.classList.contains('active')); let nxt=(cur-1+items.length)%items.length; items.forEach(x=>x.classList.remove('active')); items[nxt].classList.add('active'); items[nxt].scrollIntoView({block:'nearest'}); return; }
          if(e.key==='Enter' || e.key==='Tab'){
            const el = dropdown.querySelector('.dd-item.active') || dropdown.querySelector('.dd-item');
            if(el){
                e.preventDefault();
                // Fabricante é texto puro (sem código) — hidden e visível recebem o mesmo nome
                prodHidden.value = el.dataset.descr;
                prodInput.value = el.dataset.descr;
                hideDropdown();
                focusNext(prodInput);
                try{ applyFilters(); }catch(err){}
            }
          }
          if(e.key==='Escape'){ hideDropdown(); }
        }
      });
      dropdown.addEventListener('click', (e) => {
        const item = e.target.closest('.dd-item');
        if (!item) return;
        prodHidden.value = item.dataset.descr;
        prodInput.value = item.dataset.descr;
        hideDropdown();
        focusNext(prodInput);
        try{ applyFilters(); }catch(err){}
      });
      document.addEventListener('click', (e) => { if (!dropdown.contains(e.target) && e.target !== prodInput) hideDropdown(); });
    })();

    // Novo lançamento: abrir modal de TOPs
    const topModal = document.getElementById('topModal');
    const btnNew = document.getElementById('btnNew');
    const topClose = document.getElementById('topClose');
    const topList = document.getElementById('topList');
    const topSearch = document.getElementById('topSearch');
    function openTopModal(){ topModal.style.display = 'flex'; topSearch.value=''; loadTops(''); topSearch.focus(); }
    function closeTopModal(){ topModal.style.display = 'none'; topList.innerHTML=''; }
    
    function loadTops(q){
      const url = `${API_URLS.TOP_SEARCH}?q=${encodeURIComponent(q||'')}&limit=20`;
      fetch(url).then(r=>r.json()).then(data=>{
        const items = (data.results||[]).map(it=>{
          const tm = (it.tipmov||'').trim();
          const suffix = tm ? ` (TIPMOV ${tm})` : '';
          return `<div class="dd-item dd-item-row" data-cod="${it.cod}">${it.cod} — ${it.descr||''}${suffix}</div>`;
        }).join('');
        topList.innerHTML = items || '<div class="ia-padding ia-muted">Nenhuma TOP encontrada.</div>';
        // Ativar primeiro item por padrão
        const first = topList.querySelector('.dd-item');
        if (first) first.classList.add('active');
      }).catch(()=>{ topList.innerHTML = '<div class="ia-padding ia-muted">Erro ao carregar TOPs.</div>'; });
    }
    // The New button now links directly to Central with TOP 11; keep default navigation
    // (previously opened a TOP selection modal)
    topClose?.addEventListener('click', closeTopModal);
    topModal?.addEventListener('click', (e)=>{ if(e.target===topModal) closeTopModal(); });
    topSearch?.addEventListener('input', ()=>{ const v=topSearch.value.trim(); if(v.length===0 || v.length>=1) loadTops(v); });
    
    function moveTopSel(step){
      const items = Array.from(topList.querySelectorAll('.dd-item'));
      if (!items.length) return;
      let idx = items.findIndex(x=>x.classList.contains('active'));
      if (idx < 0) idx = 0;
      idx = (idx + step + items.length) % items.length;
      items.forEach(x=>x.classList.remove('active'));
      items[idx].classList.add('active');
      items[idx].scrollIntoView({block:'nearest'});
    }
    
    function pickTopSel(){
      const el = topList.querySelector('.dd-item.active') || topList.querySelector('.dd-item');
      if (!el) return;
      const cod = el.getAttribute('data-cod');
      window.location.href = `${API_URLS.CENTRAL_AJAX}?codtipoper=${encodeURIComponent(cod)}`;
    }
    
    topSearch?.addEventListener('keydown', (e)=>{
      if (e.key === 'ArrowDown') { e.preventDefault(); moveTopSel(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); moveTopSel(-1); }
      else if (e.key === 'Enter') { e.preventDefault(); pickTopSel(); }
      else if (e.key === 'Escape') { e.preventDefault(); closeTopModal(); }
    });
    
    topList?.addEventListener('click', (e)=>{
      const el = e.target.closest('[data-cod]');
      if(!el) return;
      const cod = el.getAttribute('data-cod');
      try{ IAOverlay.show(); }catch(e){ console.warn('Overlay failed', e); }
      window.location.href = `${API_URLS.CENTRAL_AJAX}?codtipoper=${encodeURIComponent(cod)}`;
    });
    
    // --- Novo: Modal de Cabeçalho (Portal) ---
    const cabModal = document.getElementById('cabModal');
    const cabClose = document.getElementById('cabClose');
    const cabCancel = document.getElementById('cabCancel');
    const cabSave = document.getElementById('cabSave');
    const btnNewEl = document.getElementById('btnNew');
    let cabEditingNunota = null; // when set, Save will call header_update endpoint
    let cabRecemCriado = null; // 🔥 Rastreia se a nota acabou de nascer e está vazia
    function _setOverlayVisible(visible){ try{ const ov = document.getElementById('cabModal'); const itemsOv = document.getElementById('cabItemsModal'); const rodOv = document.getElementById('rodapeModal'); if(ov) ov.style.display = visible ? 'block' : 'none'; if(itemsOv) itemsOv.style.display = visible ? 'block' : 'none'; if(rodOv) rodOv.style.display = visible ? 'block' : 'none'; }catch(e){ console.error('_setOverlayVisible', e); } }

    function showCabModal(){
      // defaults for new header: clear Parceiro when not editing
      try{
        if (!cabEditingNunota){
          const parcCode = document.getElementById('cab_codparc');
          const parcVis = document.getElementById('cab_parcSearch');
          if (parcCode) parcCode.value = '';
          if (parcVis) { parcVis.value = ''; parcVis.disabled = false; parcVis.removeAttribute('title'); }
        }
      }catch(e){ console.warn('Reset cab fields failed', e); }
      // show only the cab overlay and dock the card to left
      try{ const cabOv = document.getElementById('cabModal'); const itemsOv = document.getElementById('cabItemsModal'); const rodOv = document.getElementById('rodapeModal'); if(cabOv) cabOv.style.display = 'block'; if(itemsOv) itemsOv.style.display = 'none'; if(rodOv) rodOv.style.display = 'none'; }catch(e){ console.warn('Overlay toggle failed', e); }
      const cab = document.getElementById('cabCard'); if(cab){ cab.style.top = getViewportTopOffset() + 'px'; cab.style.left = '16px'; cab.style.opacity = '1'; }
      setTimeout(()=>{ try{ document.getElementById('cab_parcSearch')?.focus(); }catch(e){ console.debug('Focus failed', e); } },120);
    }
    
    // Helper to open modal in EDIT mode by pre-filling values from a central header object
    async function openCabModalForEdit(nunota){
      if (!nunota) return;
      // mark editing state
      cabEditingNunota = nunota;
      showCabModal();
      // Block fields that should not be edited (Parceiro)
      const parcVis = document.getElementById('cab_parcSearch'); 
      if(parcVis) { 
          parcVis.disabled = true; 
          parcVis.title = "Parceiro não pode ser alterado na edição."; 
      }
      // Try to fetch header data from central by requesting the compras_central endpoint and parsing values
      try{
        const url = `${API_URLS.CENTRAL_AJAX}?nunota=${encodeURIComponent(nunota)}&ajax_header=1`;
        const r = await fetch(url, { credentials: 'same-origin' });
        if (r.ok){
          const j = await r.json().catch(()=>null);
          if (j && j.form){
            // --- LOG DE DIAGNÓSTICO PARA VOCÊ VER NO F12 ---
            console.log("🔍 Dados do Cabeçalho recebidos do Sankhya:", j.form);

            // Preenchimento de campos básicos
            document.getElementById('cab_codemp').value = j.form.codemp || j.form.CODEMP || '1';
            try{ document.getElementById('cab_nunota').value = j.form.nunota || j.form.NUNOTA || ''; }catch(_){ }
            document.getElementById('cab_dtneg').value = j.form.dtneg || j.form.DTNEG || '';

            // --- TRATAMENTO DO PARCEIRO (CÓDIGO + NOME) ---
            const pCode = j.form.codparc || j.form.CODPARC || '';
            const pName = j.form.nomparc || j.form.NOMPARC || 
                          j.form.nomeparc || j.form.NOMEPARC || 
                          j.form.codparc_descr || j.form.CODPARC_DESCR || '';

            document.getElementById('cab_codparc').value = pCode;
            if (parcVis) {
                parcVis.value = (pCode && pName) ? `${pCode} — ${pName}` : (pCode || '');
            }

            // --- TIPO DE OPERAÇÃO (TOP) ---
            const topCode = j.form.codtipoper || j.form.CODTIPOPER || '';
            const topDescr = j.form.codtipoper_descr || j.form.CODTIPOPER_DESCR || '';
            document.getElementById('cab_top_cod').value = topCode;
            if (document.getElementById('cab_top')) {
                document.getElementById('cab_top').value = topCode ? `${topCode} — ${topDescr}` : '';
            }

            // --- NATUREZA ---
            const natCode = j.form.codnat || j.form.CODNAT || '';
            const natDescr = j.form.codnat_descr || j.form.CODNAT_DESCR || '';
            document.getElementById('cab_nat_cod').value = natCode;
            if (document.getElementById('cab_nat')) {
                document.getElementById('cab_nat').value = natCode ? `${natCode} — ${natDescr}` : '';
            }

            // --- CENTRO DE RESULTADO ---
            const cencusCode = j.form.codcencus || j.form.CODCENCUS || '';
            const cencusDescr = j.form.codcencus_descr || j.form.CODCENCUS_DESCR || '';
            document.getElementById('cab_cencus_cod').value = cencusCode;
            if (document.getElementById('cab_cencus')) {
                document.getElementById('cab_cencus').value = cencusCode ? `${cencusCode} — ${cencusDescr}` : '';
            }

            // --- OBSERVAÇÃO ---
            document.getElementById('cab_obs').value = j.form.obs || j.form.OBS || j.form.observacao || '';
          }
        }
      }catch(e){
        // ignore fetch errors; modal already open
      }
    }

    function hideCabModal(){
      const cab = document.getElementById('cabCard'); if(cab){ cab.style.left = '-1200px'; }
      // if items or rodape still open, keep overlay; otherwise hide
      setTimeout(()=>{ try{ const itemsCard = document.getElementById('cabItemsCard'); const rod = document.getElementById('rodapeCard'); const anyOpen = (itemsCard && itemsCard.style.left && itemsCard.style.left !== '100%') || (rod && rod.style.left && rod.style.left !== '100%'); if(!anyOpen) _setOverlayVisible(false); }catch(e){ console.warn('Overlay hide failed', e); _setOverlayVisible(false); } }, 320);
    }
    
    // Open modal instead of navigating when JS is available
    btnNewEl?.addEventListener('click', (e)=>{
      e.preventDefault(); cabEditingNunota = null; showCabModal();
    });

    async function interceptarFechamentoCabecalho() {
        if (cabRecemCriado) {
            const temItens = document.querySelectorAll('#itemsListBody tr[data-seq]').length > 0;
            if (!temItens) {
                await postJSON(API_URLS.NOTA_DELETE, { nunota: parseInt(cabRecemCriado, 10) });
                showToast('Cabeçalho vazio cancelado.', 'info');
                setTimeout(() => window.location.reload(), 600);
            }
            cabRecemCriado = null;
        }
        hideCabModal();
    }
    cabClose?.addEventListener('click', interceptarFechamentoCabecalho);
    cabCancel?.addEventListener('click', interceptarFechamentoCabecalho);

    // helpers `getCookie` and `postJSON` are provided by static/sankhya_integration/iagro_helpers.js

    // Mai/2026 — wrapper sobre IAgro.attachTypeahead. Mantém a assinatura legada
    // (inpId, hidId, ddId, url, options) e preserva o comportamento específico
    // do Entrada: propaga data-selecionado pro hidden e chama
    // window.__resetItemClassificaField após selecionar.
    function attachTA(inpId, hidId, ddId, url, options) {
      const lim = (options && typeof options.limit === 'number' && options.limit > 0)
                  ? Math.floor(options.limit) : 10;
      const hidEl = document.getElementById(hidId);
      return IAgro.attachTypeahead({
        inputId:    inpId,
        hiddenId:   hidId,
        dropdownId: ddId,
        url,
        limit:      Math.max(1, Math.min(lim, 500)),
        debounceMs: 400,  // legado do Entrada
        extraQuery: options?.extraQuery,
        // Renderização mantém o padrão "cod — descr" e injeta data-selecionado
        // pra que onSelect possa lê-lo via item.dataset.
        pickCod:   (it) => it.cod ?? it.codparc,
        pickDescr: (it) => it.descr ?? it.nomeparc ?? '',
        pickExtra: (it) => ({ selecionado: it.selecionado }),
        onSelect: (_cod, _descr, item) => {
          if (hidEl && item.dataset.selecionado && item.dataset.selecionado !== 'undefined') {
            hidEl.dataset.selecionado = item.dataset.selecionado;
          }
          if (typeof window.__resetItemClassificaField === 'function') {
            window.__resetItemClassificaField();
          }
        },
      });
    }

    attachTA('cab_parcSearch','cab_codparc','cab_parcDropdown', API_URLS.PARC_SEARCH);
    attachTA('cab_top','cab_top_cod','cab_top_dd', API_URLS.TOP_SEARCH);
    attachTA('cab_nat','cab_nat_cod','cab_nat_dd', API_URLS.NAT_SEARCH);
    attachTA('cab_cencus','cab_cencus_cod','cab_cencus_dd', API_URLS.CENCUS_SEARCH);

    // Add Enter to save behavior for cab_parcSearch when dropdown is closed
    try {
      const cabParcInput = document.getElementById('cab_parcSearch');
      const cabParcDropdown = document.getElementById('cab_parcDropdown');
      if (cabParcInput && cabParcDropdown) {
        cabParcInput.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' && cabParcDropdown.style.display === 'none') {
            e.preventDefault();
            // Trigger save button click
            const saveBtn = document.getElementById('cabSave');
            if (saveBtn && !saveBtn.hasAttribute('disabled')) {
              saveBtn.click();
            }
          }
        });
      }
    } catch (e) { console.warn('cabParcInput setup failed', e); }

    // Permite salvar o Cabeçalho ao pressionar Enter no campo de Data
    try {
      const cabDtNeg = document.getElementById('cab_dtneg');
      if (cabDtNeg) {
        cabDtNeg.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') {
            e.preventDefault(); // Evita que o Enter faça outra coisa na tela
            const saveBtn = document.getElementById('cabSave');
            if (saveBtn && !saveBtn.hasAttribute('disabled')) {
              saveBtn.click(); // Clica no botão Salvar magicamente
            }
          }
        });
      }
    } catch (e) { console.warn('cabDtNeg setup failed', e); }

    // Add global Enter handler for the entire cabCard modal
    try {
      const cabCard = document.getElementById('cabCard');
      if (cabCard) {
        cabCard.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') {
            const target = e.target;
            // Skip if Enter is on a button (let button handle it)
            if (target && target.tagName === 'BUTTON') return;
            
            // Check if any dropdown is currently visible
            const dropdowns = [
              document.getElementById('cab_parcDropdown'),
              document.getElementById('cab_top_dd'),
              document.getElementById('cab_nat_dd'),
              document.getElementById('cab_cencus_dd')
            ];
            const anyDropdownVisible = dropdowns.some(dd => dd && dd.style.display !== 'none');
            
            // Only trigger save if no dropdown visible AND not in a regular input field
            // (allow Enter in textarea for line breaks, but trigger save after)
            const isTextarea = target && target.tagName === 'TEXTAREA';
            const isRegularInput = target && target.tagName === 'INPUT' && target.type !== 'button' && target.type !== 'submit';
            
            if (!anyDropdownVisible && !isRegularInput) {
              // For textarea, let the Enter create a line break but DON'T trigger save
              if (isTextarea) return;
              
              e.preventDefault();
              const saveBtn = document.getElementById('cabSave');
              if (saveBtn && !saveBtn.hasAttribute('disabled')) {
                saveBtn.click();
              }
            }
          }
        });
      }
    } catch (e) { console.warn('cabCard setup failed', e); }

    // small non-blocking toast helper (soft message)
    function showToast(message, type){ // type: info|success|error
      try{
        const id = 'portalToast';
        let el = document.getElementById(id);
        if(!el){ el = document.createElement('div'); el.id = id; el.style.position = 'fixed'; el.style.right = '20px'; el.style.bottom = '20px'; el.style.minWidth = '220px'; el.style.maxWidth = '420px'; el.style.zIndex = '99999'; el.style.fontSize = '14px'; document.body.appendChild(el); }
        const msg = document.createElement('div'); msg.style.marginTop='8px'; msg.style.padding='12px 16px'; msg.style.borderRadius='8px'; msg.style.color = '#fff'; msg.style.background = type === 'error' ? '#dc2626' : (type === 'success' ? '#16a34a' : '#f59e0b'); msg.style.boxShadow = '0 8px 24px rgba(0,0,0,0.18), 0 4px 8px rgba(0,0,0,0.12)'; msg.style.fontWeight = '600'; msg.textContent = message;
        el.appendChild(msg);
        setTimeout(()=>{ try{ msg.style.transition='opacity .4s ease, transform .35s ease'; msg.style.opacity='0'; msg.style.transform='translateY(8px)'; setTimeout(()=> msg.remove(), 420); }catch(e){ console.warn('Toast anim failed', e); msg.remove(); } }, 3600);
      }catch(e){ console.error('showToast', e); }
    }
    function handleValeLockedError(resp){
      try{
        const body = resp && resp.body ? resp.body : {};
        if(resp && resp.status === 409 && body && body.vale && body.vale.locked){
          const reasons = Array.isArray(body.vale.lock_reasons) ? body.vale.lock_reasons.filter(Boolean) : [];
          const detail = reasons.length ? reasons.join(' | ') : (body.error || 'Vale bloqueado por financeiro.');
          console.warn('[DELETE] Vale bloqueado', body.vale);
          showToast(`Vale bloqueado: ${detail}`,'error');
          return true;
        }
      }catch(e){ console.warn('handleValeLockedError failed', e); }
      return false;
    }
    
    // Expose showToast globally for use in modals and other contexts
    try { window.showToast = showToast; } catch(e) { console.warn('Global showToast export failed', e); }

    // Animation helpers for sliding header left and showing items modal
    // Positioning helpers for docked modals: cabCard (left), cabItemsCard (middle), rodapeCard (right)
    function getViewportTopOffset(){ // align under header area
      return 64; // matches header height + small gap
    }
    
    function animateHeaderToLeft(){
      const cab = document.getElementById('cabCard');
      if(!cab) return;
      // dock to left edge with 16px margin
      cab.style.left = '16px';
      cab.style.opacity = '1';
    }
    
    function restoreHeaderPosition(){
      const cab = document.getElementById('cabCard');
      if(!cab) return;
      cab.style.left = '-1200px';
      cab.style.opacity = '';
    }

    function showItemsModal(nunota){
      const itemsWrap = document.getElementById('cabItemsModal');
      const itemsCard = document.getElementById('cabItemsCard');
      const itemsNunota = document.getElementById('items_nunota');
      const cab = document.getElementById('cabCard');
      if(!itemsWrap || !itemsCard || !itemsNunota || !cab) return;
// reset edit state
try{ const seqInp = document.getElementById('item_seq_edit'); if(seqInp) seqInp.value=''; setItemAddBtnMode('add'); }catch(e){ console.warn('Reset edit state failed', e); }
// resolve nunota: prefer passed param, fallback to hidden field
const resolved = normalizeNunota(nunota) || normalizeNunota(itemsNunota.value);
if(!resolved){ console.error('showItemsModal: nunota inválido', nunota, itemsNunota.value); return; }
itemsNunota.value = resolved;
console.debug('showItemsModal resolved nunota', resolved);
      // show cab overlay and items overlay (keep rodape hidden)
      try{ const cabOv = document.getElementById('cabModal'); const itemsOv = document.getElementById('cabItemsModal'); const rodOv = document.getElementById('rodapeModal'); if(cabOv) cabOv.style.display = 'block'; if(itemsOv) itemsOv.style.display = 'block'; if(rodOv) rodOv.style.display = 'none'; }catch(e){ console.warn('Overlay toggle failed', e); }
      itemsWrap.style.display = 'block';
      // Temporarily disable header inputs while Items is open (user can re-enable by closing Items)
      try{
        const header = document.getElementById('cabCard');
        if (header){
          const inputs = header.querySelectorAll('input, textarea, select, button');
          inputs.forEach(el => {
            // keep close/cancel buttons active
            const id = (el.id||'');
            const isCloseBtn = id === 'cabClose' || id === 'cabCancel';
            if (!el.dataset.hasOwnProperty('wasDisabled')){
              el.dataset.wasDisabled = el.disabled ? '1' : '0';
            }
            if (!isCloseBtn){ el.disabled = true; }
          });
        }
      }catch(e){ console.warn('Header disable failed', e); }
      // dock header first (left)
      animateHeaderToLeft();
      // compute left for items: immediately to the right of cabCard
      const cabRect = cab.getBoundingClientRect();
      const leftForItems = Math.max(16 + cabRect.width + 8, cabRect.right + 8) + 'px';
      // place items card
      requestAnimationFrame(()=>{ itemsCard.style.left = leftForItems; });
      // move focus to item product field for immediate typing
      setTimeout(()=>{ try{ document.getElementById('item_prod_vis')?.focus(); }catch(e){ console.debug('Focus failed', e); } }, 160);
      // Render itens imediatamente do cache (se houver) e iniciar load sem atraso
      try{
        let j=null; try{ j = window.__ITEMS_CACHE && window.__ITEMS_CACHE[String(resolved)]; }catch(e){ console.warn('Cache render failed', e); }
        if(j && j.ok){
          const rows = j.items || j.results || [];
          itemsListBody.innerHTML = rows.length ? '' : '<tr><td colspan="7" class="ia-padding ia-muted">Nenhum item.</td></tr>';
          for(const it of rows){ addItemRowToList(it); }
        } else {
          itemsListBody.innerHTML = '<tr><td colspan="7" class="ia-padding ia-muted">Carregando…</td></tr>';
        }
      }catch(e){ console.warn('Cache render failed', e); }
      try{ console.debug('showItemsModal calling loadItems for', resolved); loadItems(resolved); }catch(e){ console.error('loadItems call failed', e); }
    }

    // Abort controller for in-flight items list fetches
    let itemsListController = null;

    function hideItemsModal(){
      // abort any in-flight loadItems fetch to avoid race/closed-channel issues
      try{ if(itemsListController){ console.debug('hideItemsModal aborting in-flight itemsListController'); try{ itemsListController.abort(); }catch(e){ console.warn('Abort controller failed', e); } itemsListController = null; } }catch(e){ console.warn('Abort controller failed', e); }
      const itemsWrap = document.getElementById('cabItemsModal');
      const itemsCard = document.getElementById('cabItemsCard');
      const rod = document.getElementById('rodapeCard');
      if(!itemsWrap || !itemsCard) return;
      // slide items off to right
      itemsCard.style.left = '100%';
      // clear edit state and fields to avoid stale updates
      try{ document.getElementById('item_seq_edit').value=''; setItemAddBtnMode('add'); }catch(e){ console.warn('Reset edit state failed', e); }
      // also hide rodape if visible
      if(rod) rod.style.left = '100%';
      // Re-enable header inputs to allow editing after Items is closed
      try{
        const header = document.getElementById('cabCard');
        if (header){
          const inputs = header.querySelectorAll('input, textarea, select, button');
          inputs.forEach(el => {
            // restore previous disabled state if tracked
            if (el.dataset && el.dataset.wasDisabled){
              const was = el.dataset.wasDisabled === '1';
              el.disabled = was;
              delete el.dataset.wasDisabled;
            } else {
              // default: enable
              el.disabled = false;
            }
          });
          // Ensure header Save is enabled after closing Items
          try{ const saveBtn = document.getElementById('cabSave'); if(saveBtn){ saveBtn.disabled = false; if(saveBtn.dataset) delete saveBtn.dataset.wasDisabled; } }catch(e){ console.warn('Save btn enable failed', e); }
        }
      }catch(e){ console.warn('Header enable failed', e); }
      // after transition hide items wrapper only; keep header open
      setTimeout(()=>{
        // ensure any in-flight requests are aborted when hiding
        try{ if(itemsListController){ console.debug('hideItemsModal(setTimeout) aborting itemsListController'); try{ itemsListController.abort(); }catch(e){ console.warn('Abort controller failed', e); } itemsListController = null; } }catch(e){ console.warn('Abort controller failed', e); }
        itemsWrap.style.display='none';
        try{
          const rodCard = document.getElementById('rodapeCard');
          const cabCard = document.getElementById('cabCard');
          const cabOv = document.getElementById('cabModal');
          if(cabOv){
            const anyOpen = (rodCard && rodCard.style.left && rodCard.style.left !== '100%') || (cabCard && cabCard.style.left && cabCard.style.left !== '-1200px');
            if(!anyOpen) cabOv.style.display = 'none';
          }
        }catch(e){ console.warn('Overlay hide failed', e); }
      }, 320);
    }

    // Items modal buttons
    // Editar Cabeçalho: fechar apenas modal de Itens, deixar Cabeçalho aberto para edição
    document.getElementById('cabItemsEditHeader')?.addEventListener('click', ()=>{

      try{
      const nunRaw = document.getElementById('items_nunota')?.value;
      const nun = normalizeNunota(nunRaw);
      if(!nun){
        showToast('Não é possível editar cabeçalho de nota nova sem NUNOTA','error');
        return;
      }
      // Refresh items cache and panel
      try{ if(window.__ITEMS_CACHE) delete window.__ITEMS_CACHE[String(nun)]; }catch(e){ console.warn('Cache delete failed', e); }
      try{ panelLoadItems(nun); }catch(e){ console.error('panelLoadItems failed', e); }
      // Hide items modal only, keep header modal open
      hideItemsModal();
      // Ensure header modal is in edit mode
      cabEditingNunota = nun;
      // Re-enable header inputs that were disabled when Items opened
      try{
        const header = document.getElementById('cabCard');
        if (header){
          const inputs = header.querySelectorAll('input, textarea, select, button');
          inputs.forEach(el => {
            // restore previous disabled state if tracked
            if (el.dataset && el.dataset.wasDisabled){
              const was = el.dataset.wasDisabled === '1';
              el.disabled = was;
              delete el.dataset.wasDisabled;
            } else {
              // default: enable
              el.disabled = false;
            }
          });
          // Bloquear edição do parceiro ao editar cabeçalho
          const parcInput = document.getElementById('cab_parcSearch');
          if(parcInput) {
              parcInput.disabled = true;
              parcInput.title = "Parceiro não pode ser alterado na edição.";
          }
        }
      }catch(e){ console.warn('Header enable failed', e); }
      showToast('Modo de edição do cabeçalho ativado','info');
      }catch(e){ console.error('Edit header failed', e); }
    });

    // Top close (X): fechar ambos modais (Itens e Cabeçalho) e atualizar lista
    document.getElementById('cabItemsClose')?.addEventListener('click', ()=>{ 
      try{ 
      const nunRaw = document.getElementById('items_nunota')?.value; 
      const nun = normalizeNunota(nunRaw); 
      if(nun){ 
        try{ if(window.__ITEMS_CACHE) delete window.__ITEMS_CACHE[String(nun)]; }catch(e){ console.warn('Cache delete failed', e); } 
        try{ panelLoadItems(nun); }catch(e){ console.error('panelLoadItems failed', e); } 
      } 
      hideItemsModal(); 
      }catch(e){ console.error('Close items failed', e); } 
      try{ hideCabModal(); }catch(e){ console.warn('hideCabModal failed', e); }
      // Reload page to refresh the notes list
      try{
      const url = new URL(window.location.href);
      url.searchParams.delete('new');
      window.location.href = url.pathname + '?' + url.searchParams.toString();
      }catch(e){
      console.warn('Reload failed', e);
      window.location.reload();
      }
    });
    
    // Salvar: fechar os dois modais (Itens e Cabeçalho) e atualizar lista
    document.getElementById('itemsSave')?.addEventListener('click', async ()=>{
      try{ 
        const nunRaw = document.getElementById('items_nunota')?.value; 
        const nun = normalizeNunota(nunRaw); 
        
        if(nun){ 
          // 🔥 TRAVA: EXCLUSÃO AUTOMÁTICA DE CABEÇALHO ÓRFÃO
          if (cabRecemCriado === nun) {
            // Verifica se a tabela não possui NENHUMA linha de item real (com data-seq)
            const temItens = document.querySelectorAll('#itemsListBody tr[data-seq]').length > 0;
            if (!temItens) {
              const delRes = await postJSON(API_URLS.NOTA_DELETE, { nunota: parseInt(nun, 10) });
              if (delRes.ok) {
                if(typeof window.showToast === 'function') showToast('Cabeçalho excluído (Nenhum item adicionado).', 'info');
              }
              cabRecemCriado = null;
              
              try{ hideItemsModal(); }catch(e){}
              try{ hideCabModal(); }catch(e){}
              
              // Remove os parâmetros da URL e recarrega a página limpa
              setTimeout(() => {
                const url = new URL(window.location.href);
                url.searchParams.delete('new'); 
                url.searchParams.delete('sel');
                window.location.href = url.pathname + '?' + url.searchParams.toString();
              }, 600);
              
              return; // 🛑 PARA TUDO AQUI! Impede de tentar finalizar itens fantasmas.
            }
          }

          // Finalizar itens: atualizar DTFATUR, STATUSNOTA='L', DTALTER
          try {
            const finalizeRes = await postJSON(API_URLS.ITEM_FINALIZE, { nunota: nun });
            if(finalizeRes.ok && finalizeRes.body && finalizeRes.body.ok){
              console.log(`✅ Itens finalizados: ${finalizeRes.body.rows_updated} item(ns)`);
            } else {
              console.error('❌ Erro ao finalizar itens:', finalizeRes.body?.error || 'Erro desconhecido');
            }
          } catch(e) {
            console.error('❌ Exceção ao finalizar itens:', e);
          }
          
          try{ if(window.__ITEMS_CACHE) delete window.__ITEMS_CACHE[String(nun)]; }catch(e){ console.warn('Cache delete failed', e); } 
          try{ panelLoadItems(nun); }catch(e){ console.error('panelLoadItems failed', e); } 
        } 
      }catch(e){ console.error('itemsSave failed', e); }
      
      try{ hideItemsModal(); }catch(e){ console.warn('hideItemsModal failed', e); }
      try{ hideCabModal(); }catch(e){ console.warn('hideCabModal failed', e); }
      
      // Reload page to refresh the notes list
      try{
        const url = new URL(window.location.href);
        url.searchParams.delete('new');
        window.location.href = url.pathname + '?' + url.searchParams.toString();
      }catch(e){
        console.warn('Reload failed', e);
        window.location.reload();
      }
    });

    // Rodape modal show/hide
    const rodapeModal = document.getElementById('rodapeModal');
    function _setDimmed(active){ try{ const cab = document.getElementById('cabModal'); const items = document.getElementById('cabItemsModal'); if(cab) { if(active) cab.classList.add('dimmed'); else cab.classList.remove('dimmed'); } if(items) { if(active) items.classList.add('dimmed'); else items.classList.remove('dimmed'); } }catch(e){ console.error('_setDimmed', e); }
    }

    function showRodapeModal(){ try{
        const rodWrap = document.getElementById('rodapeModal'); const rod = document.getElementById('rodapeCard'); const items = document.getElementById('cabItemsCard'); if(!rodWrap || !rod || !items) return;
        // ensure all overlays visible (cab and items should already be visible)
        try{ const cabOv = document.getElementById('cabModal'); const itemsOv = document.getElementById('cabItemsModal'); if(cabOv) cabOv.style.display = 'block'; if(itemsOv) itemsOv.style.display = 'block'; }catch(e){ console.warn('Overlay toggle failed', e); }
        rodWrap.style.display = 'block';
        // compute left: place to the right of items card
        const itRect = items.getBoundingClientRect(); const leftForRod = Math.max(itRect.right + 8, 16 + itRect.width + 8) + 'px';
        requestAnimationFrame(()=>{ rod.style.left = leftForRod; rod.style.opacity = '1'; });
        setTimeout(()=>{ try{ document.getElementById('rodape_obs')?.focus(); }catch(e){ console.debug('Focus failed', e); } },300);
      }catch(e){ console.error('showRodapeModal', e); } 
    }
    
    function hideRodapeModal(){ try{ const rod = document.getElementById('rodapeCard'); if(rod){ rod.style.left = '100%'; rod.style.opacity = '0'; } setTimeout(()=>{ try{ document.getElementById('rodapeModal').style.display = 'none'; // hide overlay if nothing else open
        const itemsCard = document.getElementById('cabItemsCard'); const cab = document.getElementById('cabCard'); const cabOv = document.getElementById('cabModal'); if(cabOv){ const anyOpen = (itemsCard && itemsCard.style.left && itemsCard.style.left !== '100%') || (cab && cab.style.left && cab.style.left !== '-1200px'); if(!anyOpen) cabOv.style.display = 'none'; }
      }catch(e){ console.warn('Overlay hide failed', e); try{ document.getElementById('rodapeModal').style.display = 'none'; }catch(e2){ console.warn('Fallback hide failed', e2); } } }, 320); }catch(e){ console.error('hideRodapeModal', e); } 
    }
    
    document.getElementById('rodapeClose')?.addEventListener('click', hideRodapeModal);
    document.getElementById('rodapeCancel')?.addEventListener('click', hideRodapeModal);
    // Rodape Save: fechar todos os modais abertos (cabModal, cabItemsModal, rodapeModal)
    
    document.getElementById('rodapeSave')?.addEventListener('click', ()=>{
      try{ hideRodapeModal(); }catch(e){ console.warn('hideRodapeModal failed', e); }
      try{ hideItemsModal(); }catch(e){ console.warn('hideItemsModal failed', e); }
      try{ hideCabModal(); }catch(e){ console.warn('hideCabModal failed', e); }
      showToast('Salvo (rodapé). Todos os modais foram fechados.','success');
    });

    // Select-on-focus: select all text in editable fields (except dates)
    document.addEventListener('focusin', function(e){
      const el = e.target;
      if (!el || (el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA')) return;
      if (el.disabled || el.readOnly) return;
      if (el.tagName === 'INPUT'){
        const t = (el.type||'').toLowerCase();
        if (t === 'date') return; // skip dates
        const allow = ['text','number','search','email','tel','url','password'];
        if (!allow.includes(t)) return;
      }
      try{ el.select(); }catch(e){ console.debug('Select failed', e); }
      // ensure selection after mouseup (some browsers place caret on mouseup)
      const once = ()=>{ try{ el.select(); }catch(e){ console.debug('Select failed', e); } el.removeEventListener('mouseup', once); };
      el.addEventListener('mouseup', once, { once:true });
    });
    // Items list helpers
    const itemsListBody = document.getElementById('itemsListBody');

    // Helper: visually mark invalid fields with red border until user edits
    function markInvalidField(el){
      try{
        if(!el) return;
        el.classList.add('invalid');
        const clear = ()=>{ try{ el.classList.remove('invalid'); }catch(e){ console.debug('remove invalid failed', e); } el.removeEventListener('input', clear); el.removeEventListener('change', clear); };
        el.addEventListener('input', clear);
        el.addEventListener('change', clear);
      }catch(e){ console.warn('markInvalidField failed', e); }
    }

    const itemClassificaInput = document.getElementById('item_classifica');
    const itemClassificaToggle = document.getElementById('itemClassificaToggle');
    const itemClassificaHint = document.getElementById('itemClassificaHint');

    function setItemClassificaState(value){
      const normalized = value === 'S' || value === 'N' ? value : '';
      if(itemClassificaInput) itemClassificaInput.value = normalized;
      if(itemClassificaToggle){
        itemClassificaToggle.dataset.value = normalized;
        const buttons = Array.from(itemClassificaToggle.querySelectorAll('.tri-toggle__btn'));
        buttons.forEach(btn => {
          const isActive = btn.dataset.value === normalized;
          btn.classList.toggle('is-active', isActive);
          btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
        itemClassificaToggle.classList.remove('is-invalid');
      }
      if(itemClassificaHint) itemClassificaHint.style.display = 'none';
      return normalized;
    }

    function getItemClassificaState(){
      return itemClassificaInput?.value === 'S' || itemClassificaInput?.value === 'N'
        ? itemClassificaInput.value
        : '';
    }

    function requireItemClassificaState(){
      const value = getItemClassificaState();
      if(value === 'S' || value === 'N') return value;
      if(itemClassificaToggle){
        itemClassificaToggle.classList.add('is-invalid');
        if(itemClassificaHint) itemClassificaHint.style.display = 'block';
        const firstBtn = itemClassificaToggle.querySelector('.tri-toggle__btn');
        if(firstBtn) firstBtn.focus();
      }
      return null;
    }

    function resetItemClassificaField(){
      setItemClassificaState('');
    }

    if(itemClassificaToggle){
      itemClassificaToggle.addEventListener('click', (event)=>{
        const btn = event.target.closest('.tri-toggle__btn');
        if(!btn) return;
        setItemClassificaState(btn.dataset.value || '');
      });
    }

    try{
      window.__setItemClassificaState = setItemClassificaState;
      window.__resetItemClassificaField = resetItemClassificaField;
      window.__getItemClassificaState = getItemClassificaState;
    }catch(e){ console.warn('Window exports failed', e); }

    setItemClassificaState('');

    // Helper: toggle Add button icon between plus and checkmark for edit mode
    function setItemAddBtnMode(mode){
      try{
        const btn = document.getElementById('itemAddBtn'); 
        const prodInput = document.getElementById('item_prod_vis');
        const toggleBtns = document.querySelectorAll('#itemClassificaToggle .tri-toggle__btn');
        if(!btn) return;
        const plusSvg = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">\n  <circle cx="12" cy="12" r="9"></circle>\n  <line x1="12" y1="8" x2="12" y2="16"></line>\n  <line x1="8" y1="12" x2="16" y2="12"></line>\n</svg>';
        const checkSvg = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">\n  <circle cx="12" cy="12" r="9"></circle>\n  <polyline points="8 12 11 15 16 9"></polyline>\n</svg>';
        if (mode === 'edit'){
          btn.dataset.mode = 'edit';
          btn.setAttribute('title','Atualizar');
          btn.setAttribute('aria-label','Atualizar');
          btn.innerHTML = checkSvg;
          if(prodInput) {
            prodInput.disabled = true;
            prodInput.title = "Produto não pode ser alterado na edição.";
          }
          toggleBtns.forEach(b => {
            b.disabled = true;
            b.style.opacity = '0.5';
            b.style.cursor = 'not-allowed';
            b.title = "Classificação não pode ser alterada na edição.";
          });
        } else {
          btn.dataset.mode = '';
          btn.setAttribute('title','Adicionar');
          btn.setAttribute('aria-label','Adicionar');
          btn.innerHTML = plusSvg;
          if(prodInput) {
            prodInput.disabled = false;
            prodInput.removeAttribute('title');
          }
          toggleBtns.forEach(b => {
            b.disabled = false;
            b.style.opacity = '';
            b.style.cursor = '';
            b.removeAttribute('title');
          });
          if(typeof window.__resetItemClassificaField === 'function'){
            window.__resetItemClassificaField();
          }
        }
      }catch(e){ console.error('setItemAddBtnMode', e); }
    }

    // Number helpers: parse flexible input and format with thousand '.' and 1 decimal (pt-BR)
    function parseFlexibleNumber(val){
      try{
        if (val == null) return NaN;
        if (typeof val === 'number') return val;
        let s = String(val).trim();
        if (!s) return NaN;
        // remove thousand separators and normalize decimal comma to dot
        s = s.replace(/\./g, '').replace(/,/g, '.');
        const n = parseFloat(s);
        return Number.isFinite(n) ? n : NaN;
      }catch(e){ console.debug('parseFlexibleNumber failed', e); return NaN; }
    }

    function formatBR1(n){
      try{
        const num = typeof n === 'number' ? n : parseFlexibleNumber(n);
        if (!Number.isFinite(num)) return '';
        return num.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
      }catch(e){ console.debug('formatBR1 failed', e); return ''; }
    }

    // normalize nunota to integer or null
    function normalizeNunota(n){ try{ if(n==null) return null; const s = String(n).trim(); if(!s) return null; const m = s.match(/(\d+)/); if(!m) return null; const v = parseInt(m[1],10); return Number.isFinite(v) ? v : null; }catch(e){ console.debug('normalizeNunota failed', e); return null; } }

    function clearItemsList(){ if(!itemsListBody) return; itemsListBody.innerHTML = '<tr><td colspan="7" class="ia-padding ia-muted">Nenhum item carregado.</td></tr>'; }
    // Click-to-select for items modal rows (visual highlight and future actions)
    // Click-to-select for items modal rows (visual highlight and future actions)
    try{
      itemsListBody?.addEventListener('click', async function(e){
        // Handle delete button clicks
        const delBtn = e.target.classList?.contains('item-del') ? e.target : e.target.closest?.('button.item-del');
        if(delBtn){
          e.stopPropagation();
          e.preventDefault();
          
          const seq = delBtn.dataset.seq;
          const nunRaw = document.getElementById('items_nunota')?.value;
          const nun = normalizeNunota(nunRaw);

          if(!nun || !seq) return;

          // 🔥 1. FAZ A CHECAGEM INVISÍVEL NO BANCO ANTES DE PERGUNTAR
          const checkRes = await postJSON(API_URLS.ITEM_DELETE, { 
              nunota: parseInt(nun, 10), 
              sequencias: [parseInt(seq, 10)],
              apenas_checar: true // Manda a flag para o Python apenas testar a trava
          });

          if (!checkRes.ok) {
            // Se esbarrou na trava, mostra o erro vermelho e ABORTA antes do confirm!
            const errMsg = checkRes.body?.error || 'Falha ao validar item.';
            showToast(errMsg, 'error');
            return;
          }

          // 🔥 2. SE PASSOU PELA TRAVA (Sinal Verde), AÍ SIM PEDE A CONFIRMAÇÃO
          if(!confirm(`Excluir o item sequência ${seq}?`)) return;
          
          // 3. EXCLUI DE VERDADE
          const res = await postJSON(API_URLS.ITEM_DELETE, { 
              nunota: parseInt(nun, 10), 
              sequencias: [parseInt(seq, 10)] 
          });

          if(res.ok){ 
            showToast(res.body?.message || 'Item excluído.', 'success');
            
            // Se a nota inteira foi excluída (último item), fecha os modais e recarrega
            if(res.body?.cabecalho_excluido) {
                hideItemsModal();
                hideCabModal();
                setTimeout(() => window.location.reload(), 800);
                return;
            }

            // Caso contrário, apenas atualiza a lista de itens e o painel
            try{ if(window.__ITEMS_CACHE) delete window.__ITEMS_CACHE[String(nun)]; }catch(e){} 
            try{ loadItems(nun); }catch(e){} 
            try{ panelLoadItems(nun); }catch(e){} 
          }
          else { 
            const errMsg = res.body?.error || 'Falha ao excluir item.';
            showToast(errMsg, 'error');
          }
          return;
        }
        
        // Handle row selection
        const tr = e.target && e.target.closest ? e.target.closest('tr') : null;
        if(!tr) return;
        const rows = Array.from(itemsListBody.querySelectorAll('tr'));
        rows.forEach(r => r.classList.remove('selected','is-selected','row--active','ia-row-selected'));
        tr.classList.add('selected');
      });
    }catch(e){ console.error('itemsListBody listener failed', e); }
    
    function hasDuplicateItemInList(codprod, codvol){
      try{
        const rows = Array.from(itemsListBody?.querySelectorAll('tr') || []);
        if(!rows.length) return false;
        const cprod = String(codprod||'').trim();
        const cvol = String(codvol||'').trim().toUpperCase();
        if(!cprod) return false;
        for(const tr of rows){
          const rc = (tr.dataset && tr.dataset.cod) ? String(tr.dataset.cod).trim() : '';
          if(!rc) continue;
          if(rc !== cprod) continue;
          // If volume provided, compare as well (case-insensitive). If no volume provided, consider duplicate on product code alone
          if(cvol){
            const rv = (tr.dataset && tr.dataset.codvol) ? String(tr.dataset.codvol).trim().toUpperCase() : '';
            if(rv === cvol) return true;
            // allow duplicates of same product when volume differs
            continue;
          }
          return true;
        }
        return false;
      }catch(e){ console.warn('hasDuplicateItemInList failed', e); return false; }
    }
    
    function addItemRowToList(it) {
      if (!itemsListBody) return;

      // 🔍 LOG - Ver o que está chegando
      console.log('🔍 [addItemRowToList] Dados recebidos:', {
        cod: it.cod,
        qtd: it.qtd,
        peso: it.peso,
        total: it.total,
        totalkg: it.totalkg,
        codvol: it.codvol,
        codvolparc: it.codvolparc, // <-- Verifique no F12 se isso está vindo do Python!
        selecionado: it.selecionado,
        obs: it.obs || it.observacao
      });

      if (itemsListBody.querySelector('td')) {
        const first = itemsListBody.querySelector('td').parentElement;
        if (first && first.childElementCount === 1 && first.children[0].getAttribute('colspan')) itemsListBody.innerHTML = '';
      }

      const tr = document.createElement('tr');
      const classTxt = (it && (typeof it.classifica !== 'undefined' || typeof it.geraproducao !== 'undefined')) ? ((it.geraproducao ? String(it.geraproducao).toUpperCase() !== 'N' : !!it.classifica) ? 'Sim' : 'Não') : '';
      const qtdFormatted = (function() {
        const n = parseFlexibleNumber(it?.qtd);
        return Number.isFinite(n) ? formatBR1(n) : (it && it.qtd != null ? String(it.qtd) : '');
      })();
      const pesoFormatted = (function() {
        const n = parseFlexibleNumber(it?.peso);
        return Number.isFinite(n) ? formatBR1(n) : (it && it.peso != null ? String(it.peso) : '');
      })();

      const totalFormatted = (function() {
        const serverTotal = parseFlexibleNumber(it?.total);
        if (Number.isFinite(serverTotal)) return formatBR1(serverTotal);
        const serverTotalKg = parseFlexibleNumber(it?.totalkg);
        if (Number.isFinite(serverTotalKg)) return formatBR1(serverTotalKg);
        return (it && it.total != null) ? String(it.total) : '';
      })();

      // ==========================================================================
      // LÓGICA DE VOLUME VIA CODVOLPARC (MODAL)
      // ==========================================================================
      // Prioriza a nova coluna codvolparc. Se não vier nada, usa codvol.
      let unitQty = (it.codvolparc || it.codvol || '').trim().toLowerCase();

      const unitQtyHtml = unitQty ? `<span class="unit-suffix">${unitQty}</span>` : '';
      const totalWithUnit = totalFormatted ? `${totalFormatted} <span class="unit-suffix">kg</span>` : totalFormatted;

      tr.innerHTML = `
        <td>${it.cod || ''} ${it.descr || ''}</td>
        <td>${it.lote || ''}</td>
        <td class="text-center">${classTxt}</td>
        <td class="text-right">${qtdFormatted} ${unitQtyHtml}</td>
        <td class="text-right">${pesoFormatted}</td>
        <td class="text-right">${totalWithUnit}</td>
        <td><button class="icon-btn item-del" data-seq="${it.sequencia || ''}" aria-label="Excluir">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
            <path d="M10 11v6"></path>
            <path d="M14 11v6"></path>
            <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button></td>
      `;

      try {
        tr.dataset.seq = it.sequencia != null ? String(it.sequencia) : '';
        tr.dataset.cod = it.cod != null ? String(it.cod) : '';
        tr.dataset.descr = it.descr != null ? String(it.descr) : '';
        tr.dataset.codvol = it.codvol != null ? String(it.codvol) : '';
        tr.dataset.codvolparc = it.codvolparc != null ? String(it.codvolparc) : ''; // <-- Guardado no dataset
        tr.dataset.qtd = it.qtd != null ? String(it.qtd) : '';
        tr.dataset.peso = (it.peso != null && it.peso !== '') ? String(it.peso) : '';
        tr.dataset.obs = (it.obs || it.observacao) != null ? String(it.obs || it.observacao) : '';
        tr.dataset.lote = it.lote != null ? String(it.lote) : '';
        tr.dataset.gp = it.geraproducao != null ? String(it.geraproducao) : (typeof it.classifica !== 'undefined' ? (it.classifica ? 'S' : 'N') : '');
        tr.dataset.selecionado = (it.selecionado !== undefined && it.selecionado !== null) ? String(it.selecionado) : '0';
      } catch (e) {
        console.warn('Dataset assignment failed', e);
      }

      itemsListBody.appendChild(tr);

      tr.addEventListener('dblclick', function(){
        try {
          const seq = tr.dataset.seq; 
          if(!seq) return;
          
          const seqInp = document.getElementById('item_seq_edit'); 
          if(seqInp) seqInp.value = seq;
          
          const prodH = document.getElementById('item_prod_hidden'); 
          const prodV = document.getElementById('item_prod_vis');
          if(prodH) { 
            prodH.value = tr.dataset.cod || ''; 
            prodH.dataset.selecionado = tr.dataset.selecionado || '0'; 
          }
          if(prodV) prodV.value = tr.dataset.cod ? `${tr.dataset.cod} — ${tr.dataset.descr||''}` : '';

          // ==========================================================================
          // LÓGICA DE VOLUME PARA O FORMULÁRIO DE EDIÇÃO
          // ==========================================================================
          const volH = document.getElementById('item_vol_hidden'); 
          const volV = document.getElementById('item_vol');
          
          // Resgata direto do dataset codvolparc
          const volParaForm = (tr.dataset.codvolparc || tr.dataset.codvol || 'KG').toUpperCase();

          if(volH) volH.value = volParaForm;
          if(volV) volV.value = volParaForm;
          // ==========================================================================

          const qtd = document.getElementById('item_qtd'); 
          if(qtd) qtd.value = tr.dataset.qtd || '';
          
          const peso = document.getElementById('item_peso'); 
          if(peso) peso.value = tr.dataset.peso || '';
          
          const obs = document.getElementById('item_obs'); 
          if(obs) obs.value = tr.dataset.obs || '';
          
          const gp = String(tr.dataset.gp || '').toUpperCase();
          if(typeof window.__setItemClassificaState === 'function'){
            window.__setItemClassificaState(gp === 'N' ? 'N' : (gp === 'S' ? 'S' : ''));
          }
          
          try{ setItemAddBtnMode('edit'); }catch(e){ console.warn('setItemAddBtnMode failed', e); }
          try{ recalcItemTotal(); }catch(e){ console.warn('recalcItemTotal failed', e); }
          try{ prodV && prodV.focus(); }catch(e){ console.debug('Focus failed', e); }
        } catch(e) { console.error('editLoad failed', e); }
      });
    }

    async function loadItems(nunota){
      // abort any previous request
      try{ if(itemsListController){ try{ itemsListController.abort(); }catch(e){ console.warn('Abort controller failed', e); } itemsListController = null; } }catch(e){ console.warn('Abort controller failed', e); }
      const resolved = normalizeNunota(nunota) || normalizeNunota(document.getElementById('items_nunota')?.value);
      if(!resolved){ console.error('loadItems: nunota inválido', nunota); return; }
      document.getElementById('items_nunota').value = resolved;
      try{
        // Use client-side cache first
        let j = null; try{ const cache = window.__ITEMS_CACHE || {}; if (cache && cache[String(resolved)]) j = cache[String(resolved)]; }catch(e){ console.warn('Cache read failed', e); }
        if(j){
          const rows = j.items || j.results || [];
          itemsListBody.innerHTML = rows.length ? '' : '<tr><td colspan="7" class="ia-padding ia-muted">Nenhum item.</td></tr>';
          for(const it of rows){ addItemRowToList(it); }
        } else {
          // Status enquanto aguarda rede
          itemsListBody.innerHTML = '<tr><td colspan="7" class="ia-padding ia-muted">Carregando…</td></tr>';
          itemsListController = new AbortController();
          const opts = { credentials: 'same-origin', signal: itemsListController.signal };
          const url = API_URLS.ITEM_LIST + '?nunota=' + encodeURIComponent(resolved);
          console.debug('loadItems fetching', url);
          const r = await fetch(url, opts);
          // clear controller reference on success
          itemsListController = null;
          console.debug('loadItems response status', r.status);
          try{ j = await r.json(); console.debug('loadItems response json keys', Object.keys(j), 'itemsLen', (j.items||j.results||[]).length); }catch(_){ j = {}; console.debug('loadItems could not parse JSON'); }
          
          // 🔍 LOG DO BACKEND - Ver o que está retornando
          if (j && j.items && j.items.length > 0) {
            console.log('🔍 [FRONTEND] Primeiro item do backend:', j.items[0]);
          }
          
          // Save to cache for next loads
          try{ if(j && j.ok){ window.__ITEMS_CACHE = window.__ITEMS_CACHE || {}; window.__ITEMS_CACHE[String(resolved)] = j; } }catch(e){ console.warn('Cache write failed', e); }
          if(!j || !j.ok){ itemsListBody.innerHTML = `<tr><td colspan="7">Erro: ${(j&&j.error)||'falha'}</td></tr>`; return; }
          const rows = j.items || j.results || [];
          itemsListBody.innerHTML = rows.length ? '' : '<tr><td colspan="7" class="ia-padding ia-muted">Nenhum item.</td></tr>';
          for(const it of rows){ addItemRowToList(it); }
        }
      }catch(err){
        if(err && err.name === 'AbortError'){
          console.info('loadItems aborted for nunota', nunota);
          return;
        }
        console.error('loadItems error', err);
        itemsListBody.innerHTML = '<tr><td colspan="7">Erro ao carregar.</td></tr>'; }
    }

    // Item Produto typeahead — reutiliza attachTA para ter o mesmo comportamento do Parceiro (modal Cabeçalho)
    attachTA('item_prod_vis','item_prod_hidden','item_prod_sugg', API_URLS.PROD_SEARCH, { limit: 400, extraQuery: 'allow_in_natura=1' });

    
    // Vol suggestion dropdown + keyboard nav (non-blocking free text fallback)
    (function(){ const volVis = document.getElementById('item_vol'); const volHidden = document.getElementById('item_vol_hidden'); if(!volVis) return; // create suggest container
      const volSugg = document.createElement('div'); volSugg.id = 'item_vol_sugg'; volSugg.style.position='absolute'; volSugg.style.left='0'; volSugg.style.right='0'; volSugg.style.background='#fff'; volSugg.style.border='1px solid var(--border)'; volSugg.style.display='none'; volSugg.style.maxHeight='160px'; volSugg.style.overflow='auto'; volSugg.style.zIndex='120'; volSugg.style.fontSize='13px'; volVis.parentElement.style.position = 'relative'; volVis.parentElement.appendChild(volSugg);
      function vhide(){ volSugg.style.display='none'; volSugg.innerHTML=''; }
      function vshow(items){
        if(!items||!items.length){ vhide(); return; }
        // dedupe by cod to avoid duplicate suggestions when server returns duplicates
        const seen = new Set();
        const uniq = [];
        for(const it of items){ const c = String(it.cod||'').trim(); if(!c || seen.has(c)) continue; seen.add(c); uniq.push(it); }
        if(!uniq.length){ vhide(); return; }
        volSugg.innerHTML = uniq.map((it,idx)=>`<div class="vsugg-item${idx===0?' active':''}" data-cod="${it.cod}" data-descr="${(it.descr||'').replace(/"/g,'&quot;')}">${it.cod} - ${it.descr}</div>`).join('');
        volSugg.style.display='block';
        Array.from(volSugg.querySelectorAll('.vsugg-item')).forEach(el=> el.addEventListener('click', ()=>{ volHidden.value = el.dataset.cod; volVis.value = el.dataset.cod; vhide(); checkVolumeClassification(); try{ document.getElementById('item_qtd')?.focus(); }catch(e){ console.debug('Focus failed', e); } }));
      }
volVis.addEventListener('input', debounce(function(){ const q = volVis.value.trim(); if(!q){ vhide(); // keep hidden default (CX) if present
  if(!volHidden.value) volHidden.value = 'CX'; return; } fetch(API_URLS.VOL_SEARCH + '?q=' + encodeURIComponent(q) + '&limit=8',{credentials:'same-origin'}).then(r=>r.json()).then(j=>{ const items = j.results||[]; vshow(items); }).catch(()=> vhide()); }, 400));
volVis.addEventListener('keydown', function(e){ 
  if(e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === 'Tab' || e.key === 'Escape'){
    if(volSugg.style.display === 'none') return;
    const nodes = Array.from(volSugg.querySelectorAll('.vsugg-item')); 
    if(!nodes.length) return; 
    let idx = nodes.findIndex(x=>x.classList.contains('active')); 
    if(idx < 0) idx = 0; 
    if(e.key === 'ArrowDown'){ 
      e.preventDefault(); 
      idx = Math.min(nodes.length-1, idx+1); 
      nodes.forEach(x=>x.classList.remove('active')); 
      nodes[idx].classList.add('active'); 
      nodes[idx].scrollIntoView({block:'nearest'}); 
    } else if(e.key === 'ArrowUp'){ 
      e.preventDefault(); 
      idx = Math.max(0, idx-1); 
      nodes.forEach(x=>x.classList.remove('active')); 
      nodes[idx].classList.add('active'); 
      nodes[idx].scrollIntoView({block:'nearest'}); 
    } else if(e.key === 'Enter' || e.key === 'Tab'){ 
      const el = nodes.find(x=>x.classList.contains('active')) || nodes[0]; 
      if(el){ 
        e.preventDefault(); 
        volHidden.value = el.dataset.cod;
        volVis.value = el.dataset.cod;
        vhide(); 
        checkVolumeClassification(); 
        try{ document.getElementById('item_qtd')?.focus(); }catch(e){ console.debug('Focus failed', e); } 
      } 
    } else if(e.key === 'Escape'){ 
      vhide(); 
    } 
  }
});
// (no-op) click attachments are added when suggestions are rendered
    })();

    // Monitor volume changes and apply classification rules
    function checkVolumeClassification() {
      const volHidden = document.getElementById('item_vol_hidden');
      const volVis = document.getElementById('item_vol');
      const pesoInput = document.getElementById('item_peso');
      
      if (!volHidden || !volVis || !pesoInput) return;
      
      const volValue = (volHidden.value || volVis.value || '').trim().toUpperCase();
      
      if (volValue && volValue !== 'CX') {
        // Volume is NOT CX: set peso padrão para 1, se necessário
        // setItemClassificaState('N'); // <-- LINHA COMENTADA PARA NÃO MARCAR SOZINHO
        if (!pesoInput.value || pesoInput.value === '0') {
          pesoInput.value = '1';
          recalcItemTotal();
        }
      }
    }

  // Attach listeners to volume fields
  const volHiddenField = document.getElementById('item_vol_hidden');
  const volVisField = document.getElementById('item_vol');
  if (volHiddenField) {
    // Create a MutationObserver to watch for value changes on hidden field
    const observer = new MutationObserver(checkVolumeClassification);
    observer.observe(volHiddenField, { attributes: true, attributeFilter: ['value'] });
    // Also use input event as fallback
    volHiddenField.addEventListener('change', checkVolumeClassification);
  }

    if (volVisField) {
      volVisField.addEventListener('input', checkVolumeClassification);
      volVisField.addEventListener('change', checkVolumeClassification);
      
      // 🔥 TRAVA DO VOLUME: Se sair do campo e estiver vazio, volta pra CX
      volVisField.addEventListener('blur', function() {
          if (!this.value.trim()) {
              this.value = 'CX';
              if (volHiddenField) volHiddenField.value = 'CX';
          }
          checkVolumeClassification(); // Roda a regra de negócio logo em seguida
      });
    }

    // Check on page load
  setTimeout(checkVolumeClassification, 100);

  // Calculate total = qtd * peso when inputs change
  function recalcItemTotal(){ try{ const qtd = parseFloat(String(document.getElementById('item_qtd').value||'').replace(',','.')) || 0; const peso = parseFloat(String(document.getElementById('item_peso').value||'').replace(',','.')) || 0; const total = (qtd && peso) ? (qtd * peso) : 0; document.getElementById('item_total').value = total ? String(total) : ''; }catch(e){ console.warn('recalcItemTotal failed', e); } }

  document.getElementById('item_qtd')?.addEventListener('input', recalcItemTotal);
  document.getElementById('item_peso')?.addEventListener('input', recalcItemTotal);

  // Add Enter key support to trigger itemAddBtn click
  ['item_qtd', 'item_peso', 'item_obs', 'item_lote', 'item_prod_vis'].forEach(fieldId => {
    const field = document.getElementById(fieldId);
    if (field) {
      field.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          document.getElementById('itemAddBtn')?.click();
        }
      });
    }
  });

  // VARIÁVEL DE BLOQUEIO GLOBAL
let isAddBtnBusy = false;

document.getElementById('itemAddBtn')?.addEventListener('click', async function(e) {
    e.preventDefault(); // Previne qualquer comportamento padrão do formulário
    
    if (isAddBtnBusy) {
        console.warn("Bloqueado duplo clique.");
        return;
    }
    
    const selfBtn = this;
    isAddBtnBusy = true; // Trava a função
    selfBtn.setAttribute('disabled', 'true');
    selfBtn.style.opacity = '0.5';

    try {
        const nunRaw = document.getElementById('items_nunota')?.value; 
        const nun = normalizeNunota(nunRaw); 
        if(!nun){ showToast('NUNOTA desconhecido.', 'error'); return; }
        
        const seqEditRaw = (document.getElementById('item_seq_edit')?.value || '').trim();
        const isEdit = !!seqEditRaw && /^\d+$/.test(seqEditRaw);
        
        let codprodRaw = (document.getElementById('item_prod_hidden').value || '').trim();
        if(!codprodRaw){ 
            const txt = (document.getElementById('item_prod_vis').value || '').trim(); 
            const m = txt.match(/(\d+)/); 
            codprodRaw = m ? m[1] : ''; 
        }
        
        const codprodNum = parseInt(codprodRaw, 10);
        const fldProd = document.getElementById('item_prod_vis');
        const fldQtd = document.getElementById('item_qtd');
        const fldPeso = document.getElementById('item_peso');
        const fldVol = document.getElementById('item_vol');
        
        // 1. Limpar marcações de erro anteriores antes de reavaliar
        [fldProd, fldQtd, fldPeso, fldVol].forEach(el => { 
            try { el && el.classList.remove('invalid'); } catch(e) {} 
        });

        const qtd = parseFloat(String(fldQtd?.value || '').replace(',','.')) || 0;
        const pesoNum = parseFloat(String(fldPeso?.value || '').replace(',','.')) || 0;
        const volRaw = String((document.getElementById('item_vol_hidden').value || fldVol?.value || '').trim());
        
        // 🔥 2. TRAVA DE SEGURANÇA: Validação de campos obrigatórios
        const invalidFields = [];
        if(!codprodRaw || !Number.isFinite(codprodNum)) invalidFields.push(fldProd);
        if(qtd <= 0) invalidFields.push(fldQtd);
        if(pesoNum <= 0) invalidFields.push(fldPeso);
        if(!volRaw) invalidFields.push(fldVol);

        // CHAMA A VALIDAÇÃO DO CLASSIFICA ANTES DE ABORTAR O CÓDIGO
        const classificaValue = requireItemClassificaState();

        // SE TIVER ERRO EM QUALQUER LUGAR (Textos ou Toggle), PINTA TUDO E ABORTA
        if (invalidFields.length > 0 || !classificaValue) {
            // Pinta os campos de texto
            invalidFields.forEach(f => {
                if (f && typeof markInvalidField === 'function') {
                    markInvalidField(f);
                } else if (f) {
                    f.classList.add('invalid'); // Fallback
                }
            });
            
            showToast('Preencha todos os campos obrigatórios (incluindo a Classificação).', 'error');
            try { (invalidFields[0] || fldProd)?.focus(); } catch(e) {}
            return; // 🛑 Bloqueia o salvamento aqui
        }

        const classificaChecked = classificaValue === 'S';

        // Lógica de conversão
        let qtdneg_kg = qtd; 
        if (volRaw.toUpperCase() !== 'KG' && pesoNum > 0) {
             qtdneg_kg = qtd * pesoNum;
        }

        const total_calculado = (qtd > 0 && pesoNum > 0) ? (qtd * pesoNum) : qtd;

        const basePayload = { 
            NUNOTA: parseInt(nun, 10), 
            CODPROD: codprodNum, 
            QTDNEG: total_calculado,    // 🔥 SEMPRE recebe o "Total KG" da tela
            QTDCONFERIDA: qtd,          // O que o usuário digitou no campo QTD
            VLRUNIT: 0, 
            CODVOL: volRaw.toUpperCase(), 
            PESO: pesoNum, 
            GERAPRODUCAO: classificaChecked ? 'S' : 'N',
            CODLOCALORIG: 101
        };

        if (isEdit) {
            const updPayload = Object.assign({}, basePayload, { SEQUENCIA: parseInt(seqEditRaw, 10) });
            const resp = await postJSON(API_URLS.ITEM_SAVE, updPayload);
            if(resp.ok) {
                showToast('Item atualizado', 'success');
                document.getElementById('item_seq_edit').value = ''; 
                setItemAddBtnMode('add');
            } else {
                showToast('Falha ao atualizar item', 'error');
            }
        } else {
            // INSERÇÃO DIRETA (O backend já faz o rollback em caso de falha)
            const saveResp = await postJSON(API_URLS.ITEM_SAVE, basePayload);
            if(saveResp.ok) {
                showToast('Item inserido com sucesso', 'success');

                cabRecemCriado = null; // Já tem item! Não é mais órfão e não deve ser excluído
                
                // Limpa todos os campos para o próximo item
                document.getElementById('item_prod_vis').value = '';
                document.getElementById('item_prod_hidden').value = '';
                document.getElementById('item_qtd').value = '';
                document.getElementById('item_peso').value = '';
                document.getElementById('item_total').value = '';
                if(typeof window.__resetItemClassificaField === 'function'){ window.__resetItemClassificaField(); }
                
                // Foca novamente no campo de produto para digitação contínua
                try { document.getElementById('item_prod_vis')?.focus(); } catch(e) {}
            } else {
                showToast('Falha ao salvar no banco: ' + (saveResp.body?.error || 'Erro desconhecido'), 'error');
                return;
            }
        }
        
        // Invalida o cache da nota antes de recarregar
        try { if (window.__ITEMS_CACHE) delete window.__ITEMS_CACHE[String(nun)]; } catch(e) {}
        
        // Atualiza a lista na tela (agora forçando o fetch no backend)
        loadItems(nun);
        panelLoadItems(nun);

    } finally {
        // Libera o botão após tudo ter terminado
        selfBtn.removeAttribute('disabled');
        selfBtn.style.opacity = '1';
        setTimeout(() => { isAddBtnBusy = false; }, 300); // 300ms de "cooldown" para segurança máxima
    }
  });
  

  cabSave?.addEventListener('click', async ()=>{
    const fldDtNeg = document.getElementById('cab_dtneg');
    const fldParcCode = document.getElementById('cab_codparc');
    const fldParcVis = document.getElementById('cab_parcSearch');
    const fldTopCode = document.getElementById('cab_top_cod');
    const fldTopVis = document.getElementById('cab_top');
    const fldNatCode = document.getElementById('cab_nat_cod');
    const fldNatVis = document.getElementById('cab_nat');
    const fldCenCode = document.getElementById('cab_cencus_cod');
    const fldCenVis = document.getElementById('cab_cencus');
    const fldEmp = document.getElementById('cab_codemp');

    // Limpar estados anteriores
    [fldDtNeg, fldParcVis, fldTopVis, fldNatVis, fldCenVis].forEach(el=>{ try{ el && el.classList.remove('invalid'); }catch(e){} });
    const invalid = [];

    const extrairCodigo = (visEl, hidEl) => {
        let valor = (hidEl?.value || '').trim();
        if (!valor && visEl && visEl.value) {
            const match = String(visEl.value).trim().match(/^(\d+)/);
            if (match && match[1]) {
                valor = match[1];
                if (hidEl) hidEl.value = valor;
            }
        }
        return valor;
    };

    // =========================================================================
    // 🔥 FIX: EXTRAÇÃO E FALLBACKS (Ignorando campos que não estão na tela)
    // =========================================================================
    const codemp = (fldEmp?.value||'').trim() || '1'; // Empresa padrão 1
    const dtneg = (fldDtNeg?.value||'').trim();
    const codparc = extrairCodigo(fldParcVis, fldParcCode);
    const codtop = extrairCodigo(fldTopVis, fldTopCode);

    // Natureza e Centro de Custo não estão no modal. Enviamos o padrão do Sankhya.
    const codnat = extrairCodigo(fldNatVis, fldNatCode) || '20010100'; 
    const codcencus = extrairCodigo(fldCenVis, fldCenCode) || '10100'; 

    // Validamos apenas o que realmente aparece na tela
    if(!dtneg) invalid.push(fldDtNeg);
    if(!codparc) invalid.push(fldParcVis);
    if(!codtop) invalid.push(fldTopVis);

    if(invalid.length){
      invalid.forEach(f=> f && markInvalidField(f));
      showToast('Preencha os campos obrigatórios do cabeçalho.','error');
      try{ (invalid[0]||fldDtNeg)?.focus(); }catch(e){}
      return;
    }

    const payload = {
      codemp: codemp,
      dtneg: dtneg,
      dtmov: dtneg,
      dtentsai: dtneg,
      hrmov: null,
      codparc: codparc||null,
      codtipoper: codtop||null,
      codnat: codnat||null,
      codcencus: codcencus||null,
    };

    cabSave.setAttribute('disabled','disabled');
    try{
      if (cabEditingNunota){
        // update existing header via JSON endpoint
        const updPayload = Object.assign({ nunota: parseInt(cabEditingNunota,10) }, payload);
        const updRes = await postJSON(API_URLS.HEADER_UPDATE, updPayload);
        if (updRes.ok && updRes.body && updRes.body.executed){
          const nun = updRes.body.nunota || cabEditingNunota;
          cabEditingNunota = nun;
          animateHeaderToLeft();
          try { cabSave.removeAttribute('disabled'); if (cabSave.dataset) delete cabSave.dataset.wasDisabled; } catch(e){}
          showItemsModal(nun);
          return;
        }
        if(handleValeLockedError(updRes)){
          return;
        }
        const errs = (updRes.body?.errors||[]).join('\n');
        const errMsg = (updRes.body?.error || '').trim();
        const dbmsg = updRes.body?.db_error?.message || '';
        const warns = (updRes.body?.warnings||[]).join('\n');
        const combined = [errs, errMsg, dbmsg, warns].filter(Boolean).join('\n') || 'Falha ao atualizar cabeçalho.';
        showToast(combined, 'error');
      } else {
        const res = await postJSON(API_URLS.HEADER_SAVE, payload);
          if (res.ok && res.body && res.body.executed && res.body.nunota){
          const nun = res.body.nunota;
          cabEditingNunota = nun;
          cabRecemCriado = nun;
          animateHeaderToLeft();
          try { cabSave.removeAttribute('disabled'); if (cabSave.dataset) delete cabSave.dataset.wasDisabled; } catch(e){}
          try{ panelLoadItems(nun); }catch(e){}
          try{ showItemsModal(nun); }catch(err){}
          showToast(`✅ Cabeçalho criado (NUNOTA ${nun}). Itens abertos.`, 'success');
          return;
        }
        if(handleValeLockedError(res)){
          return;
        }
        const errs = (res.body?.errors||[]).join('\n');
        const errMsg = (res.body?.error || '').trim();
        const dbmsg = res.body?.db_error?.message || '';
        const warns = (res.body?.warnings||[]).join('\n');
        const combined = [errs, errMsg, dbmsg, warns].filter(Boolean).join('\n') || 'Falha ao criar cabeçalho.';
        showToast(combined, 'error');
      }
    } finally {
      cabSave.removeAttribute('disabled');
    }
  });

  // ==========================================================================
  // BOTÃO LIMPAR FORMULÁRIO DE ITENS
  // ==========================================================================
  document.getElementById('itemClearForm')?.addEventListener('click', function() {
      // 1. Limpa os campos de texto/número
      document.getElementById('item_prod_vis').value = '';
      document.getElementById('item_prod_hidden').value = '';
      document.getElementById('item_qtd').value = '';
      document.getElementById('item_peso').value = '';
      document.getElementById('item_total').value = '';
      
      const obs = document.getElementById('item_obs');
      if (obs) obs.value = '';

      // 2. Reseta o volume para o padrão (CX)
      const volVis = document.getElementById('item_vol');
      const volHid = document.getElementById('item_vol_hidden');
      if (volVis) volVis.value = 'CX';
      if (volHid) volHid.value = 'CX';

      // 3. Limpa o toggle de classificação (Sim/Não)
      if(typeof window.__resetItemClassificaField === 'function') {
          window.__resetItemClassificaField();
      }

      // 4. Se estiver em modo de edição, cancela e volta para modo de inserção (+)
      const seqInp = document.getElementById('item_seq_edit');
      if (seqInp) seqInp.value = '';
      try { setItemAddBtnMode('add'); } catch(e) {}

      // 5. Limpa marcações vermelhas de erro (se houver)
      ['item_prod_vis', 'item_qtd', 'item_peso', 'item_vol'].forEach(id => {
          const el = document.getElementById(id);
          if (el) el.classList.remove('invalid');
      });
      const toggle = document.getElementById('itemClassificaToggle');
      if (toggle) toggle.classList.remove('is-invalid');

      // 6. Devolve o foco para o primeiro campo (Produto)
      try { document.getElementById('item_prod_vis')?.focus(); } catch(e) {}
  });
})();