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
            # Check if app is running to provide better feedback
            from ..window_control import list_running_apps
            running_apps = list_running_apps()
            is_running = app_name in running_apps
            
            if is_running:
                print(f"Bringing '{app_name}' to front...")
            else:
                print(f"Opening '{app_name}' (app is not currently running)...")
            
            success = activate_app(app_name)
            if success:
                if is_running:
                    print(f"✓ Successfully activated '{app_name}'\n")
                else:
                    print(f"✓ Successfully opened '{app_name}'\n")
            else:
                print(f"✗ Failed to open/activate '{app_name}'\n")
            return success
        else:
            print("Error: No app name specified in intent\n")
            return False

