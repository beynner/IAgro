(function() {
  'use strict';

  /**
   * 1. Gestão de Segurança (CSRF)
   * Extrai um cookie do navegador pelo nome. Essencial para obter o csrftoken.
   * @param {string} name - O nome do cookie (ex: 'csrftoken').
   * @returns {string} O valor do cookie ou uma string vazia.
   */
  function getCookie(name) {
    let cookieValue = '';
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  /**
   * 2. Motor de Requisições (Motor AJAX)
   * Envia dados para uma URL via POST usando a Fetch API.
   * @param {string} url - A URL do endpoint.
   * @param {object} data - O objeto JavaScript a ser enviado como JSON.
   * @returns {Promise<{ok: boolean, status: number, body: object}>} Objeto com o resultado da requisição.
   */
  async function postJSON(url, data) {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify(data),
      });

      const responseBody = await response.json();
      
      return {
        ok: response.ok,
        status: response.status,
        body: responseBody,
      };
    } catch (error) {
      console.error('Erro na requisição postJSON:', error);
      return {
        ok: false,
        status: 0, // Status 0 para erros de rede/fetch
        body: { error: 'Erro de comunicação com o servidor.' },
      };
    }
  }

  /**
   * 3. Sistema de Notificações (Toast)
   * Exibe uma notificação toast na tela.
   * @param {string} message - A mensagem a ser exibida.
   * @param {'success'|'error'|'info'|'warning'} type - O tipo de notificação.
   */
  function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
      success: '<i class="ph ph-check-circle" style="font-size: 24px;"></i>',
      error:   '<i class="ph ph-warning-circle" style="font-size: 24px;"></i>',
      info:    '<i class="ph ph-info" style="font-size: 24px;"></i>',
      warning: '<i class="ph ph-warning" style="font-size: 24px;"></i>',
    };

    toast.innerHTML = `
      <div class="toast-icon">${icons[type] || icons.info}</div>
      <div class="toast-content">${message}</div>
      <button class="toast-close">&times;</button>
    `;

    container.appendChild(toast);

    const removeToast = () => {
      toast.classList.add('removing');
      toast.addEventListener('animationend', () => toast.remove());
    };

    toast.querySelector('.toast-close').addEventListener('click', removeToast);
    setTimeout(removeToast, 4000);
  }

  /**
   * 4. Controle de Overlay (Loading)
   * Objeto para controlar o overlay de carregamento da página.
   */
  const IAOverlay = {
    show: function() {
      const overlay = document.getElementById('pageOverlay');
      if (overlay) {
        overlay.style.display = 'flex';
        overlay.classList.remove('hidden');
      }
    },
    hide: function() {
      const overlay = document.getElementById('pageOverlay');
      if (overlay) {
        overlay.classList.add('hidden');
        setTimeout(() => {
          if (overlay.classList.contains('hidden')) {
            overlay.style.display = 'none';
          }
        }, 250);
      }
    }
  };

  /**
   * Atraso na execução de uma função para evitar chamadas excessivas.
   * @param {function} func A função a ser executada.
   * @param {number} wait O tempo de espera em milissegundos.
   * @returns {function} A nova função com debounce.
   */
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  /**
   * 5b. Cache em memória com TTL para responses de typeahead.
   * Evita refetch repetido do mesmo termo dentro de uma janela curta. Útil
   * para listas semi-estáticas (Empresa, Tipo de Negociação, Natureza,
   * Centro de Resultado).
   *
   * Uso:
   *   const data = await IAgro.cachedFetch('/sankhya/empresa/search/?q=10', { ttl: 60_000 });
   * O cache é por URL completa. Limpa entradas expiradas no acesso.
   */
  const _cacheFetch = new Map();   // url -> { expira, body }
  async function cachedFetch(url, opts) {
    const ttl = (opts && typeof opts.ttl === 'number') ? opts.ttl : 60_000;
    const agora = Date.now();
    const entry = _cacheFetch.get(url);
    if (entry && entry.expira > agora) return entry.body;
    if (entry) _cacheFetch.delete(url);   // expirado
    try {
      const r = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
      const body = await r.json();
      // Só cacheia respostas OK (não cacheia erros — pra não persistir falha transitória)
      if (r.ok) _cacheFetch.set(url, { expira: agora + ttl, body });
      return body;
    } catch (e) {
      return { ok: false, error: 'Erro de comunicação' };
    }
  }
  function cachedFetchClear() { _cacheFetch.clear(); }

  /**
   * 5. Modal de Confirmação reutilizável (substitui o window.confirm nativo).
   * Mostra um modal com título, mensagem e dois botões. Resolve a Promise
   * com `true` se confirmar, `false` se cancelar (ou fechar com Esc/clique fora).
   *
   * @param {object} opts
   * @param {string} opts.titulo  - Cabeçalho do modal (ex.: "Excluir pedido?")
   * @param {string} opts.mensagem - Texto descritivo (HTML escapado pelo chamador)
   * @param {string} [opts.confirmarLabel='Confirmar']
   * @param {string} [opts.cancelarLabel='Cancelar']
   * @param {'perigo'|'aviso'|'info'} [opts.tipo='perigo'] - Cor do botão de confirmar
   * @returns {Promise<boolean>}
   */
  function confirmarAcao(opts) {
    const o = opts || {};
    const titulo = o.titulo || 'Confirmar ação';
    const mensagem = o.mensagem || 'Tem certeza que deseja continuar?';
    const confirmarLabel = o.confirmarLabel || 'Confirmar';
    const cancelarLabel  = o.cancelarLabel  || 'Cancelar';
    const tipo = o.tipo || 'perigo';

    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'ia-confirm-overlay';
      overlay.innerHTML = `
        <div class="ia-confirm-card ia-confirm-${tipo}">
          <div class="ia-confirm-header">${titulo}</div>
          <div class="ia-confirm-body">${mensagem}</div>
          <div class="ia-confirm-footer">
            <button type="button" class="ia-confirm-btn ia-confirm-btn-cancel">${cancelarLabel}</button>
            <button type="button" class="ia-confirm-btn ia-confirm-btn-ok ia-confirm-btn-${tipo}">${confirmarLabel}</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);

      let resolvido = false;
      const fechar = (resultado) => {
        if (resolvido) return;
        resolvido = true;
        overlay.remove();
        document.removeEventListener('keydown', onKey);
        resolve(resultado);
      };
      const onKey = (e) => {
        if (e.key === 'Escape') { e.preventDefault(); fechar(false); }
        else if (e.key === 'Enter') { e.preventDefault(); fechar(true); }
      };
      document.addEventListener('keydown', onKey);

      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) fechar(false);
      });
      overlay.querySelector('.ia-confirm-btn-cancel')
             .addEventListener('click', () => fechar(false));
      overlay.querySelector('.ia-confirm-btn-ok')
             .addEventListener('click', () => fechar(true));

      // Foco inicial no botão de confirmar (Enter ativa)
      setTimeout(() => overlay.querySelector('.ia-confirm-btn-ok')?.focus(), 30);
    });
  }

  // ========================================================================
  // 6. UX Pattern: TYPEAHEAD CENTRALIZADO (Mai/2026)
  //
  // Substitui as 3 implementações locais de attachTA (venda.js, email_importar.js,
  // entrada.js) e os handlers ad-hoc dos demais módulos. Padroniza:
  //  - ↑/↓ navega itens; scrollIntoView automático
  //  - Enter confirma item ativo (preventDefault — não submete form)
  //  - Tab confirma + segue fluxo natural (sem preventDefault)
  //  - Esc fecha sem selecionar
  //  - Click no item confirma
  //  - Blur fecha com 200ms de tolerância (deixa click registrar)
  //  - Debounce padrão 300ms
  //  - Min 1 char pra disparar (configurável)
  //  - Suporte a position:fixed (pra dropdown dentro de <td>)
  //  - Auto-select no foco do input (configurável)
  //
  // API:
  //   IAgro.attachTypeahead({
  //     inputId, hiddenId, dropdownId,
  //     url,                               // endpoint GET ?q=&limit=
  //     limit:        15,                  // default
  //     debounceMs:   300,                 // default
  //     minChars:     1,                   // default
  //     extraQuery:   'grupo_inicia_com=1',// query extra adicionada à URL
  //     positionFixed:false,               // true: dropdown vira fixed + body
  //     onSelect:     (cod, descr, item) => {},
  //     onClear:      () => {},            // disparado quando input fica vazio
  //     renderItem:   (it) => `${it.cod} — ${it.descr}`, // opcional
  //     pickCod:      (it) => it.cod || it.codparc || it.codemp || it.codtipvenda,
  //     pickDescr:    (it) => it.descr || it.nomeparc || it.nomefantasia || it.descrtipvenda || '',
  //     pickItems:    (data) => data.results || data.items || data.lotes || [],
  //   });
  //
  // Retorna: { destroy, refresh, hide } pra controle programático.
  // ========================================================================
  function attachTypeahead(opts) {
    const o = opts || {};
    const inp = document.getElementById(o.inputId);
    // hiddenId é opcional — se omitido, o helper só atualiza o input visível
    // (útil pra typeaheads onde o "código" é só visual, sem campo escondido).
    const hid = o.hiddenId ? document.getElementById(o.hiddenId) : null;
    const dd  = document.getElementById(o.dropdownId);
    if (!inp || !dd) {
      console.warn('[attachTypeahead] elementos ausentes:', o.inputId, o.dropdownId);
      return { destroy: () => {}, refresh: () => {}, hide: () => {} };
    }

    const url           = o.url || '';
    const limit         = (typeof o.limit === 'number' && isFinite(o.limit) && o.limit > 0)
                          ? Math.floor(o.limit) : 15;
    const debounceMs    = (typeof o.debounceMs === 'number' && o.debounceMs >= 0)
                          ? o.debounceMs : 300;
    const minChars      = (typeof o.minChars === 'number' && o.minChars >= 0)
                          ? o.minChars : 1;
    const extraQuery    = (typeof o.extraQuery === 'string' && o.extraQuery.trim())
                          ? o.extraQuery.trim() : '';
    const positionFixed = !!o.positionFixed;
    const onSelect      = (typeof o.onSelect === 'function') ? o.onSelect : null;
    const onClear       = (typeof o.onClear  === 'function') ? o.onClear  : null;
    const pickItems     = (typeof o.pickItems === 'function')
                          ? o.pickItems
                          : (data) => data.results || data.items || data.lotes || data || [];
    const pickCod       = (typeof o.pickCod === 'function')
                          ? o.pickCod
                          : (it) => it.cod ?? it.codparc ?? it.codemp ?? it.codtipvenda ?? it.codprod ?? it.codnat ?? it.codagregacao ?? '';
    const pickDescr     = (typeof o.pickDescr === 'function')
                          ? o.pickDescr
                          : (it) => it.descr ?? it.nomeparc ?? it.nomefantasia ?? it.descrtipvenda ?? it.descrprod ?? it.descrnat ?? '';
    const renderItem    = (typeof o.renderItem === 'function')
                          ? o.renderItem
                          : (it) => `${pickCod(it)} — ${pickDescr(it)}`;
    // pickExtra(it) -> {key: value, ...} vira data-key="value" no <div>.
    // Útil pra propagar atributos do item raw da API pro DOM, lidos via
    // item.dataset no callback onSelect. Ex: entrada.js usa data-selecionado.
    const pickExtra     = (typeof o.pickExtra === 'function') ? o.pickExtra : null;

    let timer = null;
    let aberto = false;

    function buildUrl(q) {
      const sep = url.includes('?') ? '&' : '?';
      let full = `${url}${sep}q=${encodeURIComponent(q)}&limit=${encodeURIComponent(limit)}`;
      if (extraQuery) full += extraQuery.startsWith('&') ? extraQuery : `&${extraQuery}`;
      return full;
    }

    function hide() {
      dd.style.display = 'none';
      dd.innerHTML = '';
      aberto = false;
      if (positionFixed) {
        // Reseta posicionamento inline aplicado pelo show()
        dd.style.position = '';
        dd.style.top = '';
        dd.style.left = '';
        dd.style.width = '';
        dd.style.zIndex = '';
      }
    }

    function show(items) {
      if (!items || !items.length) { hide(); return; }
      dd.innerHTML = items.map((it, idx) => {
        const cod = pickCod(it);
        const descr = pickDescr(it);
        const safeDescr = String(descr).replace(/"/g, '&quot;');
        let extras = '';
        if (pickExtra) {
          try {
            const obj = pickExtra(it) || {};
            extras = Object.entries(obj)
              .filter(([_, v]) => v !== undefined && v !== null)
              .map(([k, v]) => ` data-${k}="${String(v).replace(/"/g, '&quot;')}"`)
              .join('');
          } catch (e) { /* ignore */ }
        }
        return `<div class="dd-item${idx === 0 ? ' active' : ''}" data-cod="${cod}" data-descr="${safeDescr}"${extras}>${renderItem(it)}</div>`;
      }).join('');
      if (positionFixed) {
        if (dd.parentElement !== document.body) document.body.appendChild(dd);
        const r = inp.getBoundingClientRect();
        dd.style.position = 'fixed';
        dd.style.top      = `${r.bottom}px`;
        dd.style.left     = `${r.left}px`;
        dd.style.width    = `${r.width}px`;
        dd.style.zIndex   = '10000';
      }
      dd.style.display = 'block';
      aberto = true;
    }

    async function buscar() {
      const q = (inp.value || '').trim();
      if (q.length < minChars) { hide(); return; }
      try {
        const r = await fetch(buildUrl(q), { credentials: 'same-origin' });
        if (!r.ok) { hide(); return; }
        const data = await r.json();
        show(pickItems(data));
      } catch (e) {
        hide();
      }
    }

    function selecionarItem(item) {
      const cod = item.dataset.cod;
      const descr = item.dataset.descr || '';
      if (hid) hid.value = cod;
      // Mai/2026 — quando cod === descr (caso típico de fabricante: cod e
      // descr são o mesmo texto), mostra só uma vez em vez de "CENOURA — CENOURA".
      inp.value = (descr && descr !== cod) ? `${cod} — ${descr}` : cod;
      hide();
      if (onSelect) {
        try { onSelect(cod, descr, item); } catch (e) { console.error('[typeahead] onSelect erro:', e); }
      }
    }

    function onInput(e) {
      const raw = (e.target.value || '').trim();
      if (timer) clearTimeout(timer);
      if (!raw) {
        hide();
        if (hid) hid.value = '';
        if (onClear) { try { onClear(); } catch (err) { console.error('[typeahead] onClear erro:', err); } }
        return;
      }
      timer = setTimeout(buscar, debounceMs);
    }

    function onKeydown(e) {
      if (!aberto) return;
      const items = Array.from(dd.querySelectorAll('.dd-item'));
      if (!items.length) return;
      const ativoIdx = items.findIndex(x => x.classList.contains('active'));
      const cur = ativoIdx < 0 ? 0 : ativoIdx;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const nxt = (cur + 1) % items.length;
        items.forEach(x => x.classList.remove('active'));
        items[nxt].classList.add('active');
        items[nxt].scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const nxt = (cur - 1 + items.length) % items.length;
        items.forEach(x => x.classList.remove('active'));
        items[nxt].classList.add('active');
        items[nxt].scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'Enter') {
        e.preventDefault();   // não submete o form / não fecha modal
        const el = items[cur] || items[0];
        if (el) selecionarItem(el);
      } else if (e.key === 'Tab') {
        // Tab confirma e segue o fluxo natural — vai pro próximo campo.
        // SEM preventDefault: deixa Tab continuar a navegação.
        const el = items[cur] || items[0];
        if (el) selecionarItem(el);
      } else if (e.key === 'Escape') {
        hide();
      }
    }

    function onClick(ev) {
      const item = ev.target.closest('.dd-item[data-cod]');
      if (item) selecionarItem(item);
    }

    function onBlur() {
      // 200ms de tolerância pra deixar click no dd registrar antes de esconder
      setTimeout(hide, 200);
    }

    function onDocClick(ev) {
      if (!dd.contains(ev.target) && ev.target !== inp) hide();
    }

    inp.addEventListener('input', onInput);
    inp.addEventListener('keydown', onKeydown);
    inp.addEventListener('blur', onBlur);
    dd.addEventListener('click', onClick);
    document.addEventListener('click', onDocClick);

    return {
      destroy() {
        inp.removeEventListener('input', onInput);
        inp.removeEventListener('keydown', onKeydown);
        inp.removeEventListener('blur', onBlur);
        dd.removeEventListener('click', onClick);
        document.removeEventListener('click', onDocClick);
        hide();
      },
      refresh: buscar,
      hide,
    };
  }

  // ========================================================================
  // 7. UX Pattern: AUTO-SELECT GLOBAL (Mai/2026)
  //
  // Delegação global no document: ao focar um input de texto/número (ou
  // textarea), seleciona todo o conteúdo automaticamente — facilita edição
  // de campos pré-populados (operador não precisa apagar manualmente).
  //
  // Opt-out por campo: <input ... data-no-select>
  // Tipos cobertos: text, number, search, tel, email, url, password, e textarea.
  // Ignora readonly e disabled.
  //
  // Chamar uma vez no boot da página (em base.html):
  //   IAgro.installAutoSelect();
  // ========================================================================
  const _TIPOS_AUTOSEL = new Set([
    'text', 'number', 'search', 'tel', 'email', 'url', 'password',
  ]);
  let _autoSelectInstalled = false;

  function installAutoSelect(opts) {
    if (_autoSelectInstalled) return;
    _autoSelectInstalled = true;

    document.addEventListener('focusin', function (e) {
      const t = e.target;
      if (!t || t.dataset?.noSelect !== undefined) return;
      if (t.readOnly || t.disabled) return;
      if (t.tagName === 'INPUT' && _TIPOS_AUTOSEL.has((t.type || 'text').toLowerCase())) {
        // setTimeout(0) é necessário porque o click subsequente ao focus
        // desselecionaria; adiamos pro próximo tick pra preservar a seleção.
        setTimeout(() => { try { t.select(); } catch (_) {} }, 0);
      } else if (t.tagName === 'TEXTAREA') {
        setTimeout(() => { try { t.select(); } catch (_) {} }, 0);
      }
    });
  }

  // ========================================================================
  // 8. UX Pattern: WIRE FILTER AUTO (Mai/2026)
  //
  // Padroniza binding de filtros de listagem: input de texto/número usa
  // debounce (default 500ms); select/date usa change imediato. Garante que
  // NENHUM filtro fica órfão sem listener.
  //
  // API:
  //   IAgro.wireFilterAuto(
  //     ['filtroTop', 'filtroPedido', 'filtroNF', 'filtroLote'],
  //     () => carregarVendas(false),
  //     { debounceMs: 500 }   // opcional
  //   );
  //
  // Funciona com IDs ou elementos. Ignora elementos ausentes silenciosamente.
  // ========================================================================
  function wireFilterAuto(fieldIds, onChange, opts) {
    const o = opts || {};
    const debounceMs = (typeof o.debounceMs === 'number' && o.debounceMs >= 0)
                       ? o.debounceMs : 500;
    if (typeof onChange !== 'function') return;
    const disparar = debounce(onChange, debounceMs);
    (Array.isArray(fieldIds) ? fieldIds : [fieldIds]).forEach(item => {
      const el = (typeof item === 'string') ? document.getElementById(item) : item;
      if (!el) return;
      const tag = (el.tagName || '').toUpperCase();
      const tipo = (el.type || '').toLowerCase();
      if (tag === 'SELECT' || tipo === 'date' || tipo === 'datetime-local' || tipo === 'month' || tipo === 'week' || tipo === 'time') {
        // Discreto: dispara imediato no change
        el.addEventListener('change', () => onChange());
      } else {
        // Texto/número: debounce + ambos eventos pra cobrir paste/autofill
        el.addEventListener('input', disparar);
        el.addEventListener('change', disparar);
      }
    });
  }

  // ===========================================================================
  // IAgro.setupSidebar — toggle expand/collapse + off-canvas mobile (Mai/2026)
  // Persiste estado em localStorage. Marca item ativo na nav baseado em
  // `body[data-active-module]`. Chamado uma única vez no base.html.
  // ===========================================================================
  function setupSidebar() {
    const sidebar = document.getElementById('appSidebar');
    if (!sidebar) return;
    const btnCollapse = document.getElementById('btnSidebarCollapse');
    const btnMobile   = document.getElementById('btnSidebarToggleMobile');

    // 1) Restaura estado recolhido (desktop) do localStorage
    const STORAGE_KEY = 'iagro:sidebar:collapsed:v1';
    try {
      if (localStorage.getItem(STORAGE_KEY) === '1' && window.innerWidth > 900) {
        sidebar.classList.add('collapsed');
      }
    } catch (_) { /* localStorage indisponível */ }

    // 2) Botão de recolher (chevron) — desktop
    if (btnCollapse) {
      btnCollapse.addEventListener('click', (e) => {
        e.stopPropagation();
        sidebar.classList.toggle('collapsed');
        try {
          localStorage.setItem(STORAGE_KEY, sidebar.classList.contains('collapsed') ? '1' : '0');
        } catch (_) {}
      });
    }

    // 3) Botão hambúrguer + backdrop — tablet/mobile
    if (btnMobile) {
      let backdrop = document.querySelector('.sidebar-backdrop');
      if (!backdrop) {
        backdrop = document.createElement('div');
        backdrop.className = 'sidebar-backdrop';
        document.body.appendChild(backdrop);
      }
      const closeMobile = () => {
        sidebar.classList.remove('open');
        btnMobile.classList.remove('open');
        backdrop.classList.remove('visible');
      };
      const openMobile = () => {
        sidebar.classList.add('open');
        btnMobile.classList.add('open');
        backdrop.classList.add('visible');
      };
      btnMobile.addEventListener('click', () => {
        sidebar.classList.contains('open') ? closeMobile() : openMobile();
      });
      backdrop.addEventListener('click', closeMobile);
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar.classList.contains('open')) closeMobile();
      });
      // Fecha automaticamente ao trocar pra desktop
      let lastW = window.innerWidth;
      window.addEventListener('resize', () => {
        if (window.innerWidth > 900 && lastW <= 900) closeMobile();
        lastW = window.innerWidth;
      });
    }

    // 4) Marca item ativo na nav (lê body[data-active-module])
    const activeMod = (document.body.getAttribute('data-active-module') || '').trim();
    if (activeMod) {
      const link = sidebar.querySelector(`.nav-item[data-mod="${activeMod}"]`);
      if (link) link.classList.add('active');
    }
  }

  // Expor os módulos para o escopo global (window)
  window.IAgro = {
    ...(window.IAgro || {}),
    getCookie, postJSON, showToast, debounce, confirmarAcao,
    cachedFetch, cachedFetchClear,
    // Mai/2026 — UX patterns centralizados
    attachTypeahead, installAutoSelect, wireFilterAuto,
    // Mai/2026 — layout v2 (sidebar)
    setupSidebar,
  };
  window.IAOverlay = IAOverlay;

})();