"""Command to list recently opened files."""

from typing import Dict, Any
from .base import Command


class ListRecentFilesCommand(Command):
    """Command to list recently opened files."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "list_recent_files"
    
    def produces_results(self) -> bool:
        """This command produces results to display."""
        return True
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the list recent files command."""
        recent_files = intent.get("recent_files", [])
        
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
        
        # Send results to Electron client via API
        try:
            from ..api_server import send_results
            send_results("Recently Opened Files", items)
        except Exception as e:
            # Fall back to console if API fails
            pass
        
        # Also output to console as fallback
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

