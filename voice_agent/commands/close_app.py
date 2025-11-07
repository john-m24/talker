"""Command to close/quit an application."""

from typing import Dict, Any
from .base import Command
from ..window_control import close_app


class CloseAppCommand(Command):
    """Command to close/quit an application."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "close_app"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the close app command."""
        app_name = intent.get("app_name")
        if app_name:
            print(f"Closing '{app_name}'...")
            success = close_app(app_name)
            if success:
                print(f"✓ Successfully closed '{app_name}'\n")
            else:
                print(f"✗ Failed to close '{app_name}'\n")
            return success
        else:
            print("Error: No app name specified in intent\n")
            return False









