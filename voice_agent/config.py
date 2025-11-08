"""Configuration for the voice agent."""

import os
import sys
from typing import Dict, Any


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
            "left": {"x": 0, "y": 0, "w": 1920, "h": 1080},  # Main monitor (1920x1080)
            "right": {"x": 1920, "y": 0, "w": 1920, "h": 1080},  # Right monitor (1920x1080)
            # Uncomment below to add a left monitor:
            # "left": {"x": -1920, "y": 0, "w": 1920, "h": 1080},  # Left monitor (standard 1920x1080)
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
]
