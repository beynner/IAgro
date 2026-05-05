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
      success: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
      error: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>',
      info: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>',
      warning: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
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

  // Expor os módulos para o escopo global (window)
  window.IAgro = {
    ...(window.IAgro || {}),
    getCookie, postJSON, showToast, debounce, confirmarAcao,
    cachedFetch, cachedFetchClear,
  };
  window.IAOverlay = IAOverlay;

})();