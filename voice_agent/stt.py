"""Speech-to-text abstraction layer supporting Whisper and Sphinx."""

import os
import sounddevice as sd
import numpy as np
from typing import Optional
from .config import STT_ENGINE, WHISPER_MODEL

# Fix SSL certificate issues on macOS
# Set SSL_CERT_FILE to Python's certifi certificates if not already set
if "SSL_CERT_FILE" not in os.environ:
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass  # certifi not available, will use system defaults


# Whisper model cache
_whisper_model = None

# Sphinx recognizer cache
_sphinx_recognizer = None
_sphinx_microphone = None


def _get_whisper_model(model_name: str = "base"):
    """Get or load the Whisper model."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            print(f"Loading Whisper model '{model_name}' (first time only, this may take a moment)...")
            _whisper_model = whisper.load_model(model_name)
            print("Whisper model loaded!")
        except ImportError:
            raise ImportError("openai-whisper not installed. Install with: pip install openai-whisper")
    return _whisper_model


def _get_sphinx_recognizer():
    """Get or initialize the Sphinx recognizer."""
    global _sphinx_recognizer, _sphinx_microphone
    if _sphinx_recognizer is None:
        try:
            import speech_recognition as sr
            _sphinx_recognizer = sr.Recognizer()
            _sphinx_microphone = sr.Microphone()
            print("Adjusting for ambient noise...")
            with _sphinx_microphone as source:
                _sphinx_recognizer.adjust_for_ambient_noise(source, duration=0.5)
        except ImportError:
            raise ImportError("SpeechRecognition and pocketsphinx not installed. Install with: pip install SpeechRecognition pocketsphinx")
    return _sphinx_recognizer, _sphinx_microphone


def _transcribe_whisper(sample_rate: int = 16000, timeout: Optional[float] = None) -> str:
    """Transcribe using Whisper."""
    import threading
    import queue
    
    model = _get_whisper_model(WHISPER_MODEL)
    
    print("\n🎤 Listening... (speak now, press Enter when done)")
    
    # Record audio using thread-safe queue
    audio_queue = queue.Queue()
    recording = threading.Event()
    recording.set()
    
    def audio_callback(indata, frames, time, status):
        """Callback for audio recording."""
        if status:
            print(f"Audio status: {status}")
        if recording.is_set():
            audio_queue.put(indata.copy())
    
    # Start recording
    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype=np.float32,
        callback=audio_callback
    )
    
    stream.start()
    
    # Wait for Enter key or timeout
    try:
        if timeout:
            import time
            time.sleep(timeout)
        else:
            input()  # Wait for Enter
    except (EOFError, KeyboardInterrupt):
        pass
    
    # Stop recording
    recording.clear()
    stream.stop()
    stream.close()
    
    # Collect all audio chunks
    audio_chunks = []
    while not audio_queue.empty():
        audio_chunks.append(audio_queue.get())
    
    if not audio_chunks:
        print("   (No audio recorded)")
        return ""
    
    audio = np.concatenate(audio_chunks, axis=0)
    print("   Processing with Whisper...")
    
    # Transcribe with Whisper
    result = model.transcribe(audio, language="en")
    text = result["text"].strip()
    
    if text:
        print(f"   Heard: '{text}'")
    else:
        print("   (No speech detected)")
    
    return text


def _transcribe_sphinx(timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> str:
    """Transcribe using Sphinx."""
    import speech_recognition as sr
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


def transcribe_once(timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> str:
    """
    Record audio from microphone and transcribe to text.
    
    Uses Whisper by default (better accuracy), falls back to Sphinx if Whisper unavailable.
    Can be configured via VOICE_AGENT_STT_ENGINE environment variable.
    
    Args:
        timeout: Maximum seconds to wait for speech to start (None = no timeout)
        phrase_time_limit: Maximum seconds for a phrase (None = no limit, Whisper only)
    
    Returns:
        Transcribed text as a string
    """
    engine = STT_ENGINE.lower()
    
    if engine == "whisper":
        try:
            return _transcribe_whisper(timeout=timeout)
        except ImportError as e:
            print(f"Warning: {e}")
            print("Falling back to Sphinx...")
            return _transcribe_sphinx(timeout=timeout, phrase_time_limit=phrase_time_limit)
    elif engine == "sphinx":
        return _transcribe_sphinx(timeout=timeout, phrase_time_limit=phrase_time_limit)
    else:
        print(f"Warning: Unknown STT engine '{engine}', using Whisper")
        try:
            return _transcribe_whisper(timeout=timeout)
        except ImportError:
            print("Falling back to Sphinx...")
            return _transcribe_sphinx(timeout=timeout, phrase_time_limit=phrase_time_limit)
