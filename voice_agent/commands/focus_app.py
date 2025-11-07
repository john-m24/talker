"""Command to focus/activate an application."""

from typing import Dict, Any
from .base import Command
from ..window_control import activate_app


class FocusAppCommand(Command):
    """Command to focus/activate an application."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "focus_app"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the focus app command."""
        app_name = intent.get("app_name")
        if app_name:
            print(f"Bringing '{app_name}' to front...")
            success = activate_app(app_name)
            if success:
                print(f"✓ Successfully activated '{app_name}'\n")
            else:
                print(f"✗ Failed to activate '{app_name}'\n")
            return success
        else:
            print("Error: No app name specified in intent\n")
            return False

