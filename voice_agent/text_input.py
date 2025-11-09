"""Text input dialog for text mode commands with auto-complete."""

import subprocess
from typing import Optional
from .utils import escape_applescript_string


def show_text_input_dialog(
    autocomplete_engine=None,
    cache_manager=None
) -> Optional[str]:
    """
    Show text input dialog with auto-complete support.
    
    Args:
        autocomplete_engine: AutocompleteEngine instance (optional, for future use)
        cache_manager: CacheManager instance (optional, for future use)
    
    Returns:
        The entered text if user submits, or None if cancelled
    """
    # TODO: Web-based dialog with auto-complete will be implemented in Phase 4
    # For now, use AppleScript fallback dialog
    
    # AppleScript dialog (temporary fallback until web dialog is ready)
    message = "Enter your command:"
    escaped_message = escape_applescript_string(message)
    
    script = f'''
    tell application "System Events"
        activate
    end tell
    
    set theResponse to display dialog "{escaped_message}" default answer "" buttons {{"Cancel", "OK"}} default button "OK" with title "Voice Agent - Text Command"
    
    set buttonPressed to button returned of theResponse
    set textEntered to text returned of theResponse
    
    if buttonPressed is "OK" then
        return textEntered
    else
        return ""
    end if
    '''
    
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            entered_text = result.stdout.strip()
            if entered_text:
                return entered_text
            else:
                return None
        else:
            print(f"Error showing text input dialog: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error showing text input dialog: {e}")
        return None
