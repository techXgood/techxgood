// loaded in <head>: the "js" class hides the elements animated on scroll before the first paint
document.documentElement.classList.add('js');

const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Return a safe absolute http(s) url, or null (blocks "javascript:" and other schemes)
function safeUrl(url) {
    if (!url) return null;
    // some websites are saved without scheme (e.g. "www.example.org")
    const withScheme = /^[a-z][a-z0-9+.-]*:/i.test(url) ? url : `https://${url}`;
    try {
        const parsed = new URL(withScheme);
        return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : null;
    } catch {
        return null;
    }
}

// 12345 -> "12K"
const compactNumber = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 });

// localStorage can throw (private mode, blocked site data): the preferences are optional
function readPreference(key) {
    try {
        return localStorage.getItem(key);
    } catch {
        return null;
    }
}

function savePreference(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch {
        // not saved: the page works the same
    }
}

// Call the callback once, the first time the element enters the screen
function onVisible(element, callback, rootMargin = '0px 0px -10% 0px') {
    if (!element) return;
    if (!('IntersectionObserver' in window)) {
        callback(element);
        return;
    }
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                observer.disconnect();
                callback(element);
            }
        });
    }, { rootMargin });
    observer.observe(element);
}

// Fade in the ".reveal" elements while scrolling (also the ones added later with observeReveal)
function observeReveal(elements) {
    elements.forEach(element => onVisible(element, el => el.classList.add('is-visible')));
}

function initHeader() {
    const header = document.querySelector('.site-header');
    const toggle = document.querySelector('.nav-toggle');
    const nav = document.getElementById('siteNav');

    if (header) {
        const update = () => header.classList.toggle('is-scrolled', window.scrollY > 40);
        update();
        window.addEventListener('scroll', update, { passive: true });
    }

    if (toggle && nav) {
        const close = () => {
            toggle.setAttribute('aria-expanded', 'false');
            nav.classList.remove('is-open');
        };
        toggle.addEventListener('click', () => {
            const open = toggle.getAttribute('aria-expanded') !== 'true';
            toggle.setAttribute('aria-expanded', String(open));
            nav.classList.toggle('is-open', open);
        });
        // close the mobile menu after choosing a link (e.g. an anchor of the same page)
        nav.addEventListener('click', (event) => {
            if (event.target.closest('a')) close();
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') close();
        });
    }
}

function initBackToTop() {
    const button = document.querySelector('.back-to-top');
    if (!button) return;
    const update = () => button.classList.toggle('is-visible', window.scrollY > 600);
    update();
    window.addEventListener('scroll', update, { passive: true });
    button.addEventListener('click', () => window.scrollTo({ top: 0, behavior: prefersReducedMotion ? 'auto' : 'smooth' }));
}

// "/" moves the focus to the search box (like many search engines)
function initSearchShortcut() {
    document.addEventListener('keydown', (event) => {
        if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return;
        const target = event.target;
        if (target.closest('input, textarea, select, [contenteditable="true"]')) return;
        const input = document.getElementById('searchInput');
        if (input) {
            event.preventDefault();
            input.focus();
            input.select();
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.current-year').forEach(el => { el.textContent = new Date().getFullYear(); });
    initHeader();
    initBackToTop();
    initSearchShortcut();
    observeReveal(document.querySelectorAll('.reveal'));
});
