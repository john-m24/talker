"""Clarification dialog for confirming or correcting transcribed text."""

from typing import Optional
from .web.dialog import get_active_dialog
from .text_input import show_text_input_dialog
from .autocomplete import AutocompleteEngine
from .cache import get_cache_manager


def show_clarification_dialog(transcribed_text: str, reason: Optional[str] = None) -> Optional[str]:
    """
    Show a web dialog asking the user to confirm or correct transcribed text.
    
    Args:
        transcribed_text: The text that was transcribed from speech
        reason: Optional reason why clarification is needed (e.g., "App name not found")
        
    Returns:
        The confirmed/corrected text if user confirms, or None if cancelled
    """
    # Try to use the active web dialog if available
    active_dialog = get_active_dialog()
    if active_dialog:
        return active_dialog.request_clarification(transcribed_text, reason)
    
    # If no active dialog, open one for clarification
    # This happens when clarification is needed in voice mode
    cache_manager = get_cache_manager()
    autocomplete_engine = None
    if cache_manager:
        try:
            from .autocomplete import AutocompleteEngine
            autocomplete_engine = AutocompleteEngine(cache_manager=cache_manager)
        except Exception:
            pass
    
    # Create and open a new dialog for clarification
    if cache_manager and autocomplete_engine:
        try:
            from .web.dialog import WebTextInputDialog
            dialog = WebTextInputDialog(autocomplete_engine, cache_manager)
            # Set clarification request first
            dialog.clarification_text = transcribed_text
            dialog.clarification_reason = reason
            # Open the dialog (this will show it in the browser and wait for response)
            # The dialog will poll for clarification and show it
            return dialog.request_clarification(transcribed_text, reason)
        except Exception as e:
            print(f"Error opening clarification dialog: {e}")
            return None
    
    # Fallback: if we can't open web dialog, return None
    print("Warning: Could not open clarification dialog")
    return None

