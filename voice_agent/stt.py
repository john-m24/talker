"""Speech-to-text abstraction layer supporting macOS native, Whisper, and Sphinx."""

import os
import sounddevice as sd
import numpy as np
import threading
import time
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

# macOS Speech Recognition delegate class (defined once at module level)
_macos_recognition_delegate_class = None
# Keep references to delegates to prevent garbage collection
_macos_delegate_refs = []

def _get_macos_recognition_delegate_class():
    """Get or create the macOS recognition delegate class."""
    global _macos_recognition_delegate_class
    if _macos_recognition_delegate_class is None:
        try:
            from Foundation import NSObject
            import objc
            
            class RecognitionDelegate(NSObject):
                def initWithResultContainer_(self, result_container):
                    self = objc.super(RecognitionDelegate, self).init()
                    if self is None:
                        return None
                    self.result_container = result_container
                    return self
                
                def speechRecognitionTask_didFinishRecognition_(self, task, result):
                    if result:
                        best_transcription = result.bestTranscription()
                        if best_transcription:
                            self.result_container['text'] = best_transcription.formattedString()
                    self.result_container['done'] = True
                
                def speechRecognitionTask_didFinishSuccessfully_(self, task, finished):
                    if not finished:
                        self.result_container['error'] = "Recognition did not finish successfully"
                    self.result_container['done'] = True
                
                # Note: wasCancelled method removed - causing signature issues with PyObjC
                # Cancellation is handled via timeout in the main loop
                
                def speechRecognitionTask_didHypothesizeTranscription_(self, task, transcription):
                    # Optional: handle partial results
                    pass
            
            _macos_recognition_delegate_class = RecognitionDelegate
        except ImportError:
            pass
    return _macos_recognition_delegate_class


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


def _transcribe_macos(timeout: Optional[float] = None) -> str:
    """Transcribe using macOS native speech recognition via Speech framework."""
    try:
        from Speech import SFSpeechRecognizer, SFSpeechAudioBufferRecognitionRequest, SFSpeechRecognitionTask
        from AVFoundation import AVAudioEngine, AVAudioSession, AVAudioSessionCategoryRecord
        from Foundation import NSLocale
        import objc
    except ImportError:
        raise ImportError("PyObjC not installed. Install with: pip install pyobjc")
    
    print("\n🎤 Listening... (speak now, press Enter when done)")
    
    # Record audio using sounddevice (simpler than AVAudioEngine)
    sample_rate = 16000
    audio_queue = []
    recording = threading.Event()
    recording.set()
    
    def audio_callback(indata, frames, time, status):
        """Callback for audio recording."""
        if recording.is_set():
            audio_queue.append(indata.copy())
    
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
            time.sleep(timeout)
        else:
            input()  # Wait for Enter
    except (EOFError, KeyboardInterrupt):
        pass
    
    # Stop recording
    recording.clear()
    stream.stop()
    stream.close()
    
    if not audio_queue:
        print("   (No audio recorded)")
        return ""
    
    audio = np.concatenate(audio_queue, axis=0)
    print("   Processing with macOS Speech Recognition...")
    
    # Convert to format Speech framework expects
    # Speech framework needs AVAudioFormat, so we'll use a workaround
    # Actually, let's use a simpler approach - save to temp file and use SFSpeechURLRecognitionRequest
    
    import tempfile
    import wave
    
    # Save audio to temporary WAV file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
        tmp_path = tmp_file.name
        
        # Convert float32 to int16
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Write WAV file
        with wave.open(tmp_path, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        try:
            # Use Speech framework to recognize
            from Foundation import NSLocale, NSURL, NSObject
            from Speech import SFSpeechURLRecognitionRequest, SFSpeechRecognitionTask
            
            locale = NSLocale.localeWithLocaleIdentifier_("en-US")
            recognizer = SFSpeechRecognizer.alloc().initWithLocale_(locale)
            
            if not recognizer.isAvailable():
                print("   macOS Speech Recognition is not available")
                return ""
            
            url = NSURL.fileURLWithPath_(tmp_path)
            request = SFSpeechURLRecognitionRequest.alloc().initWithURL_(url)
            
            result_container = {'text': None, 'done': False, 'error': None}
            
            # Get delegate class (defined at module level to avoid redefinition)
            DelegateClass = _get_macos_recognition_delegate_class()
            if DelegateClass is None:
                raise ImportError("PyObjC not available")
            
            delegate = DelegateClass.alloc().initWithResultContainer_(result_container)
            # Keep reference to prevent garbage collection
            _macos_delegate_refs.append(delegate)
            # Clean up old references (keep last 5)
            if len(_macos_delegate_refs) > 5:
                _macos_delegate_refs.pop(0)
            
            task = recognizer.recognitionTaskWithRequest_delegate_(request, delegate)
            
            # Wait for recognition to complete
            from Cocoa import NSRunLoop, NSDefaultRunLoopMode
            from Foundation import NSDate
            
            start_time = time.time()
            timeout_seconds = timeout if timeout else 15.0  # Increased timeout
            max_iterations = int(timeout_seconds * 20)  # Safety limit
            iteration = 0
            
            while not result_container['done']:
                iteration += 1
                elapsed = time.time() - start_time
                
                if elapsed > timeout_seconds:
                    task.cancel()
                    result_container['done'] = True
                    result_container['error'] = f"Recognition timeout after {timeout_seconds:.1f}s"
                    break
                
                if iteration > max_iterations:
                    task.cancel()
                    result_container['done'] = True
                    result_container['error'] = "Recognition loop exceeded max iterations"
                    break
                
                # Process run loop events - convert Python time to NSDate
                future_time = time.time() + 0.1
                ns_date = NSDate.dateWithTimeIntervalSince1970_(future_time)
                NSRunLoop.currentRunLoop().runMode_beforeDate_(
                    NSDefaultRunLoopMode,
                    ns_date
                )
                time.sleep(0.05)
            
            # Clean up
            os.unlink(tmp_path)
            
            if result_container['error']:
                print(f"   Error: {result_container['error']}")
                return ""
            
            if result_container['text']:
                text = result_container['text']
                print(f"   Heard: '{text}'")
                return text.strip()
            else:
                print("   (No speech detected)")
                return ""
                
        except Exception as e:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
            print(f"   Error with macOS speech recognition: {e}")
            raise


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
    
    Uses macOS native speech recognition by default on macOS (best performance).
    Falls back to Whisper or Sphinx if macOS native unavailable.
    Can be configured via VOICE_AGENT_STT_ENGINE environment variable.
    
    Args:
        timeout: Maximum seconds to wait for speech to start (None = no timeout)
        phrase_time_limit: Maximum seconds for a phrase (None = no limit, Whisper/macOS only)
    
    Returns:
        Transcribed text as a string
    """
    engine = STT_ENGINE.lower()
    
    if engine == "macos":
        return _transcribe_macos(timeout=timeout)
    elif engine == "whisper":
        return _transcribe_whisper(timeout=timeout)
    elif engine == "sphinx":
        return _transcribe_sphinx(timeout=timeout, phrase_time_limit=phrase_time_limit)
    else:
        raise ValueError(f"Unknown STT engine '{engine}'. Use 'macos', 'whisper', or 'sphinx'")
