// frontend/documents.js
// Documents view logic: upload, list, delete

import { API } from './api.js';
import { navigate } from './router.js';

let documentsInitialized = false;

function initDocumentsView() {
    if (documentsInitialized) return;
    documentsInitialized = true;

    loadDocuments();
    setupEventListeners();
}

function setupEventListeners() {
    // Upload form
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('upload-file');
    const uploadResult = document.getElementById('upload-result');

    uploadForm?.addEventListener('submit', async (e) => {
        e.preventDefault();

        const file = fileInput.files[0];
        if (!file) {
            showMessage(uploadResult, 'Please select a file', 'error');
            return;
        }

        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showMessage(uploadResult, 'Only PDF files are supported', 'error');
            return;
        }

        const submitBtn = uploadForm.querySelector('button[type="submit"]');
        setLoading(submitBtn, true);
        hideMessage(uploadResult);

        try {
            const response = await API.uploadDocument(file);

            if (response.ok) {
                const result = await response.json();
                showMessage(uploadResult, `Uploaded! ${result.chunk_count} chunks created`, 'success');
                uploadForm.reset();
                loadDocuments();
            } else {
                const error = await response.json();
                showMessage(uploadResult, error.detail || 'Upload failed', 'error');
            }
        } catch (err) {
            showMessage(uploadResult, err.message || 'Network error', 'error');
        } finally {
            setLoading(submitBtn, false);
        }
    });

    // Refresh button
    const refreshBtn = document.getElementById('refresh-docs');
    refreshBtn?.addEventListener('click', loadDocuments);

    // Back to chat
    const backToChatBtn = document.getElementById('back-to-chat');
    backToChatBtn?.addEventListener('click', () => navigate('chat'));

    // Logout
    const logoutBtn = document.getElementById('logout-btn-docs');
    logoutBtn?.addEventListener('click', (e) => {
        e.preventDefault();
        localStorage.removeItem('token');
        navigate('auth');
    });
}

async function loadDocuments() {
    const listContainer = document.getElementById('documents-list');
    const emptyState = document.getElementById('documents-empty');

    if (!listContainer) return;

    try {
        const response = await API.listDocuments();

        if (response.ok) {
            const data = await response.json();
            const documents = data.documents || [];

            if (documents.length === 0) {
                listContainer.innerHTML = '';
                if (emptyState) emptyState.classList.remove('hidden');
                return;
            }

            if (emptyState) emptyState.classList.add('hidden');

            listContainer.innerHTML = documents.map(doc => `
                <li class="document-item">
                    <div class="doc-info">
                        <span class="doc-name">${doc.filename}</span>
                        <span class="doc-meta">${doc.chunk_count} chunks · ${formatDate(doc.created_at)}</span>
                    </div>
                    <button class="btn btn-danger btn-sm delete-btn" data-doc-id="${doc.id}" data-doc-name="${doc.filename}">
                        Delete
                    </button>
                </li>
            `).join('');

            // Add delete handlers
            listContainer.querySelectorAll('.delete-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const docId = parseInt(e.target.dataset.docId);
                    const docName = e.target.dataset.docName;

                    if (!confirm(`Delete "${docName}"? This cannot be undone.`)) return;

                    try {
                        const response = await API.deleteDocument(docId);
                        if (response.ok) {
                            loadDocuments();
                        } else {
                            const error = await response.json();
                            alert(error.detail || 'Delete failed');
                        }
                    } catch (err) {
                        alert(err.message || 'Network error');
                    }
                });
            });

        } else {
            const error = await response.json();
            listContainer.innerHTML = `<li class="error">Failed to load: ${error.detail}</li>`;
        }
    } catch (err) {
        listContainer.innerHTML = `<li class="error">Network error: ${err.message}</li>`;
    }
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    try {
        return new Date(dateString).toLocaleDateString();
    } catch {
        return dateString;
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
    button.disabled = loading;
    if (loading) {
        button.dataset.originalText = button.textContent;
        button.textContent = 'Please wait...';
    } else if (button.dataset.originalText) {
        button.textContent = button.dataset.originalText;
    }
}

// Re-export for router
window.initDocumentsView = initDocumentsView;

export { initDocumentsView };