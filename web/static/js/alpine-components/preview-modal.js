/**
 * BEW Preview Modal — Alpine.js Component
 * 
 * Universal PDF/image preview modal used by:
 * - work_order_detail.html
 * - shop_detail.html
 * - purchase_detail.html
 * 
 * Usage:
 *   <div x-data="previewModal()">
 *     <button @click="show('/path/to/file.pdf', 'Document Title')">Preview</button>
 *     <!-- modal renders via _modals.html macro -->
 *   </div>
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('previewModal', () => ({
        open: false,
        url: '',
        title: '',

        get isPdf() {
            return this.url.toLowerCase().endsWith('.pdf');
        },

        show(url, title) {
            this.url = url;
            this.title = title || '';
            this.open = true;
            document.body.style.overflow = 'hidden';
        },

        close() {
            this.open = false;
            this.url = '';
            this.title = '';
            document.body.style.overflow = '';
        }
    }));
});
