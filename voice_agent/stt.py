"""Speech-to-text abstraction layer supporting macOS native, Whisper, and Sphinx."""

import os
import sounddevice as sd
import numpy as np
import threading
import time
from typing import Optional, Tuple
from .config import STT_ENGINE, WHISPER_MODEL, SILENCE_DURATION

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


def _calculate_audio_energy(audio_chunk: np.ndarray) -> float:
    """
    Calculate RMS energy of audio chunk and convert to dB.
    Optimized version using faster numpy operations.
    
    Args:
        audio_chunk: Audio data as numpy array
        
    Returns:
        Energy in dB
    """
    # Use np.square instead of **2, slightly faster
    rms = np.sqrt(np.mean(np.square(audio_chunk)))
    # Convert to dB, avoid log(0) by adding small epsilon
    db = 20 * np.log10(rms + 1e-10)
    return db


def _detect_speech_start(audio_chunk: np.ndarray, speech_threshold_db: float = -40.0) -> bool:
    """
    Detect if speech has started by checking if audio energy exceeds threshold.
    
    Args:
        audio_chunk: Audio data as numpy array
        speech_threshold_db: Energy threshold in dB (default: -40 dB)
        
    Returns:
        True if speech detected, False otherwise
    """
    energy_db = _calculate_audio_energy(audio_chunk)
    return energy_db > speech_threshold_db


