// frontend/router.js
// Hash-based routing for SPA

const views = ['auth', 'chat', 'documents', 'compare'];

let currentView = null;

function getHash() {
    return window.location.hash.slice(1) || '/auth';
}

function parseHash() {
    const hash = getHash();
    const [view, ...params] = hash.split('/').filter(Boolean);
    return { view: view || 'auth', params };
}

function showView(viewName) {
    // Hide all views
    views.forEach(v => {
        const el = document.getElementById(`view-${v}`);
        if (el) el.classList.add('hidden');
    });

    // Show requested view
    const targetEl = document.getElementById(`view-${viewName}`);
    if (targetEl) {
        targetEl.classList.remove('hidden');
        currentView = viewName;

        // Call view-specific init if exists
        if (window[`init${viewName.charAt(0).toUpperCase() + viewName.slice(1)}View`]) {
            window[`init${viewName.charAt(0).toUpperCase() + viewName.slice(1)}View`]();
        }
    }
}

function navigate(viewName, params = []) {
    const hash = `#/${viewName}` + (params.length ? '/' + params.join('/') : '');
    window.location.hash = hash;
}

function initRouter() {
    // Initial load
    const { view } = parseHash();
    const token = localStorage.getItem('token');

    // If no token and not on auth, redirect to auth
    if (!token && view !== 'auth') {
        navigate('auth');
        return;
    }

    // If has token and on auth, redirect to chat
    if (token && view === 'auth') {
        navigate('chat');
        return;
    }

    showView(view);

    // Listen for hash changes
    window.addEventListener('hashchange', () => {
        const { view } = parseHash();
        const token = localStorage.getItem('token');

        if (!token && view !== 'auth') {
            navigate('auth');
            return;
        }

        if (token && view === 'auth') {
            navigate('chat');
            return;
        }

        showView(view);
    });
}

// Make navigate globally available
window.navigate = navigate;

export { initRouter, navigate, showView, parseHash };