/**
 * BEW Live Search — Alpine.js Component
 * 
 * Debounced search with AJAX results dropdown.
 * Replaces the search logic in script.js (L131-180).
 * 
 * Usage:
 *   <div x-data="liveSearch({ url: '/search', minChars: 2, debounceMs: 300 })">
 *     <input type="text" x-model="query" @input.debounce="search()" />
 *     <div x-show="results.length > 0" x-cloak>
 *       <template x-for="item in results">
 *         <a :href="item.url" x-text="item.name"></a>
 *       </template>
 *     </div>
 *   </div>
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('liveSearch', (config = {}) => ({
        query: '',
        results: [],
        loading: false,
        url: config.url || '/',
        minChars: config.minChars || 2,
        _controller: null,

        async search() {
            if (this.query.length < this.minChars) {
                this.results = [];
                return;
            }

            // Cancel previous request
            if (this._controller) {
                this._controller.abort();
            }
            this._controller = new AbortController();

            this.loading = true;
            try {
                const response = await fetch(
                    `${this.url}?q=${encodeURIComponent(this.query)}`,
                    { signal: this._controller.signal }
                );
                if (response.ok) {
                    const data = await response.json();
                    this.results = data.results || data;
                }
            } catch (e) {
                if (e.name !== 'AbortError') {
                    console.error('Search failed:', e);
                }
            } finally {
                this.loading = false;
            }
        },

        clear() {
            this.query = '';
            this.results = [];
        }
    }));
});
