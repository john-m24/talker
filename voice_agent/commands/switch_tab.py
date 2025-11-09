"""Command to switch Chrome tabs."""

from typing import Dict, Any
from .base import Command
from ..tab_control import switch_to_chrome_tab


class SwitchTabCommand(Command):
    """Command to switch Chrome tabs."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "switch_tab"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the switch tab command - AI has already selected the tab."""
        tab_index = intent.get("tab_index")
        
        # Validate tab_index is a positive integer
        if not tab_index:
            print("Error: No tab_index specified")
            return False
        
        try:
            tab_index = int(tab_index)
            if tab_index <= 0:
                print(f"Error: Invalid tab_index: {tab_index} (must be positive integer)")
                return False
        except (ValueError, TypeError):
            print(f"Error: Invalid tab_index: {tab_index} (must be integer)")
            return False
        
        # AI has selected the specific tab
        print(f"Switching to Chrome tab #{tab_index}...")
        success = switch_to_chrome_tab(tab_index=tab_index)
        
        if success:
            print(f"✓ Successfully switched tab\n")
        else:
            print(f"✗ Failed to switch tab\n")
        
        return success

