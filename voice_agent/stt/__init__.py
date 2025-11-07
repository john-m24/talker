"""Speech-to-text abstraction layer supporting macOS native, Whisper, and Sphinx."""

from .factory import create_stt_engine, transcribe_once, transcribe_while_held

__all__ = ["create_stt_engine", "transcribe_once", "transcribe_while_held"]

