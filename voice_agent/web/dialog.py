"""Web-based text input dialog with auto-complete."""

import threading
import webbrowser
import time
import socket
import subprocess
import os
from typing import Optional, List, Dict, Any
from flask import Flask, render_template, request, jsonify
from ..config import AUTOCOMPLETE_MAX_SUGGESTIONS, WEB_PORT


class _DialogRegistry:
    """Singleton registry for managing the active dialog instance."""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._active_dialog = None
        return cls._instance
    
    def get_active_dialog(self) -> Optional['WebTextInputDialog']:
        """Get the currently active dialog instance."""
        with self._lock:
            return self._active_dialog
    
    def set_active_dialog(self, dialog: Optional['WebTextInputDialog']):
        """Set the currently active dialog instance."""
        with self._lock:
            self._active_dialog = dialog


# Create singleton instance
_registry = _DialogRegistry()


def get_active_dialog() -> Optional['WebTextInputDialog']:
    """Get the currently active dialog instance."""
    return _registry.get_active_dialog()


def set_active_dialog(dialog: Optional['WebTextInputDialog']):
    """Set the currently active dialog instance."""
    _registry.set_active_dialog(dialog)


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
        
        # Get the template directory
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        self.app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
        
        self.server_thread = None
        self.shutdown_event = threading.Event()
        self.command_ready_event = threading.Event()  # Signal when a command is ready
        self.results = None
        self.results_lock = threading.Lock()
        self.clarification_text = None
        self.clarification_reason = None
        self.clarification_event = threading.Event()  # Signal when clarification is ready
        self._server_lock = threading.Lock()  # Protect server operations
        self._setup_routes()
    
    def _ensure_server_running(self):
        """
        Ensure the Flask server is running. If not, start it and open the browser.
        This method is thread-safe and idempotent.
        """
        with self._server_lock:
            # Check if server is already running
            if self.server_thread and self.server_thread.is_alive():
                return
            
            # Find available port
            self.port = _find_available_port(self.port)
            
            # Reset events
            self.shutdown_event.clear()
            self.command_ready_event.clear()
            self.clarification_event.clear()
            
            # Start server in background thread
            self.server_thread = threading.Thread(
                target=self._run_flask_server,
                daemon=True
            )
            self.server_thread.start()
            
            # Wait a moment for server to start
            time.sleep(0.5)
            
            # Open browser window
            self._open_browser_window()
    
    def _run_flask_server(self):
        """Run the Flask server. This runs in a background thread."""
        try:
            self.app.run(port=self.port, debug=False, use_reloader=False, host='127.0.0.1')
        except Exception as e:
            print(f"Flask server error: {e}")
    
    def _open_browser_window(self):
        """Open the browser window for the dialog."""
        url = f'http://127.0.0.1:{self.port}'
        window_width = 600
        window_height = 500
        
        try:
            default_browser = webbrowser.get()
            browser_name = default_browser.name.lower()
            
            # Determine which browser to use
            browser_app = None
            if 'chrome' in browser_name:
                browser_app = "Google Chrome"
            elif 'safari' in browser_name:
                browser_app = "Safari"
            
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
    
    def _setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            return render_template('dialog.html')
        
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
            
            # Store command for processing
            self.result = command
            
            # Clear previous results when submitting new command
            with self.results_lock:
                self.results = None
            
            # Always keep dialog open and signal that command is ready
            self.command_ready_event.set()
            return jsonify({'status': 'ok'})
        
        @self.app.route('/get-results', methods=['GET'])
        def get_results():
            """Get results if available."""
            with self.results_lock:
                if self.results:
                    results = self.results
                    # Mark as consumed after first read to prevent duplicate display
                    self.results = None
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
        
        @self.app.route('/close', methods=['POST'])
        def close():
            """Handle explicit close button click."""
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
            return jsonify({'status': 'closed'})
    
    def show(self) -> Optional[str]:
        """Show dialog and return entered text or None if cancelled."""
        # Set as active dialog
        set_active_dialog(self)
        
        # Ensure server is running
        self._ensure_server_running()
        
        # Reset events for new command session
        self.shutdown_event.clear()
        self.command_ready_event.clear()
        
        # Wait for commands continuously - keep dialog open until user closes it
        while True:
            # Wait for either shutdown (user clicked close) or command ready (user submitted command)
            # Use a short timeout to periodically check both events
            if self.shutdown_event.wait(timeout=0.1):
                # Shutdown event set - user clicked close button
                break
            
            if self.command_ready_event.is_set():
                # Command ready - return it and keep dialog open for next command
                command = self.result
                self.result = None  # Clear for next command
                self.command_ready_event.clear()  # Reset for next submission
                return command
        
        # Clear active dialog
        set_active_dialog(None)
        
        # Give a moment for cleanup
        time.sleep(0.2)
        
        # Return None if dialog was closed
        return None
    
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
    
    def send_message(self, message: str, is_error: bool = False):
        """
        Send a simple text message to the dialog.
        
        Args:
            message: Message text to display
            is_error: If True, mark as error message
        """
        with self.results_lock:
            if is_error:
                self.results = {
                    'title': 'Error',
                    'items': [message]
                }
            else:
                self.results = {
                    'title': 'Message',
                    'items': [message]
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
        
        # Set as active dialog and ensure server is running
        set_active_dialog(self)
        self._ensure_server_running()
        
        # Wait for clarification response
        self.clarification_event.wait(timeout=300)  # 5 minute timeout
        
        # Clear clarification request
        self.clarification_text = None
        self.clarification_reason = None
        
        return self.result
