"""macOS native speech-to-text engine implementation."""

import os
import sounddevice as sd
import numpy as np
import threading
import time
import tempfile
import wave
from typing import Optional

from ..base import STTEngine
from ..audio import detect_speech_start, detect_speech_end
from ..config import SILENCE_DURATION

# Fix SSL certificate issues on macOS
if "SSL_CERT_FILE" not in os.environ:
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass  # certifi not available, will use system defaults

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
                
                def speechRecognitionTask_didHypothesizeTranscription_(self, task, transcription):
                    # Optional: handle partial results
                    pass
            
            _macos_recognition_delegate_class = RecognitionDelegate
        except ImportError:
            pass
    return _macos_recognition_delegate_class


class MacOSSTTEngine(STTEngine):
    """macOS native speech-to-text engine using Speech framework."""
    
    def transcribe(self, timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> str:
        """Transcribe using macOS native speech recognition via Speech framework."""
        try:
            from Speech import SFSpeechRecognizer, SFSpeechURLRecognitionRequest
            from Foundation import NSLocale, NSURL, NSDate
            from Cocoa import NSRunLoop, NSDefaultRunLoopMode
        except ImportError:
            raise ImportError("PyObjC not installed. Install with: pip install pyobjc")
        
        print("\n🎤 Listening... (speak now)")
        
        # Record audio using sounddevice
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
                if detect_speech_start(chunk):
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
                speech_ended, silence_start_time = detect_speech_end(
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
                        request.setRequiresOnDeviceRecognition_(True)
                        print("   Using on-device recognition only")
                    except AttributeError:
                        try:
                            request.requiresOnDeviceRecognition = True
                            print("   Using on-device recognition only")
                        except:
                            print("   On-device supported but couldn't force it (may still use cloud)")
                
                result_container = {'text': None, 'done': False, 'error': None}
                
                # Get delegate class
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
                    
                    # Safety timeout to prevent infinite hangs
                    if not timeout and elapsed > safety_timeout:
                        task.cancel()
                        result_container['done'] = True
                        result_container['error'] = f"Recognition safety timeout after {safety_timeout:.1f}s"
                        break
                    
                    # Process run loop events
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

