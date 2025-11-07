"""Configuration for the voice agent."""

import os
import sys

# Local LLM endpoint configuration
LLM_ENDPOINT = os.getenv("VOICE_AGENT_LLM_ENDPOINT", "http://192.168.1.198:10000/v1")
LLM_MODEL = os.getenv("VOICE_AGENT_LLM_MODEL", "qwen-30b")

# Speech-to-text engine: "macos", "whisper" (default), or "sphinx"
# Default to Whisper for better accuracy and cross-platform support
_default_stt = os.getenv("VOICE_AGENT_STT_ENGINE", None)
if _default_stt is None:
    # Try Whisper first (best accuracy, cross-platform)
    try:
        import whisper
        _default_stt = "whisper"
    except ImportError:
        # Fallback to macOS native on macOS if Whisper not available
        if sys.platform == "darwin":
            try:
                import AppKit
                _default_stt = "macos"
            except ImportError:
                # Fallback to Sphinx if PyObjC not available
                _default_stt = "sphinx"
        else:
            _default_stt = "sphinx"
else:
    _default_stt = _default_stt.lower()

STT_ENGINE = _default_stt
# Whisper model size: "tiny", "base", "small", "medium", "large"
WHISPER_MODEL = os.getenv("VOICE_AGENT_WHISPER_MODEL", "medium")
# Silence duration threshold for automatic speech end detection (in seconds)
SILENCE_DURATION = float(os.getenv("VOICE_AGENT_SILENCE_DURATION", "0.75"))

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
MONITORS = {
    "left": {"x": 0, "y": 0, "w": 1920, "h": 1080},  # Main monitor (1920x1080)
    "right": {"x": 1920, "y": 0, "w": 1920, "h": 1080},  # Right monitor (1920x1080)
    # Uncomment below to add a left monitor:
    # "left": {"x": -1920, "y": 0, "w": 1920, "h": 1080},  # Left monitor (standard 1920x1080)
}
