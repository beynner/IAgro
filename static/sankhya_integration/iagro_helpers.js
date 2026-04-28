;(function(window){
  'use strict';

  function getCookie(name){ const m=document.cookie.match(new RegExp('(^| )'+name+'=([^;]+)')); return m? decodeURIComponent(m[2]) : null; }

  async function postJSON(url, body){
    const csrftoken = getCookie('csrftoken');
    const headers = {'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'};
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;
    const r = await fetch(url, {method:'POST', headers, body: JSON.stringify(body), credentials:'same-origin'});
    let j={}; try{ j=await r.json(); }catch(_){ j={}; }
    return {ok:r.ok, status:r.status, body:j};
  }

  function parseFlexibleNumber(val){
    try{ if (val == null) return NaN; if (typeof val === 'number') return val; let s = String(val).trim(); if (!s) return NaN; s = s.replace(/\./g, '').replace(/,/g, '.'); const n = parseFloat(s); return Number.isFinite(n) ? n : NaN; }catch(_){ return NaN; }
  }

  function formatBR1(n){ try{ const num = typeof n === 'number' ? n : parseFlexibleNumber(n); if (!Number.isFinite(num)) return ''; return num.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }); }catch(_){ return ''; } }

  function normalizeNunota(n){ try{ if(n==null) return null; const s = String(n).trim(); if(!s) return null; const m = s.match(/(\d+)/); if(!m) return null; const v = parseInt(m[1],10); return Number.isFinite(v) ? v : null; }catch(_){ return null; } }

  // Expose helpers globally to avoid breaking existing inline code
  try{
    window.getCookie = window.getCookie || getCookie;
    window.postJSON = window.postJSON || postJSON;
    // Backwards-compatible aliases for legacy scripts that reference __postJSON / __getCookie
    window.__getCookie = window.__getCookie || window.getCookie;
    window.__postJSON = window.__postJSON || window.postJSON;
    window.parseFlexibleNumber = window.parseFlexibleNumber || parseFlexibleNumber;
    window.formatBR1 = window.formatBR1 || formatBR1;
    window.normalizeNunota = window.normalizeNunota || normalizeNunota;
    window.IAgroHelpers = window.IAgroHelpers || { getCookie, postJSON, parseFlexibleNumber, formatBR1, normalizeNunota };
  }catch(_){ }

})(window);
