"""Configuration for the voice agent."""

import os
import sys

# Local LLM endpoint configuration
LLM_ENDPOINT = os.getenv("VOICE_AGENT_LLM_ENDPOINT", "http://192.168.1.198:10000/v1")
LLM_MODEL = os.getenv("VOICE_AGENT_LLM_MODEL", "qwen-30b")

# Speech-to-text engine: "macos" (default), "whisper", or "sphinx"
# Default to macOS native speech recognition (best for macOS)
_default_stt = os.getenv("VOICE_AGENT_STT_ENGINE", None)
if _default_stt is None:
    # Check if macOS native is available (macOS only)
    if sys.platform == "darwin":
        try:
            import AppKit
            _default_stt = "macos"
        except ImportError:
            # Fallback to Sphinx if PyObjC not available
            _default_stt = "sphinx"
    else:
        # Non-macOS: try Whisper, fallback to Sphinx
        if sys.version_info < (3, 14):
            try:
                import whisper
                _default_stt = "whisper"
            except ImportError:
                _default_stt = "sphinx"
        else:
            _default_stt = "sphinx"
else:
    _default_stt = _default_stt.lower()

STT_ENGINE = _default_stt
# Whisper model size: "tiny", "base", "small", "medium", "large"
WHISPER_MODEL = os.getenv("VOICE_AGENT_WHISPER_MODEL", "tiny")
# Silence duration threshold for automatic speech end detection (in seconds)
SILENCE_DURATION = float(os.getenv("VOICE_AGENT_SILENCE_DURATION", "0.3"))
