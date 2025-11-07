"""Custom exception classes for the voice agent."""


class VoiceAgentError(Exception):
    """Base exception for voice agent errors."""
    pass


class STTError(VoiceAgentError):
    """Exception raised for speech-to-text errors."""
    pass


class STTEngineNotFoundError(STTError):
    """Exception raised when STT engine is not found or not available."""
    pass


class STTEngineNotAvailableError(STTError):
    """Exception raised when STT engine is not available (e.g., dependencies missing)."""
    pass


class AIAgentError(VoiceAgentError):
    """Exception raised for AI agent errors."""
    pass


class AIAgentConnectionError(AIAgentError):
    """Exception raised when AI agent cannot connect to the endpoint."""
    pass


class AIAgentParseError(AIAgentError):
    """Exception raised when AI agent fails to parse intent."""
    pass


class CommandError(VoiceAgentError):
    """Exception raised for command execution errors."""
    pass


class CommandNotFoundError(CommandError):
    """Exception raised when a command is not found."""
    pass


class WindowControlError(VoiceAgentError):
    """Exception raised for window control errors."""
    pass


class AppNotFoundError(WindowControlError):
    """Exception raised when an application is not found."""
    pass


class MonitorNotFoundError(WindowControlError):
    """Exception raised when a monitor is not found."""
    pass


class AppleScriptError(VoiceAgentError):
    """Exception raised for AppleScript execution errors."""
    pass

