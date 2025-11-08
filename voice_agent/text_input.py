"""Text input dialog for text mode commands."""

import subprocess
from typing import Optional
from .utils import escape_applescript_string


def show_text_input_dialog() -> Optional[str]:
    """
    Show a macOS dialog for text input command.
    
    Returns:
        The entered text if user submits, or None if cancelled
    """
    # Build the dialog message
    message = "Enter your command:"
    
    # Escape special characters for AppleScript
    escaped_message = escape_applescript_string(message)
    
    # Create AppleScript to show dialog with editable text field
    # Enter key submits (default button), Esc key cancels
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
                # User cancelled
                return None
        else:
            print(f"Error showing text input dialog: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error showing text input dialog: {e}")
        return None

