"""Configuration for the voice agent."""

import os
import sys
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for the voice agent."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Local LLM endpoint configuration
        self.llm_endpoint = os.getenv("VOICE_AGENT_LLM_ENDPOINT", "http://localhost:8000/v1")
        self.llm_model = os.getenv("VOICE_AGENT_LLM_MODEL", "qwen-30b")
        
        # Speech-to-text engine: "macos", "whisper" (default), or "sphinx"
        # Default to Whisper for better accuracy and cross-platform support
        default_stt = os.getenv("VOICE_AGENT_STT_ENGINE", None)
        if default_stt is None:
            # Try MLX Whisper first (best accuracy, GPU acceleration on Apple Silicon)
            try:
                import mlx_whisper
                default_stt = "whisper"
            except ImportError:
                # Fallback to macOS native on macOS if Whisper not available
                if sys.platform == "darwin":
                    try:
                        import AppKit
                        default_stt = "macos"
                    except ImportError:
                        # Fallback to Sphinx if PyObjC not available
                        default_stt = "sphinx"
                else:
                    default_stt = "sphinx"
        else:
            default_stt = default_stt.lower()
        
        self.stt_engine = default_stt
        
        # Whisper model size: "tiny", "base", "small", "medium", "large"
        self.whisper_model = os.getenv("VOICE_AGENT_WHISPER_MODEL", "medium")
        
        # Silence duration threshold for automatic speech end detection (in seconds)
        self.silence_duration = float(os.getenv("VOICE_AGENT_SILENCE_DURATION", "0.75"))
        
        # Global hotkey for triggering voice commands (e.g., 'cmd+alt', 'cmd+shift+v')
        self.hotkey = os.getenv("VOICE_AGENT_HOTKEY", "cmd+alt")
        
        # Global hotkey for triggering text commands (e.g., 'ctrl+alt', 'ctrl+option')
        self.text_hotkey = os.getenv("VOICE_AGENT_TEXT_HOTKEY", "ctrl+alt")
        
        # Cache configuration
        self.cache_enabled = os.getenv("VOICE_AGENT_CACHE_ENABLED", "true").lower() == "true"
        self.cache_apps_ttl = float(os.getenv("VOICE_AGENT_CACHE_APPS_TTL", "2"))  # 2 seconds for fresh data
        self.cache_tabs_ttl = float(os.getenv("VOICE_AGENT_CACHE_TABS_TTL", "5"))  # 5 seconds for tabs
        self.cache_presets_ttl = float(os.getenv("VOICE_AGENT_CACHE_PRESETS_TTL", "60"))
        self.cache_history_size = int(os.getenv("VOICE_AGENT_CACHE_HISTORY_SIZE", "100"))
        self.cache_history_path = os.getenv("VOICE_AGENT_CACHE_HISTORY_PATH", os.path.expanduser("~/.voice_agent_history.json"))
        
        # Auto-complete configuration
        self.autocomplete_enabled = os.getenv("VOICE_AGENT_AUTOCOMPLETE_ENABLED", "true").lower() == "true"
        self.autocomplete_max_suggestions = int(os.getenv("VOICE_AGENT_AUTOCOMPLETE_MAX_SUGGESTIONS", "5"))
        
        # Web dialog configuration
        self.web_port = int(os.getenv("VOICE_AGENT_WEB_PORT", "8765"))
        self.web_browser = os.getenv("VOICE_AGENT_WEB_BROWSER", "Google Chrome")
        # Local API (for external UI clients like Electron)
        self.api_port = int(os.getenv("VOICE_AGENT_API_PORT", "8770"))
        # Input mode: 'electron' | 'web' | 'applescript'
        self.input_mode = os.getenv("VOICE_AGENT_INPUT_MODE", "electron").lower()
        
        # LLM cache configuration (optional)
        # Enables caching of LLM responses using text-only cache keys (normalized text hash)
        # This is part of the tiered parsing strategy:
        # - Tier 1: Hardcoded commands (instant, 0ms)
        # - Tier 2: Pattern matching + fuzzy matching (fast, ~10-50ms, no LLM)
        # - Tier 3: LLM fallback with text-only cache (slow, ~500-2000ms, only when needed)
        # The text-only cache key means context changes (apps, tabs, presets) don't invalidate
        # the cache, but context validation is performed after cache hits to ensure app names
        # are still valid.
        self.llm_cache_enabled = os.getenv("VOICE_AGENT_LLM_CACHE_ENABLED", "true").lower() == "true"
        
        # Predictive cache configuration (UX-focused, aggressive pre-computation)
        # Pre-computes likely commands in the background to provide instant responses
        # Uses AI liberally for best UX (since AI is free)
        self.predictive_cache_enabled = os.getenv("VOICE_AGENT_PREDICTIVE_CACHE_ENABLED", "true").lower() == "true"
        self.predictive_cache_update_interval = float(os.getenv("VOICE_AGENT_PREDICTIVE_CACHE_UPDATE_INTERVAL", "2.0"))
        self.predictive_cache_max_commands = int(os.getenv("VOICE_AGENT_PREDICTIVE_CACHE_MAX_COMMANDS", "100"))
        self.predictive_cache_ai_enabled = os.getenv("VOICE_AGENT_PREDICTIVE_CACHE_AI_ENABLED", "true").lower() == "true"
        self.predictive_cache_ai_thread_pool_size = int(os.getenv("VOICE_AGENT_PREDICTIVE_CACHE_AI_THREAD_POOL_SIZE", "5"))
        
        # File context configuration
        self.cache_files_ttl = float(os.getenv("VOICE_AGENT_CACHE_FILES_TTL", "300"))
        self.file_context_enabled = os.getenv("VOICE_AGENT_FILE_CONTEXT_ENABLED", "true").lower() == "true"
        self.max_recent_files = int(os.getenv("VOICE_AGENT_MAX_RECENT_FILES", "20"))
        self.max_project_depth = int(os.getenv("VOICE_AGENT_MAX_PROJECT_DEPTH", "3"))
        
        # Monitor coordinates for multi-monitor window placement
        # Format: {monitor_name: {"x": left_edge, "y": top_edge, "w": width, "h": height}}
        # Coordinates are absolute screen coordinates
        # 
        # To find your monitor coordinates on macOS:
        # 1. Open System Settings > Displays
        # 2. Arrange your displays and note their positions
        # 3. Use AppleScript: osascript -e 'tell application "System Events" to get bounds of every window of every process'
        #    Or use a tool like DisplayLink Manager or check display arrangement
        #
        # Default: Single monitor setup
        # To add more monitors, uncomment and adjust the "right" and "left" entries below
        self.monitors = {
            # "main": {"x": 0, "y": 0, "w": 1920, "h": 1080},  # Main monitor (1920x1080)
            "right": {"x": 1920, "y": 0, "w": 1920, "h": 1080},  # Right monitor (1920x1080)
            # Uncomment below to add a left monitor:
            "left": {"x": 0, "y": 0, "w": 1920, "h": 1080},  # Left monitor (standard 1920x1080)
        }
        
        # Validate configuration
        self._validate()
    
    def _validate(self):
        """Validate configuration values."""
        # Validate STT engine
        valid_stt_engines = ["macos", "whisper", "sphinx"]
        if self.stt_engine not in valid_stt_engines:
            raise ValueError(
                f"Invalid STT engine '{self.stt_engine}'. "
                f"Must be one of: {', '.join(valid_stt_engines)}"
            )
        
        # Validate Whisper model
        valid_whisper_models = ["tiny", "base", "small", "medium", "large"]
        if self.whisper_model not in valid_whisper_models:
            raise ValueError(
                f"Invalid Whisper model '{self.whisper_model}'. "
                f"Must be one of: {', '.join(valid_whisper_models)}"
            )
        
        # Validate silence duration
        if self.silence_duration <= 0:
            raise ValueError(f"Silence duration must be positive, got {self.silence_duration}")
        
        # Validate monitors
        for monitor_name, monitor_config in self.monitors.items():
            required_keys = ["x", "y", "w", "h"]
            for key in required_keys:
                if key not in monitor_config:
                    raise ValueError(f"Monitor '{monitor_name}' missing required key: {key}")
                if not isinstance(monitor_config[key], (int, float)):
                    raise ValueError(f"Monitor '{monitor_name}' key '{key}' must be numeric")


