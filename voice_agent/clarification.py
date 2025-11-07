"""Clarification dialog for confirming or correcting transcribed text."""

import subprocess
from typing import Optional
from .utils import escape_applescript_string


def show_clarification_dialog(transcribed_text: str, reason: Optional[str] = None) -> Optional[str]:
    """
    Show a macOS dialog asking the user to confirm or correct transcribed text.
    
    Args:
        transcribed_text: The text that was transcribed from speech
        reason: Optional reason why clarification is needed (e.g., "App name not found")
        
    Returns:
        The confirmed/corrected text if user clicks "Confirm", or None if cancelled
    """
    # Build the dialog message
    message = "Did I hear that correctly?"
    if reason:
        message += f"\n\nReason: {reason}"
    message += "\n\nTranscribed text:"
    
    # Escape special characters for AppleScript
    escaped_text = escape_applescript_string(transcribed_text)
    escaped_message = escape_applescript_string(message)
    
    # Create AppleScript to show dialog with editable text field
    script = f'''
    tell application "System Events"
        activate
    end tell
    
    set theResponse to display dialog "{escaped_message}" default answer "{escaped_text}" buttons {{"Cancel", "Confirm"}} default button "Confirm" with title "Voice Agent Clarification"
    
    set buttonPressed to button returned of theResponse
    set textEntered to text returned of theResponse
    
    if buttonPressed is "Confirm" then
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
            confirmed_text = result.stdout.strip()
            if confirmed_text:
                return confirmed_text
            else:
                # User cancelled
                return None
        else:
            print(f"Error showing clarification dialog: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error showing clarification dialog: {e}")
        return None

