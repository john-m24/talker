"""Factory for creating STT engines based on configuration."""

from typing import Optional, Callable
from .base import STTEngine
from ..config import STT_ENGINE

# Module-level cache for engine instance
_cached_engine = None


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


def get_stt_engine(engine_name: Optional[str] = None) -> STTEngine:
    """
    Get or create STT engine instance (cached, with persistent stream if Whisper).
    
    Args:
        engine_name: Name of the engine to create (defaults to config value)
    
    Returns:
        STTEngine instance (cached)
    """
    global _cached_engine
    if _cached_engine is None:
        _cached_engine = create_stt_engine(engine_name)
    return _cached_engine


def set_cached_engine(engine: STTEngine):
    """
    Set the cached engine instance (used when engine is pre-initialized).
    
    Args:
        engine: STTEngine instance to cache
    """
    global _cached_engine
    _cached_engine = engine


def transcribe_while_held(is_held, context: Optional[str] = None) -> str:
    """
    Record audio while a condition is true (e.g., while hotkey is held).
    
    Args:
        is_held: Callable that returns True while recording should continue
        context: Optional context text to help with transcription accuracy
    
    Returns:
        Transcribed text as a string
    """
    engine = get_stt_engine()  # Use cached instance
    return engine.transcribe_while_held(is_held, context=context)

