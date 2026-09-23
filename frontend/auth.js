// frontend/auth.js
// Auth view logic: register, login, logout

import { API, setToken, clearToken } from './api.js';
import { navigate } from './router.js';

let authInitialized = false;

function initAuthView() {
    if (authInitialized) return;
    authInitialized = true;

    const registerForm = document.getElementById('register-form');
    const loginForm = document.getElementById('login-form');
    const registerLink = document.getElementById('register-link');
    const loginLink = document.getElementById('login-link');
    const authMessage = document.getElementById('auth-message');
    const logoutBtn = document.getElementById('logout-btn');

    // Switch between register/login forms
    registerLink?.addEventListener('click', (e) => {
        e.preventDefault();
        showForm('register-form');
    });

    loginLink?.addEventListener('click', (e) => {
        e.preventDefault();
        showForm('login-form');
    });

    // Register form submit
    registerForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('reg-email').value;
        const password = document.getElementById('reg-password').value;
        const submitBtn = registerForm.querySelector('button[type="submit"]');

        setLoading(submitBtn, true);
        hideMessage(authMessage);

        try {
            const response = await API.register(email, password);

            if (response.ok) {
                showMessage(authMessage, 'Registration successful! Please login.', 'success');
                registerForm.reset();
                showForm('login-form');
            } else {
                const error = await response.json();
                showMessage(authMessage, error.detail || 'Registration failed', 'error');
            }
        } catch (err) {
            showMessage(authMessage, err.message || 'Network error', 'error');
        } finally {
            setLoading(submitBtn, false);
        }
    });

    // Login form submit
    loginForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        const submitBtn = loginForm.querySelector('button[type="submit"]');

        setLoading(submitBtn, true);
        hideMessage(authMessage);

        try {
            const response = await API.login(email, password);

            if (response.ok) {
                const data = await response.json();
                setToken(data.access_token);
                showMessage(authMessage, 'Login successful!', 'success');
                loginForm.reset();

                // Redirect to chat after short delay
                setTimeout(() => navigate('chat'), 500);
            } else {
                const error = await response.json();
                showMessage(authMessage, error.detail || 'Login failed', 'error');
            }
        } catch (err) {
            showMessage(authMessage, err.message || 'Network error', 'error');
        } finally {
            setLoading(submitBtn, false);
        }
    });

    // Logout button (in header)
    logoutBtn?.addEventListener('click', (e) => {
        e.preventDefault();
        clearToken();
        navigate('auth');
    });
}

function showForm(formId) {
    document.querySelectorAll('#view-auth form').forEach(form => {
        form.classList.add('hidden');
    });
    const form = document.getElementById(formId);
    if (form) form.classList.remove('hidden');
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
    button.disabled = loading;
    button.textContent = loading ? 'Please wait...' : button.dataset.originalText || button.textContent;
    if (!loading && button.dataset.originalText) {
        button.textContent = button.dataset.originalText;
    } else if (!button.dataset.originalText) {
        button.dataset.originalText = button.textContent;
    }
}

export { initAuthView };