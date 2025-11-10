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
        
        # Always use web dialog - create one if it doesn't exist
        try:
            from ..web.dialog import get_active_dialog, WebTextInputDialog
            from ..cache import get_cache_manager
            from ..autocomplete import AutocompleteEngine
            from ..config import AUTOCOMPLETE_MAX_SUGGESTIONS
            
            active_dialog = get_active_dialog()
            if not active_dialog:
                # Create a new dialog if none exists
                cache_manager = get_cache_manager()
                autocomplete_engine = AutocompleteEngine(max_suggestions=AUTOCOMPLETE_MAX_SUGGESTIONS)
                active_dialog = WebTextInputDialog(autocomplete_engine, cache_manager)
                # Open the dialog
                active_dialog.show()
            
            # Format apps for display
            if not running_apps:
                items = ["No applications are currently running."]
            else:
                items = [f"{app}" for app in running_apps]
            
            # Send results to dialog
            active_dialog.send_results("Currently Running Applications", items)
            return True
        except Exception as e:
            # If web dialog fails, fall back to console (shouldn't happen)
            print(f"\nCurrently running applications:")
            if running_apps:
                for i, app in enumerate(running_apps, 1):
                    print(f"  {i}. {app}")
            else:
                print("  No applications are currently running.")
            print()
            return True

