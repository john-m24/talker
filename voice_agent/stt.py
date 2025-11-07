"""Speech-to-text abstraction layer."""


def transcribe_once() -> str:
    """
    Transcribe speech from microphone to text.
    
    Currently uses text input as a placeholder.
    Future: Replace with actual microphone transcription (e.g., Whisper).
    
    Returns:
        Transcribed text as a string
    """
    return input("Say something: ").strip()
