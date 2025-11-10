"""Web-based text input dialog with auto-complete."""

import threading
import webbrowser
import time
import socket
import subprocess
from typing import Optional, List, Dict, Any
from flask import Flask, render_template_string, request, jsonify
from ..config import AUTOCOMPLETE_MAX_SUGGESTIONS, WEB_PORT

# HTML template with auto-complete
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Voice Agent - Text Command</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            padding: 20px;
            max-width: 600px;
            margin: 0 auto;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h2 {
            margin-top: 0;
            color: #333;
        }
        .input-wrapper {
            position: relative;
            width: 100%;
            margin-bottom: 10px;
        }
        #command-input {
            width: 100%;
            padding: 12px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
            background-color: transparent;
            position: relative;
            z-index: 2;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }
        #command-input:focus {
            outline: none;
            border-color: #007AFF;
        }
        #ghost-text {
            position: absolute;
            top: 12px;
            left: 12px;
            font-size: 16px;
            color: #999;
            pointer-events: none;
            z-index: 1;
            white-space: pre;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            padding: 0;
            margin: 0;
            border: none;
            background: transparent;
            line-height: 1.5;
            overflow: hidden;
        }
        #ghost-text .ghost-prefix {
            color: transparent;
        }
        #ghost-text .ghost-suffix {
            color: #999;
        }
        #suggestions {
            margin-top: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            max-height: 200px;
            overflow-y: auto;
            background-color: white;
        }
        .suggestion {
            padding: 10px 12px;
            cursor: pointer;
            border-bottom: 1px solid #eee;
            transition: background-color 0.1s;
        }
        .suggestion:hover, .suggestion.selected {
            background-color: #f0f0f0;
        }
        .suggestion:last-child {
            border-bottom: none;
        }
        .suggestion-label {
            font-weight: 500;
            color: #333;
            font-size: 14px;
        }
        .suggestion-text {
            color: #666;
            font-size: 12px;
            margin-top: 2px;
        }
        .buttons {
            margin-top: 20px;
            text-align: right;
        }
        button {
            padding: 10px 20px;
            margin-left: 10px;
            font-size: 14px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        #ok-button {
            background-color: #007AFF;
            color: white;
        }
        #ok-button:hover {
            background-color: #0051D5;
        }
        #cancel-button {
            background-color: #f0f0f0;
            color: #333;
        }
        #cancel-button:hover {
            background-color: #e0e0e0;
        }
        .empty-state {
            padding: 20px;
            text-align: center;
            color: #999;
            font-size: 14px;
        }
        #results {
            margin-top: 15px;
            padding: 15px;
            background-color: #f9f9f9;
            border-radius: 4px;
            border: 1px solid #e0e0e0;
            max-height: 300px;
            overflow-y: auto;
            display: none;
        }
        #results.show {
            display: block;
        }
        .results-title {
            font-weight: 600;
            color: #333;
            margin-bottom: 10px;
            font-size: 14px;
        }
        .result-item {
            padding: 8px 0;
            border-bottom: 1px solid #eee;
            font-size: 14px;
            color: #333;
        }
        .result-item:last-child {
            border-bottom: none;
        }
        .result-item-number {
            color: #666;
            font-weight: 500;
            margin-right: 8px;
        }
        .result-item-content {
            color: #333;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>Voice Agent - Text Command</h2>
        <div id="results"></div>
        <div id="clarification" style="display: none; margin-bottom: 15px; padding: 15px; background-color: #fff3cd; border: 1px solid #ffc107; border-radius: 4px;">
            <div style="font-weight: 600; color: #856404; margin-bottom: 8px;">⚠️ Did I hear that correctly?</div>
            <div id="clarification-reason" style="color: #856404; margin-bottom: 10px; font-size: 14px;"></div>
            <div style="color: #856404; margin-bottom: 10px; font-size: 14px;">Transcribed text:</div>
        </div>
        <div class="input-wrapper">
            <input type="text" id="command-input" placeholder="Enter your command..." autofocus>
            <div id="ghost-text"></div>
        </div>
        <div id="suggestions"></div>
        <div class="buttons">
            <button id="cancel-button" onclick="cancel()">Cancel</button>
            <button id="ok-button" onclick="submit()">OK</button>
        </div>
    </div>

    <script>
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
            
            // Start polling for clarification requests
            pollForClarification();
        };

        let suggestions = [];
        let selectedIndex = -1;
        let debounceTimer = null;
        let bestSuggestion = null;

        const input = document.getElementById('command-input');
        const suggestionsDiv = document.getElementById('suggestions');
        const ghostText = document.getElementById('ghost-text');

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
                    submit();
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
                    submit();
                }
            } else if (e.key === 'Escape') {
                cancel();
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
                return;
            }
            suggestions.forEach((suggestion, index) => {
                const div = document.createElement('div');
                div.className = 'suggestion' + (index === selectedIndex ? ' selected' : '');
                div.innerHTML = `
                    <div class="suggestion-label">${escapeHtml(suggestion.display || suggestion.text)}</div>
                `;
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

        function submit() {
            const command = input.value;
            // Check if it's a list command - if so, don't close immediately
            const isListCommand = /^(list|show)\s+(apps|applications|tabs)/i.test(command) || 
                                /^(apps|applications|tabs)$/i.test(command.trim());
            
            fetch('/submit', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: command, keep_open: isListCommand})
            })
            .then(() => {
                if (isListCommand) {
                    // Clear input and wait for results
                    input.value = '';
                    input.placeholder = 'Waiting for results...';
                    input.disabled = true;
                    // Poll for results
                    pollForResults();
                } else {
                    window.close();
                }
            })
            .catch(err => {
                console.error('Error submitting:', err);
                window.close();
            });
        }

        function pollForResults() {
            let pollInterval = null;
            let hasReceivedResults = false;
            
            // Poll for results every 200ms
            pollInterval = setInterval(() => {
                if (hasReceivedResults) {
                    clearInterval(pollInterval);
                    return;
                }
                
                fetch('/get-results')
                    .then(response => response.json())
                    .then(data => {
                        if (data.results && !hasReceivedResults) {
                            hasReceivedResults = true;
                            clearInterval(pollInterval);
                            showResults(data.results);
                            input.placeholder = 'Enter follow-up command...';
                            input.disabled = false;
                            input.focus();
                        } else if (data.consumed && !data.results) {
                            // Results were already consumed, stop polling
                            hasReceivedResults = true;
                            clearInterval(pollInterval);
                            input.placeholder = 'Enter your command...';
                            input.disabled = false;
                        }
                    })
                    .catch(err => {
                        console.error('Error polling for results:', err);
                        // On error, stop polling after a few attempts
                        clearInterval(pollInterval);
                        input.placeholder = 'Enter your command...';
                        input.disabled = false;
                    });
            }, 200);
            
            // Stop polling after 10 seconds
            setTimeout(() => {
                if (pollInterval) {
                    clearInterval(pollInterval);
                }
                if (input.disabled) {
                    input.placeholder = 'Enter your command...';
                    input.disabled = false;
                }
            }, 10000);
        }

        function showResults(results) {
            const resultsDiv = document.getElementById('results');
            if (!results || !results.items || results.items.length === 0) {
                resultsDiv.innerHTML = '';
                resultsDiv.classList.remove('show');
                return;
            }
            
            let html = `<div class="results-title">${escapeHtml(results.title || 'Results')}</div>`;
            results.items.forEach((item, index) => {
                html += `<div class="result-item"><span class="result-item-number">${index + 1}.</span><span class="result-item-content">${escapeHtml(item)}</span></div>`;
            });
            
            resultsDiv.innerHTML = html;
            resultsDiv.classList.add('show');
            
            // Scroll results into view
            resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function cancel() {
            // Check if we're in clarification mode
            const clarificationDiv = document.getElementById('clarification');
            if (clarificationDiv && clarificationDiv.style.display !== 'none') {
                // Submit cancellation for clarification
                fetch('/submit-clarification', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({cancelled: true})
                })
                .then(() => {
                    window.close();
                })
                .catch(err => {
                    console.error('Error cancelling clarification:', err);
                    window.close();
                });
            } else {
                // Regular cancel
                fetch('/cancel', {method: 'POST'})
                .then(() => {
                    window.close();
                })
                .catch(err => {
                    console.error('Error cancelling:', err);
                    window.close();
                });
            }
        }
        
        function pollForClarification() {
            fetch('/get-clarification')
                .then(response => response.json())
                .then(data => {
                    if (data.clarification && !data.consumed) {
                        // Show clarification UI
                        const clarificationDiv = document.getElementById('clarification');
                        const reasonDiv = document.getElementById('clarification-reason');
                        const input = document.getElementById('command-input');
                        
                        if (clarificationDiv && reasonDiv && input) {
                            clarificationDiv.style.display = 'block';
                            if (data.clarification.reason) {
                                reasonDiv.textContent = 'Reason: ' + data.clarification.reason;
                            } else {
                                reasonDiv.textContent = '';
                            }
                            input.value = data.clarification.text;
                            input.focus();
                            input.select();
                            
                            // Update OK button to submit clarification
                            const okButton = document.getElementById('ok-button');
                            if (okButton) {
                                okButton.onclick = function() {
                                    submitClarification();
                                };
                            }
                        }
                    } else {
                        // Poll again after a delay
                        setTimeout(pollForClarification, 500);
                    }
                })
                .catch(err => {
                    console.error('Error polling for clarification:', err);
                    // Poll again after a delay
                    setTimeout(pollForClarification, 500);
                });
        }
        
        function submitClarification() {
            const input = document.getElementById('command-input');
            const text = input ? input.value : '';
            
            fetch('/submit-clarification', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text: text, cancelled: false})
            })
            .then(() => {
                window.close();
            })
            .catch(err => {
                console.error('Error submitting clarification:', err);
                window.close();
            });
        }
    </script>
