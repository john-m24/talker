"""Command to list running applications."""

from typing import Dict, Any
from .base import Command


class ListAppsCommand(Command):
    """Command to list running applications."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "list_apps"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the list apps command."""
        running_apps = intent.get("running_apps", [])
        
        # Check if web dialog is active - if so, send results there
        try:
            from ..web.dialog import get_active_dialog
            active_dialog = get_active_dialog()
            if active_dialog:
                # Format apps for display
                if not running_apps:
                    items = ["No applications are currently running."]
                else:
                    items = [f"{app}" for app in running_apps]
                
                # Send results to dialog
                active_dialog.send_results("Currently Running Applications", items)
                print()  # Keep a blank line for console output consistency
                return True
        except ImportError:
            pass
        
        # Fallback to console output (no popup)
        print("\nCurrently running applications:")
        if running_apps:
            for i, app in enumerate(running_apps, 1):
                print(f"  {i}. {app}")
        else:
            print("  No applications are currently running.")
        print()
        
        return True

