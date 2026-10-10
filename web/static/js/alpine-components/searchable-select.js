/**
 * BEW Searchable Select — Alpine.js Component
 * 
 * Replaces native <select> with a searchable dropdown.
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('searchableSelect', (initialValue = '', options = [], placeholder = '-- Select --') => ({
        open: false,
        search: '',
        selected: initialValue,
        options: options,
        placeholder: placeholder,

        get filteredOptions() {
            const query = this.search.trim().toLowerCase();
            if (query === '') {
                return this.options;
            }
            return this.options.filter(
                opt => opt.label.toLowerCase().includes(query)
            );
        },

        get selectedLabel() {
            const option = this.options.find(opt => opt.value == this.selected);
            return option ? option.label : this.placeholder;
        },

        selectOption(value) {
            this.selected = value;
            this.open = false;
            this.search = '';
        },
        
        toggle() {
            if (this.open) {
                return this.close();
            }
            this.open = true;
            this.$nextTick(() => {
                if (this.$refs.searchInput) {
                    this.$refs.searchInput.focus();
                }
            });
        },
        
        close() {
            this.open = false;
            this.search = '';
        }
    }));
});
