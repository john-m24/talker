"""Factory for creating STT engines based on configuration."""

from typing import Optional
from .base import STTEngine
from ..config import STT_ENGINE


def create_stt_engine(engine_name: Optional[str] = None) -> STTEngine:
    """
    Create an STT engine instance based on configuration.
    
    Args:
        engine_name: Name of the engine to create (defaults to config value)
        
    Returns:
        STTEngine instance
        
    Raises:
        ValueError: If engine name is unknown
    """
    engine = (engine_name or STT_ENGINE).lower()
    
    if engine == "macos":
        from .engines.macos_engine import MacOSSTTEngine
        return MacOSSTTEngine()
    elif engine == "whisper":
        from .engines.whisper_engine import WhisperSTTEngine
        return WhisperSTTEngine()
    elif engine == "sphinx":
        from .engines.sphinx_engine import SphinxSTTEngine
        return SphinxSTTEngine()
    else:
        raise ValueError(f"Unknown STT engine '{engine}'. Use 'macos', 'whisper', or 'sphinx'")


def transcribe_once(timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> str:
    """
    Record audio from microphone and transcribe to text using the configured engine.
    
    Args:
        timeout: Maximum seconds to wait for speech to start (None = no timeout)
        phrase_time_limit: Maximum seconds for a phrase (None = no limit)
    
    Returns:
        Transcribed text as a string
    """
    engine = create_stt_engine()
    return engine.transcribe(timeout=timeout, phrase_time_limit=phrase_time_limit)

