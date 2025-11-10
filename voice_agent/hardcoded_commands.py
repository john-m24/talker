"""Hardcoded command mappings for instant command parsing without LLM."""

from typing import Optional, Dict, Any


# Hardcoded command mappings
# These commands are simple enough that they don't need LLM parsing
HARDCODED_COMMANDS: Dict[str, Dict[str, Any]] = {
    # List apps commands
    "list apps": {"type": "list_apps"},
    "list applications": {"type": "list_apps"},
    "what's running": {"type": "list_apps"},
    "show apps": {"type": "list_apps"},
    "show applications": {"type": "list_apps"},
    "apps": {"type": "list_apps"},
    "applications": {"type": "list_apps"},
    
    # List tabs commands
    "list tabs": {"type": "list_tabs"},
    "show tabs": {"type": "list_tabs"},
    "tabs": {"type": "list_tabs"},
    
    # Note: "quit", "exit", "q" are handled in main.py process_command()
    # They return False to exit the main loop
}


def get_hardcoded_command(text: str) -> Optional[Dict[str, Any]]:
    """
    Get hardcoded command intent if the text matches a hardcoded command.
    
    Args:
        text: User command text (will be normalized)
        
    Returns:
        Intent dictionary if hardcoded command found, None otherwise
    """
    # Normalize text (lowercase, strip)
    normalized = text.lower().strip()
    
    # Direct match
    if normalized in HARDCODED_COMMANDS:
        intent = HARDCODED_COMMANDS[normalized].copy()
        # Return in the expected format with commands array
        return {
            "commands": [intent],
            "needs_clarification": False,
            "clarification_reason": None
        }
    
    return None

