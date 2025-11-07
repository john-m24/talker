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
            # Check if app is running to provide better feedback
            from ..window_control import list_running_apps
            running_apps = list_running_apps()
            is_running = app_name in running_apps
            
            monitor_display = monitor.replace("_", " ").title()
            maximize_text = " and maximizing" if maximize else ""
            
            if is_running:
                print(f"Placing '{app_name}' on {monitor_display} monitor{maximize_text}...")
            else:
                print(f"Opening '{app_name}' and placing on {monitor_display} monitor{maximize_text} (app is not currently running)...")
            
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

