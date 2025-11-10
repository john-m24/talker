"""Command to focus/activate an application."""

from typing import Dict, Any
from .base import Command
from ..window_control import activate_app


class FocusAppCommand(Command):
    """Command to focus/activate an application."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "focus_app"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the focus app command."""
        app_name = intent.get("app_name")
        
        # Handle file opening if specified
        file_path = intent.get("file_path")
        file_name = intent.get("file_name")
        
        # Handle project/folder opening if specified
        project_path = intent.get("project_path")
        project_name = intent.get("project_name")
        
        if file_path or file_name:
            # Need to open a file in the app
            from ..file_control import open_path_in_app
            from ..file_context import FileContextTracker
            from ..cache import get_cache_manager
            from ..window_control import list_running_apps
            
            # Resolve file path if only file_name is provided
            if file_name and not file_path:
                file_tracker = FileContextTracker(cache_manager=get_cache_manager())
                current_project = intent.get("current_project")
                resolved_path = file_tracker.find_file(file_name, current_project=current_project)
                if resolved_path:
                    file_path = resolved_path
                else:
                    print(f"Error: Could not find file '{file_name}'\n")
                    return False
            
            if file_path:
                # If no app specified, AI should have inferred it, but we have a fallback
                if not app_name:
                    from ..file_control import infer_app_for_file
                    app_name = infer_app_for_file(file_path)
                    if not app_name:
                        print(f"Error: Could not determine app for file '{file_path}'. Please specify an app.\n")
                        return False
                
                # Check if app is running to provide better feedback
                running_apps = list_running_apps()
                is_running = app_name in running_apps
                
                if is_running:
                    print(f"Opening '{file_path}' in '{app_name}'...")
                else:
                    print(f"Opening '{app_name}' with '{file_path}' (app is not currently running)...")
                
                success = open_path_in_app(file_path, app_name)
                if success:
                    print(f"✓ Successfully opened '{file_path}' in '{app_name}'\n")
                else:
                    print(f"✗ Failed to open '{file_path}' in '{app_name}'\n")
                return success
        
        # If we get here, we need an app_name (no file/project to open)
        if not app_name:
            print("Error: No app name specified in intent\n")
            return False
        
        # Check if app is running to provide better feedback
        from ..window_control import list_running_apps
        running_apps = list_running_apps()
        is_running = app_name in running_apps
        
        if project_path or project_name:
            # Need to open a project/folder in the app
            from ..file_control import open_path_in_app
            from ..file_context import FileContextTracker
            from ..cache import get_cache_manager
            import time
            
            # Resolve project path if only project_name is provided
            if project_name and not project_path:
                print(f"🔍 [DEBUG] focus_app: Resolving project name '{project_name}'")
                file_tracker = FileContextTracker(cache_manager=get_cache_manager())
                resolved_path = file_tracker.find_project(project_name)
                if resolved_path:
                    print(f"🔍 [DEBUG] focus_app: Resolved '{project_name}' -> {resolved_path}")
                    project_path = resolved_path
                else:
                    print(f"🔍 [DEBUG] focus_app: Failed to resolve project name '{project_name}'")
                    print(f"Error: Could not find project '{project_name}'\n")
                    return False
            
            if project_path:
                if is_running:
                    print(f"Opening '{project_path}' in '{app_name}'...")
                else:
                    print(f"Opening '{app_name}' with '{project_path}' (app is not currently running)...")
                
                success = open_path_in_app(project_path, app_name)
                if success:
                    print(f"✓ Successfully opened '{project_path}' in '{app_name}'\n")
                    # Small delay to let app launch/activate
                    time.sleep(0.5)
                else:
                    print(f"✗ Failed to open '{project_path}' in '{app_name}'\n")
                return success
        
        # Regular focus/activate without file
        if is_running:
            print(f"Bringing '{app_name}' to front...")
        else:
            print(f"Opening '{app_name}' (app is not currently running)...")
        
        success = activate_app(app_name)
        if success:
            if is_running:
                print(f"✓ Successfully activated '{app_name}'\n")
            else:
                print(f"✓ Successfully opened '{app_name}'\n")
        else:
            print(f"✗ Failed to open/activate '{app_name}'\n")
        return success

