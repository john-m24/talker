"""Parse user text input into structured commands."""

import re
from typing import Dict, Optional
from .config import normalize_app_name


# Keywords that indicate list apps intent
LIST_KEYWORDS = ["list", "show", "what", "running", "open", "apps", "applications"]

# Keywords that indicate focus/activate intent
FOCUS_KEYWORDS = ["bring", "focus", "show", "open", "activate", "switch", "to view", "to the front"]


def normalize_text(text: str) -> str:
    """
    Normalize text for parsing: lowercase, remove extra whitespace.
    
    Args:
        text: Raw input text
        
    Returns:
        Normalized text
    """
    # Convert to lowercase and strip
    text = text.lower().strip()
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text


def parse_intent(text: str) -> Optional[Dict[str, str]]:
    """
    Parse user text into a structured command.
    
    Args:
        text: User input text
        
    Returns:
        Dictionary with 'type' and relevant fields, or None if no intent detected
    """
    normalized = normalize_text(text)
    
    # Check for quit/exit
    if normalized in ["quit", "exit", "stop", "bye"]:
        return {"type": "quit"}
    
    # Check for list apps intent
    if any(keyword in normalized for keyword in LIST_KEYWORDS):
        # Make sure it's not a focus command (e.g., "show Chrome" should focus, not list)
        if not any(keyword in normalized for keyword in ["bring", "focus", "activate", "switch"]):
            return {"type": "list_apps"}
    
    # Check for focus/activate intent
    # Patterns: "bring X to view", "focus X", "show X", "open X", "activate X"
    for keyword in FOCUS_KEYWORDS:
        if keyword in normalized:
            # Try to extract app name
            app_name = extract_app_name(normalized, keyword)
            if app_name:
                normalized_app_name = normalize_app_name(app_name)
                return {
                    "type": "focus_app",
                    "app_name": normalized_app_name
                }
    
    # Fallback: if text is just an app name (single word or short phrase)
    # Try to treat it as a focus command
    words = normalized.split()
    if len(words) <= 3:  # Reasonable app name length
        potential_app = " ".join(words)
        normalized_app_name = normalize_app_name(potential_app)
        # If it matches an alias or seems like an app name, try to focus it
        if normalized_app_name != potential_app or len(words) == 1:
            return {
                "type": "focus_app",
                "app_name": normalized_app_name
            }
    
    return None


def extract_app_name(text: str, keyword: str) -> Optional[str]:
    """
    Extract app name from text given a keyword.
    
    Examples:
        "bring Docker to view" -> "Docker"
        "focus Chrome" -> "Chrome"
        "show Slack please" -> "Slack"
    
    Args:
        text: Normalized input text
        keyword: The keyword that indicates the intent
        
    Returns:
        Extracted app name or None
    """
    # Find the position of the keyword
    keyword_pos = text.find(keyword)
    if keyword_pos == -1:
        return None
    
    # Get text after the keyword
    after_keyword = text[keyword_pos + len(keyword):].strip()
    
    # Remove common trailing words
    trailing_words = ["please", "to view", "to the front", "now", "for me"]
    for trailing in trailing_words:
        if after_keyword.endswith(trailing):
            after_keyword = after_keyword[:-len(trailing)].strip()
    
    # Extract the app name (up to 3 words max, or until we hit certain stop words)
    words = after_keyword.split()
    stop_words = ["to", "the", "front", "view", "please", "now"]
    
    app_words = []
    for word in words:
        if word in stop_words:
            break
        app_words.append(word)
        if len(app_words) >= 3:  # Max reasonable app name length
            break
    
    if app_words:
        return " ".join(app_words)
    
    return None

