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
        # Force fresh data by invalidating cache before getting running_apps
        from ..cache import get_cache_manager, CacheKeys
        cache_manager = get_cache_manager()
        if cache_manager:
            cache_manager.invalidate(CacheKeys.RUNNING_APPS)
        
        # Now get fresh running_apps data
        from ..window_control import list_running_apps
        running_apps = list_running_apps()
        
        # Format apps for display
        if not running_apps:
            items = ["No applications are currently running."]
        else:
            items = [f"{app}" for app in running_apps]
        
        # Send results to Electron client via API
        try:
            from ..api_server import send_results
            send_results("Currently Running Applications", items)
        except Exception as e:
            # Fall back to console if API fails
            pass
        
        # Also output to console as fallback
        print(f"\nCurrently running applications:")
        if running_apps:
            for i, app in enumerate(running_apps, 1):
                print(f"  {i}. {app}")
        else:
            print("  No applications are currently running.")
        print()
        return True

