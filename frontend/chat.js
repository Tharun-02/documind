// frontend/chat.js
// Chat view logic: SSE streaming, message display, document picker

import { API } from './api.js';
import { navigate } from './router.js';

let chatInitialized = false;
let currentDocuments = [];
let selectedDocumentIds = [];
let eventSource = null;

function initChatView() {
    if (chatInitialized) return;
    chatInitialized = true;

    // Load user's documents for the picker
    loadDocuments();

    // Set up UI event listeners
    setupEventListeners();

    // Check health
    checkHealth();
}

function setupEventListeners() {
    // Send message form
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    chatForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (!message) return;

        // Disable input while sending
        chatInput.disabled = true;
        sendBtn.disabled = true;

        // Add user message to chat
        addMessage('user', message);
        chatInput.value = '';

        // Show typing indicator
        const typingId = showTypingIndicator();

        try {
            // Stream response from agent
            await streamAgentResponse(message, selectedDocumentIds);
        } catch (err) {
            hideTypingIndicator(typingId);
            addMessage('assistant', `Error: ${err.message}`, true);
        } finally {
            chatInput.disabled = false;
            sendBtn.disabled = false;
            chatInput.focus();
        }
    });

    // Document picker toggle
    const docPickerBtn = document.getElementById('doc-picker-btn');
    const docPicker = document.getElementById('doc-picker');
    const docPickerOverlay = document.getElementById('doc-picker-overlay');

    docPickerBtn?.addEventListener('click', () => {
        docPicker.classList.toggle('hidden');
        docPickerOverlay.classList.toggle('hidden');
    });

    docPickerOverlay?.addEventListener('click', () => {
        docPicker.classList.add('hidden');
        docPickerOverlay.classList.add('hidden');
    });

    // Document checkboxes
    docPicker?.addEventListener('change', (e) => {
        if (e.target.type === 'checkbox') {
            const docId = parseInt(e.target.dataset.docId);
            if (e.target.checked) {
                selectedDocumentIds.push(docId);
            } else {
                selectedDocumentIds = selectedDocumentIds.filter(id => id !== docId);
            }
            updateDocPickerButton();
        }
    });

    // Clear selection
    const clearSelectionBtn = document.getElementById('clear-selection-btn');
    clearSelectionBtn?.addEventListener('click', () => {
        selectedDocumentIds = [];
        document.querySelectorAll('#doc-picker input[type="checkbox"]').forEach(cb => cb.checked = false);
        updateDocPickerButton();
        docPicker.classList.add('hidden');
        docPickerOverlay.classList.add('hidden');
    });

    // Navigate to documents view
    const manageDocsBtn = document.getElementById('manage-docs-btn');
    manageDocsBtn?.addEventListener('click', () => {
        navigate('documents');
    });

    // Logout
    const logoutBtn = document.getElementById('logout-btn-chat');
    logoutBtn?.addEventListener('click', (e) => {
        e.preventDefault();
        localStorage.removeItem('token');
        navigate('auth');
    });
}

async function loadDocuments() {
    try {
        const response = await API.listDocuments();
        if (response.ok) {
            const data = await response.json();
            currentDocuments = data.documents || [];
            renderDocumentPicker();
        }
    } catch (err) {
        console.error('Failed to load documents:', err);
    }
}

function renderDocumentPicker() {
    const container = document.getElementById('doc-picker-list');
    if (!container) return;

    if (currentDocuments.length === 0) {
        container.innerHTML = '<p class="empty-state">No documents uploaded yet. Go to Documents to upload.</p>';
        return;
    }

    container.innerHTML = currentDocuments.map(doc => `
        <label class="doc-picker-item">
            <input type="checkbox" data-doc-id="${doc.id}" ${selectedDocumentIds.includes(doc.id) ? 'checked' : ''}>
            <span class="doc-name">${doc.filename}</span>
            <span class="doc-meta">${doc.chunk_count} chunks</span>
        </label>
    `).join('');
}

function updateDocPickerButton() {
    const btn = document.getElementById('doc-picker-btn');
    const count = document.getElementById('selected-doc-count');
    if (btn && count) {
        if (selectedDocumentIds.length === 0) {
            btn.textContent = 'Select Documents';
            count.textContent = '';
        } else {
            btn.textContent = 'Documents Selected';
            count.textContent = `(${selectedDocumentIds.length})`;
        }
    }
}

