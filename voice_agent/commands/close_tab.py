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
        """Execute the close tab command - AI has already selected the tabs."""
        tab_indices = intent.get("tab_indices")
        
        # Validate tab_indices is a non-empty array of positive integers
        if not tab_indices:
            print("Error: No tab_indices specified")
            return False
        
        if not isinstance(tab_indices, list):
            print(f"Error: Invalid tab_indices: {tab_indices} (must be array)")
            return False
        
        if len(tab_indices) == 0:
            print("Error: tab_indices array is empty")
            return False
        
        # Validate all elements are positive integers
        try:
            validated_indices = []
            for idx in tab_indices:
                idx_int = int(idx)
                if idx_int <= 0:
                    print(f"Error: Invalid tab index: {idx_int} (must be positive integer)")
                    return False
                validated_indices.append(idx_int)
        except (ValueError, TypeError) as e:
            print(f"Error: Invalid tab_indices: {tab_indices} (all elements must be positive integers)")
            return False
        
        # Close tabs
        if len(validated_indices) == 1:
            # Single tab - use existing function
            print(f"Closing Chrome tab #{validated_indices[0]}...")
            success = close_chrome_tab(tab_index=validated_indices[0])
        else:
            # Multiple tabs - use bulk function
            print(f"Closing Chrome tabs: {validated_indices}...")
            from ..tab_control import close_chrome_tabs_by_indices
            closed_count = close_chrome_tabs_by_indices(validated_indices)
            success = closed_count == len(validated_indices)
            if success:
                print(f"✓ Successfully closed {closed_count} tab(s)\n")
            else:
                print(f"✗ Failed to close all tabs (closed {closed_count} of {len(validated_indices)})\n")
            return success
        
        if success:
            print(f"✓ Successfully closed tab\n")
        else:
            print(f"✗ Failed to close tab\n")
        
        return success