</body>
</html>
"""




# Module-level variable to store active dialog instance
_active_dialog: Optional['WebTextInputDialog'] = None


def get_active_dialog() -> Optional['WebTextInputDialog']:
    """Get the currently active dialog instance."""
    return _active_dialog


def set_active_dialog(dialog: Optional['WebTextInputDialog']):
    """Set the currently active dialog instance."""
    global _active_dialog
    _active_dialog = dialog


def _find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """
    Find an available port starting from start_port.
    
    Args:
        start_port: Starting port number
        max_attempts: Maximum number of ports to try
        
    Returns:
        Available port number
    """
    for i in range(max_attempts):
        port = start_port + i
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    # If no port found, return start_port anyway (will fail later)
    return start_port


class WebTextInputDialog:
    """Web-based text input dialog with auto-complete."""
    
    def __init__(self, autocomplete_engine=None, cache_manager=None, port=None):
        """
        Initialize the web dialog.
        
        Args:
            autocomplete_engine: AutocompleteEngine instance
            cache_manager: CacheManager instance
            port: Port for the web server (defaults to config value)
        """
        self.autocomplete_engine = autocomplete_engine
        self.cache_manager = cache_manager
        self.port = port or WEB_PORT
        self.result = None
        self.app = Flask(__name__)
        self.server_thread = None
        self.shutdown_event = threading.Event()
        self.command_ready_event = threading.Event()  # Signal when a command is ready
        self.results = None
        self.results_lock = threading.Lock()
        self.clarification_text = None
        self.clarification_reason = None
        self.clarification_event = threading.Event()  # Signal when clarification is ready
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            return render_template_string(HTML_TEMPLATE)
        
        @self.app.route('/suggest')
        def suggest():
            text = request.args.get('text', '')
            if not text or not self.autocomplete_engine or not self.cache_manager:
                return jsonify({'suggestions': []})
            
            # Get context from cache
            context = {
                'running_apps': self.cache_manager.get('running_apps', []),
                'installed_apps': self.cache_manager.get('installed_apps', []),
                'chrome_tabs': self.cache_manager.get('chrome_tabs', []),
                'presets': list(self.cache_manager.get('presets', {}).keys()) if isinstance(self.cache_manager.get('presets', {}), dict) else [],
                'command_history': self.cache_manager.get_history()
            }
            
            # Get suggestions
            suggestions = self.autocomplete_engine.suggest_all(text, context)
            return jsonify({
                'suggestions': [s for s in suggestions[:AUTOCOMPLETE_MAX_SUGGESTIONS]]
            })
        
        @self.app.route('/submit', methods=['POST'])
        def submit():
            data = request.json
            command = data.get('command', '')
            keep_open = data.get('keep_open', False)
            
            # Store command for processing
            self.result = command
            
            # Clear previous results when submitting new command
            with self.results_lock:
                self.results = None
            
            if not keep_open:
                # Signal shutdown for non-list commands
                self.shutdown_event.set()
                # Try to shutdown server (works with Werkzeug development server)
                try:
                    func = request.environ.get('werkzeug.server.shutdown')
                    if func:
                        func()
                except Exception:
                    pass
            else:
                # For list commands, signal that command is ready (but don't shutdown)
                self.command_ready_event.set()
            return jsonify({'status': 'ok'})
        
        @self.app.route('/get-results', methods=['GET'])
        def get_results():
            """Get results if available."""
            with self.results_lock:
                if self.results:
                    results = self.results
                    # Don't clear immediately - keep results until next command
                    # This prevents race conditions with polling
                    return jsonify({'results': results, 'consumed': False})
                return jsonify({'results': None, 'consumed': True})
        
        @self.app.route('/show-results', methods=['POST'])
        def show_results():
            """Set results to display in the dialog."""
            data = request.json
            with self.results_lock:
                self.results = {
                    'title': data.get('title', 'Results'),
                    'items': data.get('items', [])
                }
            return jsonify({'status': 'ok'})
        
        @self.app.route('/get-clarification', methods=['GET'])
        def get_clarification():
            """Get clarification request if available."""
            if self.clarification_text is not None:
                clarification = {
                    'text': self.clarification_text,
                    'reason': self.clarification_reason
                }
                return jsonify({'clarification': clarification, 'consumed': False})
            return jsonify({'clarification': None, 'consumed': True})
        
        @self.app.route('/submit-clarification', methods=['POST'])
        def submit_clarification():
            """Submit clarification response."""
            data = request.json
            confirmed_text = data.get('text', '')
            cancelled = data.get('cancelled', False)
            
            if cancelled:
                self.result = None
            else:
                self.result = confirmed_text
            
            # Signal that clarification is ready
            self.clarification_event.set()
            return jsonify({'status': 'ok'})
        
        @self.app.route('/cancel', methods=['POST'])
        def cancel():
            self.result = None
            # Signal shutdown
            self.shutdown_event.set()
            # Try to shutdown server (works with Werkzeug development server)
            try:
                func = request.environ.get('werkzeug.server.shutdown')
                if func:
                    func()
            except Exception:
                pass
            return jsonify({'status': 'cancelled'})
    
    def show(self) -> Optional[str]:
        """Show dialog and return entered text or None if cancelled."""
        # Set as active dialog
        set_active_dialog(self)
        
        # Check if server is already running (for follow-up commands)
        server_already_running = self.server_thread and self.server_thread.is_alive()
        
        if not server_already_running:
            # Find available port
            self.port = _find_available_port(self.port)
            
            # Reset events
            self.shutdown_event.clear()
            self.command_ready_event.clear()
            
            # Start server in background thread
            self.server_thread = threading.Thread(
                target=lambda: self.app.run(port=self.port, debug=False, use_reloader=False, host='127.0.0.1')
            )
            self.server_thread.daemon = True
            self.server_thread.start()
            
            # Wait a moment for server to start
            time.sleep(0.5)
            
            # Open browser in popup window (macOS) - centered on screen
            url = f'http://127.0.0.1:{self.port}'
        
            # Window dimensions (keep original small size)
            window_width = 600
            window_height = 500
            
            # Detect default browser and open in popup window (only one browser)
            try:
                default_browser = webbrowser.get()
                browser_name = default_browser.name.lower()
                
                # Determine which browser to use
                if 'chrome' in browser_name:
                    browser_app = "Google Chrome"
                elif 'safari' in browser_name:
                    browser_app = "Safari"
                else:
                    # For other browsers, just use regular webbrowser.open()
                    browser_app = None
                
                if browser_app:
                    # Use AppleScript to open in popup window (centered)
                    script = f'''
                    tell application "{browser_app}"
                        activate
                        set newWindow to make new window
                        set URL of active tab of newWindow to "{url}"
                        -- Get screen dimensions and center the window
                        tell application "System Events"
                            set screenSize to size of desktop
                            set screenWidth to item 1 of screenSize
                            set screenHeight to item 2 of screenSize
                        end tell
                        set leftPos to (screenWidth - {window_width}) / 2
                        set topPos to (screenHeight - {window_height}) / 2
                        set rightPos to leftPos + {window_width}
                        set bottomPos to topPos + {window_height}
                        set bounds of newWindow to {{leftPos, topPos, rightPos, bottomPos}}
                    end tell
                    '''
                    result = subprocess.run(
                        ["osascript", "-e", script],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode != 0 or result.stderr:
                        # If AppleScript failed, fall back to regular browser open
                        webbrowser.open(url)
                else:
                    # For non-Chrome/Safari browsers, use regular webbrowser.open()
                    webbrowser.open(url)
            except Exception as e:
                # If anything fails, fall back to regular browser open
                print(f"Warning: Could not open browser in popup mode: {e}")
                try:
                    webbrowser.open(url)
                except Exception as e2:
                    print(f"Warning: Could not open browser: {e2}")
                    # Server will still run, user can manually open browser
        else:
            # Server already running, just reset events for next command
            self.shutdown_event.clear()
            self.command_ready_event.clear()
        
        # Wait for commands - handle both list commands (stay open) and regular commands (close)
        while True:
            # Wait for either shutdown (cancel/non-list command) or command ready (list command)
            # Use a short timeout to periodically check both events
            if self.shutdown_event.wait(timeout=0.1):
                # Shutdown event set - user cancelled or submitted non-list command
                break
            
            if self.command_ready_event.is_set():
                # Command ready - it's a list command, return it and keep dialog open
                command = self.result
                self.result = None  # Clear for next command
                self.command_ready_event.clear()  # Reset for next submission
                return command
        
        # Clear active dialog
        set_active_dialog(None)
        
        # Give a moment for cleanup
        time.sleep(0.2)
        
        return self.result
    
    def send_results(self, title: str, items: List[str]):
        """
        Send results to display in the dialog.
        
        Args:
            title: Title for the results
            items: List of result items to display
        """
        with self.results_lock:
            self.results = {
                'title': title,
                'items': items
            }
    
    def request_clarification(self, text: str, reason: Optional[str] = None) -> Optional[str]:
        """
        Request clarification from the user via the web dialog.
        
        Args:
            text: The text that needs clarification
            reason: Optional reason why clarification is needed
            
        Returns:
            The confirmed/corrected text if user confirms, or None if cancelled
        """
        # Set clarification request
        self.clarification_text = text
        self.clarification_reason = reason
        self.clarification_event.clear()
        self.result = None
        
        # Make sure the dialog is open
        if not (self.server_thread and self.server_thread.is_alive()):
            # Dialog not open yet, open it
            # Set as active dialog
            set_active_dialog(self)
            
            # Find available port
            self.port = _find_available_port(self.port)
            
            # Reset events
            self.shutdown_event.clear()
            self.command_ready_event.clear()
            self.clarification_event.clear()
            
            # Start server in background thread
            self.server_thread = threading.Thread(
                target=lambda: self.app.run(port=self.port, debug=False, use_reloader=False, host='127.0.0.1')
            )
            self.server_thread.daemon = True
            self.server_thread.start()
            
            # Wait a moment for server to start
            time.sleep(0.5)
            
            # Open browser in popup window (macOS) - centered on screen
            url = f'http://127.0.0.1:{self.port}'
            
            # Window dimensions (keep original small size)
            window_width = 600
            window_height = 500
            
            # Detect default browser and open in popup window (only one browser)
            try:
                default_browser = webbrowser.get()
                browser_name = default_browser.name.lower()
                
                # Determine which browser to use
                if 'chrome' in browser_name:
                    browser_app = "Google Chrome"
                elif 'safari' in browser_name:
                    browser_app = "Safari"
                else:
                    # For other browsers, just use regular webbrowser.open()
                    browser_app = None
                
                if browser_app:
                    # Use AppleScript to open in popup window (centered)
                    script = f'''
                    tell application "{browser_app}"
                        activate
                        set newWindow to make new window
                        set URL of active tab of newWindow to "{url}"
                        -- Get screen dimensions and center the window
                        tell application "System Events"
                            set screenSize to size of desktop
                            set screenWidth to item 1 of screenSize
                            set screenHeight to item 2 of screenSize
                            set windowLeft to (screenWidth - {window_width}) / 2
                            set windowTop to (screenHeight - {window_height}) / 2
                            tell process "{browser_app}"
                                set position of window 1 to {{windowLeft, windowTop}}
                                set size of window 1 to {{{window_width}, {window_height}}}
                            end tell
                        end tell
                    end tell
                    '''
                    
                    try:
                        subprocess.run(
                            ["osascript", "-e", script],
                            capture_output=True,
                            timeout=5
                        )
                    except Exception as e:
                        print(f"Warning: Could not open browser popup: {e}")
                        # Fallback to default browser
                        webbrowser.open(url)
                else:
                    # For other browsers, just use regular webbrowser.open()
                    webbrowser.open(url)
            except Exception as e:
                print(f"Warning: Could not detect browser: {e}")
                # Fallback to default browser
                webbrowser.open(url)
        
        # Wait for clarification response
        self.clarification_event.wait(timeout=300)  # 5 minute timeout
        
        # Clear clarification request
        self.clarification_text = None
        self.clarification_reason = None
        
        return self.result

