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
		'running_apps': cache_manager.get('running_apps', []),
		'installed_apps': cache_manager.get('installed_apps', []),
		'chrome_tabs': cache_manager.get('chrome_tabs', []),
		'presets': list(cache_manager.get('presets', {}).keys()) if isinstance(cache_manager.get('presets', {}), dict) else [],
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
			put_command(command)
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