def _detect_speech_end(
    audio_chunk: np.ndarray,
    silence_start_time: Optional[float],
    speech_threshold_db: float = -40.0,
    silence_duration: float = 1.5,
    current_time: Optional[float] = None
) -> Tuple[bool, Optional[float]]:
    """
    Detect if speech has ended by checking if silence persists for configured duration.
    
    Args:
        audio_chunk: Audio data as numpy array
        silence_start_time: Timestamp when silence started (None if speech is active)
        speech_threshold_db: Energy threshold in dB (default: -40 dB)
        silence_duration: Required silence duration in seconds (default: 1.5s)
        current_time: Current timestamp (if None, uses time.time())
        
    Returns:
        Tuple of (speech_ended, new_silence_start_time)
        - speech_ended: True if silence duration exceeded threshold
        - new_silence_start_time: Updated silence start time (None if speech detected)
    """
    if current_time is None:
        current_time = time.time()
    
    energy_db = _calculate_audio_energy(audio_chunk)
    is_silent = energy_db <= speech_threshold_db
    
    if is_silent:
        if silence_start_time is None:
            # Silence just started
            return False, current_time
        else:
            # Check if silence duration exceeded threshold
            elapsed_silence = current_time - silence_start_time
            if elapsed_silence >= silence_duration:
                return True, silence_start_time
            else:
                return False, silence_start_time
    else:
        # Speech detected, reset silence timer
        return False, None


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
    
    print("\n🎤 Listening... (speak now)")
    
    # Record audio using sounddevice (simpler than AVAudioEngine)
    sample_rate = 16000
    audio_queue = []
    recording = threading.Event()
    recording.set()
    chunk_duration = 0.05  # Process chunks every 50ms
    
    def audio_callback(indata, frames, time_info, status):
        """Callback for audio recording."""
        if recording.is_set():
            audio_queue.append(indata.copy())
    
    # Start recording
    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype=np.float32,
        callback=audio_callback,
        blocksize=int(sample_rate * chunk_duration)
    )
    
    stream.start()
    
    # Stage 1: Wait for speech to start
    speech_detected = False
    speech_start_timeout = 10.0  # 10 second timeout for speech start
    start_wait_time = time.time()
    
    while not speech_detected:
        elapsed = time.time() - start_wait_time
        if elapsed > speech_start_timeout:
            print("   (No speech detected within timeout)")
            recording.clear()
            stream.stop()
            stream.close()
            return ""
        
        # Check audio queue for speech
        if audio_queue:
            chunk = audio_queue[-1]
            if _detect_speech_start(chunk):
                speech_detected = True
                print("   Speech detected, listening...")
                break
        
        time.sleep(0.02)  # Small delay to avoid busy waiting
    
    # Stage 2: Record while speaking, detect end
    silence_start_time = None
    min_recording_duration = 0.1  # Minimum 0.1s recording after speech starts
    speech_start_time = time.time()
    
    while True:
        current_time = time.time()
        
        # Check if we have minimum recording duration
        if (current_time - speech_start_time) < min_recording_duration:
            time.sleep(0.02)
            continue
        
        # Check audio queue for silence
        if audio_queue:
            chunk = audio_queue[-1]
            speech_ended, silence_start_time = _detect_speech_end(
                chunk,
                silence_start_time,
                silence_duration=SILENCE_DURATION,
                current_time=current_time
            )
            
            if speech_ended:
                break
        
        time.sleep(0.02)
    
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
            
            # Check if on-device recognition is supported
            supports_on_device = recognizer.supportsOnDeviceRecognition()
            if supports_on_device:
                print("   ✓ On-device recognition available (faster, private)")
            else:
                print("   ⚠️  On-device recognition not available for this locale, may use cloud")
            
            url = NSURL.fileURLWithPath_(tmp_path)
            request = SFSpeechURLRecognitionRequest.alloc().initWithURL_(url)
            
            # Force on-device recognition if supported
            if supports_on_device:
                try:
                    # Try to set requiresOnDeviceRecognition property
                    # This ensures recognition happens on-device only
                    request.setRequiresOnDeviceRecognition_(True)
                    print("   Using on-device recognition only")
                except AttributeError:
                    # Fallback: try direct property access
                    try:
                        request.requiresOnDeviceRecognition = True
                        print("   Using on-device recognition only")
                    except:
                        print("   On-device supported but couldn't force it (may still use cloud)")
            
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
            
            # Wait for recognition to complete - delegate will signal when done
            from Cocoa import NSRunLoop, NSDefaultRunLoopMode
            from Foundation import NSDate
            
            # No timeout - just wait for delegate to signal completion
            # The delegate callbacks will set result_container['done'] = True
            # Only use timeout if explicitly provided (for safety in edge cases)
            start_time = time.time()
            safety_timeout = 60.0  # Long safety timeout (60s) to prevent infinite hangs
            
            while not result_container['done']:
                elapsed = time.time() - start_time
                
                # Check explicit timeout if provided
                if timeout and elapsed > timeout:
                    task.cancel()
                    result_container['done'] = True
                    result_container['error'] = f"Recognition timeout after {timeout:.1f}s"
                    break
                
                # Safety timeout to prevent infinite hangs (only if no explicit timeout)
                if not timeout and elapsed > safety_timeout:
                    task.cancel()
                    result_container['done'] = True
                    result_container['error'] = f"Recognition safety timeout after {safety_timeout:.1f}s"
                    break
                
                # Process run loop events - convert Python time to NSDate
                future_time = time.time() + 0.1  # Check every 100ms
                ns_date = NSDate.dateWithTimeIntervalSince1970_(future_time)
                NSRunLoop.currentRunLoop().runMode_beforeDate_(
                    NSDefaultRunLoopMode,
                    ns_date
                )
                time.sleep(0.05)  # Small sleep to avoid busy waiting
            
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
    
    print("\n🎤 Listening... (speak now)")
    
    # Record audio using thread-safe queue
    audio_queue = queue.Queue()
    recording = threading.Event()
    recording.set()
    chunk_duration = 0.05  # Process chunks every 50ms
    
    def audio_callback(indata, frames, time_info, status):
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
        callback=audio_callback,
        blocksize=int(sample_rate * chunk_duration)
    )
    
    stream.start()
    
    # Stage 1: Wait for speech to start
    speech_detected = False
    speech_start_timeout = 10.0  # 10 second timeout for speech start
    start_wait_time = time.time()
    audio_chunks = []  # Store all chunks for transcription
    
    while not speech_detected:
        elapsed = time.time() - start_wait_time
        if elapsed > speech_start_timeout:
            print("   (No speech detected within timeout)")
            recording.clear()
            stream.stop()
            stream.close()
            return ""
        
        # Collect chunks and check latest for speech
        while not audio_queue.empty():
            chunk = audio_queue.get()
            audio_chunks.append(chunk)
        
        # Check latest chunk for speech
        if audio_chunks:
            if _detect_speech_start(audio_chunks[-1]):
                speech_detected = True
                print("   Speech detected, listening...")
                break
        
        time.sleep(0.02)  # Small delay to avoid busy waiting
    
    # Stage 2: Record while speaking, detect end
    silence_start_time = None
    min_recording_duration = 0.1  # Minimum 0.1s recording after speech starts
    speech_start_time = time.time()
    
    while True:
        current_time = time.time()
        
        # Collect new chunks
        while not audio_queue.empty():
            chunk = audio_queue.get()
            audio_chunks.append(chunk)
        
        # Check if we have minimum recording duration
        if (current_time - speech_start_time) < min_recording_duration:
            time.sleep(0.02)
            continue
        
        # Check latest chunk for silence
        if audio_chunks:
            speech_ended, silence_start_time = _detect_speech_end(
                audio_chunks[-1],
                silence_start_time,
                silence_duration=SILENCE_DURATION,
                current_time=current_time
            )
            
            if speech_ended:
                break
        
        time.sleep(0.02)
    
    # Stop recording
    recording.clear()
    stream.stop()
    stream.close()
    
    if not audio_chunks:
        print("   (No audio recorded)")
        return ""
    
    audio = np.concatenate(audio_chunks, axis=0)
    # Flatten to 1D array if needed (Whisper expects 1D array)
    if audio.ndim > 1:
        audio = audio.flatten()
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
