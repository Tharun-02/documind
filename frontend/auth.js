// frontend/auth.js
// Auth view logic: register, login, logout

import { API, setToken, clearToken } from './api.js';
import { navigate } from './router.js';

let authInitialized = false;

// DOM elements cache
let elements = {};

function initAuthView() {
    // Prevent double initialization
    if (authInitialized) return;
    authInitialized = true;

    // Cache DOM elements
    cacheElements();

    // Verify critical elements are found
    if (!elements.registerForm || !elements.loginForm || !elements.registerLink || !elements.loginLink) {
        console.error('Auth view: One or more CRITICAL elements not found', elements);
        return;
    }

    // Attach event listeners
    attachEventListeners();

    // Set initial state to register form
    showForm('register-form');
}

function cacheElements() {
    elements = {
        registerForm: document.getElementById('register-form'),
        loginForm: document.getElementById('login-form'),
        registerLink: document.getElementById('register-link'),
        loginLink: document.getElementById('login-link'),
        authMessage: document.getElementById('auth-message'),
        logoutBtn: document.getElementById('logout-btn-chat')
    };
}

function attachEventListeners() {
    // Switch between register/login forms
    elements.registerLink?.addEventListener('click', (e) => {
        e.preventDefault();
        showForm('register-form');
    });

    elements.loginLink?.addEventListener('click', (e) => {
        e.preventDefault();
        showForm('login-form');
    });

    // Register form submit
    elements.registerForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('reg-email').value.trim();
        const password = document.getElementById('reg-password').value;
        const submitBtn = elements.registerForm.querySelector('button[type="submit"]');

        // Basic client-side validation
        if (!email || !password) {
            showMessage(elements.authMessage, 'Please fill in all fields', 'error');
            return;
        }

        if (password.length < 6) {
            showMessage(elements.authMessage, 'Password must be at least 6 characters', 'error');
            return;
        }

        setLoading(submitBtn, true);
        hideMessage(elements.authMessage);

        try {
            const response = await API.register(email, password);

            if (response.ok) {
                showMessage(elements.authMessage, 'Registration successful! Please login.', 'success');
                elements.registerForm.reset();
                showForm('login-form');
            } else {
                const error = await response.json();
                showMessage(elements.authMessage, error.detail || 'Registration failed', 'error');
            }
        } catch (err) {
            showMessage(elements.authMessage, err.message || 'Network error', 'error');
        } finally {
            setLoading(submitBtn, false);
        }
    });

    // Login form submit
    elements.loginForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;
        const submitBtn = elements.loginForm.querySelector('button[type="submit"]');

        // Basic client-side validation
        if (!email || !password) {
            showMessage(elements.authMessage, 'Please fill in all fields', 'error');
            return;
        }

        setLoading(submitBtn, true);
        hideMessage(elements.authMessage);

        try {
            const response = await API.login(email, password);

            if (response.ok) {
                const data = await response.json();
                setToken(data.access_token);
                showMessage(elements.authMessage, 'Login successful!', 'success');
                elements.loginForm.reset();

                // Redirect to chat after short delay
                setTimeout(() => {
                    try {
                        navigate('chat');
                    } catch (navErr) {
                        console.error('Navigation error:', navErr);
                        // Fallback: manually set hash
                        window.location.hash = '#/chat';
                    }
                }, 500);
            } else {
                const error = await response.json();
                showMessage(elements.authMessage, error.detail || 'Login failed', 'error');
            }
        } catch (err) {
            showMessage(elements.authMessage, err.message || 'Network error', 'error');
        } finally {
            setLoading(submitBtn, false);
        }
    });

    // Logout button (in header) - only attach if element exists
    if (elements.logoutBtn) {
        elements.logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            clearToken();
            navigate('auth');
        });
    }
}

function showForm(formId) {
    // Hide all forms
    document.querySelectorAll('#view-auth form').forEach(form => {
        form.classList.add('hidden');
    });

    // Show requested form
    const form = document.getElementById(formId);
    if (form) form.classList.remove('hidden');

    // Update link visibility
    if (elements.registerLink && elements.loginLink) {
        if (formId === 'register-form') {
            // Showing register form: hide register link, show login link
            elements.registerLink.classList.add('hidden');
            elements.loginLink.classList.remove('hidden');
        } else if (formId === 'login-form') {
            // Showing login form: show register link, hide login link
            elements.registerLink.classList.remove('hidden');
            elements.loginLink.classList.add('hidden');
        }
    }
}

function showMessage(element, message, type) {
    if (!element) return;
    element.textContent = message;
    element.className = `message ${type}`;
    element.style.display = 'block';
}

function hideMessage(element) {
    if (element) element.style.display = 'none';
}

function setLoading(button, loading) {
    if (!button) return;
    if (loading) {
        // Save current text if not already saved
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.textContent;
        }
        button.disabled = true;
        button.textContent = 'Please wait...';
    } else {
        // Restore original text
        button.textContent = button.dataset.originalText || button.textContent;
        button.disabled = false;
        // Clear the saved text to avoid accumulating values
        button.dataset.originalText = '';
    }
}

export { initAuthView };

// Re-export for router
window.initAuthView = initAuthView;