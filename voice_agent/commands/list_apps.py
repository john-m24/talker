"""Command to list running applications."""

from typing import Dict, Any
from .base import Command
from ..window_control import show_apps_list


class ListAppsCommand(Command):
    """Command to list running applications."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "list_apps"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the list apps command."""
        running_apps = intent.get("running_apps", [])
        show_apps_list(running_apps)
        print()  # Keep a blank line for console output consistency
        return True

