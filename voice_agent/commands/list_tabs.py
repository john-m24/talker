"""Command to list Chrome tabs."""

from typing import Dict, Any
from .base import Command


class ListTabsCommand(Command):
    """Command to list Chrome tabs."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "list_tabs"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the list tabs command."""
        chrome_tabs = intent.get("chrome_tabs")
        
        print("\nOpen Chrome tabs:")
        if chrome_tabs:
            for tab in chrome_tabs:
                print(f"  {tab['index']}. {tab['title']}")
        else:
            print("  Chrome is not running or has no tabs")
        print()
        
        return True

