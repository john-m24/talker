"""Sphinx speech-to-text engine implementation."""

import speech_recognition as sr
from typing import Optional

from ..base import STTEngine

# Sphinx recognizer cache
_sphinx_recognizer = None
_sphinx_microphone = None


def _get_sphinx_recognizer():
    """Get or initialize the Sphinx recognizer."""
    global _sphinx_recognizer, _sphinx_microphone
    if _sphinx_recognizer is None:
        try:
            _sphinx_recognizer = sr.Recognizer()
            _sphinx_microphone = sr.Microphone()
            print("Adjusting for ambient noise...")
            with _sphinx_microphone as source:
                _sphinx_recognizer.adjust_for_ambient_noise(source, duration=0.5)
        except ImportError:
            raise ImportError("SpeechRecognition and pocketsphinx not installed. Install with: pip install SpeechRecognition pocketsphinx")
    return _sphinx_recognizer, _sphinx_microphone


class SphinxSTTEngine(STTEngine):
    """Sphinx speech-to-text engine."""
    
    def transcribe(self, timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> str:
        """Transcribe using Sphinx."""
        recognizer, microphone = _get_sphinx_recognizer()
        
        print("\n🎤 Listening... (speak now)")
        
        try:
            with microphone as source:
                audio = recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )
            
            print("   Processing with Sphinx...")
            
            try:
                text = recognizer.recognize_sphinx(audio)
                print(f"   Heard: '{text}'")
                return text.strip()
            except sr.UnknownValueError:
                print("   (Could not understand audio)")
                return ""
            except sr.RequestError as e:
                print(f"   Error with speech recognition service: {e}")
                return ""
                
        except sr.WaitTimeoutError:
            print("   (No speech detected within timeout)")
            return ""
        except Exception as e:
            print(f"   Error recording audio: {e}")
            return ""

