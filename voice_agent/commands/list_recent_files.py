"""Command to list recently opened files."""

from typing import Dict, Any
from .base import Command


class ListRecentFilesCommand(Command):
    """Command to list recently opened files."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "list_recent_files"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the list recent files command."""
        recent_files = intent.get("recent_files", [])
        
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
            
            # Format files for display
            if not recent_files:
                items = ["No recently opened files found."]
            else:
                items = []
                for file_info in recent_files:
                    file_name = file_info.get('name', 'Unknown')
                    file_path = file_info.get('path', '')
                    file_type = file_info.get('type', 'other')
                    app = file_info.get('app', '')
                    
                    # Format: "filename (type) - app"
                    display = file_name
                    if file_type != 'other':
                        display += f" ({file_type})"
                    if app:
                        display += f" - {app}"
                    
                    items.append(display)
            
            # Send results to dialog
            active_dialog.send_results("Recently Opened Files", items)
            return True
        except Exception as e:
            # If web dialog fails, fall back to console (shouldn't happen)
            print(f"\nRecently opened files:")
            if recent_files:
                for i, file_info in enumerate(recent_files, 1):
                    file_name = file_info.get('name', 'Unknown')
                    file_path = file_info.get('path', '')
                    file_type = file_info.get('type', 'other')
                    app = file_info.get('app', '')
                    
                    display = f"  {i}. {file_name}"
                    if file_type != 'other':
                        display += f" ({file_type})"
                    if app:
                        display += f" - {app}"
                    print(display)
            else:
                print("  No recently opened files found.")
            print()
            return True

