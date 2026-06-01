/* ============================================================
   CADASTROS — Helpers compartilhados (Mai/2026)
   Reutilizado por cadastros_parceiros.js, _produtos.js, _veiculos.js
   Expõe window.CadHelpers
   ============================================================ */
(function () {
    'use strict';

    function escapeHtml(s) {
        if (s === null || s === undefined) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function iniciais(texto) {
        if (!texto) return '?';
        const partes = String(texto).trim().split(/\s+/).filter(Boolean);
        if (!partes.length) return '?';
        if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
        return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
    }

    function corDoHash(str) {
        let h = 0;
        for (let i = 0; i < (str || '').length; i++) {
            h = ((h << 5) - h) + str.charCodeAt(i);
        }
        const cores = [
            '#5e7e4a', '#825e38', '#3b6ea5', '#a05a8a',
            '#7a6b48', '#5a807a', '#a05a3b', '#4a6b8a',
        ];
        return cores[Math.abs(h) % cores.length];
    }

    function showToast(msg, tipo) {
        if (window.IAgro && IAgro.showToast) {
            IAgro.showToast(msg, tipo || 'info');
        } else {
            console.log('[' + (tipo || 'info').toUpperCase() + '] ' + msg);
        }
    }

    function debounce(fn, ms) {
        if (window.IAgro && IAgro.debounce) return IAgro.debounce(fn, ms);
        let t;
        return function () {
            const args = arguments;
            clearTimeout(t);
            t = setTimeout(function () { fn.apply(null, args); }, ms);
        };
    }

    function fmtCpfCnpj(s) {
        if (!s) return '';
        const v = String(s).replace(/\D/g, '');
        if (v.length === 11) {
            return v.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
        }
        if (v.length === 14) {
            return v.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5');
        }
        return s;
    }

    function fmtNumeroBR(n, casas) {
        if (n === null || n === undefined || n === '') return '';
        const num = Number(n);
        if (isNaN(num)) return String(n);
        return num.toLocaleString('pt-BR', {
            minimumFractionDigits: casas || 0,
            maximumFractionDigits: casas || 0,
        });
    }

    window.CadHelpers = {
        escapeHtml: escapeHtml,
        iniciais: iniciais,
        corDoHash: corDoHash,
        showToast: showToast,
        debounce: debounce,
        fmtCpfCnpj: fmtCpfCnpj,
        fmtNumeroBR: fmtNumeroBR,
    };
})();
