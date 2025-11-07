"""Base classes and interfaces for STT engines."""

from abc import ABC, abstractmethod
from typing import Optional, Callable


class STTEngine(ABC):
    """Abstract base class for speech-to-text engines."""
    
    @abstractmethod
    def transcribe(self, timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> str:
        """
        Record audio from microphone and transcribe to text.
        
        Args:
            timeout: Maximum seconds to wait for speech to start (None = no timeout)
            phrase_time_limit: Maximum seconds for a phrase (None = no limit)
        
        Returns:
            Transcribed text as a string
        """
        pass
    
    def transcribe_while_held(self, is_held: Callable[[], bool], context: Optional[str] = None) -> str:
        """
        Record audio while a condition is true (e.g., while hotkey is held).
        
        Args:
            is_held: Callable that returns True while recording should continue
            context: Optional context text to help with transcription accuracy
        
        Returns:
            Transcribed text as a string
        """
        # Default implementation: use regular transcribe
        # Subclasses can override for better push-to-talk support
        return self.transcribe()

