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
        tab_title = intent.get("tab_title")  # Fallback only
        
        if tab_index:
            # AI has selected the specific tab
            print(f"Switching to Chrome tab #{tab_index}...")
            success = switch_to_chrome_tab(tab_index=tab_index)
        elif tab_title:
            # Fallback: use title matching if AI didn't provide index
            print(f"Switching to Chrome tab matching '{tab_title}'...")
            success = switch_to_chrome_tab(tab_title=tab_title)
        else:
            print("Error: No tab specified")
            success = False
        
        if success:
            print(f"✓ Successfully switched tab\n")
        else:
            print(f"✗ Failed to switch tab\n")
        
        return success

