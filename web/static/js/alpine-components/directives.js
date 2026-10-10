/**
 * BEW Alpine.js Directives
 * 
 * Custom directives to handle DOM interactions declaratively.
 */

document.addEventListener('alpine:init', () => {
    
    /**
     * x-focus-class
     * Adds a class to the element (or its parent) when focused.
     * Default class is 'focused'.
     * Usage: <input x-focus-class> or <input x-focus-class="'custom-class'">
     */
    Alpine.directive('focus-class', (el, { expression }, { evaluate }) => {
        const className = expression ? evaluate(expression) : 'focused';
        const target = el.parentElement; // Apply to parent as per legacy script

        const onFocus = () => target.classList.add(className);
        const onBlur = () => target.classList.remove(className);

        el.addEventListener('focus', onFocus);
        el.addEventListener('blur', onBlur);

        // Cleanup
        el._x_cleanup = () => {
            el.removeEventListener('focus', onFocus);
            el.removeEventListener('blur', onBlur);
        };
    });

    /**
     * x-tel
     * Automatically formats the href attribute into a tel: link based on numeric content.
     * Usage: <a x-tel class="mobile-link">017-XXXXXXX</a>
     */
    Alpine.directive('tel', (el) => {
        if (!el.href || !el.href.startsWith('tel:')) {
            const phone = el.textContent.trim().replace(/[^\d]/g, '');
            if (phone) {
                el.href = 'tel:' + phone;
            }
        }
    });
});
