// DocuMind Frontend Script
// Handles authentication, document upload, listing, and comparison

// API base URL
// For development, leave empty string (same origin)
// For production, set to your deployed backend URL (e.g., 'https://your-backend.up.railway.app')
const API_BASE = '';

// Store token in localStorage
let token = localStorage.getItem('token') || null;

// DOM elements
const authSection = document.getElementById('auth-section');
const uploadSection = document.getElementById('upload-section');
const documentsSection = document.getElementById('documents-section');
const compareSection = document.getElementById('compare-section');
const apiStatus = document.getElementById('api-status');
const healthCheck = document.getElementById('health-check');
const registerForm = document.getElementById('register-form');
const loginForm = document.getElementById('login-form');
const uploadForm = document.getElementById('upload-form');
const uploadResult = document.getElementById('upload-result');
const documentsList = document.getElementById('documents-list');
const refreshDocsBtn = document.getElementById('refresh-docs');
const compareForm = document.getElementById('compare-form');
const compareResult = document.getElementById('compare-result');
const doc1Select = document.getElementById('doc1-select');
const doc2Select = document.getElementById('doc2-select');
const registerLink = document.getElementById('register-link');
const loginLink = document.getElementById('login-link');
const uploadLink = document.getElementById('upload-link');
const documentsLink = document.getElementById('documents-link');
const compareLink = document.getElementById('compare-link');
const logoutLink = document.getElementById('logout-link');

// Navigation links
registerLink.addEventListener('click', (e) => {
    e.preventDefault();
    showSection('auth-section');
    showForm('register-form');
});

loginLink.addEventListener('click', (e) => {
    e.preventDefault();
    showSection('auth-section');
    showForm('login-form');
});

uploadLink.addEventListener('click', (e) => {
    e.preventDefault();
    if (token) {
        showSection('upload-section');
    } else {
        showSection('auth-section');
        showForm('login-form');
    }
});

documentsLink.addEventListener('click', (e) => {
    e.preventDefault();
    if (token) {
        showSection('documents-section');
        loadDocuments();
    } else {
        showSection('auth-section');
        showForm('login-form');
    }
});

compareLink.addEventListener('click', (e) => {
    e.preventDefault();
    if (token) {
        showSection('compare-section');
        loadDocumentOptions();
    } else {
        showSection('auth-section');
        showForm('login-form');
    }
});

logoutLink.addEventListener('click', (e) => {
    e.preventDefault();
    logout();
});

// Forms
registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;

    try {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });

        if (response.ok) {
            showMessage('Registration successful! Please login.', 'success');
            showForm('login-form');
            registerForm.reset();
        } else {
            const error = await response.json();
            showMessage(error.detail || 'Registration failed', 'error');
        }
    } catch (err) {
        showMessage('Network error', 'error');
    }
});

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });

        if (response.ok) {
            const data = await response.json();
            token = data.access_token;
            localStorage.setItem('token', token);
            showMessage('Login successful!', 'success');
            loginForm.reset();
            showSection('upload-section');
        } else {
            const error = await response.json();
            showMessage(error.detail || 'Login failed', 'error');
        }
    } catch (err) {
        showMessage('Network error', 'error');
    }
});

uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('upload-file');
    const file = fileInput.files[0];

    if (!file) {
        showMessage('Please select a file', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/documents/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            showMessage(`Uploaded! Chunks: ${result.chunk_count}`, 'success');
            uploadForm.reset();
            // Refresh document list if we're in documents section
            if (!documentsSection.classList.contains('hidden')) {
                loadDocuments();
            }
            // Refresh compare options if we're in compare section
            if (!compareSection.classList.contains('hidden')) {
                loadDocumentOptions();
            }
        } else {
            const error = await response.json();
            showMessage(error.detail || 'Upload failed', 'error');
        }
    } catch (err) {
        showMessage('Network error', 'error');
    }
});

refreshDocsBtn.addEventListener('click', loadDocuments);

compareForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const doc1Id = parseInt(doc1Select.value);
    const doc2Id = parseInt(doc2Select.value);
    const threshold = parseFloat(document.getElementById('threshold').value);

    if (doc1Id === doc2Id) {
        showMessage('Please select two different documents', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/documents/compare`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                document_id_1: doc1Id,
                document_id_2: doc2Id,
                threshold
            })
        });

        if (response.ok) {
            const result = await response.json();
            displayCompareResult(result);
        } else {
            const error = await response.json();
            showMessage(error.detail || 'Comparison failed', 'error', compareResult);
        }
    } catch (err) {
        showMessage('Network error', 'error', compareResult);
    }
});

// Helper functions
function showSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('section').forEach(section => {
        section.classList.add('hidden');
    });
    // Show the selected section
    document.getElementById(sectionId).classList.remove('hidden');
}

function showForm(formId) {
    // Hide all forms in auth-section
    document.querySelectorAll('#auth-section form').forEach(form => {
        form.classList.add('hidden');
    });
    // Show the selected form
    document.getElementById(formId).classList.remove('hidden');
}

function showMessage(message, type, element = document.getElementById('upload-result')) {
    element.textContent = message;
    element.className = type === 'success' ? 'success' : 'error';
    element.style.display = 'block';
}

function logout() {
    token = null;
    localStorage.removeItem('token');
    showMessage('Logged out', 'success');
    showSection('auth-section');
    showForm('login-form');
}

async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        if (response.ok) {
            healthCheck.textContent = 'API is healthy';
            healthCheck.className = 'success';
        } else {
            healthCheck.textContent = 'API is unhealthy';
            healthCheck.className = 'error';
        }
    } catch (err) {
        healthCheck.textContent = 'Cannot connect to API';
        healthCheck.className = 'error';
    }
}

async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE}/documents/`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            documentsList.innerHTML = '';
            if (data.documents.length === 0) {
                documentsList.innerHTML = '<li>No documents uploaded yet.</li>';
            } else {
                data.documents.forEach(doc => {
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <span>${doc.filename} (${doc.chunk_count} chunks)</span>
                        <span>${new Date(doc.created_at).toLocaleString()}</span>
                    `;
                    documentsList.appendChild(li);
                });
            }
        } else {
            const error = await response.json();
            showMessage(error.detail || 'Failed to load documents', 'error');
        }
    } catch (err) {
        showMessage('Network error', 'error');
    }
}

async function loadDocumentOptions() {
    try {
        const response = await fetch(`${API_BASE}/documents/`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            // Clear and repopulate selects
            doc1Select.innerHTML = '<option value="">Select document 1</option>';
            doc2Select.innerHTML = '<option value="">Select document 2</option>';

            data.documents.forEach(doc => {
                const option1 = document.createElement('option');
                option1.value = doc.id;
                option1.textContent = `${doc.filename} (${doc.chunk_count} chunks)`;
                doc1Select.appendChild(option1);

                const option2 = option1.cloneNode(true);
                doc2Select.appendChild(option2);
            });
        } else {
            const error = await response.json();
            showMessage(error.detail || 'Failed to load documents', 'error');
        }
    } catch (err) {
        showMessage('Network error', 'error');
    }
}

function displayCompareResult(result) {
    compareResult.innerHTML = `
        <h3>Comparison Results</h3>
        <p><strong>${result.document_1_filename}</strong> vs <strong>${result.document_2_filename}</strong></p>
        <p>Total comparisons: ${result.total_comparisons}</p>
        <p>Similar clauses found: ${result.similar_clauses.length}</p>
        <p>Comparison time: ${result.comparison_time_ms} ms</p>

        ${result.similar_clauses.length > 0 ? `
            <h4>Similar Clauses:</h4>
            <ul>
                ${result.similar_clauses.map(clause => `
                    <li>
                        <strong>Similarity:</strong> ${(clause.similarity_score * 100).toFixed(2)}%<br>
                        <strong>Doc 1 (p${clause.document_1_page}):</strong> "${clause.clause_1.substring(0, 100)}..."<br>
                        <strong>Doc 2 (p${clause.document_2_page}):</strong> "${clause.clause_2.substring(0, 100)}..."
                    </li>
                `).join('')}
            </ul>
        ` : '<p>No similar clauses found above the threshold.</p>'}
    `;
    compareResult.style.display = 'block';
}

// Initialize
function init() {
    // Check if we have a token
    if (token) {
        showSection('upload-section');
    } else {
        showSection('auth-section');
        showForm('login-form');
    }

    // Check API health
    checkHealth();

    // Set up periodic health checks
    setInterval(checkHealth, 30000); // Every 30 seconds
}

// Start the app
init();