"""Command to place an application on a specific monitor."""

from typing import Dict, Any
from .base import Command
from ..window_control import place_app_on_monitor


class PlaceAppCommand(Command):
    """Command to place an application on a specific monitor."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "place_app"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the place app command."""
        app_name = intent.get("app_name")
        monitor = intent.get("monitor")
        maximize = intent.get("maximize", False)
        
        if app_name and monitor:
            monitor_display = monitor.replace("_", " ").title()
            maximize_text = " and maximizing" if maximize else ""
            print(f"Placing '{app_name}' on {monitor_display} monitor{maximize_text}...")
            success = place_app_on_monitor(app_name, monitor, maximize=maximize)
            if success:
                print(f"✓ Successfully placed '{app_name}' on {monitor_display} monitor\n")
            else:
                print(f"✗ Failed to place '{app_name}' on {monitor_display} monitor\n")
            return success
        else:
            missing = []
            if not app_name:
                missing.append("app name")
            if not monitor:
                missing.append("monitor")
            print(f"Error: Missing {', '.join(missing)} in intent\n")
            return False

