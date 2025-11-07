"""Audio processing utilities for speech detection."""

import numpy as np
import time
from typing import Optional, Tuple


def calculate_audio_energy(audio_chunk: np.ndarray) -> float:
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


def detect_speech_start(audio_chunk: np.ndarray, speech_threshold_db: float = -40.0) -> bool:
    """
    Detect if speech has started by checking if audio energy exceeds threshold.
    
    Args:
        audio_chunk: Audio data as numpy array
        speech_threshold_db: Energy threshold in dB (default: -40 dB)
        
    Returns:
        True if speech detected, False otherwise
    """
    energy_db = calculate_audio_energy(audio_chunk)
    return energy_db > speech_threshold_db


def detect_speech_end(
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
    
    energy_db = calculate_audio_energy(audio_chunk)
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

