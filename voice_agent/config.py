"""Configuration for the voice agent."""

import os
import sys

# Local LLM endpoint configuration
LLM_ENDPOINT = os.getenv("VOICE_AGENT_LLM_ENDPOINT", "http://192.168.1.198:10000/v1")
LLM_MODEL = os.getenv("VOICE_AGENT_LLM_MODEL", "qwen-30b")

# Speech-to-text engine: "whisper" or "sphinx"
# Default to whisper, but check if it's available
_default_stt = os.getenv("VOICE_AGENT_STT_ENGINE", None)
if _default_stt is None:
    # Check if Whisper is available (Python <3.14 and package installed)
    if sys.version_info >= (3, 14):
        _default_stt = "sphinx"  # Python 3.14+ doesn't support Whisper (numba limitation)
    else:
        try:
            import whisper
            _default_stt = "whisper"
        except ImportError:
            _default_stt = "sphinx"
else:
    _default_stt = _default_stt.lower()

STT_ENGINE = _default_stt
# Whisper model size: "tiny", "base", "small", "medium", "large"
WHISPER_MODEL = os.getenv("VOICE_AGENT_WHISPER_MODEL", "base")
