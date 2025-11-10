"""Clarification dialog for confirming or correcting transcribed text."""

import subprocess
from typing import Optional
from .utils import escape_applescript_string


def show_clarification_dialog(transcribed_text: str, reason: Optional[str] = None) -> Optional[str]:
    """
    Show a dialog asking the user to confirm or correct transcribed text.
    
    Args:
        transcribed_text: The text that was transcribed from speech
        reason: Optional reason why clarification is needed (e.g., "App name not found")
        
    Returns:
        The confirmed/corrected text if user confirms, or None if cancelled
    """
    # Use AppleScript dialog for clarification
    message = f"Please confirm or correct the command:\n\n{transcribed_text}"
    if reason:
        message += f"\n\nReason: {reason}"
    escaped_message = escape_applescript_string(message)
    
    script = f'''
    tell application "System Events"
        activate
    end tell
    
    set theResponse to display dialog "{escaped_message}" default answer "{escape_applescript_string(transcribed_text)}" buttons {{"Cancel", "OK"}} default button "OK" with title "Voice Agent - Clarification"
    
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
            print(f"Error showing clarification dialog: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error showing clarification dialog: {e}")
        return None

