;(function(){
	'use strict';

	/**
	 * Núcleo da aplicação JS do Comercial Dashboard.
	 * Responsável por expor utilitários, registrar módulos
	 * e sincronizar comportamento entre Portal e Dashboard.
	 */
// Referências básicas ao documento e aos elementos raiz para reutilização constante.
	const doc = document; // Referência global ao document para evitar lookups repetidos.
	const html = doc.documentElement; // Ponteiro para o elemento <html> usado em toggles globais.
	const body = doc.body; // Fácil acesso ao <body>, frequentemente usado por classes/flags.

// Flags de contexto que ajudam a entender em qual tela o script está rodando.
	const flags = {
		isDashboard: !!(body && body.classList.contains('comercial-dashboard')),
		isPortal: !!doc.getElementById('notasTable'),
		booted: false
	};

// Estrutura principal da aplicação para coordenar módulos e serviços compartilhados.
	const App = {
		version: '2025.12.10-alpha',
		flags,
		modules: new Map()
	};

	/**
	 * Utilitário simples para logs consistentes no console.
	 */
// Logger padronizado para facilitar a leitura dos logs no console.
	const logger = (()=>{
		const base = '[PH|Dashboard]';
		const formatArgs = (args)=>['%c'+base, 'color:#0ea5e9;font-weight:600;', ...args];
		return {
			info: (...args)=>console.info(...formatArgs(args)),
			warn: (...args)=>console.warn(...formatArgs(args)),
			error: (...args)=>console.error(...formatArgs(args)),
			debug: (...args)=>console.debug(...formatArgs(args))
		};
	})();

	/**
	 * Event emitter bem simples para comunicação cruzada.
	 */
// Event emitter simplificado para comunicação entre módulos independentes.
	const Emitter = (()=>{
		const listeners = new Map();
		return {
			on(event, handler){
				if(!listeners.has(event)) listeners.set(event, new Set());
				listeners.get(event).add(handler);
			},
			off(event, handler){
				if(!listeners.has(event)) return;
				listeners.get(event).delete(handler);
			},
			emit(event, payload){
				if(!listeners.has(event)) return;
				for(const cb of listeners.get(event)){
					try{ cb(payload); }catch(err){ logger.error('Listener falhou', event, err); }
				}
			}
		};
	})();

	/**
	 * Helpers de requisição com CSRF automático e JSON seguro.
	 */
// Camada fina de HTTP com CSRF automático e respostas normalizadas.
	const http = (()=>{
		const getCookie = window.__getCookie || function(name){
			const match = doc.cookie.match(new RegExp('(^| )'+name+'=([^;]+)'));
			return match ? decodeURIComponent(match[2]) : null;
		};

		const baseHeaders = ()=>{
			const headers = {
				'X-Requested-With': 'XMLHttpRequest',
				'Accept': 'application/json'
			};
			const csrf = getCookie('csrftoken') || getCookie('CSRF-TOKEN');
			if(csrf) headers['X-CSRFToken'] = csrf;
			return headers;
		};

		const buildOptions = (method, body, extra = {})=>{
			const headers = Object.assign({}, baseHeaders(), extra.headers || {});
			const opts = Object.assign({ credentials: 'same-origin', cache: 'no-store' }, extra, { method, headers });
			if(body !== undefined && body !== null){
				if(body instanceof FormData){
					delete headers['Content-Type'];
					opts.body = body;
				}else if(typeof body === 'string'){
					headers['Content-Type'] = headers['Content-Type'] || 'application/json';
					opts.body = body;
				}else{
					headers['Content-Type'] = headers['Content-Type'] || 'application/json';
					opts.body = JSON.stringify(body);
				}
			}
			return opts;
		};

		const parsePayload = async (response)=>{
			const text = await response.text();
			if(!text) return null;
			try{ return JSON.parse(text); }
			catch(_err){ return text; }
		};

		const request = async (url, { method = 'GET', body, headers, ...rest } = {})=>{
			const opts = buildOptions(method.toUpperCase(), body, { headers, ...rest });
			const resp = await fetch(url, opts);
			const data = await parsePayload(resp);
			if(!resp.ok){
				const error = new Error((data && data.error) || resp.statusText || 'Erro na requisição');
				error.status = resp.status;
				error.payload = data;
				throw error;
			}
			return data;
		};

		return {
			request,
			get: (url, options)=> request(url, { ...(options || {}), method: 'GET' }),
			post: (url, payload, options)=> request(url, { ...(options || {}), method: 'POST', body: payload }),
			put: (url, payload, options)=> request(url, { ...(options || {}), method: 'PUT', body: payload }),
			delete: (url, options)=> request(url, { ...(options || {}), method: 'DELETE' })
		};

		// Se não houver um alias global para postJSON, expomos um wrapper baseado em http.post
		if(typeof window !== 'undefined'){
			if(typeof window.__postJSON !== 'function'){
				window.__postJSON = async function(url, body, options){
					try{
						const data = await request(url, { ...(options||{}), method: (options && options.method) || 'POST', body });
						return { ok: true, body: data };
					}catch(err){
						return { ok: false, status: err && err.status ? err.status : 0, error: err && err.message ? err.message : String(err), body: err && err.payload ? err.payload : null };
					}
				};
			}
			if(typeof window.postJSON !== 'function') window.postJSON = window.__postJSON;
		}
	})();

	/**
	 * Utilidades compartilhadas entre módulos (formatação, DOM helpers, toast).
	 */
	const Utils = (()=>{
		const decimalFormatter = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 3 });
		const moneyFormatter = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

		const formatDecimal = (value, precision = 2)=>{
			const num = Number(value);
			if(!Number.isFinite(num)) return '0';
			const safePrecision = Math.max(0, Math.min(6, precision));
			try{
				return num.toLocaleString('pt-BR', {
					minimumFractionDigits: safePrecision,
					maximumFractionDigits: safePrecision
				});
			}catch(_err){
				return num.toFixed(safePrecision);
			}
		};

		const formatMoney = (value)=>{
			const num = Number(value);
			if(!Number.isFinite(num)) return moneyFormatter.format(0);
			try{
				return moneyFormatter.format(num);
			}catch(_err){
				return `R$ ${num.toFixed(2)}`;
			}
		};

		const formatDateBR = (value)=>{
			if(!value) return '';
			if(value instanceof Date && !Number.isNaN(value.getTime())){
				return value.toLocaleDateString('pt-BR');
			}
			const parsed = new Date(value);
			if(!Number.isNaN(parsed.getTime())){
				return parsed.toLocaleDateString('pt-BR');
			}
			const digits = String(value).trim();
			const match = digits.match(/^(\d{2})(\d{2})(\d{4})$/);
			if(match) return `${match[1]}/${match[2]}/${match[3]}`;
			return digits;
		};

		const normalizeNunota = (value)=>{
			if(value == null) return '';
			const digits = String(value).replace(/\D+/g, '').replace(/^0+/, '');
			return digits || '';
		};

		const qs = (selector, root = doc)=> (root || doc)?.querySelector(selector) || null;
		const qsa = (selector, root = doc)=> Array.from((root || doc)?.querySelectorAll(selector) || []);

		const toastQueue = [];
		let toastContainer = null;
		// Garante que o stack de toasts exista antes de exibir mensagens.
		function ensureToastContainer(){
			if(toastContainer) return toastContainer;
			toastContainer = doc.getElementById('toastStack');
			if(!toastContainer){
				toastContainer = doc.createElement('div');
				toastContainer.id = 'toastStack';
				toastContainer.style.position = 'fixed';
				toastContainer.style.bottom = '24px';
				toastContainer.style.right = '24px';
				toastContainer.style.zIndex = '9999';
				doc.body.appendChild(toastContainer);
			}
			return toastContainer;
		}

		// Exibe notificações temporárias com estilos diferentes por tipo.
		const toast = (message, type = 'info')=>{
			const stack = ensureToastContainer();
			const node = doc.createElement('div');
			node.className = `toast toast--${type}`;
			node.textContent = message || '';
			node.style.cssText = 'min-width:200px; margin-bottom:8px; padding:12px 16px; border-radius:6px; color:#0f172a; background:#e2e8f0; box-shadow:0 8px 24px rgba(15,23,42,.2); font-size:.85rem; opacity:0; transform:translateY(-6px); transition:all .25s ease;';
			const palette = {
				info: { bg: '#e0f2fe', color: '#0c4a6e' },
				success: { bg: '#15803d', color: '#f0fdf4' },
				warning: { bg: '#fef9c3', color: '#713f12' },
				error: { bg: '#fee2e2', color: '#7f1d1d' }
			};
			const theme = palette[type] || palette.info;
			node.style.background = theme.bg;
			node.style.color = theme.color;
			stack.appendChild(node);
			requestAnimationFrame(()=>{
				node.style.opacity = '1';
				node.style.transform = 'translateY(0)';
			});
			const ttl = 3200 + (toastQueue.length * 200);
			toastQueue.push(node);
			setTimeout(()=>{
				node.style.opacity = '0';
				node.style.transform = 'translateY(-8px)';
				node.addEventListener('transitionend', ()=>{
					stack.contains(node) && stack.removeChild(node);
					toastQueue.splice(toastQueue.indexOf(node), 1);
				});
			}, ttl);
		};

		return {
			formatDecimal,
			formatMoney,
			formatDateBR,
			normalizeNunota,
			qs,
			qsa,
			toast
		};
	})();

	const Overlay = (()=>{
		const el = doc.getElementById('pageOverlay');
		const show = ()=>{ if(el){ el.classList.remove('hidden'); el.style.display = 'flex'; } };
		const hide = ()=>{ if(el){ el.classList.add('hidden'); setTimeout(()=>{ el.style.display = 'none'; }, 250); } };
		if(el){
			window.addEventListener('beforeunload', show);
			window.addEventListener('pagehide', show);
			doc.addEventListener('DOMContentLoaded', hide);
			window.addEventListener('load', ()=> setTimeout(hide, 200));
		}
		return { show, hide };
	})();

	// Cria uma função com atraso controlado para evitar execuções em excesso.
	function debounce(fn, wait = 250){
		if(typeof fn !== 'function'){
			throw new TypeError('debounce requer uma função.');
		}
		let timer = null;
		// Versão atrasada da função original, reiniciando o timer a cada chamada.
		return function debounced(...args){
			clearTimeout(timer);
			timer = setTimeout(()=> fn.apply(this, args), wait);
		};
	}

	// Helpers legados para detectar se o item é classificável (reutilizados pelo card Lista).
	if(typeof window.__isClassificavelItem !== 'function'){
		window.__isClassificavelItem = function(item){
			if(!item) return false;
			try{
				const tipo = (item.tipo || '').toString().toLowerCase();
				if(tipo === 'classificavel') return true;
				if(tipo.indexOf('nao') !== -1) return false;
				const flag = item.classificavel;
				if(typeof flag === 'boolean') return flag;
				if(typeof flag === 'number') return flag === 1;
				if(typeof flag === 'string'){
					const base = typeof flag.normalize === 'function' ? flag.normalize('NFD') : flag;
					const normalized = base.replace(/[^\x00-\x7F]/g, '').trim().toUpperCase();
					if(['S','SIM','1','TRUE','Y'].includes(normalized)) return true;
					if(['N','NAO','FALSE','0'].includes(normalized)) return false;
				}
			}catch(err){
				logger.warn('[Lista] Falha ao avaliar flag classificavel', err);
			}
			return false;
		};
	}

	if(typeof window.__isNaoClassificavelItem !== 'function'){
		window.__isNaoClassificavelItem = function(item){
			return !window.__isClassificavelItem(item);
		};
	}

	/**
	 * Registro de módulos: garante inicialização única e lazy-load.
	 */
	// Registra módulos garantindo assinatura consistente de inicialização.
	// Registra um módulo e armazena sua factory para inicialização futura.
	function registerModule(name, factory){
		if(!name || typeof factory !== 'function'){
			throw new Error('registerModule requer nome e factory.');
		}
		App.modules.set(name, { factory, initialized: false, instance: null });
	}

	// Inicializa módulos registrados garantindo idempotência.
	// Inicializa o módulo solicitado apenas uma vez e reutiliza a instância.
	function initModule(name, context){
		const meta = App.modules.get(name);
		if(!meta){
			logger.warn('Módulo não registrado', name);
			return null;
		}
		if(meta.initialized) return meta.instance;
		logger.info('Inicializando módulo', name);
		meta.instance = meta.factory(context || App);
		meta.initialized = true;
		return meta.instance;
	}

	/**
	 * Namespace público exposto para futuros módulos.
	 */
	// Objeto exposto publicamente no window para integração com outros scripts.
	const namespace = {
		flags,
		events: Emitter,
		services: { http, Overlay },
		utils: Utils,
		registerModule,
		initModule,
		logger
	};
	// Controlador global do card de simulação (precisa existir antes dos módulos para evitar TDZ).
	let simulationCardController = null;

	Object.assign(App, namespace);

	/**
	 * Módulo: Portal básico (scroll/lista).
	 * Mantido como stub até concluirmos a migração do legado para o novo núcleo.
	 */
	registerModule('portalShell', (ctx)=>{
		if(!ctx.flags.isPortal) return null;
		logger.info('portalShell indisponível nesta build. Aguardando migração do legado.');
		return null;
	});

	registerModule('filtersShell', (ctx)=>{
		if(!ctx.flags.isDashboard) return null;
		const form = doc.getElementById('filtrosForm');
		if(!form) return null;
		const logger = ctx.logger || console;
		const parceiroInput = form.querySelector('#fltFornecedor');
		const parceiroCode = form.querySelector('#fltFornecedorCode');
		const parceiroDrop = form.querySelector('#fltFornecedorDropdown');
		const produtoInput = form.querySelector('#fltProduto');
		const produtoDrop = form.querySelector('#fltProdutoDropdown');
		const dataInput = form.querySelector('#fltDataCompra');
		const nunotaInput = form.querySelector('#fltNunota');
		const semPrecoInput = form.querySelector('#fltSemPreco');
		const btnLimpar = doc.getElementById('btnLimparFiltros');
		const btnReload = doc.getElementById('btnReaplicarFiltros');
		let lastProdutoFiltro = '';

		// Monta o objeto de filtros atuais a partir dos inputs visíveis.
		function buildPayload(){
			return {
				historico: '60',
				dataCompra: (dataInput?.value || '').trim(),
				nunota: (nunotaInput?.value || '').replace(/[^0-9]/g, ''),
				fornecedor: (parceiroCode?.value || '').trim(),
				produto: (produtoInput?.value || '').trim(),
				classificavelFiltro: form.querySelector('input[name="fltClassificavel"]:checked')?.value || '',
				faturadoFiltro: form.querySelector('input[name="fltFaturado"]:checked')?.value || '',
				semPreco: Boolean(semPrecoInput?.checked)
			};
		}

		// Permite que os radios funcionem como toggle on/off para limpar filtros.
		function setupRadioToggle(selector){
			const container = typeof selector === 'string' ? form.querySelector(selector) : selector;
			if(!container) return;
			const radios = Array.from(container.querySelectorAll('input[type="radio"]'));
			if(!radios.length) return;
			const clearFlags = ()=> radios.forEach((radio)=>{ radio.dataset.wasChecked = 'false'; });
			const toggleOff = (radio)=>{
				radio.checked = false;
				radio.dataset.wasChecked = 'false';
				clearFlags();
				radio.dispatchEvent(new Event('change', { bubbles: true }));
			};
			radios.forEach((radio)=>{
				radio.dataset.wasChecked = 'false';
				const markState = ()=>{ radio.dataset.wasChecked = radio.checked ? 'true' : 'false'; };
				radio.addEventListener('pointerdown', markState);
				radio.addEventListener('mousedown', markState);
				try{ radio.addEventListener('touchstart', markState, { passive: true }); }
				catch(_err){ radio.addEventListener('touchstart', markState); }
				radio.addEventListener('click', (ev)=>{
					if(radio.dataset.wasChecked === 'true'){
						ev.preventDefault();
						toggleOff(radio);
					}else{
						clearFlags();
					}
				});
				radio.addEventListener('keydown', (ev)=>{
					if((ev.key === ' ' || ev.key === 'Spacebar' || ev.key === 'Enter') && radio.checked){
						ev.preventDefault();
						toggleOff(radio);
					}
				});
			});
		}

		// Atualiza a aparência dos labels conforme o estado dos radios.
		function syncToggleState(){
			['fltClassificavel', 'fltFaturado'].forEach((name)=>{
				form.querySelectorAll(`input[name="${name}"]`).forEach((radio)=>{
					const label = radio.closest('label');
					if(!label) return;
					if(radio.checked) label.classList.add('is-active');
					else label.classList.remove('is-active');
				});
			});
		}

		// Gera o evento global de filtros, atualizando caches e cache de classificação.
		function emit(){
			syncToggleState();
			const payload = buildPayload();
			if(payload.produto !== lastProdutoFiltro && typeof window.__clearClassResumoCache === 'function'){
				window.__clearClassResumoCache('alteracao de produto nos filtros');
			}
			lastProdutoFiltro = payload.produto;
			window.__COM_FILTER_STATE = payload;
			window.dispatchEvent(new CustomEvent('filtros:change', { detail: payload }));
		}

		// Constrói dinamicamente a lista de autocomplete usando o renderer informado.
		function buildList(items, render){
			const frag = doc.createDocumentFragment();
			items.forEach((item, idx)=>{
				const row = doc.createElement('div');
				row.className = 'ac-item';
				row.setAttribute('role', 'option');
				row.dataset.idx = String(idx);
				row.innerHTML = render(item);
				row.style.padding = '6px 8px';
				row.style.cursor = 'pointer';
				row.addEventListener('mouseenter', ()=> setActive(row));
				row.addEventListener('mousedown', (ev)=>{ ev.preventDefault(); selectActive(row); });
				frag.appendChild(row);
			});
			return frag;
		}

		// Marca visualmente qual item do autocomplete está ativo para teclado/mouse.
		function setActive(node){
			const parent = node?.parentElement;
			if(!parent) return;
			parent.querySelectorAll('.ac-item.active').forEach((el)=> el.classList.remove('active'));
			node.classList.add('active');
		}

		// Seleciona o item destacado e sincroniza o respectivo input.
		function selectActive(node){
			if(!node) return;
			const parent = node.parentElement;
			if(!parent) return;
			const items = parent._items || [];
			const idx = Number(node.dataset.idx) || 0;
			const item = items[idx];
			if(!item) return;
			if(parent === parceiroDrop){
				if(parceiroInput) parceiroInput.value = item.nomeparc ? `${item.codparc} — ${item.nomeparc}` : String(item.codparc || '');
				if(parceiroCode) parceiroCode.value = item.codparc ? String(item.codparc) : '';
				parent.style.display = 'none';
				produtoInput?.focus();
			}else if(parent === produtoDrop){
				if(produtoInput) produtoInput.value = item.fabricante || item.descr || '';
				parent.style.display = 'none';
			}
			emit();
		}

		// Navega pelo autocomplete via teclado mantendo o foco dentro da lista.
		function moveActive(container, dir){
			if(!container) return;
			const nodes = Array.from(container.querySelectorAll('.ac-item'));
			if(!nodes.length) return;
			let idx = nodes.findIndex((el)=> el.classList.contains('active'));
			if(idx < 0) idx = 0;
			idx = (idx + dir + nodes.length) % nodes.length;
			setActive(nodes[idx]);
			nodes[idx].scrollIntoView({ block: 'nearest' });
		}

		const fetchParceiros = debounce(async ()=>{
			const term = (parceiroInput?.value || '').trim();
			if(!parceiroDrop) return;
			if(term.length < 2){
				parceiroDrop.style.display = 'none';
				parceiroDrop.innerHTML = '';
				return;
			}
			try{
				const resp = await fetch(`/sankhya/parceiros/search/?q=${encodeURIComponent(term)}&limit=20`, { credentials: 'same-origin' });
				const data = await resp.json().catch(()=>({ results: [] }));
				const items = Array.isArray(data?.results) ? data.results : [];
				parceiroDrop.innerHTML = '';
				parceiroDrop._items = items;
				if(items.length){
					parceiroDrop.appendChild(buildList(items, (it)=> `<div><strong>${it.codparc}</strong> — ${it.nomeparc || ''}</div>`));
					parceiroDrop.style.display = 'block';
					const first = parceiroDrop.querySelector('.ac-item');
					if(first) first.classList.add('active');
				}else{
					parceiroDrop.style.display = 'none';
				}
			}catch(err){
				logger.warn('Autocomplete de parceiros falhou', err);
				parceiroDrop.style.display = 'none';
			}
		}, 250);

		const fetchFabricantes = debounce(async ()=>{
			const term = (produtoInput?.value || '').trim();
			if(!produtoDrop) return;
			if(term.length < 2){
				produtoDrop.style.display = 'none';
				produtoDrop.innerHTML = '';
				return;
			}
			try{
				const resp = await fetch(`/sankhya/produtos/search/?q=${encodeURIComponent(term)}&limit=20&fabricante=1`, { credentials: 'same-origin' });
				const data = await resp.json().catch(()=>({ results: [] }));
				const items = Array.isArray(data?.results) ? data.results : [];
				const unique = [];
				items.forEach((item)=>{
					const fabricante = item.fabricante || item.descr || '';
					if(fabricante && !unique.find((u)=> u.fabricante === fabricante)){
						unique.push({ fabricante });
					}
				});
				produtoDrop.innerHTML = '';
				produtoDrop._items = unique;
				if(unique.length){
					produtoDrop.appendChild(buildList(unique, (it)=> `<div>${it.fabricante}</div>`));
					produtoDrop.style.display = 'block';
					const first = produtoDrop.querySelector('.ac-item');
					if(first) first.classList.add('active');
				}else{
					produtoDrop.style.display = 'none';
				}
			}catch(err){
				logger.warn('Autocomplete de fabricantes falhou', err);
				produtoDrop.style.display = 'none';
			}
		}, 250);

		// Seleciona automaticamente o texto quando o campo recebe foco.
		function focusSelect(el){
			if(!el) return;
			el.addEventListener('focus', (ev)=>{
				const target = ev.target;
				setTimeout(()=>{
					try{ target.select(); }
					catch(_err){ /* noop */ }
				}, 0);
			});
		}

		focusSelect(parceiroInput);
		focusSelect(produtoInput);
		focusSelect(dataInput);
		focusSelect(nunotaInput);

		parceiroInput?.addEventListener('input', ()=>{
			if(parceiroCode) parceiroCode.value = '';
			fetchParceiros();
		});
		parceiroInput?.addEventListener('keydown', (ev)=>{
			if(parceiroDrop?.style.display !== 'block') return;
			if(ev.key === 'ArrowDown'){ ev.preventDefault(); moveActive(parceiroDrop, +1); }
			else if(ev.key === 'ArrowUp'){ ev.preventDefault(); moveActive(parceiroDrop, -1); }
			else if(ev.key === 'Enter' || ev.key === 'Tab'){
				ev.preventDefault();
				selectActive(parceiroDrop.querySelector('.ac-item.active'));
			}
			else if(ev.key === 'Escape'){ parceiroDrop.style.display = 'none'; }
		});
		parceiroInput?.addEventListener('blur', ()=> setTimeout(()=>{ if(parceiroDrop) parceiroDrop.style.display = 'none'; }, 120));

		produtoInput?.addEventListener('input', fetchFabricantes);
		produtoInput?.addEventListener('keydown', (ev)=>{
			if(produtoDrop?.style.display !== 'block') return;
			if(ev.key === 'ArrowDown'){ ev.preventDefault(); moveActive(produtoDrop, +1); }
			else if(ev.key === 'ArrowUp'){ ev.preventDefault(); moveActive(produtoDrop, -1); }
			else if(ev.key === 'Enter' || ev.key === 'Tab'){
				ev.preventDefault();
				selectActive(produtoDrop.querySelector('.ac-item.active'));
			}
			else if(ev.key === 'Escape'){ produtoDrop.style.display = 'none'; }
		});
		produtoInput?.addEventListener('blur', ()=> setTimeout(()=>{ if(produtoDrop) produtoDrop.style.display = 'none'; }, 120));

		form.addEventListener('change', emit);
		form.addEventListener('submit', (ev)=> ev.preventDefault());
		btnReload?.addEventListener('click', (ev)=>{ ev.preventDefault(); emit(); });
		btnLimpar?.addEventListener('click', ()=>{
			form.reset();
			if(parceiroCode) parceiroCode.value = '';
			if(parceiroDrop){ parceiroDrop.style.display = 'none'; parceiroDrop.innerHTML = ''; }
			if(produtoDrop){ produtoDrop.style.display = 'none'; produtoDrop.innerHTML = ''; }
			lastProdutoFiltro = '';
			emit();
		});

		setupRadioToggle('#fltClassToggle');
		setupRadioToggle('#fltFatToggle');
		window.__COM_FILTER_STATE = buildPayload();
		lastProdutoFiltro = window.__COM_FILTER_STATE.produto || '';
		setTimeout(emit, 0);

		return {
			emit,
			reset: ()=> btnLimpar?.click()
		};
	});

	/**
	 * Módulo: Lista comercial (card "Lista" do dashboard).
	 * Recriado a partir do script legado, porém integrado ao novo núcleo modular.
	 */
	registerModule('listaShell', (ctx)=>{
		if(!ctx.flags.isDashboard) return null;
		const table = doc.getElementById('listaTable');
		const bodyEl = doc.getElementById('listaBody');
		if(!table || !bodyEl) return null;
		const logger = ctx.logger || console;
		const listaWrap = doc.getElementById('listaWrap');
		const viewToggle = doc.querySelector('#tableCard .lista-view-toggle');
		const collapseBtn = doc.getElementById('listaCollapseAll');
		const expandBtn = doc.getElementById('listaExpandAll');
		const moneyPt = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
		const qtyFormatter = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 });
		const statusRows = {
			loading: '<tr class="lista-status lista-loading"><td colspan="5" style="padding:8px; color:#64748b;">Carregando…</td></tr>',
			empty: '<tr class="lista-status lista-empty"><td colspan="5" style="padding:8px; color:#64748b;">Nenhum registro.</td></tr>',
			end: '<tr class="lista-status lista-end"><td colspan="5" style="padding:8px; color:#94a3b8;">Fim da lista.</td></tr>'
		};
		const LISTA_PAGE_SIZE = 30;
		const listaState = {
			limit: LISTA_PAGE_SIZE,
			offset: 0,
			loading: false,
			finished: false,
			rows: [],
			qsBase: '',
			signature: '',
			error: null,
			currentToken: 0
		};
		let listaTokenSeq = 0;
		let urlPreselectDone = false;
		window.__COM_LIST_ROWS = listaState.rows;
		const VIEW_STORAGE_KEY = 'ph.lista.view';
		let currentViewMode = (()=>{
			const stored = safeStorageGet(VIEW_STORAGE_KEY);
			if(stored === 'parceiro' || stored === 'vale') return stored;
			const checked = doc.querySelector('input[name="listaViewMode"]:checked');
			return checked ? checked.value : 'vale';
		})();

		function safeStorageGet(key){
			// Recupera valores do localStorage com try/catch para evitar falhas.
			try{ return window.localStorage.getItem(key); }
			catch(_err){ return null; }
		}

		function safeStorageSet(key, value){
			// Persiste preferências no localStorage ignorando ambientes restritos.
			try{ window.localStorage.setItem(key, value); }
			catch(_err){ /* ignore */ }
		}

		function fmtDate(value){
			// Normaliza datas variadas para o formato DD/MM exibido na lista.
			if(!value) return '';
			const str = String(value).trim();
			let m = str.match(/^([0-9]{2})\/([0-9]{2})$/);
			if(m) return `${m[1]}/${m[2]}`;
			m = str.match(/^([0-9]{1,2})[\/\-]([0-9]{1,2})[\/\-]([0-9]{2,4})$/);
			if(m){
				const dd = String(m[1]).padStart(2,'0');
				const mm = String(m[2]).padStart(2,'0');
				return `${dd}/${mm}`;
			}
			const date = new Date(str);
			if(!Number.isNaN(date.getTime())){
				const dd = String(date.getDate()).padStart(2,'0');
				const mm = String(date.getMonth()+1).padStart(2,'0');
				return `${dd}/${mm}`;
			}
			m = str.match(/([0-9]{1,2})[\/\-]([0-9]{1,2})/);
			if(m){
				const dd = String(m[1]).padStart(2,'0');
				const mm = String(m[2]).padStart(2,'0');
				return `${dd}/${mm}`;
			}
			return '';
		}

		function fmtQty(value){
			// Formata quantidades numéricas usando as casas configuradas na lista.
			try{ return qtyFormatter.format(Number(value||0)); }
			catch(_err){ return String(value||0); }
		}

		function toNumberSafe(val){
			// Converte strings diversas em números confiáveis, respeitando vírgulas.
			if(typeof val === 'number') return Number.isFinite(val) ? val : NaN;
			if(typeof val === 'bigint') return Number(val);
			if(typeof val === 'string'){
				const trimmed = val.trim();
				if(!trimmed) return NaN;
				const compact = trimmed.replace(/\s+/g, '');
				const usesComma = compact.includes(',');
				const candidate = usesComma ? compact.replace(/\./g, '').replace(/,/g, '.') : compact;
				const parsed = Number(candidate);
				return Number.isFinite(parsed) ? parsed : NaN;
			}
			return NaN;
		}

		function pickFirstPositive(...values){
			// Retorna o primeiro valor numérico positivo dentre várias fontes possíveis.
			for(const value of values){
				const num = toNumberSafe(value);
				if(Number.isFinite(num) && num > 0) return num;
			}
			return NaN;
		}

		function resolveListaQuantidade(row){
			// Resolve a quantidade base e unidade padronizada de cada item da lista.
			if(!row) return { value: 0, unit: '', unitRaw: '', unitNormalized: '' };
			const rawUnitSource = row.__raw_codvol ?? row.codvol ?? '';
			const unitRaw = rawUnitSource !== undefined && rawUnitSource !== null ? String(rawUnitSource).trim() : '';
			const unitNormalized = unitRaw ? unitRaw.toUpperCase() : String(row.codvol || '').toUpperCase();
			const preferredUnit = unitRaw || unitNormalized;
			const qtdBase = pickFirstPositive(
				row.qtdneg_base,
				row.__raw_qtdneg_base,
				row.qtdneg_original,
				row.qtdneg,
				row.__raw_qtdneg
			);
			const pesoUnitario = pickFirstPositive(
				row.__peso_unitario_resolvido,
				row.peso_unitario_resolvido,
				row.peso_unitario,
				row.peso_unitario_original,
				row.peso,
				row.peso_cx,
				row.kg_por_cx,
				row.fator_conversao,
				row.__raw_fator_conversao,
				row.peso_in,
				row.peso_medio,
				row.peso_liquido_unit,
				row.peso_liquido
			);
			if(qtdBase > 0 && pesoUnitario > 0){
				return {
					value: qtdBase / pesoUnitario,
					unit: preferredUnit || 'CX',
					unitRaw,
					unitNormalized
				};
			}
			const qtdDisplay = toNumberSafe(row.qtdneg);
			return {
				value: Number.isFinite(qtdDisplay) ? qtdDisplay : 0,
				unit: preferredUnit,
				unitRaw,
				unitNormalized
			};
		}

		function escapeHTML(value){
			// Escapa caracteres perigosos antes de inserir strings no HTML.
			return String(value || '').replace(/[<>"'&]/g, (char)=>({ '<':'&lt;', '>':'&gt;', '"':'&quot;', '\'':'&#39;', '&':'&amp;' }[char] || char));
		}

		function parseFilters(stateOverride){
			// Constrói a querystring para buscar a lista conforme os filtros ativos.
			const state = stateOverride || window.__COM_FILTER_STATE || {};
			const qs = new URLSearchParams();
			if(state.historico && state.historico !== 'all') qs.set('days', state.historico);
			if(state.dataCompra){
				qs.set('start', state.dataCompra);
				qs.set('end', state.dataCompra);
			}
			if(state.fornecedor) qs.set('codparc', state.fornecedor);
			if(state.nunota){
				const nun = String(state.nunota).replace(/[^0-9]/g,'').trim();
				if(nun) qs.set('nunota', nun);
			}
			if(state.produto){
				if(/^[0-9]+$/.test(String(state.produto))) qs.set('codprod', state.produto);
				else qs.set('fabricante', state.produto);
			}
			if(state.classificavelFiltro === 'S') qs.set('classificavel', 'S');
			if(state.classificavelFiltro === 'N') qs.set('classificavel', 'N');
			if(state.faturadoFiltro === 'S') qs.set('faturado', 'S');
			if(state.faturadoFiltro === 'N') qs.set('faturado', 'N');
			if(state.semPreco) qs.set('sem_preco', '1');
			const qsString = qs.toString();
			return { qs: qsString, signature: qsString || '__all__', state };
		}

		function extractHeaderKey(header){
			// Retorna a chave textual usada para lembrar o estado de expansão do agrupamento.
			if(!header) return '';
			if(currentViewMode === 'vale'){
				return (header.querySelector('.vale-head-nun')?.textContent || '').trim();
			}
			return (header.querySelector('.vale-head-inner span')?.textContent || '').trim();
		}

		function captureGroupState(){
			// Salva quais cabeçalhos estão expandidos para restaurar após recargas.
			const map = new Map();
			bodyEl.querySelectorAll('tr.vale-header').forEach((header)=>{
				const key = extractHeaderKey(header);
				if(!key) return;
				const expanded = header.getAttribute('data-expanded') !== 'false';
				map.set(key, expanded);
			});
			return map;
		}

		function applyGroupState(stateMap){
			// Reaplica o mapa salvo de expansões/colapsos na tabela renderizada.
			if(!stateMap) return;
			bodyEl.querySelectorAll('tr.vale-header').forEach((header)=>{
				const key = extractHeaderKey(header);
				if(!key) return;
				const expanded = stateMap.has(key) ? stateMap.get(key) : false;
				header.setAttribute('data-expanded', expanded ? 'true' : 'false');
				let row = header.nextElementSibling;
				while(row && !row.classList.contains('vale-header')){
					row.style.display = expanded ? '' : 'none';
					row = row.nextElementSibling;
				}
			});
		}

		function buildListaHTML(rows, mode){
			// Monta o HTML da tabela agrupando por vale ou parceiro, conforme o modo ativo.
			const parts = [];
			if(mode === 'vale'){
				const byNun = new Map();
				rows.forEach((row)=>{
					const key = String(row.nunota || '');
					if(!key) return;
					if(!byNun.has(key)) byNun.set(key, []);
					byNun.get(key).push(row);
				});
				for(const [nunota, group] of byNun.entries()){
					if(!group.length) continue;
					const parceiro = group[0].parceiro || '';
					const dt = fmtDate(group[0].dtneg);
					const classif = group.filter((row)=> window.__isClassificavelItem(row));
					const nclass = group.filter((row)=> window.__isNaoClassificavelItem(row));
					const faturado = group.some((row)=> row && row.nufin);
					const precoZero = group.some((row)=> Number(row.precobase || row.preco_inicial || 0) <= 0);
					const headerClass = faturado ? 'vale-header vale--faturado' : 'vale-header vale--aberto';
					const headerBg = precoZero ? 'background-color:#fee2e2;' : '';
					const nunSafe = escapeHTML(nunota);
					parts.push(`
						<tr class="${headerClass}" data-expanded="true" data-status="${faturado ? 'faturado' : 'aberto'}" data-nunota="${nunSafe}" data-parceiro="${escapeHTML(parceiro)}" style="${headerBg}">
							<td colspan="3" title="${escapeHTML(parceiro)}" style="padding:6px 8px; border-bottom:1px solid #e5e7eb;">
								<span class="vale-head-inner"><span>${escapeHTML(parceiro)}</span></span>
							</td>
							<td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">
								<span class="vale-head-nun">${nunSafe}</span>
								<span>${dt}</span>
							</td>
							<td style="padding:6px 4px; border-bottom:1px solid #e5e7eb; text-align:right;">
								<span class="lista-vale-ico" role="button" tabindex="0" data-nunota="${nunSafe}" title="Resumo do Vale ${nunSafe}">
									<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
										<circle cx="9" cy="21" r="1"></circle>
										<circle cx="20" cy="21" r="1"></circle>
										<path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h7.72a2 2 0 0 0 2-1.61L23 6H6"></path>
									</svg>
								</span>
							</td>
						</tr>
					`);
					const renderValeRow = (row, classificavel)=>{
						const qtyInfo = resolveListaQuantidade(row);
						const unit = qtyInfo.unit ? `<span class="list-unit"> ${qtyInfo.unit}</span>` : '';
						parts.push(`
							<tr data-classificavel="${classificavel ? '1' : '0'}" data-idx="${row._i}">
								<td style="padding:6px 4px; border-bottom:1px solid #e5e7eb;"></td>
								<td colspan="4" title="${escapeHTML(row.produto || '')}" style="padding:6px 8px; border-bottom:1px solid #e5e7eb; font-size:.78rem;">
									<div class="list-prod-inner">
										<span class="list-name">${escapeHTML(row.produto || '')}</span>
										<span class="list-qty">${fmtQty(qtyInfo.value)}${unit}</span>
									</div>
								</td>
							</tr>
						`);
					};
					classif.forEach((row)=> renderValeRow(row, true));
					nclass.forEach((row)=> renderValeRow(row, false));
				}
				return parts.join('');
			}
			const byParc = new Map();
			rows.forEach((row)=>{
				const key = String(row.parceiro || '');
				if(!key) return;
				if(!byParc.has(key)) byParc.set(key, []);
				byParc.get(key).push(row);
			});
			for(const [parceiro, group] of byParc.entries()){
				if(!group.length) continue;
				const dates = Array.from(new Set(group.map((row)=> fmtDate(row.dtneg)))).filter(Boolean);
				const dtCell = dates.length === 1 ? dates[0] : '—';
				const classif = group.filter((row)=> window.__isClassificavelItem(row));
				const nclass = group.filter((row)=> window.__isNaoClassificavelItem(row));
				const allFaturado = group.every((row)=> row && row.nufin);
				const allAberto = group.every((row)=> !row || !row.nufin);
				const precoZero = group.some((row)=> Number(row.precobase || row.preco_inicial || 0) <= 0);
				let headerClass = 'vale-header';
				if(allFaturado) headerClass += ' vale--faturado';
				else if(allAberto) headerClass += ' vale--aberto';
				const status = allFaturado ? 'faturado' : (allAberto ? 'aberto' : 'mixed');
				parts.push(`
					<tr class="${headerClass}" data-expanded="true" data-status="${status}" data-parceiro="${escapeHTML(parceiro)}" style="${precoZero ? 'background-color:#fee2e2;' : ''}">
						<td colspan="3" title="${escapeHTML(parceiro)}" style="padding:6px 8px; border-bottom:1px solid #e5e7eb;">
							<span class="vale-head-inner"><span>${escapeHTML(parceiro)}</span></span>
						</td>
						<td style="padding:6px 8px; border-bottom:1px solid #e5e7eb;">${dtCell}</td>
						<td style="padding:6px 4px; border-bottom:1px solid #e5e7eb; text-align:right;">
							<span class="lista-parc-ico" role="button" tabindex="0" data-parceiro="${escapeHTML(parceiro)}" title="Resumo do Parceiro">
								<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
									<circle cx="9" cy="21" r="1"></circle>
									<circle cx="20" cy="21" r="1"></circle>
									<path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h7.72a2 2 0 0 0 2-1.61L23 6H6"></path>
								</svg>
							</span>
						</td>
					</tr>
				`);
				const renderParcRow = (row, classificavel)=>{
					const qtyInfo = resolveListaQuantidade(row);
					const unit = qtyInfo.unit ? `<span class="list-unit"> ${qtyInfo.unit}</span>` : '';
					const dtRow = fmtDate(row.dtneg) || '—';
					parts.push(`
						<tr data-classificavel="${classificavel ? '1' : '0'}" data-idx="${row._i}">
							<td style="padding:6px 4px; border-bottom:1px solid #e5e7eb;"></td>
							<td title="${escapeHTML(row.produto || '')}" style="padding:6px 8px; border-bottom:1px solid #e5e7eb; font-size:.78rem;">
								<div class="list-prod-inner"><span class="list-name">${escapeHTML(row.produto || '')}</span></div>
							</td>
							<td style="padding:6px 4px; border-bottom:1px solid #e5e7eb;"></td>
							<td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; color:#64748b;">${dtRow}</td>
							<td style="padding:6px 4px; border-bottom:1px solid #e5e7eb; text-align:right;">
								<span class="list-qty">${fmtQty(qtyInfo.value)}${unit}</span>
							</td>
						</tr>
					`);
				};
				classif.forEach((row)=> renderParcRow(row, true));
				nclass.forEach((row)=> renderParcRow(row, false));
			}
			return parts.join('');
		}

		function renderListaRows({ reset = false, preserveScroll = false, preserveState = false, errorMessage = null } = {}){
			// Atualiza o corpo da tabela exibindo linhas, estados e placeholders.
			const prevScroll = listaWrap ? listaWrap.scrollTop : 0;
			const groupState = preserveState ? captureGroupState() : null;
			if(!listaState.rows.length){
				if(listaState.loading) bodyEl.innerHTML = statusRows.loading;
				else if(errorMessage || listaState.error){
					const msg = escapeHTML(errorMessage || listaState.error || 'Falha ao carregar.');
					bodyEl.innerHTML = `<tr class="lista-status lista-error"><td colspan="5" style="padding:8px; color:#b91c1c;">${msg}</td></tr>`;
				}else{
					bodyEl.innerHTML = statusRows.empty;
				}
			}else{
				let html = buildListaHTML(listaState.rows, currentViewMode);
				if(listaState.loading) html += statusRows.loading;
				else if(listaState.finished) html += statusRows.end;
				bodyEl.innerHTML = html;
				if(preserveState && groupState) applyGroupState(groupState);
			}
			window.__COM_LIST_ROWS = listaState.rows;
			table.setAttribute('data-view', currentViewMode);
			if(listaWrap){
				if(reset && !preserveScroll) listaWrap.scrollTop = 0;
				else listaWrap.scrollTop = prevScroll;
			}
		}

		function applyUrlPreselect(rows){
			// Seleciona automaticamente um item da lista quando parâmetros estão na URL.
			try{
				const usp = new URLSearchParams(location.search);
				const sn = Number(usp.get('sel_nunota') || 0);
				const ss = Number(usp.get('sel_seq') || 0);
				if(!(sn && ss)) return;
				const match = rows.find((row)=> Number(row.nunota || 0) === sn && Number(row.sequencia || 0) === ss);
				if(match) applyItemToEntrada(match);
			}catch(err){ logger.warn('URL preselect falhou', err); }
		}

		async function fetchListaPage({ reset = false, preserveScroll = false, preserveState = true, force = false } = {}){
			// Busca uma página de resultados no backend e atualiza o estado da lista.
			if(listaState.loading && !force) return false;
			if(listaState.finished && !reset) return false;
			const token = listaState.currentToken;
			listaState.loading = true;
			listaState.error = null;
			renderListaRows({ reset, preserveScroll, preserveState });
			const parts = [];
			if(listaState.qsBase) parts.push(listaState.qsBase);
			parts.push(`offset=${listaState.offset}`);
			parts.push(`limit=${listaState.limit}`);
			parts.push(`_t=${Date.now()}`);
			const query = parts.filter(Boolean).join('&');
			const url = '/sankhya/comercial/lista/' + (query ? `?${query}` : '');
			try{
				const resp = await fetch(url, {
					credentials: 'same-origin',
					cache: 'no-store',
					headers: { 'Cache-Control': 'no-cache', 'Accept': 'application/json' }
				});
				let payload = {};
				try{ payload = await resp.json(); }catch(_err){ payload = {}; }
				if(token !== listaState.currentToken) return false;
				if(!resp.ok || payload?.ok === false){
					throw new Error(payload?.error || 'Falha ao carregar.');
				}
				const fetched = Array.isArray(payload.rows) ? payload.rows : (Array.isArray(payload.results) ? payload.results : []);
				const baseIndex = listaState.rows.length;
				fetched.forEach((row, idx)=>{ row._i = baseIndex + idx; });
				listaState.rows.push(...fetched);
				listaState.offset = listaState.rows.length;
				listaState.finished = Boolean(payload.finished) || fetched.length < listaState.limit;
				renderListaRows({ reset, preserveScroll, preserveState: true });
				try{ window.dispatchEvent(new CustomEvent('lista:loaded', { detail: { rows: listaState.rows.slice(), finished: listaState.finished } })); }
				catch(_err){ /* noop */ }
				if(!urlPreselectDone && listaState.rows.length){
					applyUrlPreselect(listaState.rows);
					urlPreselectDone = true;
				}
				if(listaWrap && !listaState.finished){
					const remaining = listaWrap.scrollHeight - (listaWrap.scrollTop + listaWrap.clientHeight);
					if(remaining <= 120){
						setTimeout(()=>{ fetchListaPage({ preserveScroll: true, preserveState: true }); }, 40);
					}
				}
				return true;
			}catch(err){
				if(token !== listaState.currentToken) return false;
				logger.error('[Lista] Erro ao carregar', err);
				listaState.error = err?.message || 'Erro ao carregar.';
				renderListaRows({ reset: false, preserveScroll: true, preserveState: true, errorMessage: listaState.error });
				return false;
			}finally{
				listaState.loading = false;
			}
		}

		async function loadLista({ reset = true, filterState, preserveScroll = false, preserveState = false } = {}){
			// Orquestra carregamentos completos da lista aplicando filtros e paginação.
			const { qs, signature } = parseFilters(filterState);
			const mustReset = reset || signature !== listaState.signature;
			if(mustReset){
				listaState.signature = signature;
				listaState.qsBase = qs;
				listaState.offset = 0;
				listaState.rows = [];
				listaState.finished = false;
				listaState.loading = false;
				listaState.error = null;
				listaState.currentToken = ++listaTokenSeq;
				urlPreselectDone = false;
				window.__COM_LIST_ROWS = listaState.rows;
			}
			return fetchListaPage({
				reset: mustReset,
				preserveScroll,
				preserveState: mustReset ? preserveState : true
			});
		}

		function updateViewMode(mode){
			// Alterna entre a visão por vale ou por parceiro e re-renderiza a tabela.
			const next = mode === 'parceiro' ? 'parceiro' : 'vale';
			if(next === currentViewMode) return;
			currentViewMode = next;
			safeStorageSet(VIEW_STORAGE_KEY, currentViewMode);
			table.setAttribute('data-view', currentViewMode);
			renderListaRows({ preserveState: true, preserveScroll: true });
		}

		function collapseAllGrupos(){
			// Fecha todos os agrupamentos da lista para facilitar a varredura rápida.
			bodyEl.querySelectorAll('tr.vale-header').forEach((header)=>{
				header.setAttribute('data-expanded', 'false');
				let row = header.nextElementSibling;
				while(row && !row.classList.contains('vale-header')){
					row.style.display = 'none';
					row = row.nextElementSibling;
				}
			});
		}

		function expandAllGrupos(){
			// Expande novamente todos os grupos quando o usuário deseja ver tudo.
			bodyEl.querySelectorAll('tr.vale-header').forEach((header)=>{
				header.setAttribute('data-expanded', 'true');
				let row = header.nextElementSibling;
				while(row && !row.classList.contains('vale-header')){
					row.style.display = '';
					row = row.nextElementSibling;
				}
			});
		}

		function toggleGroup(header){
			// Inverte o estado (aberto/fechado) de um grupo específico.
			const expanded = header.getAttribute('data-expanded') !== 'false';
			header.setAttribute('data-expanded', expanded ? 'false' : 'true');
			let row = header.nextElementSibling;
			while(row && !row.classList.contains('vale-header')){
				row.style.display = expanded ? 'none' : '';
				row = row.nextElementSibling;
			}
		}

		function selectRow(rowEl){
			// Destaca visualmente a linha selecionada para indicar o item em foco.
			bodyEl.querySelectorAll('tr.row--sel').forEach((node)=> node.classList.remove('row--sel'));
			if(rowEl) rowEl.classList.add('row--sel');
		}

		function handleBodyClick(ev){
			// Gerencia cliques dentro da tabela, abrindo modais ou aplicando itens.
			const valeBtn = ev.target.closest('.lista-vale-ico');
			if(valeBtn){
				const nunota = valeBtn.getAttribute('data-nunota');
				if(nunota && typeof window.openValeResumo === 'function'){
					window.openValeResumo(nunota, { forceReload: true });
				}
				ev.stopPropagation();
				return;
			}
			const parcBtn = ev.target.closest('.lista-parc-ico');
			if(parcBtn){
				const parceiro = parcBtn.getAttribute('data-parceiro');
				if(parceiro) openParceiroResumo(parceiro);
				ev.stopPropagation();
				return;
			}
			const header = ev.target.closest('tr.vale-header');
			if(header){
				// Ao interagir com o cabeçalho limpamos o dashboard para evitar dados obsoletos.
				const dash = window.__PH_DASHBOARD__;
				if(dash && typeof dash.clearDashboard === 'function'){
					dash.clearDashboard({ reason: 'lista:header-click' });
				}
				// Também removemos qualquer linha marcada, pois o contexto deixou de ser válido.
				selectRow(null);
				toggleGroup(header);
				return;
			}
			const row = ev.target.closest('tr[data-idx]');
			if(!row) return;
			selectRow(row);
			const idx = row.getAttribute('data-idx');
			const item = listaState.rows.find((r)=> String(r._i) === String(idx));
			if(item) applyItemToEntrada(item);
		}

		function handleBodyKeydown(ev){
			// Permite acessar atalhos de ícones da lista via teclado.
			const ico = ev.target.closest('.lista-vale-ico, .lista-parc-ico');
			if(!ico) return;
			if(ev.key !== 'Enter' && ev.key !== ' ' && ev.key !== 'Spacebar') return;
			ev.preventDefault();
			if(ico.classList.contains('lista-vale-ico')){
				const nunota = ico.getAttribute('data-nunota');
				if(nunota && typeof window.openValeResumo === 'function'){
					window.openValeResumo(nunota, { forceReload: true });
				}
			}else if(ico.classList.contains('lista-parc-ico')){
				const parceiro = ico.getAttribute('data-parceiro');
				if(parceiro) openParceiroResumo(parceiro);
			}
		}

		function handleScroll(){
			// Dispara carregamento infinito quando o usuário se aproxima do final.
			if(!listaWrap || listaState.loading || listaState.finished) return;
			const remaining = listaWrap.scrollHeight - (listaWrap.scrollTop + listaWrap.clientHeight);
			if(remaining <= 160){
				fetchListaPage({ preserveScroll: true, preserveState: true });
			}
		}

		function handleFiltersChange(ev){
			// Reage às mudanças nos filtros sincronizando o estado global e recarregando.
			const state = ev?.detail || null;
			if(state) window.__COM_FILTER_STATE = state;
			const dash = window.__PH_DASHBOARD__;
			if(dash && typeof dash.reloadDashboard === 'function'){
				try{
					if(typeof dash.clearDashboard === 'function'){
						dash.clearDashboard({ reason: 'filters' });
					}
				}catch(err){
					logger.warn('Falha ao limpar dashboard antes do filtro', err);
				}
				dash.reloadDashboard({ scope: ['lista'], filterState: state, force: true, reason: 'filters' }).catch((error)=> logger.error('Recarregar lista após filtros falhou', error));
				return;
			}
			loadLista({ reset: true, filterState: state, preserveScroll: false, preserveState: false }).catch((error)=> logger.error('Recarregar lista após filtros falhou', error));
		}

		function setText(id, value){
			// Atualiza elementos do cabeçalho de entrada com fallback seguro.
			const el = doc.getElementById(id);
			if(el) el.textContent = value || '—';
		}

		const valeDistribSummaryCache = new Map();
		let valeSummaryFetchSeq = 0;
		const VALE_VALUE_FIELDS = Object.freeze(['vlrtot','VLRTOT','vlrtot_banco','VLRNOTA','vlrnota_cab','VLRNOTA_CAB','vlrtot_total','VLRTOT_TOTAL','valor_total','VALOR_TOTAL','total','TOTAL','vlrliq','VLRLIQ']);
		const VALE_KG_FIELDS = Object.freeze(['qtdneg','QTDNEG','qtdneg_base','QTDNEG_BASE','qtd','QTD','kg','KG','peso','PESO']);
		const VALE_CX_FIELDS = Object.freeze(['qtdcx','QTDCX','qtdcx_base','QTDCX_BASE','qtd','QTD']);

		function normalizeNunotaValue(value){
			if(value === null || value === undefined) return '';
			const digits = String(value).replace(/[^0-9]/g, '');
			return digits.replace(/^0+/, '') || '';
		}

		function pickFirstPositiveFromRow(row, fields){
			if(!row || !Array.isArray(fields)) return NaN;
			for(const field of fields){
				const raw = row[field];
				const num = toNumberSafe(raw);
				if(Number.isFinite(num) && num > 0){
					return num;
				}
			}
			return NaN;
		}

		function detectValeBucket(row, codes){
			const codprod = toNumberSafe(row?.codprod ?? row?.CODPROD);
			if(Number.isFinite(codprod) && codprod > 0){
				if(Number(codes?.extra) > 0 && codprod === Number(codes.extra)) return 'extra';
				if(Number(codes?.medio) > 0 && codprod === Number(codes.medio)) return 'medio';
			}
			const produto = String(row?.produto || row?.descr || '').toUpperCase();
			if(produto.includes('EXTRA')) return 'extra';
			if(produto.includes('MEDIO') || produto.includes('MÉDIO') || produto.includes('MÉDIA') || produto.includes('MEDIA')) return 'medio';
			return null;
		}

		function buildValeSummary(rows, codes){
			const summary = {
				hasItems: false,
				extra: { total: 0, kg: 0, cx: 0 },
				medio: { total: 0, kg: 0, cx: 0 }
			};
			if(!Array.isArray(rows) || !rows.length) return summary;
			rows.forEach((row)=>{
				const bucket = detectValeBucket(row, codes);
				if(!bucket) return;
				const total = pickFirstPositiveFromRow(row, VALE_VALUE_FIELDS);
				if(!(total > 0)) return;
				summary[bucket].total += total;
				const kg = pickFirstPositiveFromRow(row, VALE_KG_FIELDS);
				if(kg > 0) summary[bucket].kg += kg;
				const cx = pickFirstPositiveFromRow(row, VALE_CX_FIELDS);
				if(cx > 0) summary[bucket].cx += cx;
				summary.hasItems = true;
			});
			return summary;
		}

		function applyValeSummaryToState(summary){
			const distState = window.__DIST_EXTRA_MEDIO_STATE;
			if(!distState) return;
			const overrideActive = distState.forceSimTotals === true;
			if(!overrideActive){
				distState.forceSimTotals = false;
				distState.lastSimTotal = 0;
			}
			const extraTotal = Number(summary?.extra?.total) || 0;
			const medioTotal = Number(summary?.medio?.total) || 0;
			const hasVale = Boolean(summary?.hasItems && (extraTotal > 0 || medioTotal > 0));
			distState.hasVale = hasVale;
			if(!hasVale){
				distState.extraCustoTotal = 0;
				distState.medioCustoTotal = 0;
				if(typeof window.__applyExtraMedioResultado === 'function'){
					window.__applyExtraMedioResultado();
				}
				return;
			}
			const applyBucket = (bucketName, bucketSummary)=>{
				if(!bucketSummary) return;
				const total = Number(bucketSummary.total) || 0;
				if(!(total > 0)) return;
				const cxKey = `${bucketName}Cx`;
				const kgKey = `${bucketName}Kg`;
				const totalKey = `${bucketName}CustoTotal`;
				const cxCostKey = `${bucketName}CustoCx`;
				const kgCostKey = `${bucketName}CustoKg`;
				const qtyCx = Number(distState[cxKey]) > 0 ? Number(distState[cxKey]) : Number(bucketSummary.cx) || 0;
				const qtyKg = Number(distState[kgKey]) > 0 ? Number(distState[kgKey]) : Number(bucketSummary.kg) || 0;
				distState[totalKey] = total;
				distState[cxCostKey] = qtyCx > 0 ? (total / qtyCx) : distState.precoBase;
				const pesoPorCx = (qtyKg > 0 && qtyCx > 0) ? (qtyKg / qtyCx) : 0;
				distState[kgCostKey] = qtyKg > 0
					? (total / qtyKg)
					: (pesoPorCx > 0 ? distState[cxCostKey] / pesoPorCx : 0);
			};
			applyBucket('extra', summary.extra);
			applyBucket('medio', summary.medio);
			if(typeof window.__applyExtraMedioResultado === 'function'){
				window.__applyExtraMedioResultado();
			}
		}

		function syncValeTotalsFromTop13(item){
			const distState = window.__DIST_EXTRA_MEDIO_STATE;
			if(!distState) return;
			const nunotaVale = normalizeNunotaValue(item?.nunota_13 || item?.nunotaVale || '');
			if(!nunotaVale){
				distState.hasVale = false;
				distState.forceSimTotals = false;
				distState.lastSimTotal = 0;
				if(typeof window.__applyExtraMedioResultado === 'function'){
					window.__applyExtraMedioResultado();
				}
				return;
			}
			if(valeDistribSummaryCache.has(nunotaVale)){
				applyValeSummaryToState(valeDistribSummaryCache.get(nunotaVale));
				return;
			}
			const fetchSeq = ++valeSummaryFetchSeq;
			const endpoint = `/sankhya/comercial/api/itens_vale/?nunota=${encodeURIComponent(nunotaVale)}&limit=all&_=${Date.now()}`;
			fetch(endpoint, { credentials: 'same-origin' })
				.then((resp)=>{
					if(!resp.ok) throw new Error(`Falha ao consultar itens do vale (${resp.status})`);
					return resp.json();
				})
				.then((data)=>{
					const items = Array.isArray(data?.items) ? data.items : [];
					const summary = buildValeSummary(items, {
						extra: Number(distState.extraCodprod) || null,
						medio: Number(distState.medioCodprod) || null
					});
					valeDistribSummaryCache.set(nunotaVale, summary);
					if(fetchSeq !== valeSummaryFetchSeq) return;
					applyValeSummaryToState(summary);
				})
				.catch((err)=>{
					logger.warn('Não foi possível carregar produtos do Vale', err);
				});
		}

		window.__invalidateValeDistribCache = (nunota)=>{
			if(!nunota){
				valeDistribSummaryCache.clear();
				return;
			}
			const key = normalizeNunotaValue(nunota);
			if(key) valeDistribSummaryCache.delete(key);
		};

		function applyItemToEntrada(item){
			// Replica os dados do item selecionado nos cards de entrada e dispara refresh.
			try{
				if(!item) return;
				const parseSimField = (...keys)=>{
					for(const key of keys){
						const num = toNumberSafe(item?.[key]);
						if(Number.isFinite(num)) return num;
					}
					return NaN;
				};
				const simSnapshot = {
					extraCx: parseSimField('ad_simqtd1','AD_SIMQTD1'),
					extraTotal: parseSimField('ad_simvlr1','AD_SIMVLR1'),
					medioCx: parseSimField('ad_simqtd2','AD_SIMQTD2'),
					medioTotal: parseSimField('ad_simvlr2','AD_SIMVLR2'),
					quebra: parseSimField('ad_simqtddesc','AD_SIMQTDDESC')
				};
				const resetExtraMedioState = ()=>{
					const distState = window.__DIST_EXTRA_MEDIO_STATE;
					if(!distState) return;
					['extraCx','extraKg','extraCustoCx','extraCustoKg','extraCustoTotal','medioCx','medioKg','medioCustoCx','medioCustoKg','medioCustoTotal']
						.forEach((key)=>{ distState[key] = 0; });
					distState.valorEntrada = 0;
					distState.hasVale = false;
					distState.forceSimTotals = false;
					distState.lastSimTotal = 0;
				};
				const applyExtraMedioSeed = ({ qtyCx, totalValue, unitPrice, hasVale = false })=>{
					const distState = window.__DIST_EXTRA_MEDIO_STATE;
					if(!distState) return;
					distState.codprod = Number(item?.codprod || item?.CODPROD || 0) || null;
					distState.sequencia = Number(item?.sequencia || item?.SEQUENCIA || 0) || null;
					distState.qtdCxInNatura = Number.isFinite(qtyCx) && qtyCx > 0 ? qtyCx : 0;
					distState.precoBase = Number(unitPrice) > 0 ? Number(unitPrice) : 0;
					distState.valorEntrada = Number(totalValue) || 0;
					distState.hasVale = Boolean(hasVale);
					if(distState.hasVale){
						distState.forceSimTotals = false;
						distState.lastSimTotal = 0;
					}
					const extraTotal = Number.isFinite(simSnapshot.extraTotal) && simSnapshot.extraTotal > 0 ? simSnapshot.extraTotal : 0;
					const medioTotal = Number.isFinite(simSnapshot.medioTotal) && simSnapshot.medioTotal > 0 ? simSnapshot.medioTotal : 0;
					const allowSnapshotTotals = distState.hasVale;
					distState.extraCustoTotal = allowSnapshotTotals ? extraTotal : 0;
					distState.medioCustoTotal = allowSnapshotTotals ? medioTotal : 0;
					if(extraTotal > 0 && Number.isFinite(simSnapshot.extraCx) && simSnapshot.extraCx > 0){
						distState.extraCustoCx = extraTotal / simSnapshot.extraCx;
					}else{
						distState.extraCustoCx = distState.precoBase;
					}
					if(medioTotal > 0 && Number.isFinite(simSnapshot.medioCx) && simSnapshot.medioCx > 0){
						distState.medioCustoCx = medioTotal / simSnapshot.medioCx;
					}else{
						distState.medioCustoCx = distState.extraCustoCx > 0 ? distState.extraCustoCx / 2 : 0;
					}
					distState.extraCustoKg = 0;
					distState.medioCustoKg = 0;
					try{ if(typeof window.updateExtraCard === 'function') window.updateExtraCard(); }
					catch(err){ logger.debug('Falha ao atualizar card Extra', err); }
					try{ if(typeof window.updateMedioCard === 'function') window.updateMedioCard(); }
					catch(err){ logger.debug('Falha ao atualizar card Médio', err); }
				};
				resetExtraMedioState();
				window.__CURRENT_VALE_NUNOTA = item.nunota || null;
				const dash = window.__PH_DASHBOARD__;
				const nunota = item.nunota ? String(item.nunota) : '';
				const sequencia = item.sequencia ? String(item.sequencia) : '';
				const lote = item.codagregacao || item.lote || '';
				const codprod = item.codprod || '';
				const selectionKey = [nunota, sequencia].filter(Boolean).join('#') || nunota || '';
				const previousKey = doc.body?.dataset?.entradaKey || '';
				if(selectionKey && selectionKey !== previousKey){
					// Antes de carregar um novo pedido, limpamos o dashboard para evitar resíduos visuais.
					if(dash && typeof dash.clearDashboard === 'function'){
						dash.clearDashboard({ reason: 'lista:item-select' });
					}else{
						logger.warn('Dashboard shell indisponível para limpeza inicial.');
					}
				}
				if(doc.body){
					doc.body.dataset.entradaKey = selectionKey;
					if(nunota) doc.body.dataset.nunota = nunota;
					else delete doc.body.dataset.nunota;
				}
				const qtyInfo = resolveListaQuantidade(item);
				const pesoUnit = pickFirstPositive(
					item.__peso_unitario_resolvido,
					item.peso_unitario_resolvido,
					item.peso_unitario,
					item.peso,
					item.kg_por_cx,
					item.fator_conversao
				);
				const totalKg = pickFirstPositive(
					item.qtdneg_base,
					item.__raw_qtdneg_base,
					item.qtdneg,
					(pesoUnit > 0 && qtyInfo.value > 0) ? pesoUnit * qtyInfo.value : NaN
				);
				const qtyValue = Number.isFinite(qtyInfo.value) ? qtyInfo.value : 0;
				const resolvedTotalKg = Number.isFinite(totalKg)
					? totalKg
					: ((pesoUnit > 0 && qtyValue > 0) ? pesoUnit * qtyValue : NaN);
				const resolvedPesoPorCx = (pesoUnit > 0)
					? pesoUnit
					: ((qtyValue > 0 && Number.isFinite(resolvedTotalKg)) ? (resolvedTotalKg / qtyValue) : NaN);
				const qtyCard = doc.getElementById('quantidadeInnCard');
				const entradaCard = doc.getElementById('entradaCard');
				// Pequena função utilitária para reaproveitar parsing numérico tolerante.
				const resolveFirstFinite = (...values)=>{
					for(const value of values){
						const num = toNumberSafe(value);
						if(Number.isFinite(num)) return num;
					}
					return null;
				};
				[qtyCard, entradaCard].forEach((el)=>{
					if(!el) return;
					el.dataset.nunota = nunota;
					el.dataset.seq = sequencia;
					el.dataset.codprod = codprod;
					if(lote) el.dataset.lote = lote;
					el.dataset.cx = qtyValue > 0 ? String(qtyValue) : '';
					el.dataset.kgIn = Number.isFinite(resolvedTotalKg) ? String(resolvedTotalKg) : '';
					el.dataset.unit = qtyInfo.unit || '';
					el.dataset.pesoPorCx = Number.isFinite(resolvedPesoPorCx) ? String(resolvedPesoPorCx) : '';
				});
				setText('supplierName', item.parceiro || '—');
				setText('entProduct', item.produto || '—');
				setText('entPartner', item.parceiro || '—');
				const badgePedido = doc.getElementById('entBadgePedido');
				if(badgePedido) badgePedido.textContent = nunota ? `Pedido ${nunota}` : 'Pedido —';
				const badgeTipo = doc.getElementById('entBadgeTipo');
				if(badgeTipo) badgeTipo.textContent = fmtDate(item.dtneg) || '—';
				const badgeVale = doc.getElementById('entBadgeVale13');
				if(badgeVale){
					const nunota13 = item.nunota_13 || item.nunotaVale || '';
					badgeVale.textContent = nunota13 ? `Vale ${nunota13}` : '';
					badgeVale.style.display = nunota13 ? '' : 'none';
				}
				const qtyEl = doc.getElementById('quantidadeInn');
				if(qtyEl) qtyEl.textContent = fmtQty(qtyInfo.value);
				const unitEl = doc.querySelector('#quantidadeInnCard .headline .unit');
				if(unitEl) unitEl.textContent = qtyInfo.unit || '';
				const pesoUnitEl = doc.getElementById('pesoInnDisplay');
				if(pesoUnitEl){
					const pesoDisplay = Number.isFinite(resolvedPesoPorCx) ? resolvedPesoPorCx : pesoUnit;
					pesoUnitEl.textContent = pesoDisplay > 0 ? fmtQty(pesoDisplay) : '—';
				}
				const totalKgEl = doc.getElementById('totalInn');
				if(totalKgEl){
					const displayKg = Number.isFinite(resolvedTotalKg) ? resolvedTotalKg : 0;
					totalKgEl.textContent = displayKg > 0 ? fmtQty(displayKg) : '—';
				}
				// Atualiza o peso classificado (QTDCONFERIDA) quando disponível para manter o card coerente.
				const pesoClassificadoVal = resolveFirstFinite(
					item.qtdconferida,
					item.QTDCONFERIDA,
					item.__raw_qtdconferida
				);
				const pesoClassificadoDisplay = doc.getElementById('pesoClassificadoDisplay');
				if(pesoClassificadoDisplay){
					pesoClassificadoDisplay.textContent = Number.isFinite(pesoClassificadoVal) ? fmtQty(pesoClassificadoVal) : '—';
				}
				const pesoClassificadoInput = doc.getElementById('pesoClassificadoInput');
				if(pesoClassificadoInput){
					pesoClassificadoInput.value = Number.isFinite(pesoClassificadoVal)
						? pesoClassificadoVal.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
						: '';
				}
				// Preenche o campo R$/CX utilizando VLRUNIT (ou equivalentes) para exibir o preço atual.
				const precoCxDisplay = doc.getElementById('entPrecoCxDisplay');
				let precoCxFonte = null;
				if(precoCxDisplay){
					precoCxFonte = resolveFirstFinite(
						item.precobase,
						item.PRECOBASE,
						item.preco_inicial,
						item.vlrunit,
						item.VLRUNIT
					);
					const precoFormatter = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
					precoCxDisplay.textContent = Number.isFinite(precoCxFonte) ? precoFormatter.format(precoCxFonte) : '0,00';
					const precoUnitLabel = precoCxDisplay.nextElementSibling;
					if(precoUnitLabel?.classList?.contains('unit')){
						precoUnitLabel.textContent = qtyInfo.unit ? `/${qtyInfo.unit}` : '';
					}
					if(entradaCard){
						entradaCard.dataset.vlrunit = Number.isFinite(precoCxFonte) ? String(precoCxFonte) : '';
					}
				}
				// Calcula o valor total do item (VLRTOT) e exibe em "Valor Total".
				const totalValorDisplay = doc.getElementById('entTotalIn');
				const vlrtotFonte = resolveFirstFinite(item.vlrtot, item.VLRTOT, item.vlrnota_cab, item.VLRNOTA_CAB);
				const valorTotalRes = Number.isFinite(vlrtotFonte)
					? vlrtotFonte
					: (Number.isFinite(precoCxFonte) && Number.isFinite(qtyInfo.value) ? precoCxFonte * qtyInfo.value : null);
				if(totalValorDisplay){
					const moneyFmt = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
					totalValorDisplay.textContent = Number.isFinite(valorTotalRes) ? moneyFmt.format(valorTotalRes) : '0,00';
					if(entradaCard){
						entradaCard.dataset.vlrtot = Number.isFinite(valorTotalRes) ? String(valorTotalRes) : '';
					}
				}
				const distribTotal = Number.isFinite(valorTotalRes) ? valorTotalRes : 0;
				window.__SAVED_VLRTOT = distribTotal;
				window.__SAVED_VLRUNIT = Number.isFinite(precoCxFonte) ? precoCxFonte : 0;
				applyExtraMedioSeed({ qtyCx: qtyValue, totalValue: distribTotal, unitPrice: precoCxFonte });
				syncValeTotalsFromTop13(item);
				if(typeof window.__setDistribTotal === 'function'){
					try{ window.__setDistribTotal(distribTotal, { source: 'item-select', allowUI: true, syncInput: true }); }
					catch(err){ logger.debug('Falha ao sincronizar total de distribuição', err); }
				}
				if(typeof window.__updateToggleFromPendenteClass === 'function'){
					setTimeout(()=>{
						try{ window.__updateToggleFromPendenteClass(); }
						catch(err){ logger.debug('Falha ao sinalizar pendência da classificação', err); }
					}, 120);
				}
				// O campo R$/kg deriva de VLRTOT/QTDNEG (ou equivalentes) para manter coerência com TGFITE.
				const precoKgDisplay = doc.getElementById('entPrecoKg');
				const qtdNegKg = resolveFirstFinite(
					item.qtdneg_base,
					item.__raw_qtdneg_base,
					item.qtdneg,
					item.QTDNEG
				);
				if(precoKgDisplay){
					const precoKgVal = Number.isFinite(valorTotalRes) && Number.isFinite(qtdNegKg) && qtdNegKg > 0
						? valorTotalRes / qtdNegKg
						: null;
					const precoFormatter = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
					precoKgDisplay.textContent = Number.isFinite(precoKgVal) ? precoFormatter.format(precoKgVal) : '0,00';
					if(entradaCard){
						entradaCard.dataset.vlrkg = Number.isFinite(precoKgVal) ? String(precoKgVal) : '';
					}
				}
				if(lote){
					doc.body.dataset.lote = lote;
					const badge = doc.getElementById('classLoteBadge');
					if(badge){
						badge.textContent = lote;
						badge.title = `Lote ${lote}`;
						badge.dataset.lote = lote;
					}
					if(dash && typeof dash.reloadDashboard === 'function'){
						// Atualizamos apenas classificação/ distribuição; o modal do vale abre somente via ícone dedicado.
						dash.reloadDashboard({ scope: ['classificacao','distribuicao'], lote, nunota, reason: 'lista:item-select' }).catch((err)=> logger.error('[Lista] Refresh pós seleção falhou', err));
					}else if(dash && typeof dash.reloadClassificacao === 'function'){
						dash.reloadClassificacao(lote);
					}
				}
				if(typeof window.__initEntradaEditors === 'function'){
					// Reaproveita o mesmo binding para manter os campos editáveis após cada seleção.
					window.__initEntradaEditors();
				}
				if(typeof window.__applyEntradaLockState === 'function'){
					// Seleção na lista sempre libera edição; o bloqueio será reativado apenas via vale faturado.
					window.__applyEntradaLockState(false);
				}
				if(typeof window.__applySimulacaoFromItem === 'function'){
					// Atualiza o card de simulação com os campos persistidos na TOP 11.
					window.__applySimulacaoFromItem(item);
				}
				window.dispatchEvent(new CustomEvent('entrada:update', { detail: { item } }));
			}catch(err){
				logger.error('[Lista] applyItemToEntrada falhou', err);
			}
		}

		function applyValeToEntrada(nunota){
			// Seleciona automaticamente o primeiro item de um vale específico.
			const rows = listaState.rows.filter((row)=> String(row.nunota || '') === String(nunota || ''));
			if(!rows.length) return;
			applyItemToEntrada(rows[0]);
		}

		function openParceiroResumo(parceiro){
			// Monta e exibe o modal com resumo financeiro do parceiro escolhido.
			const modal = doc.getElementById('parceiroResumoModal');
			const title = doc.getElementById('parceiroResumoTitle');
			const classBody = doc.getElementById('parceiroClassBody');
			const outrosBody = doc.getElementById('parceiroOutrosBody');
			const totalEl = doc.getElementById('parceiroResumoTotal');
			if(!modal || !title || !classBody || !outrosBody || !totalEl) return;
			const rows = listaState.rows.filter((row)=> String(row.parceiro || '') === String(parceiro || ''));
			title.textContent = parceiro ? `Parceiro — ${parceiro}` : 'Parceiro';
			if(!rows.length){
				const emptyHtml = '<tr><td colspan="3" style="padding:8px; color:#64748b;">Sem itens.</td></tr>';
				classBody.innerHTML = emptyHtml;
				outrosBody.innerHTML = emptyHtml;
				totalEl.textContent = moneyPt.format(0);
				modal.style.display = 'flex';
				modal.addEventListener('click', (ev)=>{ if(ev.target === modal) modal.style.display = 'none'; }, { once: true });
				return;
			}
			const classificaveis = rows.filter((row)=> window.__isClassificavelItem(row));
			const naoClassificaveis = rows.filter((row)=> !window.__isClassificavelItem(row));
			classBody.innerHTML = classificaveis.length ? classificaveis.map((row)=>{
				const qty = resolveListaQuantidade(row);
				return `<tr>
					<td style="padding:6px 8px; border-bottom:1px solid #e5e7eb;">${escapeHTML(row.produto || '')}</td>
					<td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${fmtQty(qty.value)}${qty.unit ? `<span style='color:#94a3b8; font-size:.7rem; margin-left:4px;'>${qty.unit}</span>` : ''}</td>
					<td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${moneyPt.format(Number(row.precobase || row.preco_inicial || 0) || 0)}</td>
				</tr>`;
			}).join('') : '<tr><td colspan="3" style="padding:8px; color:#64748b;">—</td></tr>';
			outrosBody.innerHTML = naoClassificaveis.length ? naoClassificaveis.map((row)=>{
				const qty = resolveListaQuantidade(row);
				const vlr = Number(row.vlrunit || row.preco_inicial || 0) || 0;
				return `<tr>
					<td style="padding:6px 8px; border-bottom:1px solid #e5e7eb;">${escapeHTML(row.produto || '')}</td>
					<td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${fmtQty(qty.value)}${qty.unit ? `<span style='color:#94a3b8; font-size:.7rem; margin-left:4px;'>${qty.unit}</span>` : ''}</td>
					<td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${vlr > 0 ? moneyPt.format(vlr) : '—'}</td>
				</tr>`;
			}).join('') : '<tr><td colspan="3" style="padding:8px; color:#64748b;">—</td></tr>';
			const total = rows.reduce((sum, row)=> sum + (Number(row.vlrtot || 0) || 0), 0);
			totalEl.textContent = moneyPt.format(total);
			modal.style.display = 'flex';
			modal.addEventListener('click', (ev)=>{ if(ev.target === modal) modal.style.display = 'none'; }, { once: true });
		}

		function bindViewToggle(){
			// Liga o controle de segmentação para alternar entre visões da tabela.
			if(!viewToggle) return;
			updateViewToggleA11y();
			viewToggle.addEventListener('change', (ev)=>{
				const input = ev.target.closest('input[name="listaViewMode"]');
				if(!input) return;
				updateViewMode(input.value);
				updateViewToggleA11y();
			});
		}

		function updateViewToggleA11y(){
			// Ajusta atributos ARIA do toggle para refletir a seleção atual.
			if(!viewToggle) return;
			Array.from(viewToggle.querySelectorAll('.seg')).forEach((seg)=>{
				const input = seg.querySelector('input[name="listaViewMode"]');
				seg.setAttribute('aria-selected', input && input.checked ? 'true' : 'false');
			});
		}

		function bindGroupButtons(){
			// Conecta os botões de expandir/contrair todos os grupos.
			collapseBtn?.addEventListener('click', (ev)=>{ ev.preventDefault(); collapseAllGrupos(); });
			expandBtn?.addEventListener('click', (ev)=>{ ev.preventDefault(); expandAllGrupos(); });
		}

		function init(){
			// Inicializa o módulo Lista, liga eventos e busca os primeiros dados.
			table.setAttribute('data-view', currentViewMode);
			if(viewToggle){
				const checked = viewToggle.querySelector(`input[value="${currentViewMode}"]`);
				if(checked) checked.checked = true;
			}
			bindViewToggle();
			bindGroupButtons();
			bodyEl.addEventListener('click', handleBodyClick);
			bodyEl.addEventListener('keydown', handleBodyKeydown);
			listaWrap?.addEventListener('scroll', handleScroll, { passive: true });
			window.addEventListener('filtros:change', handleFiltersChange);
			const dash = window.__PH_DASHBOARD__;
			if(dash && typeof dash.reloadDashboard === 'function'){
				dash.reloadDashboard({ scope: ['lista'], reason: 'initial' }).catch((err)=> logger.error('Lista inicial falhou', err));
			}else{
				loadLista({ reset: true, filterState: window.__COM_FILTER_STATE, preserveState: false }).catch((err)=> logger.error('Lista inicial falhou', err));
			}
		}

		function destroy(){
			// Remove listeners do módulo quando a lista precisar ser desmontada.
			bodyEl.removeEventListener('click', handleBodyClick);
			bodyEl.removeEventListener('keydown', handleBodyKeydown);
			listaWrap?.removeEventListener('scroll', handleScroll);
			window.removeEventListener('filtros:change', handleFiltersChange);
		}

		window.applyItemToEntrada = applyItemToEntrada;
		window.applyValeToEntrada = applyValeToEntrada;
		window.openParceiroResumo = openParceiroResumo;
		window.loadLista = loadLista;
		init();

		return {
			state: listaState,
			reload: loadLista,
			destroy
		};
	});

	/**
	 * Módulo: Portal básico (scroll/lista). Placeholder para migração futura.
	 */
	/**
	 * Módulo: Vale shell. Centraliza carregamento do modal de faturamento.
	 */
	registerModule('valeShell', (ctx)=>{
		const modal = doc.getElementById('modalFaturamento');
		if(!modal) return null; // Nada para fazer se o modal não estiver presente.
		const spinner = doc.getElementById('loadingSpinner');
		const { http } = ctx.services;
		const { formatMoney, formatDecimal, normalizeNunota, toast } = ctx.utils;
		const logger = ctx.logger || console;
		const events = ctx.events || null;
		window.__CURRENT_VALE_LOCKED = window.__CURRENT_VALE_LOCKED || false;

		const state = {
			cache: {
				pedido: new Map(),
				vale: new Map()
			},
			current: {
				nunota: null,
				nunotaVale: null,
				rows: [],
				classRows: [],
				outrosRows: []
			},
			pending: false,
			dom: {
				modal,
				spinner,
				title: doc.getElementById('valeResumoTitle'),
				classBody: doc.getElementById('valeClassBody'),
				outrosBody: doc.getElementById('valeOutrosBody'),
				total: doc.getElementById('valeResumoTotal'),
				bruto: doc.getElementById('valeResumoTotalBruto'),
				inss: doc.getElementById('valeResumoINSS'),
				pedidoWrap: doc.getElementById('valeResumoPedido'),
				pedidoNum: doc.getElementById('valeResumoPedidoNum'),
				valeWrap: doc.getElementById('valeResumoVale'),
				valeNum: doc.getElementById('valeResumoValeNum'),
				obsButton: doc.getElementById('valeResumoObsBtn'),
				obsModal: doc.getElementById('valeObservacaoModal'),
				obsInput: doc.getElementById('valeObservacaoInput'),
				obsSave: doc.getElementById('valeObservacaoSave'),
				obsCancel: doc.getElementById('valeObservacaoCancel') || doc.querySelector('#valeObservacaoModal [data-close]'),
				obsIdent: doc.getElementById('valeObservacaoIdent'),
				checkboxINSS: doc.getElementById('valeDescontaINSS'),
				btnFaturar: doc.getElementById('valeResumoFaturar'),
				btnDesfaturar: doc.getElementById('valeResumoDesfaturar'),
				nufinBadge: doc.getElementById('valeResumoNufinBadge'),
				nufinNum: doc.getElementById('valeResumoNufinNum'),
				marcaDagua: doc.getElementById('modalMarcaDagua'),
				statusBanner: doc.getElementById('valeResumoStatusBanner')
			}
		};

		const MAX_DECIMALS = 2;
		const deepClone = (value)=>{
			try{
				return structuredClone(value);
			}catch(_err){
				try{ return JSON.parse(JSON.stringify(value)); }catch(__){ return value; }
			}
		};
		const parseLocaleNumber = (value)=>{
			if(typeof value === 'number') return Number.isFinite(value) ? value : 0;
			if(value == null) return 0;
			const cleaned = String(value)
				.replace(/[^0-9,\.\-]/g, '')
				.replace(/\.(?=\d{3}(\D|$))/g, '')
				.replace(',', '.');
			const num = Number(cleaned);
			return Number.isFinite(num) ? num : 0;
		};
		const formatQty = (value)=>{
			const num = Number(value);
			if(!Number.isFinite(num)) return '0';
			try{
				return num.toLocaleString('pt-BR', { maximumFractionDigits: MAX_DECIMALS });
			}catch(_err){
				return num.toFixed(MAX_DECIMALS).replace('.', ',');
			}
		};

		window.__CURRENT_VALE_NUNOTA = null;
		window.__CURRENT_VALE_NUNOTA_TOP13 = null;
		window.__CURRENT_VALE_OBSERVACAO = '';
		window.__syncValeSimDataDom = (items)=>{
			if(Array.isArray(items)){
				state.current.rows = deepClone(items);
			}
		};

		function showSpinner(flag){
			// Mostra ou oculta o overlay de carregamento do modal de vale.
			if(!state.dom.spinner) return;
			state.dom.spinner.style.display = flag ? 'flex' : 'none';
		}

		function setModalVisible(flag){
			// Controla a visibilidade do modal principal e seus atributos ARIA.
			state.dom.modal.style.display = flag ? 'flex' : 'none';
			if(flag){
				state.dom.modal.setAttribute('aria-hidden', 'false');
			}else{
				state.dom.modal.setAttribute('aria-hidden', 'true');
			}
		}

		function refreshValeUI(nunotaVale){
			// Atualiza badges e estado global quando o número do vale muda.
			const normalized = nunotaVale ? String(nunotaVale).trim() : '';
			const badge = doc.getElementById('entBadgeVale13');
			if(badge){
				if(normalized){
					badge.textContent = `Vale ${normalized}`;
					badge.style.display = '';
				}else{
					badge.textContent = '';
					badge.style.display = 'none';
				}
			}
			if(state.dom.valeWrap && state.dom.valeNum){
				state.dom.valeWrap.style.display = normalized ? 'block' : 'none';
				state.dom.valeNum.textContent = normalized || '—';
			}
			window.__CURRENT_VALE_NUNOTA_TOP13 = normalized || null;
			if(typeof window.__syncValeObservationButton === 'function'){
				window.__syncValeObservationButton(window.__CURRENT_VALE_OBSERVACAO || '');
			}
		}
		window.__refreshValeUI = refreshValeUI;

		function syncValeObservationButton(text){
			// Ajusta o botão de observação conforme existe texto salvo ou não.
			window.__CURRENT_VALE_OBSERVACAO = typeof text === 'string' ? text : '';
			const nunotaVale = window.__CURRENT_VALE_NUNOTA_TOP13 || window.__CURRENT_VALE_NUNOTA;
			const btn = state.dom.obsButton;
			if(btn){
				const hasVale = !!nunotaVale;
				btn.disabled = !hasVale;
				btn.style.opacity = hasVale ? '1' : '0.45';
				btn.style.cursor = hasVale ? 'pointer' : 'not-allowed';
				btn.title = hasVale ? (text ? 'Editar observação do vale' : 'Adicionar observação do vale') : 'Vale não disponível';
				if(hasVale && text){
					btn.style.borderColor = '#0ea5e9';
					btn.style.color = '#0ea5e9';
					btn.style.background = '#f0f9ff';
				}else{
					btn.style.borderColor = '#cbd5e1';
					btn.style.color = hasVale ? '#475569' : '#94a3b8';
					btn.style.background = hasVale ? '#fff' : '#f8fafc';
				}
			}
			if(state.dom.obsIdent){
				state.dom.obsIdent.textContent = nunotaVale ? `Vale ${nunotaVale}` : 'Vale —';
			}
		}
		window.__syncValeObservationButton = syncValeObservationButton;

		async function fetchValeObservation(nunotaVale){
			// Consulta o backend para buscar a observação do vale selecionado.
			const target = nunotaVale ? String(nunotaVale).trim() : '';
			if(!target){
				syncValeObservationButton('');
				return '';
			}
			syncValeObservationButton('');
			try{
				const { ok, body } = await http.get(`/sankhya/comercial/vale/observacao/?nunota=${encodeURIComponent(target)}`);
				const obs = ok && body && typeof body.observacao === 'string' ? body.observacao : '';
				syncValeObservationButton(obs);
				return obs;
			}catch(err){
				logger.error('Falha ao carregar observação do vale', err);
				return '';
			}
		}
		window.__fetchValeObservation = fetchValeObservation;

		function openObservationModal(){
			// Abre o modal de observação garantindo que haja um vale associado.
			const nunotaVale = window.__CURRENT_VALE_NUNOTA_TOP13 || window.__CURRENT_VALE_NUNOTA;
			if(!nunotaVale){
				toast('Crie o vale antes de adicionar observação.', 'warning');
				return;
			}
			if(state.dom.obsIdent) state.dom.obsIdent.textContent = `Vale ${nunotaVale}`;
			if(state.dom.obsInput){
				state.dom.obsInput.value = window.__CURRENT_VALE_OBSERVACAO || '';
				setTimeout(()=> state.dom.obsInput?.focus(), 60);
			}
			if(state.dom.obsModal){
				state.dom.obsModal.style.display = 'flex';
			}
		}

		function closeObservationModal(){
			// Fecha o modal de observação sem alterar o conteúdo.
			if(state.dom.obsModal) state.dom.obsModal.style.display = 'none';
		}

		async function saveObservation(){
			// Persiste a observação do vale e atualiza o botão de acesso rápido.
			const nunotaVale = window.__CURRENT_VALE_NUNOTA_TOP13 || window.__CURRENT_VALE_NUNOTA;
			if(!nunotaVale || !state.dom.obsInput) return;
			const texto = state.dom.obsInput.value || '';
			const btn = state.dom.obsSave;
			if(btn){
				btn.disabled = true;
				btn.textContent = 'Salvando...';
			}
			try{
				const payload = { nunota: Number(nunotaVale), observacao: texto };
				const { ok, body } = await http.post('/sankhya/comercial/vale/observacao/', payload);
				if(ok && body?.ok !== false){
					const normalized = typeof body?.observacao === 'string' ? body.observacao : texto;
					syncValeObservationButton(normalized);
					toast('Observação salva.', 'success');
					closeObservationModal();
				}else{
					toast(body?.error || 'Erro ao salvar observação.', 'error');
				}
			}catch(err){
				logger.error('Erro ao salvar observação do vale', err);
				toast('Erro ao salvar observação.', 'error');
			}finally{
				if(btn){
					btn.disabled = false;
					btn.textContent = 'Salvar observação';
				}
			}
		}

		function applyDescontoINSS(){
			// Calcula o valor líquido do vale conforme o checkbox de INSS.
			const checkbox = state.dom.checkboxINSS;
			const totalEl = state.dom.total;
			if(!checkbox || !totalEl) return;
			const brutoAttr = Number(totalEl.dataset.totalOriginal || 0);
			const brutoEl = state.dom.bruto;
			const inssEl = state.dom.inss;
			const base = brutoAttr > 0 ? brutoAttr : 0;
			if(checkbox.checked){
				const desconto = base * 0.015;
				const liquido = base - desconto;
				if(inssEl) inssEl.textContent = `- ${formatMoney(desconto)}`;
				if(totalEl){
					totalEl.textContent = formatMoney(liquido);
					totalEl.dataset.totalLiquido = String(liquido);
				}
				if(brutoEl) brutoEl.textContent = formatMoney(base);
			}else{
				if(inssEl) inssEl.textContent = formatMoney(0);
				if(totalEl){
					totalEl.textContent = formatMoney(base);
					totalEl.dataset.totalLiquido = String(base);
				}
				if(brutoEl) brutoEl.textContent = formatMoney(base);
			}
		}
		window.__aplicarDescontoINSS = applyDescontoINSS;

		function resolveNunotaVale(rows){
			// Determina o número do vale a partir das linhas carregadas.
			if(!rows || !rows.length) return null;
			const direct = rows[0]?.nunota_13 || rows[0]?.nunotaVale;
			if(direct) return normalizeNunota(direct);
			const match = rows.find((row)=> row?.nunota_13 || row?.nunotaVale);
			return match ? normalizeNunota(match.nunota_13 || match.nunotaVale) : null;
		}

		async function loadPedidoRows(nunota, options = {}){
			// Busca itens do pedido, usando cache local quando possível.
			const key = normalizeNunota(nunota);
			if(!key) return [];
			if(!options.force && state.cache.pedido.has(key)){
				return deepClone(state.cache.pedido.get(key)) || [];
			}
			const localRows = (window.__COM_LIST_ROWS || []).filter((row)=> normalizeNunota(row?.nunota) === key);
			if(localRows.length && !options.force){
				state.cache.pedido.set(key, deepClone(localRows));
				return deepClone(localRows);
			}
			const url = `/sankhya/comercial/lista/?nunota=${encodeURIComponent(key)}&limit=all&_=${Date.now()}`;
			try{
				const { ok, body } = await http.get(url);
				const rows = ok && body ? (body.rows || body.items || []) : [];
				state.cache.pedido.set(key, deepClone(rows));
				return deepClone(rows);
			}catch(err){
				logger.error('Falha ao carregar itens do pedido', err);
				return deepClone(localRows);
			}
		}

		async function loadValeItems(nunotaVale, options = {}){
			// Carrega itens já existentes no vale para permitir merge e edição.
			const key = normalizeNunota(nunotaVale);
			if(!key) return [];
			if(!options.force && state.cache.vale.has(key)){
				return deepClone(state.cache.vale.get(key));
			}
			const cacheBust = options.force ? `&_=${Date.now()}` : '';
			try{
				const { ok, body } = await http.get(`/sankhya/comercial/api/itens_vale/?nunota=${encodeURIComponent(key)}${cacheBust}`);
				if(ok && Array.isArray(body?.items)){
					state.cache.vale.set(key, deepClone(body.items));
					return deepClone(body.items);
				}
			}catch(err){
				logger.error('Falha ao carregar itens do vale', err);
			}
			return [];
		}

		function buildMergeKey(row){
			// Gera uma chave única por produto/seq/lote para casar linhas.
			const codprod = normalizeNunota(row?.codprod || row?.CODPROD) || '0';
			const seq = normalizeNunota(row?.sequencia || row?.SEQUENCIA || row?.sequencia_pedido) || '0';
			const lote = String(row?.codagregacao || row?.CODAGREGACAO || row?.lote || row?.LOTE || '').trim().toUpperCase();
			return `${codprod}#${seq}#${lote}`;
		}

		function mergeValeRows(pedidoRows, valeItems){
			// Combina linhas do pedido com itens do vale para exibição consolidada.
			const map = new Map();
			valeItems.forEach((item)=>{
				map.set(buildMergeKey(item), item);
			});
			const merged = pedidoRows.map((row)=>{
				const key = buildMergeKey(row);
				if(map.has(key)){
					const valeRow = map.get(key);
					map.delete(key);
					return Object.assign({}, row, valeRow, { __merged_from_vale: true });
				}
				return Object.assign({}, row);
			});
			map.forEach((leftover)=>{
				merged.push(Object.assign({}, leftover, { __fromValeOnly: true }));
			});
			return merged;
		}

		function splitRows(rows){
			// Separa linhas em classificáveis e outros itens auxiliares.
			const classificaveis = [];
			const outros = [];
			rows.forEach((row)=>{
				const flag = row?.classificavel;
				const normalizedFlag = typeof flag === 'string' ? flag.toUpperCase() : flag;
				if(normalizedFlag === false || normalizedFlag === 'N') outros.push(row);
				else classificaveis.push(row);
			});
			return { classificaveis, outros };
		}

		function renderClassRows(rows){
			// Renderiza a tabela de itens classificáveis dentro do modal.
			const body = state.dom.classBody;
			if(!body) return;
			if(!rows.length){
				body.innerHTML = '<tr><td colspan="6">Sem itens classificáveis.</td></tr>';
				return;
			}
			const html = rows.map((row)=>{
				const produto = (row.produto || row.descr || '').toString().trim();
				const qtd = parseLocaleNumber(row.qtdneg ?? row.qtd ?? row.qtdneg_base);
				const unit = (row.codvol || row.unidade || '').toString().toUpperCase();
				const total = parseLocaleNumber(row.vlrtot ?? row.total ?? row.valor_total);
				const unitPrice = parseLocaleNumber(row.vlrunit ?? row.preco_inicial ?? row.valor_unitario);
				return `<tr>
					<td>${produto}</td>
					<td>${formatQty(qtd)} <span class="unit">${unit}</span></td>
					<td>${unitPrice ? formatMoney(unitPrice) : '—'}</td>
					<td>${total ? formatMoney(total) : '—'}</td>
				</tr>`;
			}).join('');
			body.innerHTML = html;
		}

		function renderOutrosRows(rows){
			// Constrói a tabela editável de itens adicionais do vale.
			const body = state.dom.outrosBody;
			if(!body) return;
			if(!rows.length){
				body.innerHTML = '<tr><td colspan="5">Sem itens adicionais.</td></tr>';
				state.current.outrosRows = [];
				return;
			}
			state.current.outrosRows = rows.map((row, index)=> Object.assign({}, row, { __index: index }));
			const html = state.current.outrosRows.map((row)=>{
				const produto = (row.produto || row.descr || '').toString().trim();
				const qtd = parseLocaleNumber(row.qtdneg ?? row.qtd ?? row.qtdneg_base);
				const preco = parseLocaleNumber(row.vlrunit ?? row.preco_inicial);
				const total = parseLocaleNumber(row.vlrtot ?? (qtd * preco));
				return `<tr data-index="${row.__index}">
					<td>${produto}</td>
					<td class="vale-qtd">${formatQty(qtd)}</td>
					<td class="vale-preco"><input type="text" class="vale-price" data-index="${row.__index}" value="${preco ? formatDecimal(preco, 2) : ''}" placeholder="0,00" /></td>
					<td class="vale-total" data-index="${row.__index}">${total ? formatMoney(total) : '—'}</td>
				</tr>`;
			}).join('');
			body.innerHTML = html;
		}

		function recomputeOutros(index, value){
			// Recalcula valores totais quando o usuário altera preços de outros itens.
			const rows = state.current.outrosRows;
			if(!rows || !rows.length) return;
			const target = rows.find((row)=> row.__index === index);
			if(!target) return;
			const parsed = parseLocaleNumber(value);
			target.vlrunit = parsed;
			const qty = parseLocaleNumber(target.qtdneg ?? target.qtd ?? target.qtdneg_base);
			target.vlrtot = qty * parsed;
			const totalCell = state.dom.outrosBody?.querySelector(`.vale-total[data-index="${index}"]`);
			if(totalCell){
				totalCell.textContent = target.vlrtot ? formatMoney(target.vlrtot) : '—';
			}
		}

		function bindOutrosListeners(){
			// Liga eventos de input para manter os totais em sincronia.
			state.dom.outrosBody?.addEventListener('input', (ev)=>{
				const input = ev.target.closest('.vale-price');
				if(!input) return;
				const idx = Number(input.dataset.index);
				recomputeOutros(idx, input.value);
				renderTotals(state.current.classRows, state.current.outrosRows);
			});
		}

		function renderTotals(classRows, outrosRows){
			// Atualiza totais bruto/líquido do vale considerando INSS.
			const totalClass = classRows.reduce((acc, row)=> acc + parseLocaleNumber(row.vlrtot ?? row.total ?? 0), 0);
			const totalOutros = (outrosRows || []).reduce((acc, row)=> acc + parseLocaleNumber(row.vlrtot ?? row.total ?? 0), 0);
			const bruto = totalClass + totalOutros;
			if(state.dom.total){
				state.dom.total.textContent = formatMoney(bruto);
				state.dom.total.dataset.totalOriginal = String(bruto);
				state.dom.total.dataset.totalLiquido = String(bruto);
			}
			if(state.dom.bruto){
				state.dom.bruto.textContent = formatMoney(bruto);
				state.dom.bruto.dataset.brutoOriginal = String(bruto);
			}
			if(state.dom.inss){
				state.dom.inss.textContent = formatMoney(0);
			}
			applyDescontoINSS();
		}

		function buildSequenceIndex(){
			// Mapeia sequências originais para manter referência durante merges.
			const lookup = new Map();
			const target = state.current.nunota;
			(state.current.rows || []).forEach((row)=>{
				const codprod = Number(row?.codprod || row?.CODPROD || 0);
				if(!codprod) return;
				const lote = String(row?.codagregacao || row?.CODAGREGACAO || row?.lote || '').trim().toUpperCase();
				const seq = Number(row?.sequencia || row?.SEQUENCIA || row?.sequencia_pedido || 0);
				const nunotaRow = normalizeNunota(row?.nunota || row?.nunota_pedido || row?.NUNOTA);
				if(target && nunotaRow && nunotaRow !== target) return;
				if(seq > 0){
					const key = `${codprod}#${lote}`;
					if(!lookup.has(key)) lookup.set(key, seq);
				}
			});
			return lookup;
		}

		function resolveSequencia(row, map){
			// Determina a sequência correta para envio ao backend.
			if(!row) return 0;
			const seqPedido = Number(row.sequencia_pedido || row.SEQUENCIA_PEDIDO || 0);
			if(seqPedido) return seqPedido;
			const nunRow = normalizeNunota(row.nunota || row.nunota_pedido || row.NUNOTA);
			if(nunRow && nunRow === state.current.nunota){
				const seqDirect = Number(row.sequencia || row.SEQUENCIA || 0);
				if(seqDirect) return seqDirect;
			}
			const codprod = Number(row.codprod || row.CODPROD || 0);
			if(!codprod) return Number(row.sequencia || row.SEQUENCIA || 0);
			const lote = String(row.codagregacao || row.CODAGREGACAO || row.lote || '').trim().toUpperCase();
			const key = `${codprod}#${lote}`;
			return map.get(key) || Number(row.sequencia || row.SEQUENCIA || 0) || 0;
		}

		function buildValeItems(){
			// Produz o payload final dos itens com preços ajustados.
			const seqIndex = buildSequenceIndex();
			const items = [];
			const pushPreco = (row, field)=>{
				const seq = resolveSequencia(row, seqIndex);
				if(!seq) return;
				const preco = parseLocaleNumber(row?.[field] ?? row?.vlrunit ?? row?.preco_inicial ?? row?.preco);
				if(!(preco > 0)) return;
				items.push({
					sequencia: seq,
					[field === 'vlrunit' ? 'preco' : 'preco_inicial']: preco > 0 ? preco : null
				});
			};
			state.current.classRows.forEach((row)=> pushPreco(row, 'preco_inicial'));
			state.current.outrosRows.forEach((row)=> pushPreco(row, 'vlrunit'));
			return items;
		}

		function resolveTotalLiquido(){
			// Obtém o total líquido atual considerando eventuais descontos.
			const totalEl = state.dom.total;
			if(!totalEl) return null;
			const candidate = totalEl.dataset.totalLiquido || totalEl.dataset.totalOriginal || totalEl.textContent;
			const parsed = parseLocaleNumber(candidate);
			return Number.isFinite(parsed) ? parsed : null;
		}

		function setButtonBusy(button, label){
			// Coloca botões em estado de carregamento prevenindo cliques repetidos.
			if(!button) return;
			if(!button.dataset.originalText){
				button.dataset.originalText = button.textContent || '';
			}
			button.disabled = true;
			button.textContent = label;
			button.classList.add('is-loading');
		}

		function restoreButton(button){
			// Restaura o texto/estado original após a ação do botão concluir.
			if(!button) return;
			button.disabled = false;
			if(button.dataset.originalText){
				button.textContent = button.dataset.originalText;
			}
			button.classList.remove('is-loading');
		}

		function setValeLocked(flag){
			// Habilita ou bloqueia campos quando o vale está faturado.
			const inputs = state.dom.outrosBody?.querySelectorAll('.vale-price') || [];
			inputs.forEach((input)=>{
				input.disabled = flag;
				input.classList.toggle('is-readonly', flag);
			});
			if(state.dom.checkboxINSS){
				state.dom.checkboxINSS.disabled = flag;
				const wrapper = state.dom.checkboxINSS.closest('label');
				if(wrapper) wrapper.classList.toggle('is-disabled', flag);
			}
			const entradaCard = doc.getElementById('quantidadeInnCard') || doc.getElementById('entradaCard');
			if(entradaCard){
				entradaCard.classList.toggle('locked', flag);
			}
			if(typeof window.__applyEntradaLockState === 'function'){
				window.__applyEntradaLockState(flag);
			}
			if(typeof window.__setSimulationButtonsDisabled === 'function'){
				window.__setSimulationButtonsDisabled(flag, flag ? 'Simulação bloqueada: vale faturado.' : '');
			}
		}

		function applyValeFaturadoState({ nunotaVale, nufin } = {}){
			// Ajusta o modal para o modo somente leitura quando o vale já foi faturado.
			setValeLocked(true);
			if(state.dom.btnFaturar) state.dom.btnFaturar.style.display = 'none';
			if(state.dom.btnDesfaturar){
				state.dom.btnDesfaturar.style.display = '';
				state.dom.btnDesfaturar.disabled = false;
			}
			if(nufin && state.dom.nufinBadge){
				state.dom.nufinBadge.style.display = 'inline-block';
				if(state.dom.nufinNum) state.dom.nufinNum.textContent = String(nufin);
			}
			if(state.dom.marcaDagua) state.dom.marcaDagua.style.display = 'block';
			const resolvedVale = nunotaVale ? String(nunotaVale).trim() : '';
			if(resolvedVale) refreshValeUI(resolvedVale);
			state.current.isFaturado = true;
			window.__CURRENT_VALE_LOCKED = true;
			if(events && typeof events.emit === 'function'){
				events.emit('vale:lock', { locked: true, nunota: state.current.nunota, nunotaVale: nunotaVale || state.current.nunotaVale });
			}
		}

		function applyValeAbertoState(){
			// Reativa inputs quando o vale está aberto para edição.
			setValeLocked(false);
			if(state.dom.btnFaturar){
				state.dom.btnFaturar.style.display = '';
				state.dom.btnFaturar.disabled = false;
			}
			if(state.dom.btnDesfaturar){
				state.dom.btnDesfaturar.style.display = 'none';
				state.dom.btnDesfaturar.disabled = false;
			}
			if(state.dom.nufinBadge) state.dom.nufinBadge.style.display = 'none';
			if(state.dom.nufinNum) state.dom.nufinNum.textContent = '—';
			if(state.dom.marcaDagua) state.dom.marcaDagua.style.display = 'none';
			state.current.isFaturado = false;
			window.__CURRENT_VALE_LOCKED = false;
			if(events && typeof events.emit === 'function'){
				events.emit('vale:lock', { locked: false, nunota: state.current.nunota, nunotaVale: state.current.nunotaVale });
			}
		}

		function resolveCurrentNufin(){
			// Descobre o NUFIN atual usando linhas carregadas ou badges.
			const rowWithNufin = (state.current.rows || []).find((row)=> Number(row?.nufin || row?.NUFIN || 0) > 0);
			if(rowWithNufin){
				const val = Number(rowWithNufin.nufin || rowWithNufin.NUFIN);
				if(Number.isFinite(val) && val > 0) return val;
			}
			if(state.current.nunotaVale && state.cache.vale.has(state.current.nunotaVale)){
				const cached = state.cache.vale.get(state.current.nunotaVale) || [];
				const cachedMatch = cached.find((row)=> Number(row?.nufin || row?.NUFIN || 0) > 0);
				if(cachedMatch){
					const val = Number(cachedMatch.nufin || cachedMatch.NUFIN);
					if(Number.isFinite(val) && val > 0) return val;
				}
			}
			const badge = state.dom.nufinNum;
			if(badge && badge.textContent){
				const found = badge.textContent.match(/\d+/);
				if(found) return Number(found[0]);
			}
			return null;
		}

		async function handleFaturarClick(){
			// Reúne os dados do vale e dispara a API para faturamento.
			if(state.pending || state.faturando) return;
			if(!state.current.nunota){
				toast('Selecione um pedido antes de faturar.', 'warning');
				return;
			}
			const items = buildValeItems();
			if(!items.length){
				toast('Nenhum item disponível para faturar.', 'warning');
				return;
			}
			const totalLiquido = resolveTotalLiquido();
			state.faturando = true;
			setButtonBusy(state.dom.btnFaturar, 'Faturando...');
			try{
				const payload = {
					nunota: Number(state.current.nunota),
					items,
					faturar: true
				};
				if(Number.isFinite(totalLiquido) && totalLiquido > 0){
					payload.valor_liquido = Number(totalLiquido.toFixed(2));
				}
				const { ok, body } = await http.post('/sankhya/comercial/vale/save/', payload);
				if(!ok || body?.ok === false){
					const errors = Array.isArray(body?.errors) ? body.errors.filter(Boolean).join(' | ') : null;
					throw new Error(errors || body?.error || 'Erro ao faturar o vale.');
				}
				const warnings = Array.isArray(body?.warnings) ? body.warnings.filter(Boolean) : [];
				applyValeFaturadoState({
					nunotaVale: body?.nunota_vale || body?.nunota_13,
					nufin: body?.financeiro?.nufin
				});
				const msg = warnings.length ? `Vale faturado com avisos: ${warnings.join(' | ')}` : 'Vale faturado com sucesso.';
				toast(msg, warnings.length ? 'warning' : 'success');
				await openValeResumo(state.current.nunota, { force: true, forceReload: true });
			}catch(err){
				logger.error('Erro ao faturar vale', err);
				toast(err?.message || 'Erro ao faturar vale.', 'error');
			}finally{
				state.faturando = false;
				restoreButton(state.dom.btnFaturar);
			}
		}

		async function handleDesfaturarClick(){
			// Solicita o desfaturamento removendo o financeiro associado.
			if(state.pending || state.desfaturando) return;
			const nufin = resolveCurrentNufin();
			if(!nufin){
				toast('NUFIN não localizado para desfaturar.', 'warning');
				return;
			}
			if(!window.confirm('Remover o faturamento vai excluir o financeiro e reabrir o vale. Deseja continuar?')) return;
			state.desfaturando = true;
			setButtonBusy(state.dom.btnDesfaturar, 'Desfaturando...');
			try{
				const { ok, body } = await http.post('/sankhya/comercial/vale/desfaturar/', { nufin: Number(nufin) });
				if(!ok || body?.ok === false){
					throw new Error(body?.error || 'Erro ao desfaturar vale.');
				}
				toast('Vale desfaturado com sucesso.', 'success');
				applyValeAbertoState();
				await openValeResumo(state.current.nunota, { force: true, forceReload: true });
			}catch(err){
				logger.error('Erro ao desfaturar vale', err);
				toast(err?.message || 'Erro ao desfaturar vale.', 'error');
			}finally{
				state.desfaturando = false;
				restoreButton(state.dom.btnDesfaturar);
			}
		}

		function wireActionButtons(){
			// Garante que os botões de ação sejam ligados somente uma vez.
			if(state.dom.btnFaturar && !state.dom.btnFaturar.dataset.bound){
				state.dom.btnFaturar.dataset.bound = 'true';
				state.dom.btnFaturar.addEventListener('click', (ev)=>{
					ev.preventDefault();
					handleFaturarClick();
				});
			}
			if(state.dom.btnDesfaturar && !state.dom.btnDesfaturar.dataset.bound){
				state.dom.btnDesfaturar.dataset.bound = 'true';
				state.dom.btnDesfaturar.addEventListener('click', (ev)=>{
					ev.preventDefault();
					handleDesfaturarClick();
				});
			}
		}

		async function openValeResumo(nunota, options = {}){
			// Carrega dados do pedido/vale, renderiza o modal e controla estados.
			const targetNunota = normalizeNunota(nunota || state.current.nunota);
			if(!targetNunota){
				toast('Selecione um pedido válido para abrir o vale.', 'warning');
				return;
			}
			if(state.pending) return;
			state.pending = true;
			showSpinner(true);
			try{
				const pedidoRows = await loadPedidoRows(targetNunota, { force: options.force || options.forceReload });
				if(!pedidoRows.length){
					toast('Pedido sem itens disponíveis.', 'warning');
					return;
				}
				const nunotaVale = resolveNunotaVale(pedidoRows);
				state.current.nunota = targetNunota;
				state.current.nunotaVale = nunotaVale;
				window.__CURRENT_VALE_NUNOTA = targetNunota;
				refreshValeUI(nunotaVale);
				const valeItems = nunotaVale ? await loadValeItems(nunotaVale, { force: options.force || options.forceReload }) : [];
				const mergedRows = mergeValeRows(pedidoRows, valeItems);
				const { classificaveis, outros } = splitRows(mergedRows);
				state.current.rows = mergedRows;
				state.current.classRows = classificaveis;
				state.current.outrosRows = outros;
				renderClassRows(classificaveis);
				renderOutrosRows(outros);
				renderTotals(classificaveis, outros);
				const nufinRow = mergedRows.find((row)=> Number(row?.nufin || row?.NUFIN || 0) > 0);
				if(nufinRow){
					applyValeFaturadoState({ nunotaVale, nufin: Number(nufinRow.nufin || nufinRow.NUFIN) });
				}else{
					applyValeAbertoState();
				}
				if(state.dom.title){
					state.dom.title.textContent = `Resumo do Vale — Pedido ${targetNunota}`;
				}
				if(state.dom.pedidoWrap && state.dom.pedidoNum){
					state.dom.pedidoWrap.style.display = 'block';
					state.dom.pedidoNum.textContent = targetNunota;
				}
				if(state.dom.valeWrap && state.dom.valeNum){
					state.dom.valeWrap.style.display = nunotaVale ? 'block' : 'none';
					state.dom.valeNum.textContent = nunotaVale || '—';
				}
				await fetchValeObservation(nunotaVale);
				setModalVisible(true);
			}catch(err){
				logger.error('Erro ao abrir modal do vale', err);
				toast('Erro ao abrir modal do vale.', 'error');
			}finally{
				showSpinner(false);
				state.pending = false;
			}
		}

		function wireModal(){
			// Conecta listeners do modal e inicializa interações auxiliares.
			modal.addEventListener('click', (ev)=>{
				if(ev.target === modal){
					setModalVisible(false);
				}
			});
			state.dom.obsButton?.addEventListener('click', openObservationModal);
			state.dom.obsSave?.addEventListener('click', saveObservation);
			state.dom.obsCancel?.addEventListener('click', closeObservationModal);
			state.dom.checkboxINSS?.addEventListener('change', applyDescontoINSS);
			bindOutrosListeners();
			wireActionButtons();
		}

		wireModal();
		syncValeObservationButton('');

		window.openValeResumo = openValeResumo;

		return {
			open: openValeResumo,
			state
		};
	});

	/**
	 * Módulo: Dashboard shell. Entrypoint para recursos avançados.
	 */
	registerModule('dashboardShell', (ctx)=>{
		if(!ctx.flags.isDashboard) return null;
		const { logger, events, services, utils } = ctx;
		const dom = collectDom();
		const cache = {
			classificacao: new Map(),
			valeResumo: new Map(),
			distribuicao: new Map(),
			produtoVariantes: new Map(),
			payloads: Object.create(null)
		}; // Estruturas de cache por domínio (classificação, vale, distribuição, mapeamento de produtos).
		const state = {
			ready: false,
			context: extractContext(),
			dom,
			cache,
			loadingFlags: new Set(),
			actions: {}
		}; // Snapshot vivo contendo dom, contexto atual e ações do shell.
		const extraMedio = createExtraMedioSync();
		const simulationCard = createSimulationCard();
		simulationCardController = simulationCard;
		if(simulationCard){
			window.__SIM_CARD__ = simulationCard;
		}
		const valeShell = typeof ctx.initModule === 'function' ? ctx.initModule('valeShell') : null;
		const distribActions = initDistribuicaoActions();
		window.__clearClassResumoCache = (reason)=>{
			try{
				logger.info('Limpando cache de classificação', reason ? `(${reason})` : '');
			}catch(_err){ /* noop */ }
			cache.classificacao.clear();
			if(cache.payloads){
				cache.payloads.classificacao = null;
			}
		};

		// Lê dataset inicial para saber nota, sequência e lote em foco.
		function extractContext(){
			const cardEntrada = doc.getElementById('quantidadeInnCard');
			const nunota = cardEntrada?.dataset?.nunota || doc.body?.dataset?.nunota || null;
			const sequencia = cardEntrada?.dataset?.seq || null;
			const codprod = cardEntrada?.dataset?.codprod || null;
			const currentLote = doc.getElementById('classLoteBadge')?.textContent?.replace(/[^0-9]/g, '') || null;
			return {
				nunota: nunota ? utils.normalizeNunota(nunota) : null,
				sequencia: sequencia ? utils.normalizeNunota(sequencia) : null,
				codprod: codprod ? Number(codprod) : null,
				lote: currentLote || null
			};
		}

		// Junta referências aos principais elementos usados no dashboard.
		function collectDom(){
			return {
				root: doc.body,
				cards: {
					// Sempre preferimos o card interno (quantidadeInnCard) porque é nele que as classes de edição/bloqueio atuam no CSS.
					entrada: doc.getElementById('quantidadeInnCard') || doc.getElementById('entradaCard'),
					classificacao: doc.getElementById('classCard'),
					distribuicao: doc.getElementById('distCard') || doc.getElementById('distribuicaoCard'),
					miniExtra: doc.getElementById('distMiniExtra'),
					miniMedio: doc.getElementById('distMiniMedio')
				},
				modals: {
					vale: doc.getElementById('modalFaturamento'),
					printPreview: doc.getElementById('printPreviewModal'),
					obervacaoVale: doc.getElementById('valeObservacaoModal')
				},
				buttons: {
					refresh: utils.qsa('[data-dashboard-refresh]'),
					reloadClass: doc.getElementById('btnReloadClass')
				},
				classificacao: {
					card: doc.getElementById('classCard'),
					body: doc.getElementById('classBody') || doc.querySelector('#classCard .class-body'),
					badge: doc.getElementById('classLoteBadge'),
					openLink: doc.getElementById('classOpenLink'),
					resumo: {
						innKg: doc.getElementById('resInnKg'),
						innCx: doc.getElementById('resInnCx'),
						classKg: doc.getElementById('resClassKg'),
						classCx: doc.getElementById('resClassCx'),
						inservKg: doc.getElementById('resInservKg'),
						inservCx: doc.getElementById('resInservCx'),
						rend: doc.getElementById('kpiRendimento')
					},
					kpis: {
						aproveitamento: doc.getElementById('kpiAproveitamento'),
						estoque: doc.getElementById('kpiEstoque'),
						estoqueApprox: doc.getElementById('kpiEstoqueApprox'),
						rend: doc.getElementById('kpiRendimento')
					},
					gauge: {
						root: doc.getElementById('gaugeProgress'),
						arc: doc.getElementById('gArc'),
						pct: doc.getElementById('gPct'),
						label: doc.getElementById('gaugeLabel'),
						watermark: doc.getElementById('gaugeWatermark')
					}
				}
			};
		}

		function createExtraMedioSync(){
			const state = window.__DIST_EXTRA_MEDIO_STATE = window.__DIST_EXTRA_MEDIO_STATE || {
				isUpdating: false,
				precoBase: 0,
				extraCx: 0,
				extraKg: 0,
				medioCx: 0,
				medioKg: 0,
				extraCodprod: null,
				medioCodprod: null,
				extraCustoCx: 0,
				extraCustoKg: 0,
				extraCustoTotal: 0,
				medioCustoCx: 0,
				medioCustoKg: 0,
				medioCustoTotal: 0,
				valorEntrada: 0,
				hasVale: false,
				forceSimTotals: false,
				lastSimTotal: 0
			};
			if(typeof state.forceSimTotals !== 'boolean') state.forceSimTotals = false;
			if(!Number.isFinite(state.lastSimTotal)) state.lastSimTotal = 0;
			const domRefs = {
				extraCard: doc.getElementById('distMiniExtra'),
				medioCard: doc.getElementById('distMiniMedio'),
				totalDisplay: doc.getElementById('totalValueDisplay'),
				custoCxDisplay: doc.getElementById('costCxDisplay'),
				custoKgDisplay: doc.getElementById('costKgDisplay')
			};

			const parseLocale = (value)=>{
				if(typeof value === 'number') return Number.isFinite(value) ? value : 0;
				if(!value) return 0;
				const cleaned = String(value)
					.replace(/[^0-9,\.\-]/g, '')
					.replace(/\.(?=\d{3}(\D|$))/g, '')
					.replace(',', '.');
				const num = Number(cleaned);
				return Number.isFinite(num) ? num : 0;
			};
			const formatMoneySafe = (value)=> utils.formatMoney(Number(value) || 0);
			const formatDec2 = (value)=> utils.formatDecimal(Number(value) || 0, 2) || '0,00';
			const quantizeValue = (value, precision = 4)=>{
				if(!Number.isFinite(value)) return 0;
				const factor = 10 ** precision;
				return Math.round(value * factor) / factor;
			};
			const resolveDisplayTotalForBucket = (bucket)=>{
				const kgRaw = Number(state[`${bucket}Kg`]) || 0;
				const kgCostRaw = Number(state[`${bucket}CustoKg`]) || 0;
				if(kgRaw > 0 && kgCostRaw > 0){
					const kgRounded = quantizeValue(kgRaw, 4);
					const kgCostRounded = quantizeValue(kgCostRaw, 4);
					return quantizeValue(kgRounded * kgCostRounded, 2);
				}
				return quantizeValue(Number(state[`${bucket}CustoTotal`]) || 0, 2);
			};

			function resolvePrecoBase(){
				if(state.precoBase > 0) return state.precoBase;
				const datasetBase = domRefs.extraCard?.dataset?.precoBase;
				const displayBase = doc.getElementById('extraCustoCxDisplay')?.textContent;
				const parsed = parseLocale(datasetBase || displayBase);
				if(parsed > 0){
					state.precoBase = parsed;
				}
				return state.precoBase;
			}

			function hasExtra(){
				return (state.extraCx > 0) || (state.extraKg > 0);
			}

			function setDistribTotal(valorTotal, source){
				if(typeof window.__setDistribTotal === 'function'){
					window.__setDistribTotal(valorTotal, { source, allowUI: true, syncInput: true });
				}
				if(domRefs.totalDisplay){
					domRefs.totalDisplay.textContent = formatMoneySafe(valorTotal);
				}
			}

			function updateCostDisplays(totalCustoCx, totalCustoKg){
				if(domRefs.custoCxDisplay) domRefs.custoCxDisplay.textContent = formatDec2(totalCustoCx);
				if(domRefs.custoKgDisplay) domRefs.custoKgDisplay.textContent = formatDec2(totalCustoKg);
			}

			function updateExtraCard(){
				const card = domRefs.extraCard;
				if(!card) return;
				const kgEl = card.querySelector('[data-field="custoKg"]');
				if(kgEl) kgEl.textContent = formatDec2(state.extraCustoKg);
				const cxEl = card.querySelector('[data-field="custoCx"]');
				if(cxEl) cxEl.textContent = formatDec2(state.extraCustoCx);
				const totalEl = card.querySelector('[data-field="custo"]');
				if(totalEl) totalEl.textContent = formatMoneySafe(state.extraCustoTotal);
			}

			function updateMedioCard(){
				const card = domRefs.medioCard;
				if(!card) return;
				const kgEl = card.querySelector('[data-field="custoKg"]');
				if(kgEl) kgEl.textContent = formatDec2(state.medioCustoKg);
				const cxEl = card.querySelector('[data-field="custoCx"]');
				if(cxEl) cxEl.textContent = formatDec2(state.medioCustoCx);
				const totalEl = card.querySelector('[data-field="custo"]');
				if(totalEl) totalEl.textContent = formatMoneySafe(state.medioCustoTotal);
			}

			function applyResultado(){
				const extraDisplayTotal = resolveDisplayTotalForBucket('extra');
				const medioDisplayTotal = resolveDisplayTotalForBucket('medio');
				const valorTotal = quantizeValue(extraDisplayTotal + medioDisplayTotal, 2);
				const totalCx = (state.extraCx || 0) + (state.medioCx || 0);
				const totalKg = (state.extraKg || 0) + (state.medioKg || 0);
				const custoCx = totalCx > 0 ? (valorTotal / totalCx) : 0;
				const custoKg = totalKg > 0 ? (valorTotal / totalKg) : 0;
				const fallbackEntrada = Number(state.valorEntrada) || 0;
				const hasDistrib = (totalCx > 0) || (totalKg > 0);
				const hasSimOverride = state.forceSimTotals === true;
				if(hasSimOverride){
					if(valorTotal > 0){
						state.lastSimTotal = valorTotal;
					}else if(!(state.lastSimTotal > 0)){
						state.forceSimTotals = false;
					}
				}else{
					state.lastSimTotal = 0;
				}
				const shouldFallback = ((!state.hasVale && !hasSimOverride) || !hasDistrib);
				const effectiveTotal = hasSimOverride
					? ((valorTotal > 0 ? valorTotal : state.lastSimTotal) || fallbackEntrada || valorTotal)
					: (shouldFallback ? (fallbackEntrada || valorTotal) : valorTotal);
				setDistribTotal(effectiveTotal, 'extra-medio');
				updateCostDisplays(custoCx, custoKg);
				updateExtraCard();
				updateMedioCard();
				return effectiveTotal;
			}

			function seedScenarioBase(){
				const precoBase = resolvePrecoBase();
				if(hasExtra()){
					state.extraCustoCx = precoBase;
					state.extraCustoTotal = state.extraCx * state.extraCustoCx;
					state.extraCustoKg = state.extraKg > 0 ? (state.extraCustoTotal / state.extraKg) : 0;
					state.medioCustoKg = state.extraCustoKg / 2;
					state.medioCustoTotal = state.medioKg * state.medioCustoKg;
					state.medioCustoCx = state.medioCx > 0 ? (state.medioCustoTotal / state.medioCx) : 0;
				}else{
					state.extraCustoCx = 0;
					state.extraCustoKg = 0;
					state.extraCustoTotal = 0;
					const base = precoBase > 0 ? (precoBase / 2) : 0;
					state.medioCustoCx = base;
					state.medioCustoTotal = state.medioCx * base;
					state.medioCustoKg = state.medioKg > 0 ? (state.medioCustoTotal / state.medioKg) : 0;
				}
				applyResultado();
			}

			function distributeByTotal(valorTotal){
				const extraKg = state.extraKg;
				const medioKg = state.medioKg;
				if(hasExtra()){
					const divisor = extraKg + (medioKg / 2);
					if(divisor <= 0){
						state.extraCustoTotal = 0;
						state.medioCustoTotal = valorTotal;
						state.medioCustoCx = state.medioCx > 0 ? (state.medioCustoTotal / state.medioCx) : 0;
						state.medioCustoKg = state.medioKg > 0 ? (state.medioCustoTotal / state.medioKg) : 0;
						state.extraCustoCx = 0;
						state.extraCustoKg = 0;
					}else{
						state.extraCustoKg = valorTotal / divisor;
						state.extraCustoTotal = state.extraCustoKg * extraKg;
						state.extraCustoCx = state.extraCx > 0 ? (state.extraCustoTotal / state.extraCx) : 0;
						state.medioCustoKg = state.extraCustoKg / 2;
						state.medioCustoTotal = state.medioCustoKg * medioKg;
						state.medioCustoCx = state.medioCx > 0 ? (state.medioCustoTotal / state.medioCx) : 0;
					}
				}else{
					state.extraCustoCx = 0;
					state.extraCustoKg = 0;
					state.extraCustoTotal = 0;
					state.medioCustoTotal = valorTotal;
					state.medioCustoCx = state.medioCx > 0 ? (valorTotal / state.medioCx) : 0;
					state.medioCustoKg = state.medioKg > 0 ? (valorTotal / state.medioKg) : 0;
				}
				applyResultado();
			}

			function distributeByTotalCx(totalCustoCx){
				const totalCx = (state.extraCx || 0) + (state.medioCx || 0);
				const valorTotal = totalCx > 0 ? (totalCustoCx * totalCx) : 0;
				distributeByTotal(valorTotal);
			}

			function distributeByTotalKg(totalCustoKg){
				const totalKg = (state.extraKg || 0) + (state.medioKg || 0);
				const valorTotal = totalKg > 0 ? (totalCustoKg * totalKg) : 0;
				distributeByTotal(valorTotal);
			}

			function editExtraCustoCx(extraCustoCx){
				if(!hasExtra()){
					logger.warn('Tentativa de editar Extra sem quantidade cadastrada.');
					return;
				}
				state.extraCustoCx = extraCustoCx;
				state.extraCustoTotal = state.extraCx * state.extraCustoCx;
				state.extraCustoKg = state.extraKg > 0 ? (state.extraCustoTotal / state.extraKg) : 0;
				state.medioCustoKg = state.extraCustoKg / 2;
				state.medioCustoTotal = state.medioKg * state.medioCustoKg;
				state.medioCustoCx = state.medioCx > 0 ? (state.medioCustoTotal / state.medioCx) : 0;
				applyResultado();
			}

			function sync(source, value){
				if(state.isUpdating) return;
				state.isUpdating = true;
				try{
					const numVal = Number(value) || 0;
					switch(source){
						case 'initial':
						case 'reset':
							seedScenarioBase();
							break;
						case 'valorTotal':
							distributeByTotal(numVal);
							break;
						case 'totalCustoCx':
							distributeByTotalCx(numVal);
							break;
						case 'totalCustoKg':
							distributeByTotalKg(numVal);
							break;
						case 'extraCustoCx':
							editExtraCustoCx(numVal);
							break;
						default:
							logger.warn('Fonte de sincronização Extra/Médio desconhecida', source);
							break;
					}
				}finally{
					state.isUpdating = false;
				}
			}

			function seedFromAggregate(aggregate){
				if(!aggregate){
					state.extraCodprod = null;
					state.medioCodprod = null;
					updateExtraCard();
					updateMedioCard();
					return;
				}
				state.extraCx = parseLocale(aggregate?.extra?.cx);
				state.extraKg = parseLocale(aggregate?.extra?.kg);
				state.medioCx = parseLocale(aggregate?.medio?.cx);
				state.medioKg = parseLocale(aggregate?.medio?.kg);
				state.extraCodprod = aggregate?.extra?.codprod || null;
				state.medioCodprod = aggregate?.medio?.codprod || null;
				const hasSim = (
					(state.extraCustoTotal > 0 && (state.extraCx > 0 || state.extraKg > 0)) ||
					(state.medioCustoTotal > 0 && (state.medioCx > 0 || state.medioKg > 0))
				);
				const savedVlrtot = parseLocale(window.__SAVED_VLRTOT);
				const savedVlrunit = parseLocale(window.__SAVED_VLRUNIT);
				if(hasSim){
					applyResultado();
					return;
				}
				if(savedVlrtot > 0){
					sync('valorTotal', savedVlrtot);
					return;
				}
				if(savedVlrunit > 0){
					sync('extraCustoCx', savedVlrunit);
					return;
				}
				sync('initial');
			}

			window.updateExtraCard = updateExtraCard;
			window.updateMedioCard = updateMedioCard;
			window.__syncExtraMedio = sync;
			window.__applyExtraMedioResultado = ()=> applyResultado();

			return {
				state,
				sync,
				seedFromAggregate
			};
		}

		async function legacyRefreshValeInterfaces(nunota, options = {}){
			const targetNunota = Number(nunota || state.context?.nunota || 0);
			if(!(targetNunota > 0)){
				return;
			}
			const { skipReload = false } = options;
			logger.info('[VALE REFRESH] Atualizando interfaces para', targetNunota, options);
			try{
				window.__FORCE_NEXT_RELOAD = true;
			}catch(err){
				logger.debug('[VALE REFRESH] Não foi possível sinalizar FORCE_NEXT_RELOAD', err);
			}
			if(!skipReload){
				let silentReloadOk = false;
				if(typeof window.reloadDataSilent === 'function'){
					try{
						await window.reloadDataSilent();
						silentReloadOk = true;
						logger.debug('[VALE REFRESH] reloadDataSilent executado');
					}catch(err){
						logger.warn('[VALE REFRESH] reloadDataSilent falhou', err);
					}
				}
				if(!silentReloadOk && state.actions?.reloadDashboard){
					try{
						await state.actions.reloadDashboard({ scope: ['lista','entrada'], reason: 'vale-refresh' });
					}catch(err){
						logger.warn('[VALE REFRESH] reloadDashboard fallback falhou', err);
					}
				}
			}
			try{
				const modal = doc.getElementById('modalFaturamento');
				const isOpen = modal && modal.style.display && modal.style.display !== 'none';
				if(isOpen && typeof window.openValeResumo === 'function'){
					logger.debug('[VALE REFRESH] Atualizando modal de faturamento');
					await window.openValeResumo(targetNunota, { forceReload: true });
				}
			}catch(err){
				logger.error('[VALE REFRESH] Falha ao atualizar modal de faturamento', err);
			}
			try{
				const previewModal = doc.getElementById('printPreviewModal');
				const isPreviewOpen = previewModal && previewModal.style.display && previewModal.style.display !== 'none';
				if(isPreviewOpen && typeof window.printVale === 'function'){
					logger.debug('[VALE REFRESH] Atualizando preview de impressão');
					await window.printVale();
				}
			}catch(err){
				logger.warn('[VALE REFRESH] Falha ao atualizar preview de impressão', err);
			}
		}

		async function getLoteFromPedido(nunota, sequencia){
			if(!(nunota > 0) || !(sequencia > 0)){
				return null;
			}
			try{
				const rows = Array.isArray(window.__COM_LIST_ROWS) ? window.__COM_LIST_ROWS : [];
				const match = rows.find((row)=> Number(row?.nunota ?? row?.NUNOTA ?? 0) === Number(nunota) && Number(row?.sequencia ?? row?.SEQUENCIA ?? 0) === Number(sequencia));
				if(match){
					const lote = match.codagregacao || match.CODAGREGACAO || match.lote || match.LOTE;
					if(lote){
						logger.debug('[LOTE] Encontrado no cache', lote);
						return lote;
					}
				}
				logger.debug('[LOTE] Buscando lote no backend', { nunota, sequencia });
				const endpoint = `/sankhya/comercial/item/lote/?nunota=${encodeURIComponent(nunota)}&sequencia=${encodeURIComponent(sequencia)}`;
				const data = await services.http.get(endpoint);
				if(data?.lote){
					logger.debug('[LOTE] Encontrado no backend', data.lote);
					return data.lote;
				}
				logger.warn('[LOTE] Não encontrado', { nunota, sequencia });
				return null;
			}catch(err){
				logger.error('[LOTE] Erro ao buscar lote', err);
				return null;
			}
		}

		try{
			window.__getLoteFromPedido = getLoteFromPedido;
		}catch(err){
			logger.debug('Não foi possível expor __getLoteFromPedido', err);
		}

		// Controla o card Distribuição para habilitar o botão Salvar e sincronizar com o vale.
		function initDistribuicaoActions(){
			const dom = {
				btnSave: doc.getElementById('dist-btn-save'),
				btnReset: doc.getElementById('dist-btn-reset'),
				lockIcon: doc.getElementById('lockIconContainer')
			};
			const distState = {
				saving: false,
				resetting: false,
				locked: Boolean(window.__CURRENT_VALE_LOCKED),
				cacheTTL: 60000
			};

			function setLockVisual(flag){
				distState.locked = Boolean(flag);
				if(dom.lockIcon){
					dom.lockIcon.style.display = distState.locked ? 'inline-block' : 'none';
				}
				if(dom.btnSave){
					dom.btnSave.disabled = distState.locked;
					dom.btnSave.style.opacity = distState.locked ? '0.4' : '0.85';
					dom.btnSave.style.cursor = distState.locked ? 'not-allowed' : 'pointer';
					dom.btnSave.title = distState.locked ? 'Vale faturado - edição bloqueada.' : '';
				}
				if(dom.btnReset){
					dom.btnReset.disabled = distState.locked;
					dom.btnReset.style.opacity = distState.locked ? '0.4' : '0.8';
					dom.btnReset.style.cursor = distState.locked ? 'not-allowed' : 'pointer';
					dom.btnReset.title = distState.locked ? 'Vale faturado - edição bloqueada.' : '';
				}
			}

			setLockVisual(distState.locked);
			if(events && typeof events.on === 'function'){
				events.on('vale:lock', (payload)=> setLockVisual(Boolean(payload && payload.locked)));
			}

			function resolvePedidoContext(){
				const card = state.dom.cards.entrada || doc.getElementById('quantidadeInnCard');
				const getNumber = (node, attr)=> Number(node?.dataset?.[attr] || node?.getAttribute?.(`data-${attr}`) || 0);
				const nunota = getNumber(card, 'nunota') || Number(state.context?.nunota || 0);
				const sequencia = getNumber(card, 'seq') || Number(state.context?.sequencia || 0);
				const codprod = getNumber(card, 'codprod') || Number(state.context?.codprod || 0);
				return { card, nunota, sequencia, codprod };
			}

			function resolveNovoPreco(extraState){
				const readTextValue = (selector)=>{
					const node = selector ? doc.querySelector(selector) : null;
					return node ? parseLocaleNumber(node.textContent) : 0;
				};
				const candidates = [
					Number(extraState?.precoBase),
					Number(extraState?.extraCustoCx),
					Number(extraState?.medioCustoCx),
					parseLocaleNumber(state.dom.cards.entrada?.dataset?.precobase),
					readTextValue('#extraCustoCxDisplay'),
					readTextValue('#entPrecoCxDisplay')
				];
				for(const candidate of candidates){
					const num = Number(candidate);
					if(Number.isFinite(num) && num > 0){
						return num;
					}
				}
				return 0;
			}

			function round(value, decimals = 4){
				const factor = Math.pow(10, decimals);
				const num = Number(value);
				if(!Number.isFinite(num)) return 0;
				return Math.round(num * factor) / factor;
			}

			function setButtonBusy(button, label){
				if(!button) return ()=>{};
				const original = button.textContent;
				button.disabled = true;
				button.textContent = label;
				button.classList.add('is-loading');
				return ()=>{
					button.classList.remove('is-loading');
					button.textContent = original;
					setLockVisual(distState.locked);
				};
			}

			async function postJsonCompat(url, payload){
				if(typeof window.__postJSON === 'function'){
					return window.__postJSON(url, payload);
				}
				const body = await services.http.post(url, payload);
				return { ok: true, body };
			}

			async function saveDistribuicao(){
				if(distState.saving) return;
				if(distState.locked){
					utils.toast('Vale faturado - não é possível salvar.', 'warning');
					return;
				}
				const pedidoCtx = resolvePedidoContext();
				if(!(pedidoCtx.nunota > 0) || !(pedidoCtx.sequencia > 0)){
					utils.toast('Selecione um vale da lista antes de salvar.', 'warning');
					return;
				}
				if(!extraMedio || !extraMedio.state || extraMedio.state.isUpdating){
					utils.toast('Distribuição ainda está sincronizando. Aguarde um instante.', 'warning');
					return;
				}
				const stateExtra = extraMedio.state;
				const hasKg = Number(stateExtra.extraKg || 0) > 0 || Number(stateExtra.medioKg || 0) > 0;
				if(!hasKg){
					utils.toast('Não há quantidades Extra/Médio para salvar.', 'warning');
					return;
				}
				distState.saving = true;
				const release = setButtonBusy(dom.btnSave, 'Validando...');
				try{
					if(dom.btnSave) dom.btnSave.textContent = 'Buscando lote...';
					const lote = await getLoteFromPedido(pedidoCtx.nunota, pedidoCtx.sequencia);
					if(!lote){
						utils.toast('Não foi possível determinar o lote do produto.', 'error');
						return;
					}
					const codprodInNatura = pedidoCtx.codprod || Number(stateExtra.codprod || 0) || Number(state.context?.codprod || 0);
					if(!(codprodInNatura > 0)){
						utils.toast('Produto IN NATURA não identificado.', 'error');
						return;
					}
					const novoPrecoBase = resolveNovoPreco(stateExtra);
					if(!(novoPrecoBase > 0)){
						utils.toast('Informe o preço base (R$/cx) antes de salvar.', 'warning');
						return;
					}
					if(dom.btnSave) dom.btnSave.textContent = 'Preparando vale...';
					const headerRes = await postJsonCompat('/sankhya/comercial/vale/verificar_ou_criar_cabecalho/', {
						nunota_11: pedidoCtx.nunota,
						codprod: codprodInNatura,
						novo_preco: novoPrecoBase
					});
					if(!headerRes || headerRes.ok === false || headerRes?.body?.ok === false){
						const errMsg = headerRes?.body?.error || headerRes?.error || 'Falha ao preparar o Vale.';
						throw new Error(errMsg);
					}
					try{ window.__FORCE_NEXT_RELOAD = true; }
					catch(_err){ /* noop */ }
					const payload = {
						nunota_pedido: pedidoCtx.nunota,
						sequencia_pedido: pedidoCtx.sequencia,
						codprod_in_natura: codprodInNatura,
						lote,
						extra_kg: round(stateExtra.extraKg, 4),
						extra_vlrunit_kg: round(stateExtra.extraCustoKg, 4),
						medio_kg: round(stateExtra.medioKg, 4),
						medio_vlrunit_kg: round(stateExtra.medioCustoKg, 4)
					};
					if(dom.btnSave) dom.btnSave.textContent = 'Sincronizando...';
					const syncRes = await postJsonCompat('/sankhya/comercial/vale/sync/', payload);
					if(!syncRes || syncRes.ok === false || syncRes?.body?.ok === false){
						const errMsg = syncRes?.body?.error || syncRes?.error || 'Falha ao salvar no Vale.';
						throw new Error(errMsg);
					}
					const responseBody = syncRes.body || syncRes;
					utils.toast('Salvo no Vale com sucesso.', 'success');
					const consolidation = responseBody.pedido_consolidation;
					if(consolidation){
						if(consolidation.success){
							const totalConsolidado = consolidation.total_consolidated || 0;
							const msg = `PEDIDO atualizado! Total consolidado: ${utils.formatMoney(totalConsolidado)}`;
							utils.toast(msg, 'success');
						}else if(consolidation.error){
							utils.toast(`Vale salvo, mas consolidação falhou: ${consolidation.error}`, 'warning');
						}
					}
					if(responseBody.nunota_vale){
						try{
							window.__CURRENT_VALE_NUNOTA = responseBody.nunota_vale;
							window.__CURRENT_VALE_NUNOTA_TOP13 = responseBody.nunota_vale;
							if(typeof window.__refreshValeUI === 'function'){
								window.__refreshValeUI(responseBody.nunota_vale);
							}
							const badge = doc.getElementById('entBadgeVale13');
							if(badge){
								badge.textContent = `Vale ${responseBody.nunota_vale}`;
								badge.style.display = '';
							}
						}catch(err){
							logger.warn('Falha ao atualizar indicadores do vale', err);
						}
						try{
							const rows = Array.isArray(window.__COM_LIST_ROWS) ? window.__COM_LIST_ROWS : [];
							const match = rows.find((row)=> Number(row?.nunota ?? row?.NUNOTA ?? 0) === Number(pedidoCtx.nunota) && Number(row?.sequencia ?? row?.SEQUENCIA ?? 0) === Number(pedidoCtx.sequencia));
							if(match){
								match.nunota_13 = responseBody.nunota_vale;
								match.NUNOTA_13 = responseBody.nunota_vale;
							}
						}catch(err){
							logger.debug('Falha ao atualizar cache da lista', err);
						}
						if(typeof window.__invalidateValeDistribCache === 'function'){
							window.__invalidateValeDistribCache(responseBody.nunota_vale);
						}
					}
					await legacyRefreshValeInterfaces(pedidoCtx.nunota);
				}catch(err){
					logger.error('Erro ao salvar distribuição no vale', err);
					utils.toast(err?.message || 'Erro ao salvar o Vale.', 'error');
				}finally{
					distState.saving = false;
					release();
				}
			}

			if(dom.btnSave){
				dom.btnSave.addEventListener('click', (ev)=>{
					ev.preventDefault();
					saveDistribuicao();
				});
			}

			async function resetDistribuicao(){
				if(distState.resetting) return;
				if(distState.locked){
					utils.toast('Vale faturado - não é possível zerar.', 'warning');
					return;
				}
				const pedidoCtx = resolvePedidoContext();
				if(!(pedidoCtx.nunota > 0) || !(pedidoCtx.sequencia > 0)){
					utils.toast('Selecione um vale da lista antes de zerar.', 'warning');
					return;
				}
				if(!(pedidoCtx.codprod > 0)){
					utils.toast('Produto IN NATURA não identificado.', 'warning');
					return;
				}
				const confirmMsg = 'Deseja zerar a negociação? Os produtos Extra/Médio serão removidos do Vale (TOP 13) e os valores serão recalculados com o preço inicial.';
				if(typeof window.confirm === 'function' && !window.confirm(confirmMsg)){
					return;
				}
				distState.resetting = true;
				const release = setButtonBusy(dom.btnReset, 'Processando...');
				let deletedCount = 0;
				try{
					try{
						if(dom.btnReset) dom.btnReset.textContent = 'Removendo do Vale...';
						const clearRes = await postJsonCompat('/sankhya/comercial/vale/clear/', {
							nunota_pedido: pedidoCtx.nunota,
							codprod_in_natura: pedidoCtx.codprod
						});
						const clearBody = clearRes?.body || clearRes;
						if(clearBody?.ok === false){
							throw new Error(clearBody?.error || 'Falha ao remover itens do Vale.');
						}
						deletedCount = Number(clearBody?.deleted_count || 0);
						const valeCleared = clearBody?.nunota_vale || window.__CURRENT_VALE_NUNOTA_TOP13 || window.__CURRENT_VALE_NUNOTA;
						if(valeCleared && typeof window.__invalidateValeDistribCache === 'function'){
							window.__invalidateValeDistribCache(valeCleared);
						}
					}catch(err){
						logger.warn('[DIST][RESET] Falha ao remover produtos do Vale', err);
						utils.toast('Não foi possível remover os produtos do Vale (TOP 13). Continuando com o reset local.', 'warning');
					}
					if(dom.btnReset) dom.btnReset.textContent = 'Zerando simulação...';
					const resetRes = await postJsonCompat('/sankhya/comercial/dist/reset/', {
						nunota: pedidoCtx.nunota,
						sequencia: pedidoCtx.sequencia
					});
					const resetBody = resetRes?.body || resetRes;
					if(resetBody?.ok === false){
						throw new Error(resetBody?.error || 'Falha ao zerar a negociação.');
					}
					try{
						window.__SAVED_VLRTOT = 0;
						window.__SAVED_VLRUNIT = 0;
					}catch(err){
						logger.debug('[DIST][RESET] Não foi possível limpar os totais salvos', err);
					}
					try{
						if(extraMedio && typeof extraMedio.sync === 'function'){
							extraMedio.sync('reset');
						}else if(typeof window.__syncExtraMedio === 'function'){
							window.__syncExtraMedio('reset');
						}
					}catch(err){
						logger.warn('[DIST][RESET] Falha ao sincronizar cartões Extra/Médio', err);
					}
					try{
						const rows = Array.isArray(window.__COM_LIST_ROWS) ? window.__COM_LIST_ROWS : [];
						const match = rows.find((row)=> Number(row?.nunota ?? row?.NUNOTA ?? 0) === Number(pedidoCtx.nunota)
							&& Number(row?.sequencia ?? row?.SEQUENCIA ?? 0) === Number(pedidoCtx.sequencia));
						if(match){
							match.vlrtot = 0;
							match.VLRTOT = 0;
							match.vlrunit = 0;
							match.VLRUNIT = 0;
							if(Object.prototype.hasOwnProperty.call(match, 'valor_total')){
								match.valor_total = 0;
							}
						}
					}catch(err){
						logger.debug('[DIST][RESET] Não foi possível atualizar cache da lista', err);
					}
					try{
						window.dispatchEvent(new CustomEvent('dist:reset', {
							detail: { nunota: pedidoCtx.nunota, sequencia: pedidoCtx.sequencia }
						}));
					}catch(err){
						logger.debug('[DIST][RESET] Falha ao disparar evento dist:reset', err);
					}
					try{
						await legacyRefreshValeInterfaces(pedidoCtx.nunota);
					}catch(err){
						logger.warn('[DIST][RESET] Falha ao atualizar interfaces do Vale', err);
					}
					const successMsg = deletedCount > 0
						? `Negociação zerada. ${deletedCount} produto(s) removido(s) do Vale.`
						: 'Negociação zerada.';
					utils.toast(successMsg, 'success');
				}catch(err){
					logger.error('Erro ao zerar a negociação', err);
					utils.toast(err?.message || 'Erro ao zerar a negociação.', 'error');
				}finally{
					distState.resetting = false;
					release();
				}
			}

			if(dom.btnReset){
				dom.btnReset.addEventListener('click', (ev)=>{
					ev.preventDefault();
					resetDistribuicao();
				});
			}

			return { setLocked: setLockVisual };
		}

		// Atualiza o contexto compartilhado preservando valores anteriores.
		function mutateContext(next){
			state.context = Object.assign({}, state.context, next);
		}

		// Controla estado visual de carregamento baseado em chaves simbólicas.
		function setLoading(key, flag){
			if(flag){ state.loadingFlags.add(key); }
			else { state.loadingFlags.delete(key); }
			state.dom.root?.classList.toggle('dashboard-loading', state.loadingFlags.size > 0);
		}

		const VALID_REFRESH_SCOPE = new Set(['lista','entrada','classificacao','vale','distribuicao']);
		// Mantemos o vale fora do escopo padrão para impedir aberturas automáticas do modal.
		const DEFAULT_REFRESH_SCOPE = Object.freeze(['lista','entrada','classificacao','distribuicao']);
		const DASHBOARD_CLEAR_TEXT_TARGETS = Object.freeze([
			'#supplierName','#classFabricanteName','#entPartner','#entProduct',
			'#rfMargem','#costCxDisplay','#costKgDisplay','#totalValueDisplay',
			'#kpiAproveitamento','#kpiRendimento','#kpiEstoque','#kpiEstoqueApprox',
			'#gPct','#gaugeLabel','#resInnKg','#resInnCx','#resClassKg','#resClassCx',
			'#resInservKg','#resInservCx','#quantidadeInn','#pesoInnDisplay','#totalInn',
			'#pesoClassificadoDisplay','#entPrecoCxDisplay','#entPrecoKg','#entTotalIn','#sim-sum-cx',
			'#sim-sum-unit','#sim-total-geral','#extraCustoCxDisplay','#histMarginMeta'
		]);
		const DASHBOARD_CLEAR_INPUTS = Object.freeze([
			'#sim-extra-qty','#sim-extra-unit','#sim-extra-total',
			'#sim-medio-qty','#sim-medio-unit','#sim-medio-total',
			'#entPrecoCxInput','#pesoClassificadoInput'
		]);
		const DASHBOARD_DATASET_KEYS = Object.freeze(['nunota','seq','codprod','lote','cx','kgIn','unit','pesoPorCx']);

		function normalizeRefreshScope(scope){
			if(!scope) return DEFAULT_REFRESH_SCOPE;
			const arr = Array.isArray(scope) ? scope : [scope];
			const normalized = arr.map((entry)=> String(entry || '').trim().toLowerCase()).filter((name)=> VALID_REFRESH_SCOPE.has(name));
			return normalized.length ? normalized : DEFAULT_REFRESH_SCOPE;
		}

		const CLASSIFICATION_CACHE_TTL = 120000; // TTL (ms) para reaproveitar resumos em cache.
		const CLASSIFICATION_DEFAULT_KG_PER_CX = 20; // Peso padrão por caixa usado como fallback.

		// Converte textos (pt-BR) em números seguros usados nos cálculos.
		function parseLocaleNumber(value){
			if(value === null || value === undefined) return 0;
			if(typeof value === 'number') return Number.isFinite(value) ? value : 0;
			const cleaned = String(value).trim()
				.replace(/[^0-9,\.\-]/g, '')
				.replace(/\.(?=\d{3}(\D|$))/g, '')
				.replace(',', '.');
			const num = Number(cleaned);
			return Number.isFinite(num) ? num : 0;
		}

		// Formata inteiros com separador BR para exibição rápida.
		function formatInt(value){
			return Number(value || 0).toLocaleString('pt-BR');
		}

		function updateDistQuantityCardDisplay({ kg = 0, cx = 0 } = {}){
			// Mantém o card "Qtde Total" sincronizado com os valores classificados.
			const card = doc.getElementById('distMini3');
			if(!card) return;
			const kgEl = card.querySelector('.qty-top .dist-value');
			const cxEl = card.querySelector('.qty-bottom .dist-value');
			const safeKg = Number.isFinite(kg) ? kg : 0;
			const safeCx = Number.isFinite(cx) ? cx : 0;
			if(kgEl) kgEl.textContent = formatInt(Math.round(safeKg));
			if(cxEl){
				const decimals = Math.abs(safeCx) >= 100 ? 0 : 2;
				const formatted = utils.formatDecimal(safeCx, decimals) || '0';
				cxEl.textContent = formatted;
			}
		}

		function updateQtysFromClass(cx, kg){
			updateDistQuantityCardDisplay({ kg, cx });
		}

		// Controla o card de simulação (EXTRA/MÉDIO) reaproveitando regras do legado.
		function createSimulationCard(){
			const domSim = {
				sections: {
					extra: {
						qty: doc.getElementById('sim-extra-qty'),
						unit: doc.getElementById('sim-extra-unit'),
						total: doc.getElementById('sim-extra-total')
					},
					medio: {
						qty: doc.getElementById('sim-medio-qty'),
						unit: doc.getElementById('sim-medio-unit'),
						total: doc.getElementById('sim-medio-total')
					}
				},
				summary: {
					total: doc.getElementById('sim-total-geral'),
					cx: doc.getElementById('sim-sum-cx'),
					unit: doc.getElementById('sim-sum-unit')
				},
				quebra: doc.getElementById('sim-quebra'),
				buttons: {
					apply: doc.getElementById('sim-btn-apply'),
					clear: doc.getElementById('sim-btn-clear')
				}
			};
			if(!domSim.sections.extra.qty || !domSim.sections.medio.qty){
				window.__setSimulationButtonsDisabled = ()=>undefined;
				window.__applySimulacaoFromItem = ()=>undefined;
				return null;
			}
			const simState = {
				isPatching: false,
				busy: false,
				autoSaving: false,
				lastEdited: { extra: null, medio: null },
				lastPersisted: null,
				cache: null
			};
			const quantizeValue = (value, precision = 4)=>{
				if(!Number.isFinite(value)) return 0;
				const factor = 10 ** precision;
				return Math.round(value * factor) / factor;
			};
			const getDistState = ()=> window.__DIST_EXTRA_MEDIO_STATE || null;
			const enableSimOverride = (total)=>{
				const distState = getDistState();
				if(!distState) return;
				distState.forceSimTotals = true;
				distState.lastSimTotal = Number.isFinite(total) ? quantizeValue(total, 2) : 0;
			};
			const disableSimOverride = ({ refresh = false } = {})=>{
				const distState = getDistState();
				if(!distState) return;
				distState.forceSimTotals = false;
				distState.lastSimTotal = 0;
				if(refresh && typeof window.__applyExtraMedioResultado === 'function'){
					try{ window.__applyExtraMedioResultado(); }
					catch(err){ logger?.debug?.('Falha ao reaplicar Extra/Médio após limpar simulação', err); }
				}
			};
			const fieldMap = {
				sim_qtd1: 'ad_simqtd1',
				sim_vlr1: 'ad_simvlr1',
				sim_qtd2: 'ad_simqtd2',
				sim_vlr2: 'ad_simvlr2',
				ad_simqtddesc: 'ad_simqtddesc'
			};
			const formatQty = (value)=> Number.isFinite(value) ? utils.formatDecimal(value, Math.abs(value) >= 1 ? 2 : 3) : '';
			const formatMoney = (value)=> Number.isFinite(value) ? utils.formatMoney(value) : '';
			const parseValue = (value)=>{
				const num = parseLocaleNumber(value);
				return Number.isFinite(num) ? num : NaN;
			};
			const runPatched = (fn)=>{
				simState.isPatching = true;
				try{ fn(); }
				finally { simState.isPatching = false; }
			};
			const setInputValue = (input, value, formatter)=>{
				if(!input) return;
				runPatched(()=>{ input.value = Number.isFinite(value) ? formatter(value) : ''; });
			};
			const setSummaryValue = (node, formatter)=>{
				if(node) node.textContent = formatter();
			};
			const getSectionValues = (section)=>{
				const refs = domSim.sections[section];
				return {
					qty: parseValue(refs.qty.value),
					unit: parseValue(refs.unit.value),
					total: parseValue(refs.total.value)
				};
			};
			const getFormValues = ()=>{
				return {
					extra: getSectionValues('extra'),
					medio: getSectionValues('medio'),
					quebra: parseValue(domSim.quebra?.value)
				};
			};
			const roundTo = (value, precision = 2)=>{
				if(!Number.isFinite(value)) return 0;
				const factor = 10 ** precision;
				return Math.round(value * factor) / factor;
			};
			// Mantém snapshot persistido e dispara autosave silencioso ao mudar quantidade/valor.
			const normalizeSimValues = (values = {})=>{
				const safe = (num, precision)=> Number.isFinite(num) ? roundTo(num, precision) : 0;
				return {
					extra: {
						qty: safe(values.extra?.qty, 4),
						total: safe(values.extra?.total, 2)
					},
					medio: {
						qty: safe(values.medio?.qty, 4),
						total: safe(values.medio?.total, 2)
					},
					quebra: safe(values.quebra, 4)
				};
			};
			const rememberPersistedValues = (values)=>{
				simState.lastPersisted = normalizeSimValues(values);
			};
			const hasSimChangesPending = (values)=>{
				const normalized = normalizeSimValues(values);
				const previous = simState.lastPersisted;
				if(!previous) return { changed: true };
				const diff = (curr, prevVal, epsilon)=> Math.abs(curr - prevVal) > epsilon;
				const changed = diff(normalized.extra.qty, previous.extra?.qty ?? 0, 0.0001)
					|| diff(normalized.extra.total, previous.extra?.total ?? 0, 0.01)
					|| diff(normalized.medio.qty, previous.medio?.qty ?? 0, 0.0001)
					|| diff(normalized.medio.total, previous.medio?.total ?? 0, 0.01)
					|| diff(normalized.quebra, previous.quebra ?? 0, 0.0001);
				return { changed };
			};
			const autoPersistSimulation = debounce(async (meta = {})=>{
				if(simState.busy || simState.autoSaving) return;
				const context = resolveSimContext();
				if(!context?.nunota) return;
				const values = getFormValues();
				const { changed } = hasSimChangesPending(values);
				if(!changed) return;
				simState.autoSaving = true;
				try{
					const applied = await persistSimulation(values, { quiet: true });
					if(applied){
						rememberPersistedValues(values);
						if(logger && typeof logger.debug === 'function'){
							logger.debug('[Simulação] Auto-save disparado', meta);
						}
					}
				}catch(err){
					if(logger && typeof logger.warn === 'function'){
						logger.warn('[Simulação] Auto-save falhou', err);
					}
				}finally{
					simState.autoSaving = false;
				}
			}, 500);
			const updateSummary = ()=>{
				const values = getFormValues();
				const sumCx = (Number.isFinite(values.extra.qty) ? values.extra.qty : 0) + (Number.isFinite(values.medio.qty) ? values.medio.qty : 0);
				const sumTotal = (Number.isFinite(values.extra.total) ? values.extra.total : 0) + (Number.isFinite(values.medio.total) ? values.medio.total : 0);
				const weightedUnit = sumCx > 0 ? (sumTotal / sumCx) : (()=>{
					const units = [values.extra.unit, values.medio.unit].filter((num)=> Number.isFinite(num) && num > 0);
					return units.length ? (units.reduce((acc,val)=> acc + val, 0) / units.length) : 0;
				})();
				setSummaryValue(domSim.summary.cx, ()=> Number.isFinite(sumCx) && sumCx > 0 ? formatQty(sumCx) : '0');
				setSummaryValue(domSim.summary.total, ()=> formatMoney(sumTotal || 0));
				setSummaryValue(domSim.summary.unit, ()=> formatMoney(weightedUnit || 0));
				simState.cache = values;
				window.__DIST_SIM_CACHE = {
					extra: { cx: Number.isFinite(values.extra.qty) ? values.extra.qty : 0, total: Number.isFinite(values.extra.total) ? values.extra.total : 0 },
					medio: { cx: Number.isFinite(values.medio.qty) ? values.medio.qty : 0, total: Number.isFinite(values.medio.total) ? values.medio.total : 0 },
					quebra: Number.isFinite(values.quebra) ? values.quebra : 0,
					total: sumTotal,
					updatedAt: Date.now()
				};
			};
			const markAuto = ()=>{}; // Placeholder mantendo compatibilidade com o legado.
			const solveSection = (section)=>{
				const refs = domSim.sections[section];
				const q = parseValue(refs.qty.value);
				const u = parseValue(refs.unit.value);
				const t = parseValue(refs.total.value);
				const hasQ = Number.isFinite(q) && q !== 0;
				const hasU = Number.isFinite(u) && u !== 0;
				const hasT = Number.isFinite(t) && t !== 0;
				const count = (hasQ?1:0) + (hasU?1:0) + (hasT?1:0);
				if(count < 2) return;
				if(count === 2){
					if(!hasT && hasQ && hasU){ setInputValue(refs.total, q * u, formatMoney); markAuto(refs.total, true); return; }
					if(!hasU && hasQ && hasT && q){ setInputValue(refs.unit, t / q, formatMoney); markAuto(refs.unit, true); return; }
					if(!hasQ && hasU && hasT && u){ setInputValue(refs.qty, t / u, formatQty); markAuto(refs.qty, true); }
					return;
				}
				const last = simState.lastEdited[section];
				if(last === 'qty' || last === 'unit'){
					setInputValue(refs.total, (hasQ ? q : 0) * (hasU ? u : 0), formatMoney);
					markAuto(refs.total, true);
					return;
				}
				if(last === 'total'){
					if(hasQ && q){ setInputValue(refs.unit, t / q, formatMoney); markAuto(refs.unit, true); return; }
					if(hasU && u){ setInputValue(refs.qty, t / u, formatQty); markAuto(refs.qty, true); return; }
				}
				setInputValue(refs.total, (hasQ ? q : 0) * (hasU ? u : 0), formatMoney);
				markAuto(refs.total, true);
			};
			const handleInput = (section, field)=>()=>{
				if(simState.isPatching) return;
				simState.lastEdited[section] = field;
				solveSection(section);
				updateSummary();
			};
			const buildBlurHandler = (section, field, formatter, { autoSave = false } = {})=>{
				// Normaliza o campo ao sair do foco e, quando necessário, agenda o salvamento automático.
				return ()=>{
					const refs = domSim.sections[section];
					const input = refs[field];
					const val = parseValue(input.value);
					setInputValue(input, val, formatter);
					solveSection(section);
					updateSummary();
					if(autoSave){
						autoPersistSimulation({ section, field });
					}
				};
			};
			const bindSelectAllBehavior = ()=>{
				// Facilita a edição selecionando todo o conteúdo ao focar qualquer campo do card.
				const targets = [
					domSim.sections.extra.qty,
					domSim.sections.extra.unit,
					domSim.sections.extra.total,
					domSim.sections.medio.qty,
					domSim.sections.medio.unit,
					domSim.sections.medio.total,
					domSim.quebra
				].filter(Boolean);
				targets.forEach((input)=>{
					if(input.dataset.selectAllBound === 'true') return;
					input.dataset.selectAllBound = 'true';
					input.addEventListener('focus', ()=>{
						requestAnimationFrame(()=>{
							try{ input.select(); }
							catch(_err){ /* seleção pode falhar em campos inativos */ }
						});
					});
					input.addEventListener('mouseup', (ev)=>{
						ev.preventDefault();
						input.select();
					});
				});
			};
			['extra','medio'].forEach((section)=>{
				const refs = domSim.sections[section];
				refs.qty.addEventListener('input', handleInput(section,'qty'));
				refs.unit.addEventListener('input', handleInput(section,'unit'));
				refs.total.addEventListener('input', handleInput(section,'total'));
				refs.qty.addEventListener('blur', buildBlurHandler(section,'qty', formatQty, { autoSave: true }));
				refs.unit.addEventListener('blur', buildBlurHandler(section,'unit', formatMoney));
				refs.total.addEventListener('blur', buildBlurHandler(section,'total', formatMoney, { autoSave: true }));
			});
			bindSelectAllBehavior();
			if(domSim.quebra){
				domSim.quebra.addEventListener('blur', ()=>{
					const val = parseValue(domSim.quebra.value);
					setInputValue(domSim.quebra, val, formatQty);
					updateSummary();
				});
			}
			const resolveSimContext = ()=>{
				const card = state.dom.cards.entrada || doc.getElementById('quantidadeInnCard');
				if(!card) return { nunota: null, sequencia: null, codagregacao: '', sequencias: [] };
				const nunota = Number(card.dataset?.nunota || card.getAttribute('data-nunota') || 0) || null;
				const sequencia = Number(card.dataset?.seq || card.getAttribute('data-seq') || 0) || null;
				const codagregacao = (card.dataset?.lote || card.dataset?.codagregacao || '').trim();
				const seqSet = new Set();
				if(sequencia) seqSet.add(sequencia);
				const rows = Array.isArray(window.__COM_LIST_ROWS) ? window.__COM_LIST_ROWS : [];
				rows.forEach((row)=>{
					const rowNunota = Number(row?.nunota ?? row?.NUNOTA ?? 0);
					if(rowNunota !== nunota) return;
					const rowLote = String(row?.codagregacao ?? row?.CODAGREGACAO ?? row?.lote ?? '').trim();
					if(codagregacao && rowLote !== codagregacao) return;
					const seqVal = Number(row?.sequencia ?? row?.SEQUENCIA ?? 0);
					if(Number.isFinite(seqVal) && seqVal > 0) seqSet.add(seqVal);
				});
				return {
					nunota,
					sequencia,
					codagregacao,
					sequencias: Array.from(seqSet).filter(Boolean)
				};
			};
			const syncCachedRows = (context, fields)=>{
				const rows = Array.isArray(window.__COM_LIST_ROWS) ? window.__COM_LIST_ROWS : [];
				if(!rows.length) return;
				const seqSet = new Set(context.sequencias.length ? context.sequencias : (context.sequencia ? [context.sequencia] : []));
				rows.forEach((row)=>{
					const rowNunota = Number(row?.nunota ?? row?.NUNOTA ?? 0);
					if(rowNunota !== context.nunota) return;
					if(context.codagregacao){
						const rowLote = String(row?.codagregacao ?? row?.CODAGREGACAO ?? row?.lote ?? '').trim();
						if(rowLote !== context.codagregacao) return;
					}else if(seqSet.size){
						const rowSeq = Number(row?.sequencia ?? row?.SEQUENCIA ?? 0);
						if(!seqSet.has(rowSeq)) return;
					}
					Object.entries(fields).forEach(([apiField, val])=>{
						const rowField = fieldMap[apiField];
						if(!rowField) return;
						row[rowField] = val;
						if(!row.__simFields || typeof row.__simFields !== 'object'){
							row.__simFields = {};
						}
						row.__simFields[rowField] = val;
					});
				});
			};
			const postSimulationPayload = async (payload)=>{
				if(typeof window.__postJSON === 'function'){
					const response = await window.__postJSON('/sankhya/comercial/dist/save/', payload);
					if(!response || response.ok === false){
						throw new Error(response?.body?.error || response?.error || 'Erro ao salvar simulação.');
					}
					return response.body || response;
				}
				return services.http.post('/sankhya/comercial/dist/save/', payload);
			};
			const persistSimulation = async (values, { forceZero = false, quiet = false } = {})=>{
				const context = resolveSimContext();
				if(!context.nunota){
					if(!quiet) utils.toast('Selecione um item antes de salvar a simulação.', 'warning');
					return null;
				}
				const payload = { nunota: context.nunota };
				if(context.sequencia) payload.sequencia = context.sequencia;
				if(context.sequencias.length) payload.sequencias = context.sequencias;
				if(context.codagregacao) payload.codagregacao = context.codagregacao;
				const applied = {};
				const pushField = (key, value, precision)=>{
					if(forceZero){
						payload[key] = 0;
						applied[key] = 0;
						return;
					}
					if(!Number.isFinite(value)) return;
					payload[key] = roundTo(value, precision);
					applied[key] = payload[key];
				};
				pushField('sim_qtd1', values.extra.qty, 4);
				pushField('sim_vlr1', values.extra.total, 2);
				pushField('sim_qtd2', values.medio.qty, 4);
				pushField('sim_vlr2', values.medio.total, 2);
				pushField('ad_simqtddesc', values.quebra, 4);
				if(Object.keys(applied).length === 0){
					if(!quiet) utils.toast('Preencha os campos da simulação antes de aplicar.', 'warning');
					return null;
				}
				await postSimulationPayload(payload);
				syncCachedRows(context, applied);
				return applied;
			};
			const setButtonsDisabled = (disabled, reason = '')=>{
				['apply','clear'].forEach((key)=>{
					const btn = domSim.buttons[key];
					if(!btn) return;
					btn.disabled = !!disabled;
					btn.style.opacity = disabled ? '0.5' : '0.85';
					if(disabled && reason){
						btn.dataset.disabledReason = reason;
						btn.title = reason;
					}else{
						delete btn.dataset.disabledReason;
						btn.title = '';
					}
				});
			};
			window.__setSimulationButtonsDisabled = setButtonsDisabled;
			const withButtonBusy = (button, label)=>{
				if(!button) return ()=>{};
				const original = button.textContent;
				button.disabled = true;
				button.textContent = label;
				button.classList.add('is-loading');
				return ()=>{
					button.disabled = false;
					button.textContent = original;
					button.classList.remove('is-loading');
				};
			};
			const handleApply = async ()=>{
				if(simState.busy) return;
				simState.busy = true;
				const release = withButtonBusy(domSim.buttons.apply, 'Aplicando...');
				try{
					const values = getFormValues();
					const totalGeral = (Number.isFinite(values.extra.total) ? values.extra.total : 0) + (Number.isFinite(values.medio.total) ? values.medio.total : 0);
					if(!(totalGeral > 0)){
						utils.toast('Total geral inválido. Preencha a simulação antes de aplicar.', 'warning');
						return;
					}
					if(typeof window.__setDistribTotal === 'function'){
						try{ window.__setDistribTotal(totalGeral, { source: 'simulacao-aplicar', allowUI: true, syncInput: true }); }
						catch(err){ logger.debug('Falha ao sincronizar distribuição via simulação', err); }
					}
					if(typeof window.__syncExtraMedio === 'function'){
						enableSimOverride(totalGeral);
						try{ window.__syncExtraMedio('valorTotal', totalGeral); }
						catch(err){
							disableSimOverride();
							logger.debug('Falha ao recalcular Extra/Médio após simulação', err);
						}
					}
					utils.toast('Simulação aplicada!', 'success');
				}catch(err){
					logger.error('Erro ao aplicar simulação', err);
					utils.toast(err?.message || 'Erro ao aplicar simulação.', 'error');
				}finally{
					simState.busy = false;
					release();
				}
			};
			const handleClear = async ()=>{
				if(simState.busy) return;
				if(!window.confirm('Tem certeza que deseja limpar a simulação?')) return;
				simState.busy = true;
				const release = withButtonBusy(domSim.buttons.clear, 'Limpando...');
				try{
					['extra','medio'].forEach((section)=>{
						const refs = domSim.sections[section];
						setInputValue(refs.qty, NaN, formatQty);
						setInputValue(refs.unit, NaN, formatMoney);
						setInputValue(refs.total, NaN, formatMoney);
					});
					setInputValue(domSim.quebra || null, NaN, formatQty);
					updateSummary();
					disableSimOverride({ refresh: true });
					const clearedValues = { extra: { qty: 0, unit: 0, total: 0 }, medio: { qty: 0, unit: 0, total: 0 }, quebra: 0 };
					const applied = await persistSimulation(clearedValues, { forceZero: true, quiet: false });
					if(applied){
						rememberPersistedValues(clearedValues);
					}
					utils.toast('Simulação limpa no banco.', 'success');
				}catch(err){
					logger.error('Erro ao limpar simulação', err);
					utils.toast(err?.message || 'Erro ao limpar simulação.', 'error');
				}finally{
					simState.busy = false;
					release();
				}
			};
			const applyFromItem = (item)=>{
				if(!item){
					['extra','medio'].forEach((section)=>{
						const refs = domSim.sections[section];
						setInputValue(refs.qty, NaN, formatQty);
						setInputValue(refs.unit, NaN, formatMoney);
						setInputValue(refs.total, NaN, formatMoney);
					});
					setInputValue(domSim.quebra || null, NaN, formatQty);
					updateSummary();
					disableSimOverride({ refresh: true });
					simState.lastPersisted = null;
					return;
				}
				const resolveField = (...keys)=>{
					for(const key of keys){
						const raw = item[key];
						if(raw === undefined || raw === null || raw === '') continue;
						const num = parseValue(raw);
						if(Number.isFinite(num)) return num;
					}
					return NaN;
				};
				setInputValue(domSim.sections.extra.qty, resolveField('ad_simqtd1','AD_SIMQTD1'), formatQty);
				setInputValue(domSim.sections.extra.unit, NaN, formatMoney);
				setInputValue(domSim.sections.extra.total, resolveField('ad_simvlr1','AD_SIMVLR1'), formatMoney);
				setInputValue(domSim.sections.medio.qty, resolveField('ad_simqtd2','AD_SIMQTD2'), formatQty);
				setInputValue(domSim.sections.medio.unit, NaN, formatMoney);
				setInputValue(domSim.sections.medio.total, resolveField('ad_simvlr2','AD_SIMVLR2'), formatMoney);
				setInputValue(domSim.quebra || null, resolveField('ad_simqtddesc','AD_SIMQTDDESC'), formatQty);
				solveSection('extra');
				solveSection('medio');
				updateSummary();
				rememberPersistedValues(getFormValues());
			};
			if(domSim.buttons.apply){
				domSim.buttons.apply.addEventListener('click', (ev)=>{
					ev.preventDefault();
					handleApply();
				});
			}
			if(domSim.buttons.clear){
				domSim.buttons.clear.addEventListener('click', (ev)=>{
					ev.preventDefault();
					handleClear();
				});
			}
			updateSummary();
			setButtonsDisabled(false);
			const api = {
				applyFromItem,
				reset: ({ silent } = {})=>{
					applyFromItem(null);
					if(!silent) updateSummary();
				}
			};
			window.__applySimulacaoFromItem = applyFromItem;
			return api;
		}

		// Extrai valores atuais dos cards de entrada (caixas, kg, fator).
		function getEntradaSnapshot(){
			const card = state.dom.cards.entrada;
			const dataset = card?.dataset || {};
			const qtyText = dataset.cx ?? dataset.caixas ?? doc.getElementById('quantidadeInn')?.textContent;
			const kgText = dataset.kgIn ?? dataset.kg_in ?? doc.getElementById('totalInn')?.textContent;
			const pesoText = dataset.pesoPorCx ?? doc.getElementById('pesoInnDisplay')?.textContent;
			const totalApprox = parseLocaleNumber(doc.getElementById('totalInn')?.textContent);
			const fatorConv = parseLocaleNumber(card?.getAttribute('data-fator-conv'));
			const cx = parseLocaleNumber(qtyText);
			const kgIn = parseLocaleNumber(kgText);
			let pesoPorCx = parseLocaleNumber(pesoText);
			if(!(pesoPorCx > 0) && kgIn > 0 && cx > 0){
				pesoPorCx = kgIn / cx;
			}
			if(!(pesoPorCx > 0)){
				const datasetPeso = parseLocaleNumber(dataset.pesoClassificado);
				if(datasetPeso > 0) pesoPorCx = datasetPeso;
			}
			return {
				cx,
				kgIn,
				pesoPorCx,
				totalApproxKg: totalApprox,
				fatorConversao: fatorConv > 0 ? fatorConv : 0
			};
		}

		// Estima meta em kg quando backend não envia valor explícito.
		function computeTargetKgFallback(){
			const snapshot = getEntradaSnapshot();
			if(snapshot.kgIn > 0) return snapshot.kgIn;
			if(snapshot.totalApproxKg > 0) return snapshot.totalApproxKg;
			if(snapshot.cx > 0 && snapshot.pesoPorCx > 0){
				return snapshot.cx * snapshot.pesoPorCx;
			}
			return Number(state.dom.cards.classificacao?.getAttribute?.('data-target')) || 0;
		}

		// Resolve peso médio por caixa consultando inputs/modais/entradas.
		function getKgPerCx(){
			try{
				if(window.pesoClassificado && typeof window.pesoClassificado.getValue === 'function'){
					const val = Number(window.pesoClassificado.getValue());
					if(Number.isFinite(val) && val > 0) return val;
				}
			}catch(_){ /* silencioso */ }
			const display = doc.getElementById('pesoClassificadoDisplay');
			if(display){
				const val = parseLocaleNumber(display.textContent);
				if(val > 0) return val;
			}
			const input = doc.getElementById('pesoClassificadoInput');
			if(input){
				const val = parseLocaleNumber(input.value);
				if(val > 0) return val;
			}
			const snapshot = getEntradaSnapshot();
			if(snapshot.pesoPorCx > 0) return snapshot.pesoPorCx;
			if(snapshot.kgIn > 0 && snapshot.cx > 0){
				const peso = snapshot.kgIn / snapshot.cx;
				if(peso > 0) return peso;
			}
			if(snapshot.fatorConversao > 0) return snapshot.fatorConversao;
			return CLASSIFICATION_DEFAULT_KG_PER_CX;
		}

		// Tenta descobrir o lote ativo olhando parâmetros e badges.
		function resolveLote(options = {}){
			const explicit = options.lote || state.context.lote || state.dom.cards.entrada?.dataset?.lote || body?.dataset?.lote;
			if(explicit){
				const normalized = String(explicit).trim();
				if(normalized) return normalized;
			}
			const badge = doc.getElementById('classLoteBadge');
			if(badge){
				const badgeLote = badge.dataset?.lote || badge.textContent || '';
				const trimmed = String(badgeLote).trim();
				if(trimmed) return trimmed;
			}
			return null;
		}

		// Mostra placeholder amigável dentro do painel de classificação.
		function setClassPlaceholder(message){
			const bodyEl = state.dom.classificacao.body;
			if(bodyEl){
				bodyEl.innerHTML = `<div class="placeholder">${message}</div>`;
			}
		}

		function clearDashboardState(options = {}){
			const reason = options.reason || 'manual';
			const setText = (selector, value = '')=>{
				if(!selector) return;
				const nodes = doc.querySelectorAll(selector);
				nodes.forEach((node)=>{ node.textContent = value; });
			};
			try{
				logger.info('Limpando dashboard (motivo: %s)', reason);
			}catch(_err){ /* noop */ }
			DASHBOARD_CLEAR_TEXT_TARGETS.forEach((selector)=> setText(selector, ''));
			const badgePedido = doc.getElementById('entBadgePedido');
			if(badgePedido) badgePedido.textContent = 'Pedido —';
			const badgeTipo = doc.getElementById('entBadgeTipo');
			if(badgeTipo) badgeTipo.textContent = '—';
			const badgeVale = doc.getElementById('entBadgeVale13');
			if(badgeVale){
				badgeVale.textContent = '';
				badgeVale.style.display = 'none';
			}
			const loteBadge = doc.getElementById('classLoteBadge');
			if(loteBadge){
				loteBadge.textContent = '';
				loteBadge.removeAttribute('title');
			}
			const unitLabel = doc.querySelector('#quantidadeInnCard .headline .unit');
			if(unitLabel) unitLabel.textContent = '';
			DASHBOARD_CLEAR_INPUTS.forEach((selector)=>{
				const input = doc.querySelector(selector);
				if(input) input.value = '';
			});
			[['#distMini3 .dist-value',''],['.dist-class-card [data-field]',''],['.dist-class-card .class-share','']].forEach(([selector,value])=>{
				const nodes = doc.querySelectorAll(selector);
				nodes.forEach((node)=>{ node.textContent = value; });
			});
			doc.querySelectorAll('.dist-class-card .bar-fill').forEach((bar)=>{ bar.style.width = '0%'; });
			const custoCard = doc.getElementById('distMini2');
			custoCard?.classList.remove('editing-cx','editing-kg');
			const cardsToReset = [state.dom.cards.entrada, doc.getElementById('quantidadeInnCard')].filter(Boolean);
			cardsToReset.forEach((card)=>{
				DASHBOARD_DATASET_KEYS.forEach((key)=>{
					if(card.dataset && key in card.dataset) delete card.dataset[key];
				});
			});
			if(doc.body?.dataset){
				delete doc.body.dataset.lote;
				delete doc.body.dataset.nunota;
			}
			setClassPlaceholder('Selecione um item na lista para carregar a classificação.');
			if(state.dom.classificacao.badge){
				state.dom.classificacao.badge.textContent = '';
				state.dom.classificacao.badge.style.display = 'none';
			}
			if(state.dom.classificacao.openLink){
				state.dom.classificacao.openLink.style.display = 'none';
			}
			const classCard = state.dom.classificacao.card;
			if(classCard){
				classCard.setAttribute('data-target','0');
				classCard.setAttribute('data-classified','0');
				classCard.removeAttribute('data-pendente-class');
			}
			if(typeof window.__updateToggleFromPendenteClass === 'function'){
				try{ window.__updateToggleFromPendenteClass(); }
				catch(_err){ /* noop */ }
			}
			const estoqueBox = state.dom.classificacao.kpis?.estoque?.closest?.('.kpi');
			estoqueBox?.classList.remove('kpi--warn','kpi--muted');
			const gauge = state.dom.classificacao.gauge;
			if(gauge){
				const arcLen = Math.PI * 90;
				if(gauge.arc){
					gauge.arc.setAttribute('stroke-dasharray', `0 ${arcLen.toFixed(1)}`);
				}
				if(gauge.pct) gauge.pct.textContent = '0%';
				if(gauge.label) gauge.label.textContent = '';
				if(gauge.watermark) gauge.watermark.classList.remove('is-visible');
			}
			updateMiniCards(null);
			if(typeof window.updateMarginHistory === 'function'){
				try{ window.updateMarginHistory([]); }
				catch(err){ logger.debug('Falha ao limpar histórico de margem', err); }
			}
			if(typeof window.__setDistribTotal === 'function'){
				try{ window.__setDistribTotal(0, { source: 'dashboard-clear', allowUI: true, syncInput: true }); }
				catch(err){ logger.debug('Falha ao limpar total de distribuição', err); }
			}
			if(typeof window.__clearClassResumoCache === 'function'){
				window.__clearClassResumoCache('dashboard-clear');
			}else{
				cache.classificacao.clear();
			}
			cache.payloads.classificacao = null;
			cache.payloads.distribuicao = null;
			window.__CURRENT_VALE_NUNOTA = null;
			window.__DIST_QTY_FROM_CLASS = null;
			window.__DIST_CLASS_UI_OVERRIDE = false;
			if(extraMedio){
				try{
					Object.assign(extraMedio.state, {
						precoBase: 0,
						extraCx: 0,
						extraKg: 0,
						medioCx: 0,
						medioKg: 0,
						extraCustoCx: 0,
						extraCustoKg: 0,
						extraCustoTotal: 0,
						medioCustoCx: 0,
						medioCustoKg: 0,
						medioCustoTotal: 0,
						forceSimTotals: false,
						lastSimTotal: 0
					});
					extraMedio.seedFromAggregate({
						totalKg: 0,
						totalCx: 0,
						extra: { kg: 0, cx: 0 },
						medio: { kg: 0, cx: 0 },
						descarte: { kg: 0, cx: 0 }
					});
				}catch(err){
					logger.debug('Falha ao resetar estado Extra/Médio', err);
				}
			}
			if(simulationCardController && typeof simulationCardController.reset === 'function'){
				// Limpa o card de simulação sempre que o dashboard é reiniciado.
				simulationCardController.reset({ silent: true });
			}
			mutateContext({ nunota: null, sequencia: null, codprod: null, lote: null });
			events.emit('dashboard:cleared', { reason });
			try{ window.dispatchEvent(new CustomEvent('dashboard:cleared', { detail: { reason } })); }
			catch(_err){ /* noop */ }
			return true;
		}

		function applyEntradaLockState(flag){
			// Mantém o cartão de entrada bloqueado/desbloqueado em sincronia com o status do vale.
			const card = state.dom.cards.entrada || doc.getElementById('quantidadeInnCard');
			const precoInput = doc.getElementById('entPrecoCxInput');
			const pesoInput = doc.getElementById('pesoClassificadoInput');
			const locked = Boolean(flag);
			if(card){
				card.classList.toggle('locked', locked);
			}
			if(precoInput) precoInput.disabled = locked;
			if(pesoInput) pesoInput.disabled = locked;
		}

		// Centraliza o refresh pós-edição para reutilizar a mesma rotina em preço e peso.
		function requestDashboardRefresh(options = {}){
			const { reason, scope, force, lote } = options;
			const targetLote = lote || state.context?.lote || state.dom.cards.entrada?.dataset?.lote || null;
			if(state.actions?.reloadDashboard){
				state.actions.reloadDashboard({ scope, force, lote: targetLote, reason }).catch((err)=> logger.warn('Refresh pós edição falhou', err));
				return true;
			}
			if(targetLote && Array.isArray(scope) && scope.includes('classificacao') && typeof window.__reloadClassificacaoCard === 'function'){
				try{ window.__reloadClassificacaoCard(targetLote); }
				catch(err){ logger.warn('Fallback de classificação falhou', err); }
				return true;
			}
			return false;
		}

		window.__applyEntradaLockState = applyEntradaLockState;
		window.__initEntradaEditors = initEntradaEditors;

		function initEntradaEditors(){
			// Reativa a edição inline de R$/cx e Peso Classificado reaproveitando os elementos existentes.
			const card = state.dom.cards.entrada || doc.getElementById('quantidadeInnCard');
			if(!card) return;
			const refs = {
				priceDisplay: doc.getElementById('entPrecoCxDisplay'),
				priceInput: doc.getElementById('entPrecoCxInput'),
				totalDisplay: doc.getElementById('entTotalIn'),
				precoKgDisplay: doc.getElementById('entPrecoKg'),
				pesoTotalDisplay: doc.getElementById('totalInn'),
				qtyDisplay: doc.getElementById('quantidadeInn'),
				pesoDisplay: doc.getElementById('pesoClassificadoDisplay'),
				pesoInput: doc.getElementById('pesoClassificadoInput')
			};
			if(refs.priceDisplay && refs.priceInput && refs.totalDisplay && refs.precoKgDisplay && refs.pesoTotalDisplay && refs.qtyDisplay){
				setupEntradaPrecoEditor(card, refs);
			}
			if(refs.pesoDisplay && refs.pesoInput){
				setupPesoClassificadoEditor(card, refs);
			}
			// Mantém o estado de bloqueio alinhado com o status atual do vale (default: desbloqueado).
			applyEntradaLockState(Boolean(state.current?.isFaturado));
		}

		function setupEntradaPrecoEditor(card, refs){
			if(refs.priceDisplay.dataset.bound === 'true') return;
			const datasetSource = doc.getElementById('quantidadeInnCard') || card;
			const moneyFmt = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
			let exiting = false;
			let lastPersistedValue = 0;
			const parseValue = (text)=> parseLocaleNumber(text);
			lastPersistedValue = parseValue(refs.priceDisplay.textContent);
			const getDatasetNumber = (key)=>{
				const raw = datasetSource?.dataset?.[key];
				return raw != null ? parseLocaleNumber(raw) : NaN;
			};
			const callItemSave = async (payload)=>{
				// Replica o comportamento do legado utilizando __postJSON quando disponível para evitar divergências no endpoint.
				if(typeof window.__postJSON === 'function'){
					const response = await window.__postJSON('/sankhya/item/save/', payload);
					if(!response || response.ok === false){
						const message = response?.body?.error || response?.error || 'Erro ao salvar item.';
						throw new Error(message);
					}
					return response.body || {};
				}
				return services.http.post('/sankhya/item/save/', payload);
			};
			const notifyLocked = ()=>{
				if(!card.classList.contains('locked')) return false;
				utils.toast('Vale faturado - edição bloqueada.', 'warning');
				return true;
			};
			const autosize = ()=>{
				try{
					const rect = refs.priceDisplay.getBoundingClientRect();
					refs.priceInput.style.width = `${Math.ceil(Math.min(260, Math.max(80, rect.width + 14)))}px`;
				}catch(_err){ /* noop */ }
			};
			const getIdentifiers = ()=>{
				return {
					nunota: Number(datasetSource?.dataset?.nunota || datasetSource?.getAttribute?.('data-nunota') || 0) || 0,
					sequencia: Number(datasetSource?.dataset?.seq || datasetSource?.getAttribute?.('data-seq') || 0) || 0
				};
			};
			const applyDerivedValues = (unitPrice)=>{
				const qtyCx = parseValue(refs.qtyDisplay.textContent);
				const total = (Number.isFinite(qtyCx) ? qtyCx : 0) * unitPrice;
				const pesoTotal = parseValue(refs.pesoTotalDisplay.textContent);
				const precoKg = (pesoTotal > 0) ? (total / pesoTotal) : 0;
				refs.priceDisplay.textContent = moneyFmt.format(unitPrice);
				refs.totalDisplay.textContent = moneyFmt.format(total);
				refs.precoKgDisplay.textContent = moneyFmt.format(precoKg);
				if(datasetSource?.dataset){
					datasetSource.dataset.vlrunit = String(unitPrice);
					datasetSource.dataset.vlrtot = String(total);
					datasetSource.dataset.vlrkg = precoKg ? String(precoKg) : '';
				}
				window.__SAVED_VLRUNIT = Number(unitPrice) || 0;
				window.__SAVED_VLRTOT = Number(total) || 0;
				if(typeof window.__DIST_seedExtraCustoKg === 'function' && precoKg > 0){
					try{
						window.__DIST_seedExtraCustoKg(precoKg, true);
						if(typeof window.__DIST_refresh === 'function') window.__DIST_refresh();
					}catch(err){ logger.debug('Falha ao sincronizar distribuição após editar preço', err); }
				}
				if(window.__DIST_EXTRA_MEDIO_STATE){
					window.__DIST_EXTRA_MEDIO_STATE.precoBase = Number(unitPrice) || 0;
				}
				if(typeof window.__syncExtraMedio === 'function'){
					try{ window.__syncExtraMedio('initial'); }
					catch(err){ logger.debug('Falha ao sincronizar Extra/Médio após editar preço', err); }
				}
				return { qtyCx, total, pesoTotal, precoKg };
			};
			// Monta o payload completo reaproveitando métricas já calculadas para manter o backend sincronizado.
			const buildPersistPayload = (unitPrice, derived)=>{
				const { qtyCx, total, pesoTotal, precoKg } = derived || {};
				return {
					nunota: Number(getDatasetNumber('nunota')),
					sequencia: Number(getDatasetNumber('seq')),
					codprod: Number(getDatasetNumber('codprod')) || undefined,
					qtdneg: Number.isFinite(pesoTotal) ? Number(pesoTotal) : undefined,
					vlrunit: Number.isFinite(precoKg) ? Number(precoKg) : undefined,
					vlrtot: Number.isFinite(total) ? Number(total) : undefined,
					preco_inicial: Number(unitPrice),
					codvol: 'CX',
					codagregacao: datasetSource?.dataset?.lote || undefined
				};
			};
			const persistPrice = async (value, derived)=>{
				const { nunota, sequencia } = getIdentifiers();
				if(!(nunota && sequencia)){
					utils.toast('Selecione um pedido antes de editar o preço.', 'warning');
					return;
				}
				try{
					const payload = buildPersistPayload(value, derived);
					const response = await callItemSave(payload);
					const rows = Array.isArray(window.__COM_LIST_ROWS) ? window.__COM_LIST_ROWS : [];
					rows.forEach((row)=>{
						if(Number(row?.nunota || row?.NUNOTA || 0) === nunota && Number(row?.sequencia || row?.SEQUENCIA || 0) === sequencia){
							row.preco_inicial = Number(value);
							row.precobase = Number(value);
						}
					});
					if(response?.nunota_vale){
						const badge = doc.getElementById('entBadgeVale13');
						if(badge){
							badge.textContent = `Vale ${response.nunota_vale}`;
							badge.style.display = '';
						}
					}
					utils.toast('Preço salvo.', 'success');
					lastPersistedValue = Number(value);
					requestDashboardRefresh({ reason: 'preco:edited', scope: ['entrada','lista','classificacao','distribuicao'], force: true });
				}catch(err){
					logger.error('Erro ao salvar preço/cx', err);
					utils.toast(err?.message || 'Erro ao salvar preço.', 'error');
					applyDerivedValues(lastPersistedValue);
				}
			};
			const exitEditor = async (commit)=>{
				if(exiting) return;
				exiting = true;
				card.classList.remove('editing-cx');
				try{
					if(!commit){
						refs.priceInput.value = '';
						return;
					}
					const parsed = parseValue(refs.priceInput.value);
					if(!Number.isFinite(parsed) || parsed < 0){
						return;
					}
					const derived = applyDerivedValues(parsed);
					await persistPrice(parsed, derived);
				}finally{
					exiting = false;
				}
			};
			const openEditor = ()=>{
				if(notifyLocked()) return;
				const current = refs.priceDisplay.textContent || '0,00';
				card.classList.add('editing-cx');
				const parsed = parseValue(current);
				refs.priceInput.value = Number.isFinite(parsed) ? moneyFmt.format(parsed) : '';
				autosize();
				setTimeout(()=>{ if(!refs.priceInput.disabled){ refs.priceInput.focus(); refs.priceInput.select(); } }, 0);
			};
			refs.priceDisplay.addEventListener('click', openEditor);
			refs.priceDisplay.addEventListener('keydown', (ev)=>{
				if(ev.key === 'Enter' || ev.key === ' ' || ev.key === 'Spacebar'){
					ev.preventDefault();
					openEditor();
				}
			});
			refs.priceInput.addEventListener('keydown', (ev)=>{
				if(ev.key === 'Enter'){
					ev.preventDefault();
					exitEditor(true);
				}else if(ev.key === 'Escape'){
					ev.preventDefault();
					exitEditor(false);
				}
			});
			refs.priceInput.addEventListener('blur', ()=> exitEditor(true));
			refs.priceInput.addEventListener('input', autosize);
			refs.priceDisplay.dataset.bound = 'true';
		}

		function setupPesoClassificadoEditor(card, refs){
			if(refs.pesoDisplay.dataset.bound === 'true') return;
			const datasetSource = doc.getElementById('quantidadeInnCard') || card;
			const numberFmt = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
			let exiting = false;
			const parseValue = (text)=> parseLocaleNumber(text);
			window.pesoClassificado = {
				getValue: ()=> parseValue(refs.pesoDisplay.textContent),
				setValue: (value)=>{
					if(!Number.isFinite(value)){ return false; }
					refs.pesoDisplay.textContent = numberFmt.format(value);
					if(datasetSource?.dataset){
						datasetSource.dataset.pesoClassificado = String(value);
					}
					return true;
				}
			};
			const notifyLocked = ()=>{
				if(!card.classList.contains('locked')) return false;
				utils.toast('Vale faturado - edição bloqueada.', 'warning');
				return true;
			};
			const autosize = ()=>{
				try{
					const rect = refs.pesoDisplay.getBoundingClientRect();
					refs.pesoInput.style.width = `${Math.min(70, Math.ceil(rect.width + 10))}px`;
				}catch(_err){ /* noop */ }
			};
			const getIdentifiers = ()=>{
				return {
					nunota: Number(datasetSource?.dataset?.nunota || datasetSource?.getAttribute?.('data-nunota') || 0) || 0,
					sequencia: Number(datasetSource?.dataset?.seq || datasetSource?.getAttribute?.('data-seq') || 0) || 0
				};
			};
			const persistPeso = async (value)=>{
				const { nunota, sequencia } = getIdentifiers();
				if(!(nunota && sequencia)){
					utils.toast('Selecione um pedido antes de editar o peso.', 'warning');
					return;
				}
				try{
					await services.http.post('/sankhya/comercial/peso/save/', { nunota, sequencia, qtdconferida: Number(value) });
					const rows = Array.isArray(window.__COM_LIST_ROWS) ? window.__COM_LIST_ROWS : [];
					rows.forEach((row)=>{
						if(Number(row?.nunota || row?.NUNOTA || 0) === nunota && Number(row?.sequencia || row?.SEQUENCIA || 0) === sequencia){
							row.qtdconferida = Number(value);
						}
					});
					if(datasetSource?.dataset){
						datasetSource.dataset.pesoClassificado = String(value);
					}
					utils.toast('Peso classificado salvo.', 'success');
					requestDashboardRefresh({ reason: 'peso:edited', scope: ['classificacao'], force: true, lote: datasetSource?.dataset?.lote });
				}catch(err){
					logger.error('Erro ao salvar peso classificado', err);
					utils.toast(err?.message || 'Erro ao salvar peso.', 'error');
				}
			};
			const exitEditor = async (commit)=>{
				if(exiting) return;
				exiting = true;
				card.classList.remove('editing-cx');
				try{
					if(!commit){
						refs.pesoInput.value = '';
						return;
					}
					const parsed = parseValue(refs.pesoInput.value);
					if(!Number.isFinite(parsed) || parsed < 0){
						return;
					}
					if(window.pesoClassificado && typeof window.pesoClassificado.setValue === 'function'){
						window.pesoClassificado.setValue(parsed);
					}else{
						refs.pesoDisplay.textContent = numberFmt.format(parsed);
					}
					await persistPeso(parsed);
				}finally{
					exiting = false;
				}
			};
			const openEditor = ()=>{
				if(notifyLocked()) return;
				const current = refs.pesoDisplay.textContent || '0,0';
				card.classList.add('editing-cx');
				const parsed = parseValue(current);
				refs.pesoInput.value = Number.isFinite(parsed) ? numberFmt.format(parsed) : '';
				autosize();
				setTimeout(()=>{ if(!refs.pesoInput.disabled){ refs.pesoInput.focus(); refs.pesoInput.select(); } }, 0);
			};
			refs.pesoDisplay.addEventListener('click', openEditor);
			refs.pesoDisplay.addEventListener('keydown', (ev)=>{
				if(ev.key === 'Enter' || ev.key === ' ' || ev.key === 'Spacebar'){
					ev.preventDefault();
					openEditor();
				}
			});
			refs.pesoInput.addEventListener('keydown', (ev)=>{
				if(ev.key === 'Enter'){
					ev.preventDefault();
					exitEditor(true);
				}else if(ev.key === 'Escape'){
					ev.preventDefault();
					exitEditor(false);
				}
			});
			refs.pesoInput.addEventListener('blur', ()=> exitEditor(true));
			refs.pesoInput.addEventListener('input', autosize);
			refs.pesoDisplay.dataset.bound = 'true';
		}

		// Busca o resumo consolidado da classificação para um lote.
		async function fetchClassificacaoResumo(lote, options = {}){
			const key = String(lote);
			const cached = cache.classificacao.get(key);
			if(cached && !options.force && (Date.now() - cached.cachedAt) < CLASSIFICATION_CACHE_TTL){
				return cached.payload;
			}
			const payload = await services.http.get(`/sankhya/classificacao/resumo/?lote=${encodeURIComponent(lote)}`);
			if(!payload || payload.ok === false){
				throw new Error(payload?.error || 'Não foi possível carregar a classificação.');
			}
			cache.classificacao.set(key, { payload, cachedAt: Date.now() });
			return payload;
		}

		// Recupera detalhes extras do lote para enriquecer o painel.
		async function fetchLoteDetails(lote){
			const payload = await services.http.get(`/sankhya/lote/consultar/?lote=${encodeURIComponent(lote)}`);
			return payload && payload.ok !== false ? payload : null;
		}

		function resolveCodprodInNatura(){
			const ctxCod = Number(state.context?.codprod || 0);
			if(ctxCod > 0) return ctxCod;
			const datasetCod = Number(state.dom.cards.entrada?.dataset?.codprod || 0);
			return datasetCod > 0 ? datasetCod : null;
		}

		async function fetchProdutoVariantes(codprod){
			const normalized = Number(codprod);
			if(!(normalized > 0)) return null;
			if(cache.produtoVariantes.has(normalized)){
				return cache.produtoVariantes.get(normalized);
			}
			try{
				const payload = await services.http.get(`/sankhya/comercial/produtos/variantes/?codprod=${encodeURIComponent(normalized)}`);
				if(!payload || payload.ok === false){
					return null;
				}
				const mapped = {
					extra: Number(payload.extra) > 0 ? Number(payload.extra) : null,
					medio: Number(payload.medio) > 0 ? Number(payload.medio) : null,
					fabricante: payload.fabricante || null
				};
				cache.produtoVariantes.set(normalized, mapped);
				return mapped;
			}catch(err){
				logger.warn('Falha ao carregar variantes Extra/Médio', err);
				return null;
			}
		}

		async function ensureCanonicalExtraMedioCodes(aggregate){
			if(!aggregate) return aggregate;
			const codInNatura = resolveCodprodInNatura();
			if(!(codInNatura > 0)) return aggregate;
			try{
				const variants = await fetchProdutoVariantes(codInNatura);
				if(variants){
					if(variants.extra){
						aggregate.extra = aggregate.extra || { kg: 0, cx: 0 };
						aggregate.extra.codprod = Number(variants.extra);
					}
					if(variants.medio){
						aggregate.medio = aggregate.medio || { kg: 0, cx: 0 };
						aggregate.medio.codprod = Number(variants.medio);
					}
				}
			}catch(err){
				logger.debug('Falha ao aplicar códigos canônicos Extra/Médio', err);
			}
			return aggregate;
		}

		// Recupera o código do produto tanto de campos explícitos quanto do label textual.
		function resolveRowCodprod(row, produtoLabel = ''){
			const direct = row?.codprod ?? row?.CODPROD ?? row?.codProduto ?? row?.COD_PROD ?? row?.codigo ?? row?.CODIGO;
			const numeric = Number(direct);
			if(Number.isFinite(numeric) && numeric > 0){
				return numeric;
			}
			const label = produtoLabel || String(row?.produto || row?.descr || '').trim();
			const inlineMatch = label.match(/^\s*(\d{3,})\b/);
			if(inlineMatch){
				const inferred = Number(inlineMatch[1]);
				if(Number.isFinite(inferred) && inferred > 0){
					return inferred;
				}
			}
			return null;
		}

		// Normaliza linhas vindas da API convertendo kg/cx para floats seguros.
		function normalizeClassRows(linhas, kgPerCx){
			const rows = Array.isArray(linhas) ? linhas : [];
			return rows.map((row, index)=>{
				const rawKg = parseLocaleNumber(row?.kg);
				const rawCx = parseLocaleNumber(row?.cx);
				const kg = rawKg > 0 ? rawKg : (rawCx > 0 ? rawCx : 0);
				const cx = kg > 0 ? (kg / kgPerCx) : 0;
				const produto = String(row?.produto || row?.descr || '').trim();
				const codprod = resolveRowCodprod(row, produto);
				const rawSelecionado = row?.selecionado ?? row?.SELECIONADO;
				const parsedSelecionado = (rawSelecionado === null || rawSelecionado === undefined || rawSelecionado === '')
					? null
					: Number(rawSelecionado);
				const selecionado = Number.isFinite(parsedSelecionado) ? parsedSelecionado : null;
				return { produto, kg, cx, rawKg, rawCx, codprod, selecionado, index };
			}).filter((row)=> (row.kg > 0 || row.cx > 0));
		}

		// Gera agregados (extra/médio/descarte) a partir das linhas normalizadas.
		function buildClassAggregate(rows, kgPerCx, descarteKg = 0){
			let totalKg = 0;
			let totalCx = 0;
			let extraKg = 0;
			let extraCx = 0;
			let medioKg = 0;
			let medioCx = 0;
			let extraCodprod = null;
			let medioCodprod = null;
			let medioFallbackCod = null;
			let descarteTotalKg = Number(descarteKg) || 0;
			const hasFlagExtra = rows.some((row)=> row.selecionado === 1);
			const hasFlagMedio = rows.some((row)=> row.selecionado === 2);
			const hasNamedExtra = rows.some((row)=> row.produto.toUpperCase().includes('EXTRA'));
			const hasNamedMedio = rows.some((row)=>{
				const upper = row.produto.toUpperCase();
				return upper.includes('MEDIO') || upper.includes('MÉDIO') || upper.includes('MÉDIA') || upper.includes('MEDIA');
			});
			const hasExtra = hasFlagExtra || hasNamedExtra;
			const hasMedio = hasFlagMedio || hasNamedMedio;
			rows.forEach((row)=>{
				const upper = row.produto.toUpperCase();
				const candidateCod = row.codprod && Number(row.codprod) > 0 ? Number(row.codprod) : null;
				const flagValue = Number.isFinite(row.selecionado) ? row.selecionado : null;
				totalKg += row.kg;
				totalCx += row.cx;
				const isDescarte = upper.includes('DESCARTE') || upper.includes('AVARIA') || upper.includes('INSERV');
				if(isDescarte){
					descarteTotalKg += row.kg;
					return;
				}
				const matchesLabelMedio = upper.includes('MEDIO') || upper.includes('MÉDIO') || upper.includes('MÉDIA') || upper.includes('MEDIA');
				if(!hasExtra && !hasMedio){
					extraKg += row.kg;
					extraCx += row.cx;
					if(!extraCodprod && candidateCod){ extraCodprod = candidateCod; }
					return;
				}
				if(flagValue === 1 || upper.includes('EXTRA')){
					extraKg += row.kg;
					extraCx += row.cx;
					if(!extraCodprod && candidateCod){ extraCodprod = candidateCod; }
					return;
				}
				if(flagValue === 2 || matchesLabelMedio){
					medioKg += row.kg;
					medioCx += row.cx;
					if(!medioCodprod && candidateCod){ medioCodprod = candidateCod; }
					return;
				}
				if(!medioFallbackCod && candidateCod){
					medioFallbackCod = candidateCod;
				}
			});
			if(hasExtra || hasMedio){
				const somaClassificados = extraKg + medioKg + descarteTotalKg;
				if(somaClassificados < totalKg){
					const restanteKg = Math.max(0, totalKg - extraKg - descarteTotalKg);
					medioKg = restanteKg;
					medioCx = Math.max(0, totalCx - extraCx);
					if(!medioCodprod && medioFallbackCod){
						medioCodprod = medioFallbackCod;
					}
				}
			}
			const descarteCx = kgPerCx > 0 ? (descarteTotalKg / kgPerCx) : 0;
			return {
				totalKg,
				totalCx,
				extra: { kg: extraKg, cx: extraCx, codprod: extraCodprod },
				medio: { kg: medioKg, cx: medioCx, codprod: medioCodprod },
				descarte: { kg: descarteTotalKg, cx: descarteCx }
			};
		}

		// Publica o resumo atual em cache global para consultas cruzadas.
		function updateGlobalClassCache(lote, rows, aggregate){
			try{
				const normalizeKey = (value)=>{
					if(value == null) return '';
					return String(value)
						.normalize('NFD')
						.replace(/[\u0300-\u036f]/g, '')
						.toUpperCase()
						.replace(/\s+/g, ' ')
						.trim();
				};
				const key = normalizeKey(lote);
				if(!key) return;
				const payload = {
					rows: rows.map((row, idx)=>({
						produto: row.produto,
						key: normalizeKey(row.produto),
						cx: row.cx,
						kg: row.kg,
						rowId: `${normalizeKey(row.produto)}#${idx}`
					})),
					aggregate,
					updatedAt: Date.now()
				};
				window.__CLASS_RESUMOS_BY_LOTE = window.__CLASS_RESUMOS_BY_LOTE || {};
				window.__CLASS_RESUMOS_BY_LOTE[key] = payload;
			}catch(err){ logger.debug('Falha ao atualizar cache global de classificação', err); }
		}

		// Renderiza o painel visual da classificação e sincroniza badge/links.
		function renderClassificacaoRows({ lote, linhas, descarteKg }){
			const classDom = state.dom.classificacao;
			if(classDom.badge){
				classDom.badge.textContent = lote ? `Lote ${lote}` : '';
				classDom.badge.style.display = lote ? '' : 'none';
			}
			if(classDom.openLink){
				if(lote){
					classDom.openLink.style.display = 'inline';
					classDom.openLink.href = `/sankhya/compras/classificacao/?sel=${encodeURIComponent(lote)}&open=items`;
				}else{
					classDom.openLink.style.display = 'none';
				}
			}
			const kgPerCx = getKgPerCx();
			const normalized = normalizeClassRows(linhas, kgPerCx);
			if(!normalized.length){
				setClassPlaceholder('Sem classificações para este lote.');
				const aggregate = buildClassAggregate([], kgPerCx, descarteKg);
				updateGlobalClassCache(lote, [], aggregate);
				return { aggregate, kgPerCx };
			}
			const sorted = normalized.slice().sort((a,b)=> b.kg - a.kg);
			const totalKg = sorted.reduce((sum,row)=> sum + row.kg, 0);
			const fmtDecimal = (value)=> utils.formatDecimal(value, 1);
			let html = sorted.map((row)=>{
				const pct = totalKg > 0 ? Math.max(0, Math.min(100, (row.kg / totalKg) * 100)) : 0;
				const title = row.produto.replace(/"/g,'&quot;');
				return `<div class="class-row" role="row" data-cx="${row.cx}" data-kg="${row.kg}" data-prod="${title}">
					<div class="line1" title="${title}">${title}</div>
					<div class="line2">
						<div class="pct" style="padding-left:10px">
							<div class="pct-val" style="font-size:.85em;">${pct.toLocaleString('pt-BR',{maximumFractionDigits:1})}%</div>
							<div class="percent-bar" aria-hidden="true"><span style="width:${pct.toFixed(1)}%"></span></div>
						</div>
						<div class="qty">
							<span class="meta-val"><strong>${fmtDecimal(row.cx)}</strong> <span class="u">cx</span></span>
							<span class="sep">/</span>
							<span class="meta-val"><strong>${fmtDecimal(row.kg)}</strong> <span class="u">kg</span></span>
						</div>
					</div>
				</div>`;
			}).join('');
			if(descarteKg > 0){
				const descartePct = totalKg > 0 ? (descarteKg / totalKg) * 100 : 0;
				const descarteCx = kgPerCx > 0 ? (descarteKg / kgPerCx) : 0;
				html += `
					<div class="class-row descarte-row" role="row" data-cx="${descarteCx}" data-kg="${descarteKg}" data-prod="DESCARTE" style="opacity:0.85; border-top:1px solid #e2e8f0; margin-top:8px; padding-top:8px;">
						<div class="line1" title="DESCARTE">DESCARTE</div>
						<div class="line2">
							<div class="pct" style="padding-left:10px">
								<div class="pct-val" style="font-size:.85em;">${descartePct.toLocaleString('pt-BR',{maximumFractionDigits:1})}%</div>
								<div class="percent-bar" aria-hidden="true"><span style="width:${descartePct.toFixed(1)}%; background-color:#dc2626;"></span></div>
							</div>
							<div class="qty">
								<span class="meta-val"><strong>${fmtDecimal(descarteCx)}</strong> <span class="u">cx</span></span>
								<span class="sep">/</span>
								<span class="meta-val"><strong>${fmtDecimal(descarteKg)}</strong> <span class="u">kg</span></span>
							</div>
						</div>
					</div>`;
			}
			if(classDom.body){
				classDom.body.innerHTML = html;
			}
			if(classDom.card){
				classDom.card.setAttribute('data-current-lote', lote || '');
			}
			const aggregate = buildClassAggregate(sorted, kgPerCx, descarteKg);
			updateGlobalClassCache(lote, sorted, aggregate);
			return { aggregate, kgPerCx };
		}

		// Traduz total em kg para caixas considerando o peso atual configurado.
		function calcClassCxFromDetail(detail, kgPerCx){
			if(!(detail && Array.isArray(detail.classificacoes))) return null;
			let total = 0;
			detail.classificacoes.forEach((item)=>{
				const vol = String(item?.codvol || item?.CODVOL || '').trim().toUpperCase();
				const qtd = parseLocaleNumber(item?.qtd ?? item?.QTDNEG);
				const peso = parseLocaleNumber(item?.peso ?? item?.PESO);
				if(vol === 'CX'){
					total += qtd;
					return;
				}
				if(vol === 'KG' && peso > 0){
					total += qtd / peso;
					return;
				}
				if(qtd > 0 && kgPerCx > 0){
					total += qtd / kgPerCx;
				}
			});
			return total > 0 ? total : null;
		}

		// Atualiza cards principais (entrada/classificação/rendimento) com os dados atuais.
		function updateResumoCards({ aggregate, detail, targetKg, kgPerCx }){
			const resumo = state.dom.classificacao.resumo;
			if(!resumo) return;
			const snapshot = getEntradaSnapshot();
			const innKg = Math.round(targetKg || computeTargetKgFallback());
			const innCx = Math.round(snapshot.cx || 0);
			const classKg = Math.round(aggregate?.totalKg || 0);
			// Mantemos o cálculo das caixas classificadas diretamente (kg total / peso classificado) para refletir o valor exibido no card Resumo.
			const pesoReferencia = kgPerCx > 0 ? kgPerCx : getKgPerCx();
			const classCxReferencia = (classKg > 0 && pesoReferencia > 0) ? (classKg / pesoReferencia) : 0;
			const classCx = Math.round(classCxReferencia || aggregate?.totalCx || 0);
			const descarteKg = Math.round(aggregate?.descarte?.kg || 0);
			const descarteCx = aggregate?.descarte?.cx || 0;
			if(resumo.innKg) resumo.innKg.textContent = formatInt(innKg);
			if(resumo.innCx) resumo.innCx.textContent = formatInt(innCx);
			if(resumo.classKg) resumo.classKg.textContent = formatInt(classKg);
			if(resumo.classCx) resumo.classCx.textContent = formatInt(classCx);
			if(resumo.inservKg) resumo.inservKg.textContent = formatInt(descarteKg);
			if(resumo.inservCx) resumo.inservCx.textContent = utils.formatDecimal(descarteCx, 1);
			const rendimentoCx = classCx - innCx;
			if(resumo.rend){
				resumo.rend.textContent = `${formatInt(rendimentoCx)}cx`;
				resumo.rend.style.color = rendimentoCx < 0 ? '#dc2626' : '#0a3392';
			}
			window.__DIST_QTY_FROM_CLASS = {
				kg: classKg,
				cx: classCx,
				locked: true,
				source: 'classification',
				updatedAt: Date.now()
			};
			updateQtysFromClass(classCx, classKg);
		}

		// Apresenta volume de caixas com casas fixas e fallback amigável.
		function formatVolumeValue(value){
			const num = Number(value);
			if(!Number.isFinite(num) || Math.abs(num) < 1e-9) return '0';
			const hasDecimal = Math.abs(num - Math.trunc(num)) > 0;
			return num.toLocaleString('pt-BR', {
				minimumFractionDigits: hasDecimal ? 2 : 0,
				maximumFractionDigits: hasDecimal ? 2 : 0
			});
		}

		// Reseta conteúdo visual dos minicards de Extra/Médio.
		function clearMiniCard(card){
			if(!card) return;
			const shareEl = card.querySelector('.class-share');
			const fillEl = card.querySelector('.bar-fill');
			const kgEl = card.querySelector('[data-field="kg"]');
			const cxEl = card.querySelector('[data-field="cx"]');
			const codeEl = card.querySelector('[data-field="codprod"]');
			if(shareEl) shareEl.textContent = '';
			if(fillEl) fillEl.style.width = '0%';
			if(kgEl) kgEl.textContent = '';
			if(cxEl) cxEl.textContent = '';
			if(codeEl){
				codeEl.textContent = '';
				codeEl.removeAttribute('title');
			}
		}

		// Preenche cada mincard com percentuais e totais do bucket fornecido.
		function updateMiniCard(card, bucket, baseKg){
			if(!card || !bucket) return;
			const sharePct = baseKg > 0 ? Math.max(0, Math.min(100, (bucket.kg / baseKg) * 100)) : 0;
			const shareEl = card.querySelector('.class-share');
			const fillEl = card.querySelector('.bar-fill');
			const kgEl = card.querySelector('[data-field="kg"]');
			const cxEl = card.querySelector('[data-field="cx"]');
			const codeEl = card.querySelector('[data-field="codprod"]');
			if(shareEl) shareEl.textContent = `${sharePct.toLocaleString('pt-BR',{maximumFractionDigits:1})}%`;
			if(fillEl) fillEl.style.width = `${sharePct}%`;
			if(kgEl) kgEl.textContent = formatVolumeValue(bucket.kg);
			if(cxEl) cxEl.textContent = formatVolumeValue(bucket.cx);
			if(codeEl){
				// Exibe o código agrupado informado pela classificação TOP 26
				const text = bucket.codprod ? String(bucket.codprod) : '';
				codeEl.textContent = text;
				if(text){ codeEl.title = `Código ${text}`; }
				else { codeEl.removeAttribute('title'); }
			}
		}

		// Persiste totais Extra/Médio no dataset para uso posterior.
		function syncExtraMedioState(aggregate){
			if(!extraMedio) return;
			extraMedio.seedFromAggregate(aggregate);
		}

		// Coordena a atualização de ambos os minicards a partir do agregado.
		function updateMiniCards(aggregate){
			const extraCard = state.dom.cards.miniExtra;
			const medioCard = state.dom.cards.miniMedio;
			if(!aggregate || (!extraCard && !medioCard)){
				window.__DIST_CLASS_UI_OVERRIDE = false;
				clearMiniCard(extraCard);
				clearMiniCard(medioCard);
				return;
			}
			const baseKg = aggregate.totalKg > 0 ? aggregate.totalKg : Math.max(aggregate.extra.kg + aggregate.medio.kg, 0);
			updateMiniCard(extraCard, aggregate.extra, baseKg);
			updateMiniCard(medioCard, aggregate.medio, baseKg);
			window.__DIST_CLASS_UI_OVERRIDE = true;
			syncExtraMedioState(aggregate);
		}

		// Ajusta gauge circular e indicadores de estoque com novos percentuais.
		function updateGaugeAndInventory({ targetKg, classifiedKg }){
			const kpis = state.dom.classificacao.kpis;
			const gauge = state.dom.classificacao.gauge;
			const card = state.dom.classificacao.card;
			const pendenteClass = (card?.getAttribute('data-pendente-class') || '').toUpperCase();
			const estoqueKg = Math.max(0, (targetKg || 0) - (classifiedKg || 0));
			if(kpis?.estoque){
				if(estoqueKg > 1){
					kpis.estoque.innerHTML = `<span class="estoque-alert">⚠️</span>${formatInt(estoqueKg)} kg`;
				}else{
					kpis.estoque.textContent = `${formatInt(estoqueKg)} kg`;
				}
				const box = kpis.estoque.closest?.('.kpi');
				if(box){
					if(estoqueKg > 1){
						box.classList.add('kpi--warn');
						box.classList.remove('kpi--muted');
					}else if(Math.round(estoqueKg) === 0){
						box.classList.add('kpi--muted');
						box.classList.remove('kpi--warn');
					}else{
						box.classList.remove('kpi--warn');
						box.classList.remove('kpi--muted');
					}
				}
			}
			if(kpis?.estoqueApprox){
				const peso = getKgPerCx();
				const approxCx = peso > 0 ? (estoqueKg / peso) : 0;
				kpis.estoqueApprox.textContent = `~ ${utils.formatDecimal(approxCx, 1)} cx`;
			}
			if(kpis?.aproveitamento){
				const snapshot = getEntradaSnapshot();
				const esperadoKg = snapshot.cx > 0 ? (snapshot.cx * 22) : targetKg;
				const kgUtil = Math.min(classifiedKg, esperadoKg || 0);
				const aprPct = classifiedKg > 0 ? (kgUtil / classifiedKg) * 100 : 0;
				kpis.aproveitamento.textContent = `${aprPct.toLocaleString('pt-BR',{maximumFractionDigits:1})}%`;
			}
			if(gauge?.arc && gauge?.pct){
				const target = targetKg > 0 ? targetKg : classifiedKg;
				let progress = 0;
				if(pendenteClass === 'N') progress = 1;
				else if(target > 0) progress = Math.max(0, Math.min(1, classifiedKg / target));
				const arcLen = Math.PI * 90;
				requestAnimationFrame(()=>{
					gauge.arc.setAttribute('stroke-dasharray', `0 ${arcLen.toFixed(1)}`);
					void gauge.arc.getBBox();
					gauge.arc.setAttribute('stroke-dasharray', `${(arcLen * progress).toFixed(1)} ${arcLen.toFixed(1)}`);
				});
				const pctText = `${(progress * 100).toLocaleString('pt-BR',{maximumFractionDigits:1})}%`;
				gauge.pct.textContent = pctText;
				if(gauge.label) gauge.label.textContent = 'Classificado';
				if(gauge.watermark){
					if(pendenteClass === 'N') gauge.watermark.classList.add('is-visible');
					else gauge.watermark.classList.remove('is-visible');
				}
			}
		}

		// Recalcula porcentagens linha a linha após qualquer atualização manual.
		function refreshRowPercentages(){
			const bodyEl = state.dom.classificacao.body;
			if(!bodyEl) return;
			const rows = Array.from(bodyEl.querySelectorAll('.class-row'));
			if(!rows.length) return;
			const totalKg = rows.reduce((sum, row)=> sum + parseLocaleNumber(row.dataset.kg), 0);
			if(!(totalKg > 0)) return;
			rows.forEach((row)=>{
				const pct = Math.max(0, Math.min(100, (parseLocaleNumber(row.dataset.kg) / totalKg) * 100));
				const pctEl = row.querySelector('.pct-val');
				const bar = row.querySelector('.percent-bar span');
				if(pctEl) pctEl.textContent = `${pct.toLocaleString('pt-BR',{maximumFractionDigits:1})}%`;
				if(bar) bar.style.width = `${pct.toFixed(1)}%`;
			});
		}

		// Gera novamente totais e atualiza elementos dependentes dos datasets.
		function recalcClassificacaoMetrics(){
			refreshRowPercentages();
			const target = Number(state.dom.classificacao.card?.getAttribute('data-target')) || computeTargetKgFallback();
			const classified = Number(state.dom.classificacao.card?.getAttribute('data-classified')) || (cache.payloads.classificacao?.aggregate?.totalKg || 0);
			updateGaugeAndInventory({ targetKg: target, classifiedKg: classified });
		}

		// Pipeline completo de recarregamento do card de classificação.
		async function runClassificacaoReload(options = {}){
			const lote = resolveLote(options);
			if(!lote){
				logger.warn('Nenhum lote disponível para recarregar a classificação.');
				return;
			}
			mutateContext({ lote });
			if(!state.dom.classificacao.card || !state.dom.classificacao.body){
				logger.warn('Card de classificação indisponível no DOM.');
				return;
			}
			setClassPlaceholder('Carregando…');
			setLoading('classificacao', true);
			try{
				const resumo = await fetchClassificacaoResumo(lote, options);
				const linhas = Array.isArray(resumo?.linhas) ? resumo.linhas : [];
				const descarteKg = Number(resumo?.extra?.qtdbatidas) || 0;
				const rendered = renderClassificacaoRows({ lote, linhas, descarteKg });
				const detail = await fetchLoteDetails(lote);
				await ensureCanonicalExtraMedioCodes(rendered.aggregate);
				if(detail && detail.pendente_class && state.dom.classificacao.card){
					state.dom.classificacao.card.setAttribute('data-pendente-class', String(detail.pendente_class).toUpperCase());
					if(typeof window.__updateToggleFromPendenteClass === 'function'){
						window.__updateToggleFromPendenteClass();
					}
				}
				const targetKg = computeTargetKgFallback();
				state.dom.classificacao.card?.setAttribute('data-target', String(Math.round(targetKg || 0)));
				state.dom.classificacao.card?.setAttribute('data-classified', String(Math.round(rendered.aggregate.totalKg || 0)));
				updateResumoCards({ aggregate: rendered.aggregate, detail, targetKg, kgPerCx: rendered.kgPerCx });
				updateMiniCards(rendered.aggregate);
				cache.payloads.classificacao = {
					lote,
					linhas,
					aggregate: rendered.aggregate,
					detail,
					targetKg,
					descarteKg,
					fetchedAt: Date.now()
				};
				recalcClassificacaoMetrics();
				events.emit('dashboard:classificacao:updated', cache.payloads.classificacao);
				window.dispatchEvent(new Event('classificacao:updated'));
			}catch(err){
				logger.error('Falha ao carregar classificação', err);
				setClassPlaceholder(err?.message || 'Erro ao carregar classificação.');
				utils.toast('Erro ao atualizar classificação.', 'error');
			}finally{
				setLoading('classificacao', false);
			}
		}

		window.recalcClassificacaoMetrics = recalcClassificacaoMetrics;
		// Exposição compatível com legado para reusar o novo renderizador.
		function legacyRenderClassCardsFromClassification(payload){
			if(payload && payload.aggregate){
				updateMiniCards(payload.aggregate);
				return;
			}
			if(payload && typeof payload.totalKg !== 'undefined' && payload.extra && payload.medio){
				updateMiniCards(payload);
				return;
			}
			if(cache.payloads.classificacao?.aggregate){
				updateMiniCards(cache.payloads.classificacao.aggregate);
				return;
			}
			updateMiniCards(null);
		}
		window.__DIST_renderClassCardsFromClassification = legacyRenderClassCardsFromClassification;
		window.__updateQtysFromClass = updateQtysFromClass;

		async function reloadEntradaInternal(){
			mutateContext(extractContext());
			events.emit('dashboard:entrada:updated', state.context);
			return state.context;
		}

		async function reloadListaInternal(options = {}){
			if(typeof window.loadLista !== 'function'){
				logger.warn('ListaShell não disponível para reload.');
				return false;
			}
			const reset = typeof options.reset === 'boolean' ? options.reset : Boolean(options.force || options.reason === 'filters');
			const preserveScroll = options.preserveScroll ?? !reset;
			setLoading('lista', true);
			try{
				await window.loadLista({
					reset,
					filterState: options.filterState || window.__COM_FILTER_STATE,
					preserveScroll,
					preserveState: true
				});
				return true;
			}catch(err){
				logger.error('Falha ao recarregar lista', err);
				utils.toast('Erro ao recarregar a lista.', 'error');
				throw err;
			}finally{
				setLoading('lista', false);
			}
		}

		async function reloadValeResumoInternal(options = {}){
			const reason = options.reason || 'manual';
			const targetNunota = options.nunota || state.context.nunota || valeShell?.state?.current?.nunota;
			if(!targetNunota){
				// Evita logar warning em ciclos automáticos (boot/silent) onde ainda não há seleção.
				if(reason !== 'initial' && reason !== 'silent'){
					logger.warn('Nenhuma nota disponível para recarregar o Vale.');
				}
				return false;
			}
			try{
				if(valeShell && typeof valeShell.open === 'function'){
					await valeShell.open(targetNunota, { force: options.force || options.full, forceReload: options.force || options.full });
					return true;
				}
				if(typeof window.openValeResumo === 'function'){
					await window.openValeResumo(targetNunota, { forceReload: options.force || options.full });
					return true;
				}
				logger.warn('Vale shell não disponível para reload.');
				return false;
			}catch(err){
				logger.error('Erro ao recarregar resumo do vale', err);
				throw err;
			}
		}

		async function reloadDistribuicaoInternal(){
			logger.info('reloadDistribuicao() aguardando implementação.');
			return false;
		}

		async function refreshDashboard(options = {}){
			const scope = normalizeRefreshScope(options.scope);
			const scopeSet = new Set(scope);
			const reason = options.reason || 'manual';
			const results = {};
			const failures = [];
			const runStep = async (label, runner)=>{
				try{
					results[label] = await runner();
				}catch(err){
					failures.push({ label, error: err });
					logger.error(`[Dashboard] Falha ao atualizar ${label}`, err);
				}
			};
			if(scopeSet.has('lista')){
				await runStep('lista', ()=> reloadListaInternal({
					force: options.force || options.forceLista,
					reason,
					filterState: options.filterState,
					reset: options.resetLista
				}));
			}
			if(scopeSet.has('entrada')){
				await runStep('entrada', ()=> reloadEntradaInternal());
			}
			if(scopeSet.has('classificacao')){
				await runStep('classificacao', ()=> runClassificacaoReload({
					...options,
					lote: options.lote,
					force: options.force || options.forceClassificacao
				}));
			}
			if(scopeSet.has('vale')){
				await runStep('vale', ()=> reloadValeResumoInternal({
					nunota: options.nunota,
					force: options.force || options.forceVale,
					full: options.fullVale,
					reason
				}));
			}
			if(scopeSet.has('distribuicao')){
				await runStep('distribuicao', ()=> reloadDistribuicaoInternal(options));
			}
			events.emit('dashboard:refresh:complete', { scope, reason, failures, results });
			if(failures.length){
				const message = failures.length === scopeSet.size ? 'Falha ao atualizar o dashboard.' : 'Dashboard atualizado parcialmente.';
				utils.toast(message, failures.length === scopeSet.size ? 'error' : 'warning');
				if(failures.length === scopeSet.size){
					const error = failures[0]?.error || new Error(message);
					error.details = failures;
					throw error;
				}
			}
			return results;
		}

		// Listener do botão de atualizar classificação com proteção contra spam.
		function handleRefreshClick(ev){
			const trigger = ev.target.closest('[data-dashboard-refresh]');
			if(!trigger) return;
			ev.preventDefault();
			const target = (trigger.dataset.dashboardRefresh || '').toLowerCase();
			const force = trigger.dataset.force === 'true' || trigger.hasAttribute('data-force');
			const scope = VALID_REFRESH_SCOPE.has(target) ? [target] : undefined;
			state.actions.reloadDashboard({ scope, force, reason: 'button' }).catch((err)=> logger.error('Refresh manual falhou', err));
		}

		// Pausa/resume atualizações quando a aba perde foco para economizar recursos.
		function handleVisibility(){
			if(doc.hidden) return;
			if(state.ready){
				state.actions.queueSilentRefresh?.();
			}
		}

		// Expõe funções chave no escopo global para scripts antigos.
		function exposeLegacyApi(){
			const api = {
				state,
				clearDashboard: (opts)=> state.actions.clearDashboard(opts),
				reloadDashboard: (opts)=> state.actions.reloadDashboard(opts),
				reloadClassificacao: (lote)=> state.actions.reloadDashboard({ scope: ['classificacao'], lote }),
				reloadValeResumo: (nunota, opts)=> state.actions.reloadDashboard({ scope: ['vale'], nunota, ...opts }),
				reloadDistribuicao: ()=> state.actions.reloadDashboard({ scope: ['distribuicao'] }),
				refreshValeInterfaces: legacyRefreshValeInterfaces
			};
			window.__PH_DASHBOARD__ = api;
			window.__reloadClassificacaoCard = (lote)=> api.reloadDashboard({ scope: ['classificacao'], lote });
			window.__refreshValeInterfaces = (nunota, options)=> legacyRefreshValeInterfaces(nunota, options);
		}
		function registerActions(){
			state.actions = {
				clearDashboard: (options = {})=> clearDashboardState(options),
				reloadEntrada: async (options = {})=> reloadEntradaInternal(options),
				reloadClassificacao: async (options = {})=> runClassificacaoReload(options),
				reloadValeResumo: async (options = {})=> reloadValeResumoInternal(options),
				reloadDistribuicao: async (options = {})=> reloadDistribuicaoInternal(options),
				reloadLista: async (options = {})=> reloadListaInternal(options),
				reloadDashboard: async (options = {})=> refreshDashboard(options),
				queueSilentRefresh: debounce(async ()=>{
					await state.actions.reloadDashboard({ reason: 'silent' });
				}, 800)
			};
		}

		// Sequência de inicialização do dashboard Shell.
		function init(){
			registerActions();
			exposeLegacyApi();
			initEntradaEditors();
			doc.addEventListener('click', handleRefreshClick);
			doc.addEventListener('visibilitychange', handleVisibility);
			if(state.dom.buttons.reloadClass){
				state.dom.buttons.reloadClass.addEventListener('click', (ev)=>{
					ev.preventDefault();
					state.actions.reloadDashboard({ scope: ['classificacao'], force: true, reason: 'button' }).catch((err)=> logger.error('Refresh manual (botão) falhou', err));
				});
			}
			state.ready = true;
			events.emit('dashboard:ready', state);
			logger.info('Dashboard pronto para migração dos módulos.');
			// No boot inicial evitamos incluir o vale para que o modal só abra via ícone do carrinho.
			const initialScopes = state.context.lote ? ['classificacao','distribuicao'] : ['distribuicao'];
			state.actions.reloadDashboard({ scope: initialScopes, reason: 'initial' }).catch((err)=> logger.error('Refresh inicial falhou', err));
		}

		init();
		return state;
	});

	// Entrada oficial do script: prepara serviços e dispara módulos necessários.
	function boot(){
		if(App.flags.booted) return;
		App.flags.booted = true;
		logger.info('Boot iniciando...', App.flags);
		initModule('valeShell');
		if(flags.isPortal) initModule('portalShell');
		if(flags.isDashboard){
			initModule('dashboardShell');
			initModule('filtersShell');
			initModule('listaShell');
		}
		logger.info('Boot concluído.');
	}

	if(doc.readyState === 'complete' || doc.readyState === 'interactive'){
		setTimeout(boot, 0);
	}else{
		doc.addEventListener('DOMContentLoaded', boot, { once: true });
	}

	try{
		window.IAgro = Object.assign(window.IAgro || {}, namespace);
		window.showToast = Utils.toast;
		window.normalizeNunota = Utils.normalizeNunota;
	}catch(err){
		logger.error('Falha ao expor namespace global', err);
	}
})();