# Create a global config instance
_config = Config()

# Expose configuration values as module-level variables for backward compatibility
LLM_ENDPOINT = _config.llm_endpoint
LLM_MODEL = _config.llm_model
STT_ENGINE = _config.stt_engine
WHISPER_MODEL = _config.whisper_model
SILENCE_DURATION = _config.silence_duration
HOTKEY = _config.hotkey
TEXT_HOTKEY = _config.text_hotkey
MONITORS = _config.monitors
CACHE_ENABLED = _config.cache_enabled
CACHE_APPS_TTL = _config.cache_apps_ttl
CACHE_TABS_TTL = _config.cache_tabs_ttl
CACHE_PRESETS_TTL = _config.cache_presets_ttl
CACHE_HISTORY_SIZE = _config.cache_history_size
CACHE_HISTORY_PATH = _config.cache_history_path
AUTOCOMPLETE_ENABLED = _config.autocomplete_enabled
AUTOCOMPLETE_MAX_SUGGESTIONS = _config.autocomplete_max_suggestions
WEB_PORT = _config.web_port
WEB_BROWSER = _config.web_browser
API_PORT = _config.api_port
INPUT_MODE = _config.input_mode
LLM_CACHE_ENABLED = _config.llm_cache_enabled
PREDICTIVE_CACHE_ENABLED = _config.predictive_cache_enabled
PREDICTIVE_CACHE_UPDATE_INTERVAL = _config.predictive_cache_update_interval
PREDICTIVE_CACHE_MAX_COMMANDS = _config.predictive_cache_max_commands
PREDICTIVE_CACHE_AI_ENABLED = _config.predictive_cache_ai_enabled
PREDICTIVE_CACHE_AI_THREAD_POOL_SIZE = _config.predictive_cache_ai_thread_pool_size
CACHE_FILES_TTL = _config.cache_files_ttl
FILE_CONTEXT_ENABLED = _config.file_context_enabled
MAX_RECENT_FILES = _config.max_recent_files
MAX_PROJECT_DEPTH = _config.max_project_depth

