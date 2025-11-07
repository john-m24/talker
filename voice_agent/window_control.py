"""Window control functions using AppleScript."""

import subprocess
import os
from typing import List, Optional


def list_running_apps() -> List[str]:
    """
    Get a list of currently running, non-background applications.
    
    Returns:
        List of application names (strings)
    """
    try:
        script = 'tell application "System Events" to get name of every process whose background only is false'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse the comma-separated list
        apps = [app.strip() for app in result.stdout.strip().split(", ")]
        return apps
    except subprocess.CalledProcessError as e:
        print(f"Error listing running apps: {e.stderr}")
        return []
    except Exception as e:
        print(f"Unexpected error listing apps: {e}")
        return []


def list_installed_apps() -> List[str]:
    """
    Get a list of installed applications from /Applications directory.
    
    Returns:
        List of application names (without .app extension)
    """
    apps = []
    applications_dir = "/Applications"
    
    try:
        if not os.path.exists(applications_dir):
            return apps
        
        for item in os.listdir(applications_dir):
            if item.endswith(".app"):
                # Remove .app extension
                app_name = item[:-4]
                apps.append(app_name)
        
        return sorted(apps)
    except Exception as e:
        print(f"Error listing installed apps: {e}")
        return []


def activate_app(app_name: str) -> bool:
    """
    Activate (bring to front) an application by name.
    
    Args:
        app_name: Name of the application to activate
        
    Returns:
        True if successful, False otherwise
    """
    try:
        script = f'tell application "{app_name}" to activate'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            return True
        else:
            print(f"Error activating app '{app_name}': {result.stderr}")
            return False
    except Exception as e:
        print(f"Unexpected error activating app '{app_name}': {e}")
        return False
