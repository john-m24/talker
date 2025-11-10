// Chat history
let chatHistory = [];

// Resize and center window when it loads (popup mode)
window.onload = function() {
    // Only resize if window was opened in a new tab (not a popup)
    // Check if we can resize (some browsers restrict this)
    try {
        const width = 600;
        const height = 500;
        const left = Math.max(0, (screen.width - width) / 2);
        const top = Math.max(0, (screen.height - height) / 2);
        
        // Try to resize and move window
        window.resizeTo(width, height);
        window.moveTo(left, top);
        
        // Focus the input field
        document.getElementById('command-input').focus();
    } catch (e) {
        // Some browsers restrict window resizing - that's okay
        // Just focus the input field
        document.getElementById('command-input').focus();
    }
};

let suggestions = [];
let selectedIndex = -1;
let debounceTimer = null;
let bestSuggestion = null;

const input = document.getElementById('command-input');
const suggestionsDiv = document.getElementById('suggestions');
const ghostText = document.getElementById('ghost-text');
const chatContainer = document.getElementById('chat-container');
const closeButton = document.getElementById('close-button');

// Close dialog
function closeDialog() {
    fetch('/close', {method: 'POST'})
        .then(() => {
            window.close();
        })
        .catch(err => {
            console.error('Error closing dialog:', err);
            window.close();
        });
}

// Set up close button
if (closeButton) {
    closeButton.addEventListener('click', closeDialog);
}

// Add message to chat
function addMessage(type, content) {
    const message = {
        type: type,
        content: content,
        timestamp: Date.now()
    };
    chatHistory.push(message);
    renderMessage(message);
    scrollToBottom();
}

// Render a single message
function renderMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ' + message.type;
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    if (typeof message.content === 'string') {
        // Plain text message - preserve line breaks
        const lines = message.content.split('\n');
        lines.forEach((line, index) => {
            if (index > 0) {
                bubble.appendChild(document.createElement('br'));
            }
            bubble.appendChild(document.createTextNode(line));
        });
    } else if (message.content && message.content.title && message.content.items) {
        // List results
        const title = document.createElement('div');
        title.className = 'message-title';
        title.textContent = message.content.title;
        bubble.appendChild(title);
        
        const list = document.createElement('ul');
        list.className = 'message-list';
        message.content.items.forEach(item => {
            const li = document.createElement('li');
            li.textContent = item;
            list.appendChild(li);
        });
        bubble.appendChild(list);
    }
    
    messageDiv.appendChild(bubble);
    chatContainer.appendChild(messageDiv);
}

// Scroll chat to bottom
function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

input.addEventListener('input', function() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        fetchSuggestions(input.value);
    }, 100);
    updateGhostText();
});

input.addEventListener('keydown', function(e) {
    if (e.key === 'Tab') {
        e.preventDefault();
        if (bestSuggestion && bestSuggestion.text) {
            // Complete with best suggestion and submit
            input.value = bestSuggestion.text;
            updateGhostText();
            handleSubmit();
        }
    } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (suggestions.length > 0) {
            selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
            updateSuggestions();
        }
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = Math.max(selectedIndex - 1, -1);
        updateSuggestions();
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedIndex >= 0 && suggestions[selectedIndex]) {
            input.value = suggestions[selectedIndex].text;
            suggestions = [];
            selectedIndex = -1;
            bestSuggestion = null;
            updateSuggestions();
            updateGhostText();
        } else {
            // Submit the command - use state machine
            handleSubmit();
        }
    } else if (e.key === 'Escape') {
        // Don't close on escape, just clear input
        input.value = '';
        updateGhostText();
    } else {
        // Update ghost text on any other key press
        setTimeout(updateGhostText, 0);
    }
});

function fetchSuggestions(text) {
    if (!text) {
        suggestions = [];
        selectedIndex = -1;
        bestSuggestion = null;
        updateSuggestions();
        updateGhostText();
        return;
    }

    fetch('/suggest?text=' + encodeURIComponent(text))
        .then(response => response.json())
        .then(data => {
            suggestions = data.suggestions || [];
            bestSuggestion = suggestions.length > 0 ? suggestions[0] : null;
            selectedIndex = -1;
            updateSuggestions();
            updateGhostText();
        })
        .catch(err => {
            console.error('Error fetching suggestions:', err);
            suggestions = [];
            bestSuggestion = null;
            updateSuggestions();
            updateGhostText();
        });
}

function updateGhostText() {
    const currentText = input.value;
    
    if (!bestSuggestion || !bestSuggestion.text) {
        ghostText.textContent = '';
        return;
    }

    const suggestionText = bestSuggestion.text;
    
    // Check if suggestion starts with current text (case-insensitive)
    if (suggestionText.toLowerCase().startsWith(currentText.toLowerCase()) && currentText.length > 0) {
        // Show the full suggestion, but make the matching prefix transparent
        // This ensures perfect alignment
        const remaining = suggestionText.substring(currentText.length);
        ghostText.innerHTML = '<span class="ghost-prefix">' + escapeHtml(currentText) + '</span><span class="ghost-suffix">' + escapeHtml(remaining) + '</span>';
    } else {
        ghostText.textContent = '';
    }
}

