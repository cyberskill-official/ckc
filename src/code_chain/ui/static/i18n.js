class I18n {
    constructor() {
        this.locale = localStorage.getItem('ckc_lang') || 'en';
        this.translations = {};
        this.subscribers = [];
    }

    async init() {
        try {
            const resp = await fetch(`/locales/${this.locale}.json`);
            this.translations = await resp.json();
            this.applyTranslations();
        } catch (e) {
            console.error('Failed to load i18n file', e);
        }
    }

    async setLocale(lang) {
        this.locale = lang;
        localStorage.setItem('ckc_lang', lang);
        await this.init();
        this.notifySubscribers();
    }

    t(key) {
        const parts = key.split('.');
        let current = this.translations;
        for (const part of parts) {
            if (current[part] === undefined) return key;
            current = current[part];
        }
        return current;
    }

    applyTranslations() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translation = this.t(key);
            
            if (el.tagName === 'INPUT' && el.hasAttribute('placeholder')) {
                el.placeholder = translation;
            } else if (el.tagName === 'BUTTON' && el.hasAttribute('title')) {
                el.title = translation;
            } else {
                // If the element has children, try not to overwrite non-text nodes if possible
                // But for simplicity, we set textContent if it's a simple element
                // Or if it contains spans, we might need a more complex logic.
                // We'll assume simple text injection for now.
                el.textContent = translation;
            }
        });
    }

    subscribe(callback) {
        this.subscribers.push(callback);
    }

    notifySubscribers() {
        for (const cb of this.subscribers) {
            cb();
        }
    }
}

window.i18n = new I18n();
document.addEventListener('DOMContentLoaded', () => {
    window.i18n.init();
});
// Update lang label
document.addEventListener('DOMContentLoaded', () => {
    window.i18n.subscribe(() => {
        const lbl = document.getElementById('lang-label');
        if (lbl) {
            lbl.textContent = window.i18n.locale.toUpperCase();
        }
    });
});