async function streamAgentResponse(question, documentIds) {
    let fullAnswer = '';
    let messageElement = null;
    let stepsElement = null;
    let isFirstToken = true;

    try {
        await API.queryAgentStream(
            question,
            documentIds.length > 0 ? documentIds : null,
            5,
            (data) => {
                switch (data.type) {
                    case 'token':
                        if (isFirstToken) {
                            // Create assistant message element
                            messageElement = addMessage('assistant', '', false);
                            isFirstToken = false;
                        }
                        fullAnswer += data.token;
                        updateMessageContent(messageElement, fullAnswer);
                        break;

                    case 'chunks':
                        // Could show retrieved chunks as collapsible
                        if (data.retrieved_chunks && data.retrieved_chunks.length > 0) {
                            stepsElement = addStepsElement(messageElement, data.retrieved_chunks);
                        }
                        break;

                    case 'done':
                        hideTypingIndicator();
                        break;

                    case 'error':
                        hideTypingIndicator();
                        if (messageElement) {
                            updateMessageContent(messageElement, `Error: ${data.error}`);
                        } else {
                            addMessage('assistant', `Error: ${data.error}`, true);
                        }
                        break;
                }
            },
            (err) => {
                hideTypingIndicator();
                if (messageElement) {
                    updateMessageContent(messageElement, `Connection error: ${err.message}`);
                } else {
                    addMessage('assistant', `Connection error: ${err.message}`, true);
                }
            },
            () => {
                // onOpen - stream started
            }
        );
    } catch (err) {
        hideTypingIndicator();
        throw err;
    }
}

function addMessage(role, content, isError = false) {
    const container = document.getElementById('chat-messages');
    if (!container) return null;

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}${isError ? ' error' : ''}`;

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message-bubble';
    bubbleDiv.textContent = content;

    messageDiv.appendChild(bubbleDiv);
    container.appendChild(messageDiv);

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;

    return bubbleDiv;
}

function updateMessageContent(messageElement, content) {
    if (messageElement) {
        messageElement.textContent = content;
        const container = document.getElementById('chat-messages');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }
}

function addStepsElement(messageElement, chunks) {
    const stepsDiv = document.createElement('div');
    stepsDiv.className = 'agent-steps';

    const summary = document.createElement('summary');
    summary.textContent = `🔍 Retrieved ${chunks.length} chunk(s)`;

    const details = document.createElement('details');
    details.appendChild(summary);

    const content = document.createElement('div');
    content.className = 'steps-content';

    chunks.forEach((chunk, i) => {
        const item = document.createElement('div');
        item.className = 'step-item';
        item.innerHTML = `
            <strong>Chunk ${i + 1}</strong> (score: ${chunk.similarity_score?.toFixed(3) || 'N/A'})
            <br><small>${chunk.filename || 'Unknown'}, p.${chunk.page_number || '?'}</small>
            <br><span class="chunk-preview">${chunk.content?.substring(0, 150)}...</span>
        `;
        content.appendChild(item);
    });

    details.appendChild(content);
    stepsDiv.appendChild(details);

    // Insert after the message bubble
    const messageContainer = messageElement.parentElement;
    if (messageContainer) {
        messageContainer.appendChild(stepsDiv);
    }

    return stepsDiv;
}

function showTypingIndicator() {
    const container = document.getElementById('chat-messages');
    if (!container) return null;

    const typingId = 'typing-' + Date.now();
    const typingDiv = document.createElement('div');
    typingDiv.id = typingId;
    typingDiv.className = 'message assistant typing';
    typingDiv.innerHTML = '<div class="message-bubble typing-bubble"><span></span><span></span><span></span></div>';

    container.appendChild(typingDiv);
    container.scrollTop = container.scrollHeight;

    return typingId;
}

function hideTypingIndicator(typingId) {
    if (typingId) {
        const el = document.getElementById(typingId);
        if (el) el.remove();
    } else {
        // Hide all typing indicators
        document.querySelectorAll('.typing').forEach(el => el.remove());
    }
}

async function checkHealth() {
    try {
        const response = await API.checkHealth();
        const statusEl = document.getElementById('health-status');
        if (statusEl) {
            if (response.ok) {
                statusEl.textContent = '● Connected';
                statusEl.className = 'health-status connected';
            } else {
                statusEl.textContent = '● Disconnected';
                statusEl.className = 'health-status disconnected';
            }
        }
    } catch (err) {
        const statusEl = document.getElementById('health-status');
        if (statusEl) {
            statusEl.textContent = '● Disconnected';
            statusEl.className = 'health-status disconnected';
        }
    }
}

// Re-export for router
window.initChatView = initChatView;

export { initChatView };