__all__ = [
    "Config",
    "LLM_ENDPOINT",
    "LLM_MODEL",
    "STT_ENGINE",
    "WHISPER_MODEL",
    "SILENCE_DURATION",
    "HOTKEY",
    "TEXT_HOTKEY",
    "MONITORS",
    "CACHE_ENABLED",
    "CACHE_APPS_TTL",
    "CACHE_TABS_TTL",
    "CACHE_PRESETS_TTL",
    "CACHE_HISTORY_SIZE",
    "CACHE_HISTORY_PATH",
    "AUTOCOMPLETE_ENABLED",
    "AUTOCOMPLETE_MAX_SUGGESTIONS",
    "WEB_PORT",
    "WEB_BROWSER",
    "API_PORT",
    "INPUT_MODE",
    "LLM_CACHE_ENABLED",
    "PREDICTIVE_CACHE_ENABLED",
    "PREDICTIVE_CACHE_UPDATE_INTERVAL",
    "PREDICTIVE_CACHE_MAX_COMMANDS",
    "PREDICTIVE_CACHE_AI_ENABLED",
    "PREDICTIVE_CACHE_AI_THREAD_POOL_SIZE",
    "CACHE_FILES_TTL",
    "FILE_CONTEXT_ENABLED",
    "MAX_RECENT_FILES",
    "MAX_PROJECT_DEPTH",
]
