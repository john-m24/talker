"""Whisper speech-to-text engine implementation."""

import sounddevice as sd
import numpy as np
import threading
import queue
import time
from typing import Optional, Callable

from ..base import STTEngine
from ..audio import detect_speech_start, detect_speech_end
from ..config import WHISPER_MODEL, SILENCE_DURATION

# Whisper model cache
_whisper_model = None


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


class WhisperSTTEngine(STTEngine):
    """Whisper speech-to-text engine."""
    
    def transcribe(self, timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> str:
        """Transcribe using Whisper."""
        model = _get_whisper_model(WHISPER_MODEL)
        
        print("\n🎤 Listening... (speak now)")
        
        # Record audio using thread-safe queue
        sample_rate = 16000
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
                if detect_speech_start(audio_chunks[-1]):
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
                speech_ended, silence_start_time = detect_speech_end(
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
        transcribe_options = {"language": "en"}
        result = model.transcribe(audio, **transcribe_options)
        text = result["text"].strip()
        
        if text:
            print(f"   Heard: '{text}'")
        else:
            print("   (No speech detected)")
        
        return text
    
    def transcribe_while_held(self, is_held: Callable[[], bool], context: Optional[str] = None) -> str:
        """
        Record audio while hotkey is held, then transcribe.
        
        Args:
            is_held: Callable that returns True while recording should continue
            context: Optional context text to help with transcription accuracy
        
        Returns:
            Transcribed text as a string
        """
        model = _get_whisper_model(WHISPER_MODEL)
        
        print("\n🎤 Listening... (hold hotkey to speak)")
        
        # Record audio using thread-safe queue
        sample_rate = 16000
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
        
        # Record while hotkey is held
        audio_chunks = []
        min_recording_duration = 0.1  # Minimum 0.1s recording
        
        while is_held():
            # Collect chunks
            while not audio_queue.empty():
                chunk = audio_queue.get()
                audio_chunks.append(chunk)
            
            time.sleep(0.02)  # Small delay to avoid busy waiting
        
        # Wait a bit more to ensure we get all audio
        time.sleep(0.1)
        while not audio_queue.empty():
            chunk = audio_queue.get()
            audio_chunks.append(chunk)
        
        # Stop recording
        recording.clear()
        stream.stop()
        stream.close()
        
        if not audio_chunks:
            print("   (No audio recorded)")
            return ""
        
        # Check minimum duration
        duration = len(audio_chunks) * chunk_duration
        if duration < min_recording_duration:
            print("   (Recording too short)")
            return ""
        
        audio = np.concatenate(audio_chunks, axis=0)
        # Flatten to 1D array if needed (Whisper expects 1D array)
        if audio.ndim > 1:
            audio = audio.flatten()
        print("   Processing with Whisper...")
        
        # Transcribe with Whisper
        transcribe_options = {"language": "en"}
        if context:
            # Limit context to ~224 tokens (Whisper's effective limit)
            # Roughly 1 token = 4 characters, so ~900 characters max
            if len(context) > 900:
                context = context[:900]
            transcribe_options["initial_prompt"] = context
        
        result = model.transcribe(audio, **transcribe_options)
        text = result["text"].strip()
        
        if text:
            print(f"   Heard: '{text}'")
        else:
            print("   (No speech detected)")
        
        return text

