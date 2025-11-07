"""Command to close Chrome tabs."""

from typing import Dict, Any
from .base import Command
from ..tab_control import close_chrome_tab


class CloseTabCommand(Command):
    """Command to close Chrome tabs."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "close_tab"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the close tab command."""
        tab_title = intent.get("tab_title")
        tab_index = intent.get("tab_index")
        
        if tab_index:
            print(f"Closing Chrome tab #{tab_index}...")
            success = close_chrome_tab(tab_index=tab_index)
        elif tab_title:
            print(f"Closing Chrome tab matching '{tab_title}'...")
            success = close_chrome_tab(tab_title=tab_title)
        else:
            print("Error: No tab specified")
            success = False
        
        if success:
            print(f"✓ Successfully closed tab\n")
        else:
            print(f"✗ Failed to close tab\n")
        
        return success

