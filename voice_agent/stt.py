"""Speech-to-text abstraction layer using Apple's Speech Recognition."""

import speech_recognition as sr
from typing import Optional


# Initialize recognizer once
_recognizer: Optional[sr.Recognizer] = None
_microphone: Optional[sr.Microphone] = None


def _get_recognizer():
    """Get or initialize the speech recognizer."""
    global _recognizer, _microphone
    if _recognizer is None:
        _recognizer = sr.Recognizer()
        _microphone = sr.Microphone()
        # Adjust for ambient noise
        print("Adjusting for ambient noise...")
        with _microphone as source:
            _recognizer.adjust_for_ambient_noise(source, duration=0.5)
    return _recognizer, _microphone


def transcribe_once(timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> str:
    """
    Record audio from microphone and transcribe to text using Apple's Speech Recognition.
    
    Args:
        timeout: Maximum seconds to wait for speech to start (None = no timeout)
        phrase_time_limit: Maximum seconds for a phrase (None = no limit)
    
    Returns:
        Transcribed text as a string
    """
    recognizer, microphone = _get_recognizer()
    
    print("\n🎤 Listening... (speak now)")
    
    try:
        with microphone as source:
            # Listen for audio
            audio = recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit
            )
        
        print("   Processing...")
        
        # Recognize speech using Apple's Speech Recognition
        # Try recognize_apple first (if available), fallback to recognize_sphinx (offline)
        try:
            # Try Apple's recognition (macOS native)
            try:
                text = recognizer.recognize_apple(audio)
            except AttributeError:
                # recognize_apple might not be available, use Sphinx (offline, no API key)
                text = recognizer.recognize_sphinx(audio)
            print(f"   Heard: '{text}'")
            return text.strip()
        except sr.UnknownValueError:
            print("   (Could not understand audio)")
            return ""
        except sr.RequestError as e:
            print(f"   Error with speech recognition service: {e}")
            print("   Note: If using Sphinx, you may need to install: pip install pocketsphinx")
            return ""
            
    except sr.WaitTimeoutError:
        print("   (No speech detected within timeout)")
        return ""
    except Exception as e:
        print(f"   Error recording audio: {e}")
        return ""
