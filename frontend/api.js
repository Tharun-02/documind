// frontend/api.js
// Shared API helpers: token management, fetch wrappers, SSE

const API_BASE = 'https://documind-api-6vyu.onrender.com'; // Backend URL in production

// Token management
function getToken() {
    return localStorage.getItem('token');
}

function setToken(token) {
    if (token) {
        localStorage.setItem('token', token);
    } else {
        localStorage.removeItem('token');
    }
}

function clearToken() {
    localStorage.removeItem('token');
}

// Authenticated fetch wrapper
async function apiFetch(endpoint, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
    });

    // Handle 401 - token expired/invalid
    if (response.status === 401) {
        clearToken();
        window.location.hash = '#/auth';
        throw new Error('Session expired. Please login again.');
    }

    return response;
}

// FormData fetch (for file uploads)
async function apiFetchForm(endpoint, formData) {
    const token = getToken();
    const headers = {};

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers,
        body: formData,
    });

    if (response.status === 401) {
        clearToken();
        window.location.hash = '#/auth';
        throw new Error('Session expired. Please login again.');
    }

    return response;
}

// SSE connection helper
function createEventSource(endpoint, body, onMessage, onError, onOpen) {
    // SSE doesn't support POST with body natively, so we use fetch + stream reading
    // For true SSE with POST, we'd need a different approach
    // Here we use the /query/agent/stream endpoint which accepts POST
    return fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`,
            'Accept': 'text/event-stream',
        },
        body: JSON.stringify(body),
    }).then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function read() {
            return reader.read().then(({ done, value }) => {
                if (done) {
                    if (buffer.trim()) {
                        // Process remaining buffer
                        processBuffer(buffer);
                    }
                    return;
                }

                buffer += decoder.decode(value, { stream: true });
                processBuffer(buffer);
                return read();
            });
        }

        function processBuffer(buf) {
            const lines = buf.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        onMessage(data);
                    } catch (e) {
                        console.error('Failed to parse SSE:', line);
                    }
                }
            }
        }

        if (onOpen) onOpen();
        return read().catch(err => {
            if (onError) onError(err);
        });
    });
}

// API methods
const API = {
    // Auth
    register: (email, password) => apiFetch('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
    }),

    login: (email, password) => apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
    }),

    // Documents
    uploadDocument: (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return apiFetchForm('/documents/upload', formData);
    },

    listDocuments: () => apiFetch('/documents/'),

    deleteDocument: (id) => apiFetch(`/documents/${id}`, { method: 'DELETE' }),

    compareDocuments: (doc1Id, doc2Id, threshold) => apiFetch('/documents/compare', {
        method: 'POST',
        body: JSON.stringify({ document_id_1: doc1Id, document_id_2: doc2Id, threshold }),
    }),

    // Query / Agent
    queryAgent: (question, documentIds, topK) => apiFetch('/query/agent', {
        method: 'POST',
        body: JSON.stringify({ question, document_ids: documentIds, top_k: topK }),
    }),

    queryAgentStream: (question, documentIds, topK, onMessage, onError, onOpen) => {
        return createEventSource('/query/agent/stream', {
            question,
            document_ids: documentIds,
            top_k: topK,
        }, onMessage, onError, onOpen);
    },

    // Health
    checkHealth: () => fetch(`${API_BASE}/health`),
};

export { API, getToken, setToken, clearToken };