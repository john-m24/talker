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
        
        # Check if web dialog is active - if so, send results there
        try:
            from ..web.dialog import get_active_dialog
            active_dialog = get_active_dialog()
            if active_dialog:
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
                print()  # Keep a blank line for console output consistency
                return True
        except ImportError:
            pass
        
        # Fallback to console output
        print("\nRecently opened files:")
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

