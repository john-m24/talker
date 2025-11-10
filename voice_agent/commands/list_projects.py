"""Command to list active projects."""

from typing import Dict, Any
from .base import Command


class ListProjectsCommand(Command):
    """Command to list active projects."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "list_projects"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the list projects command."""
        active_projects = intent.get("active_projects", [])
        
        # Check if web dialog is active - if so, send results there
        try:
            from ..web.dialog import get_active_dialog
            active_dialog = get_active_dialog()
            if active_dialog:
                # Format projects for display
                if not active_projects:
                    items = ["No active projects found."]
                else:
                    items = []
                    for project in active_projects:
                        project_name = project.get('name', 'Unknown')
                        project_path = project.get('path', '')
                        project_type = project.get('type', 'unknown')
                        
                        # Format: "project_name (type) - path"
                        display = project_name
                        if project_type != 'unknown':
                            display += f" ({project_type})"
                        if project_path:
                            display += f" - {project_path}"
                        
                        items.append(display)
                
                # Send results to dialog
                active_dialog.send_results("Active Projects", items)
                print()  # Keep a blank line for console output consistency
                return True
        except ImportError:
            pass
        
        # Fallback to console output
        print("\nActive projects:")
        if active_projects:
            for i, project in enumerate(active_projects, 1):
                project_name = project.get('name', 'Unknown')
                project_path = project.get('path', '')
                project_type = project.get('type', 'unknown')
                
                display = f"  {i}. {project_name}"
                if project_type != 'unknown':
                    display += f" ({project_type})"
                if project_path:
                    display += f" - {project_path}"
                print(display)
        else:
            print("  No active projects found.")
        print()
        
        return True

