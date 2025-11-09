"""Web-based text input dialog with auto-complete."""

import threading
import webbrowser
import time
import socket
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
        #command-input {
            width: 100%;
            padding: 12px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
            margin-bottom: 10px;
        }
        #command-input:focus {
            outline: none;
            border-color: #007AFF;
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
    </style>
</head>
<body>
    <div class="container">
        <h2>Voice Agent - Text Command</h2>
        <input type="text" id="command-input" placeholder="Enter your command..." autofocus>
        <div id="suggestions"></div>
        <div class="buttons">
            <button id="cancel-button" onclick="cancel()">Cancel</button>
            <button id="ok-button" onclick="submit()">OK</button>
        </div>
    </div>

    <script>
        let suggestions = [];
        let selectedIndex = -1;
        let debounceTimer = null;

        const input = document.getElementById('command-input');
        const suggestionsDiv = document.getElementById('suggestions');

        input.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                fetchSuggestions(input.value);
            }, 100);
        });

        input.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (suggestions.length > 0) {
                    selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
                    updateSuggestions();
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectedIndex = Math.max(selectedIndex - 1, -1);
                updateSuggestions();
            } else if (e.key === 'Tab' && selectedIndex >= 0 && suggestions[selectedIndex]) {
                e.preventDefault();
                input.value = suggestions[selectedIndex].text;
                suggestions = [];
                selectedIndex = -1;
                updateSuggestions();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (selectedIndex >= 0 && suggestions[selectedIndex]) {
                    input.value = suggestions[selectedIndex].text;
                    suggestions = [];
                    selectedIndex = -1;
                    updateSuggestions();
                } else {
                    submit();
                }
            } else if (e.key === 'Escape') {
                cancel();
            }
        });

        function fetchSuggestions(text) {
            if (!text) {
                suggestions = [];
                selectedIndex = -1;
                updateSuggestions();
                return;
            }

            fetch('/suggest?text=' + encodeURIComponent(text))
                .then(response => response.json())
                .then(data => {
                    suggestions = data.suggestions || [];
                    selectedIndex = -1;
                    updateSuggestions();
                })
                .catch(err => {
                    console.error('Error fetching suggestions:', err);
                    suggestions = [];
                    updateSuggestions();
                });
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
                    updateSuggestions();
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
            fetch('/submit', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: command})
            })
            .then(() => {
                window.close();
            })
            .catch(err => {
                console.error('Error submitting:', err);
                window.close();
            });
        }

        function cancel() {
            fetch('/cancel', {method: 'POST'})
            .then(() => {
                window.close();
            })
            .catch(err => {
                console.error('Error cancelling:', err);
                window.close();
            });
        }
    </script>
</body>
</html>
"""


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
            self.result = data.get('command', '')
            # Signal shutdown
            self.shutdown_event.set()
            # Try to shutdown server (works with Werkzeug development server)
            try:
                func = request.environ.get('werkzeug.server.shutdown')
                if func:
                    func()
            except Exception:
                pass
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
        # Find available port
        self.port = _find_available_port(self.port)
        
        # Reset shutdown event
        self.shutdown_event.clear()
        
        # Start server in background thread
        self.server_thread = threading.Thread(
            target=lambda: self.app.run(port=self.port, debug=False, use_reloader=False, host='127.0.0.1')
        )
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Wait a moment for server to start
        time.sleep(0.5)
        
        # Open browser
        try:
            webbrowser.open(f'http://127.0.0.1:{self.port}')
        except Exception as e:
            print(f"Warning: Could not open browser: {e}")
            # Server will still run, user can manually open browser
        
        # Wait for shutdown event (when user submits/cancels)
        # Also wait for thread to finish (with timeout as backup)
        self.shutdown_event.wait(timeout=300)  # 5 minute timeout
        
        # Give a moment for server to shutdown
        time.sleep(0.2)
        
        return self.result

