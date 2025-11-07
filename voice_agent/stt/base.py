"""Base classes and interfaces for STT engines."""

from abc import ABC, abstractmethod
from typing import Optional


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

