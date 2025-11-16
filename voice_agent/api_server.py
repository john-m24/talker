"""Lightweight local HTTP API for Electron client: /suggest and /submit."""

from typing import Optional, Any, Dict, List
import threading
from flask import Flask, request, jsonify

from .command_queue import put_command
from .cache import get_cache_manager
from .config import AUTOCOMPLETE_MAX_SUGGESTIONS


_app_instance: Optional[Flask] = None
_server_thread: Optional[threading.Thread] = None
_autocomplete_engine = None

# Thread-safe flag for showing palette
_show_palette_flag = False
_show_palette_lock = threading.Lock()

# Thread-safe results store
_results_data: Optional[Dict[str, Any]] = None
_results_consumed = False
_results_lock = threading.Lock()

# Thread-safe request/response store
_pending_request: Optional[Dict[str, Any]] = None
_request_response: Optional[Dict[str, Any]] = None
_request_lock = threading.Lock()
_request_event = threading.Event()


def _build_context(cache_manager) -> Dict[str, Any]:
	"""Build context dict consistent with existing web dialog suggest route."""
	if not cache_manager:
		return {
			'running_apps': [],
			'installed_apps': [],
			'chrome_tabs': [],
			'presets': [],
			'command_history': []
		}
	return {
		'running_apps': cache_manager.get_apps('running') or [],
		'installed_apps': cache_manager.get_apps('installed') or [],
		'chrome_tabs': cache_manager.get_tabs('tabs') or [],
		'presets': list(cache_manager.get_system('presets').keys()) if isinstance(cache_manager.get_system('presets'), dict) else [],
		'command_history': cache_manager.get_history(),
	}


def _create_app() -> Flask:
	app = Flask("voice_agent_api")

	@app.get("/health")
	def health():
		return jsonify({"status": "ok"})

	# Basic CORS for local file:// Electron renderer
	@app.after_request
	def add_cors_headers(response):
		response.headers["Access-Control-Allow-Origin"] = "*"
		response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
		response.headers["Access-Control-Allow-Headers"] = "Content-Type"
		return response

	@app.route("/suggest", methods=["GET", "OPTIONS"])
	def suggest():
		if request.method == "OPTIONS":
			return ("", 204)
		text = request.args.get('text', '') or ''
		cache_manager = get_cache_manager()
		if not _autocomplete_engine or not cache_manager:
			return jsonify({'suggestions': []})
		context = _build_context(cache_manager)
		try:
			# Use existing API: suggest_all returns ranked list
			suggestions: List[str] = _autocomplete_engine.suggest_all(text, context)  # type: ignore[attr-defined]
		except Exception:
			suggestions = []
		return jsonify({'suggestions': suggestions[:AUTOCOMPLETE_MAX_SUGGESTIONS]})

	@app.route("/submit", methods=["POST", "OPTIONS"])
	def submit():
		if request.method == "OPTIONS":
			return ("", 204)
		try:
			data = request.get_json(silent=True) or {}
			command = str(data.get('command', '')).strip()
			if not command:
				return jsonify({'status': 'error', 'message': 'empty command'}), 400
			# Clear previous results when submitting new command
			global _results_data, _results_consumed
			with _results_lock:
				_results_data = None
				_results_consumed = False
			put_command(command)
			return jsonify({'status': 'ok'})
		except Exception as e:
			return jsonify({'status': 'error', 'message': str(e)}), 500

	@app.route("/show-palette", methods=["GET", "OPTIONS"])
	def show_palette():
		"""Check if palette should be shown (triggered by TEXT_HOTKEY)."""
		if request.method == "OPTIONS":
			return ("", 204)
		global _show_palette_flag
		with _show_palette_lock:
			should_show = _show_palette_flag
			if should_show:
				# Clear flag after reading
				_show_palette_flag = False
			return jsonify({"show": should_show})

	@app.route("/get-results", methods=["GET", "OPTIONS"])
	def get_results():
		"""Get results if available (for list commands)."""
		if request.method == "OPTIONS":
			return ("", 204)
		global _results_data, _results_consumed
		with _results_lock:
			if _results_data and not _results_consumed:
				# Mark as consumed after first read
				_results_consumed = True
				return jsonify({"results": _results_data})
			return jsonify({"results": None})

	@app.route("/get-request", methods=["GET", "OPTIONS"])
	def get_request():
		"""Get pending request if available (for clarifications, etc.)."""
		if request.method == "OPTIONS":
			return ("", 204)
		global _pending_request
		with _request_lock:
			if _pending_request:
				# Return request and mark as consumed
				request_data = _pending_request
				_pending_request = None
				return jsonify({"request": request_data})
			return jsonify({"request": None})

	@app.route("/submit-response", methods=["POST", "OPTIONS"])
	def submit_response():
		"""Submit response to pending request."""
		if request.method == "OPTIONS":
			return ("", 204)
		try:
			data = request.get_json(silent=True) or {}
			response_type = data.get('type', '')
			if not response_type:
				return jsonify({'status': 'error', 'message': 'missing type'}), 400
			
			global _request_response, _request_event
			with _request_lock:
				_request_response = data
				_request_event.set()  # Signal that response is ready
			
			return jsonify({'status': 'ok'})
		except Exception as e:
			return jsonify({'status': 'error', 'message': str(e)}), 500

	return app


def start_api_server(autocomplete_engine, port: int = 8770) -> None:
	"""
	Start the local API server in a background thread.
	Only binds to 127.0.0.1.
	"""
	global _app_instance, _server_thread, _autocomplete_engine
	if _server_thread and _server_thread.is_alive():
		return
	_autocomplete_engine = autocomplete_engine
	_app_instance = _create_app()

	def run():
		_app_instance.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

	_server_thread = threading.Thread(target=run, daemon=True)
	_server_thread.start()


def trigger_palette() -> None:
	"""Trigger the Electron palette to show (called when TEXT_HOTKEY is pressed)."""
	global _show_palette_flag
	with _show_palette_lock:
		_show_palette_flag = True


def send_results(title: str, items: List[str]) -> None:
	"""
	Send results to Electron client (for list commands).
	
	Args:
		title: Title for the results
		items: List of result items to display
	"""
	global _results_data, _results_consumed
	with _results_lock:
		_results_data = {
			"title": title,
			"items": items
		}
		_results_consumed = False


def send_error(message: str) -> None:
	"""
	Send error message to Electron client.
	
	Args:
		message: Error message to display
	"""
	global _results_data, _results_consumed
	with _results_lock:
		_results_data = {
			"error": message
		}
		_results_consumed = False


def send_request(request_type: str, request_data: Dict[str, Any]) -> None:
	"""
	Send a request to Electron client (e.g., clarification request).
	
	Args:
		request_type: Type of request (e.g., "clarification")
		request_data: Request-specific data
	"""
	global _pending_request, _request_response, _request_event
	with _request_lock:
		# Clear any previous response
		_request_response = None
		_request_event.clear()
		# Set new request
		_pending_request = {
			"type": request_type,
			**request_data
		}


def wait_for_response(timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
	"""
	Wait for response from Electron client.
	
	Args:
		timeout: Optional timeout in seconds (None = wait indefinitely)
		
	Returns:
		Response dictionary if received, None if timeout or cancelled
	"""
	global _request_response, _request_event
	
	# Wait for response event
	if _request_event.wait(timeout=timeout):
		with _request_lock:
			response = _request_response
			_request_response = None
			_request_event.clear()
			return response
	return None


