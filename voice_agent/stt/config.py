"""Configuration for STT engines."""

# Re-export from main config for convenience
from ..config import STT_ENGINE, WHISPER_MODEL, SILENCE_DURATION

__all__ = ["STT_ENGINE", "WHISPER_MODEL", "SILENCE_DURATION"]