function updateSuggestions() {
    suggestionsDiv.innerHTML = '';
    if (suggestions.length === 0) {
        suggestionsDiv.classList.remove('show');
        return;
    }
    suggestionsDiv.classList.add('show');
    suggestions.forEach((suggestion, index) => {
        const div = document.createElement('div');
        div.className = 'suggestion' + (index === selectedIndex ? ' selected' : '');
        const label = document.createElement('div');
        label.className = 'suggestion-label';
        label.textContent = suggestion.display || suggestion.text;
        div.appendChild(label);
        div.onclick = () => {
            input.value = suggestion.text;
            suggestions = [];
            selectedIndex = -1;
            bestSuggestion = null;
            updateSuggestions();
            updateGhostText();
        };
        suggestionsDiv.appendChild(div);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Submit normal command (not clarification)
function submitCommand(command) {
    // Add user message to chat
    addMessage('user', command);
    
    // Clear input
    input.value = '';
    updateGhostText();
    suggestions = [];
    selectedIndex = -1;
    bestSuggestion = null;
    updateSuggestions();
    
    // Submit command
    fetch('/submit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({command: command, keep_open: true})
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('HTTP error! status: ' + response.status);
        }
        return response.json();
    })
    .then(data => {
        // Start polling for results after submitting command
        startResultsPolling();
        // Keep dialog open and wait for results
        input.focus();
    })
    .catch(err => {
        console.error('Error submitting:', err);
        addMessage('system', {title: 'Error', items: ['Failed to submit command. Please try again.']});
    });
}

let resultsPollInterval = null;
let resultsPollAttempts = 0;
const MAX_RESULT_POLL_ATTEMPTS = 20; // 10 seconds (20 * 500ms)

function startResultsPolling() {
    // Stop any existing polling
    stopResultsPolling();
    
    // Reset attempt counter
    resultsPollAttempts = 0;
    
    // Poll for results every 500ms
    resultsPollInterval = setInterval(() => {
        resultsPollAttempts++;
        
        // Stop polling after max attempts (most commands don't produce results)
        if (resultsPollAttempts >= MAX_RESULT_POLL_ATTEMPTS) {
            stopResultsPolling();
            return;
        }
        
        fetch('/get-results')
            .then(response => response.json())
            .then(data => {
                if (data.results && !data.consumed) {
                    // Add results as system message
                    addMessage('system', data.results);
                    // Stop polling after receiving results
                    stopResultsPolling();
                }
            })
            .catch(err => {
                // Silently handle errors
            });
    }, 500);
}

function stopResultsPolling() {
    if (resultsPollInterval) {
        clearInterval(resultsPollInterval);
        resultsPollInterval = null;
        resultsPollAttempts = 0;
    }
}

// State machine for dialog modes
const DialogMode = {
    NORMAL: 'normal',
    CLARIFICATION: 'clarification'
};

let dialogState = {
    mode: DialogMode.NORMAL,
    clarificationData: null
};

let clarificationPollTimeout = null;

function handleSubmit() {
    const command = input.value.trim();
    if (!command) {
        return;
    }
    
    // Route to appropriate handler based on mode
    if (dialogState.mode === DialogMode.CLARIFICATION) {
        submitClarification(command);
    } else {
        submitCommand(command);
    }
}

function submitClarification(correctedText) {
    fetch('/submit-clarification', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: correctedText, cancelled: false})
    })
    .then(() => {
        addMessage('user', correctedText);
        input.value = '';
        // Exit clarification mode
        dialogState.mode = DialogMode.NORMAL;
        dialogState.clarificationData = null;
        input.focus();
        // Resume clarification polling after handling
        startClarificationPolling();
    })
    .catch(err => {
        console.error('Error submitting clarification:', err);
        addMessage('system', {title: 'Error', items: ['Failed to submit clarification.']});
        // Resume clarification polling even on error
        startClarificationPolling();
    });
}

function pollForClarification() {
    // Clear any existing timeout
    if (clarificationPollTimeout) {
        clearTimeout(clarificationPollTimeout);
        clarificationPollTimeout = null;
    }
    
    fetch('/get-clarification')
        .then(response => response.json())
        .then(data => {
            if (data.clarification && !data.consumed) {
                // Show clarification as system message
                const reason = data.clarification.reason || 'Did I hear that correctly?';
                const text = data.clarification.text || '';
                addMessage('system', `⚠️ ${reason}\n\nTranscribed: "${text}"\n\nPlease confirm or correct:`);
                
                // Pre-fill input with transcribed text
                input.value = text;
                input.focus();
                input.select();
                
                // Enter clarification mode
                dialogState.mode = DialogMode.CLARIFICATION;
                dialogState.clarificationData = data.clarification;
            } else {
                // Poll again after a longer delay (2 seconds instead of 500ms)
                // Only poll if we're not in clarification mode
                if (dialogState.mode !== DialogMode.CLARIFICATION) {
                    clarificationPollTimeout = setTimeout(pollForClarification, 2000);
                }
            }
        })
        .catch(err => {
            // Silently handle errors, poll again after delay
            if (dialogState.mode !== DialogMode.CLARIFICATION) {
                clarificationPollTimeout = setTimeout(pollForClarification, 2000);
            }
        });
}

function startClarificationPolling() {
    // Clear any existing timeout first
    if (clarificationPollTimeout) {
        clearTimeout(clarificationPollTimeout);
    }
    // Start polling
    clarificationPollTimeout = setTimeout(pollForClarification, 2000);
}

function stopClarificationPolling() {
    if (clarificationPollTimeout) {
        clearTimeout(clarificationPollTimeout);
        clarificationPollTimeout = null;
    }
}

// Start polling for clarification requests (with longer interval)
startClarificationPolling();

