/**
 * BEW Alpine.js Global Stores
 * 
 * Loaded on every page via layout.html.
 * Individual page components are in alpine-components/*.js
 */

document.addEventListener('alpine:init', () => {

    // ── App Settings Store (Font & Scale) ─────────────────
    Alpine.store('appSettings', {
        scale: localStorage.getItem('bew-app-scale') || 'm',
        fontFamily: localStorage.getItem('bew-font-family') || 'default',

        scales: {
            's': '11px',
            'm': '12px',
            'l': '13px',
            'xl': '14px'
        },

        fonts: {
            'default': "'Noto Sans Bengali', system-ui, -apple-system, sans-serif",
            'inter': "'Inter', 'Noto Sans Bengali', sans-serif",
            'poppins': "'Poppins', 'Noto Sans Bengali', sans-serif",
            'roboto': "'Roboto', 'Noto Sans Bengali', sans-serif"
        },

        init() {
            this.applySettings();
        },

        setScale(s) {
            this.scale = s;
            localStorage.setItem('bew-app-scale', s);
            this.applySettings();
        },

        setFont(f) {
            this.fontFamily = f;
            localStorage.setItem('bew-font-family', f);
            this.applySettings();
        },

        applySettings() {
            const root = document.documentElement;
            // Apply scale
            const size = this.scales[this.scale] || this.scales['m'];
            root.style.fontSize = size;

            // Apply font
            const font = this.fonts[this.fontFamily] || this.fonts['default'];
            root.style.setProperty('--font-primary', font);
        }
    });

    // ── Sidebar Store ─────────────────────────────────────
    Alpine.store('sidebar', {
        collapsed: JSON.parse(localStorage.getItem('bew-sidebar-collapsed') || 'false'),
        mobileOpen: false,
        width: parseInt(localStorage.getItem('bew-sidebar-width') || '280', 10),
        minWidth: 220,
        maxWidth: 400,

        toggle() {
            this.collapsed = !this.collapsed;
            localStorage.setItem('bew-sidebar-collapsed', JSON.stringify(this.collapsed));
        },
        expand() { this.collapsed = false; localStorage.setItem('bew-sidebar-collapsed', 'false'); },
        collapse() { this.collapsed = true; localStorage.setItem('bew-sidebar-collapsed', 'true'); },
        openMobile() { this.mobileOpen = true; },
        closeMobile() { this.mobileOpen = false; },
        setWidth(w) {
            this.width = Math.max(this.minWidth, Math.min(this.maxWidth, w));
            localStorage.setItem('bew-sidebar-width', String(this.width));
        }
    });

    // ── Category Panel Store ──────────────────────────────
    Alpine.store('catPanel', {
        open: false,
        toggle() { this.open = !this.open; },
        close() { this.open = false; }
    });

    // ── Header Toolbar Store ─────────────────────────────
    // Driven by #page-meta element inside #content-area.
    // Synced on load + every HTMX swap.
    Alpine.store('header', {
        title: '',
        icon: '',
        searchUrl: '',
        searchQuery: '',
        addUrl: '',
        backUrl: '',

        sync() {
            const meta = document.getElementById('page-meta');
            if (!meta) { this.title = ''; this.icon = ''; this.searchUrl = ''; this.addUrl = ''; this.backUrl = ''; return; }
            this.title = meta.dataset.title || '';
            this.icon = meta.dataset.icon || '';
            this.searchUrl = meta.dataset.searchUrl || '';
            this.searchQuery = meta.dataset.searchQuery || '';
            this.addUrl = meta.dataset.addUrl || '';
            this.backUrl = meta.dataset.backUrl || '';
        }
    });

    // ── Confirm Dialog Store ──────────────────────────────
    Alpine.store('confirm', {
        open: false,
        message: '',
        action: null,

        show(message, action) {
            this.message = message;
            this.action = action;
            this.open = true;
        },

        accept() {
            if (this.action) this.action();
            this.reset();
        },

        cancel() { this.reset(); },

        reset() {
            this.open = false;
            this.message = '';
            this.action = null;
        }
    });

    // ── Delete Confirmation Store ────────────────────────
    // Used by components/_delete.html for password-based delete
    Alpine.store('deleteConfirm', {
        open: false,
        actionUrl: '',

        show(url) {
            this.actionUrl = url;
            this.open = true;
            // Focus password input after modal opens
            setTimeout(() => {
                const input = document.querySelector('[x-ref="deletePasswordInput"]');
                if (input) input.focus();
            }, 100);
        },

        cancel() {
            this.open = false;
            this.actionUrl = '';
        }
    });
});

// ── Header Sync: runs after Alpine init + every HTMX content swap ──
function bewSyncHeader() {
    if (window.Alpine && Alpine.store) {
        Alpine.store('header').sync();
    }
}
// Sync once Alpine is fully initialized (replaces unreliable DOMContentLoaded + rAF hack)
document.addEventListener('alpine:initialized', bewSyncHeader);
// Re-sync on every HTMX swap into content-area
document.addEventListener('htmx:afterSwap', (e) => {
    if (e.detail.target && e.detail.target.id === 'content-area') {
        bewSyncHeader();
    }
});
