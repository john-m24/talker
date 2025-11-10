"""File control functions for opening files and folders in applications."""

import os
import subprocess
from typing import Optional
from .utils import AppleScriptExecutor, escape_applescript_string


# Create a module-level executor instance
_executor = AppleScriptExecutor()


def open_path_in_app(path: str, app_name: str) -> bool:
    """
    Open a file or folder in a specific application.
    
    Args:
        path: Path to the file or folder to open
        app_name: Name of the application to open the path in
        
    Returns:
        True if successful, False otherwise
    """
    if not os.path.exists(path):
        print(f"Error: Path not found: {path}")
        return False
    
    # Normalize path
    path = os.path.abspath(path)
    
    # Escape special characters for AppleScript
    escaped_path = escape_applescript_string(path)
    escaped_app = escape_applescript_string(app_name)
    
    try:
        # Use macOS 'open' command first (simpler, more reliable, works for both files and folders)
        cmd = ["open", "-a", app_name, path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return True
        
        # Fallback to AppleScript if 'open' command fails
        script = f'''
        tell application "{escaped_app}"
            activate
            open POSIX file "{escaped_path}"
        end tell
        '''
        
        success, stdout, stderr = _executor.execute(script, check=True)
        
        if success:
            return True
        else:
            print(f"Error opening path in {app_name}: {stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"Error: Timeout opening path in {app_name}")
        return False
    except Exception as e:
        print(f"Error opening path in {app_name}: {e}")
        return False


def open_file_in_app(file_path: str, app_name: str) -> bool:
    """
    Open a file in a specific application.
    
    This is an alias for open_path_in_app() for backward compatibility.
    
    Args:
        file_path: Path to the file to open
        app_name: Name of the application to open the file in
        
    Returns:
        True if successful, False otherwise
    """
    return open_path_in_app(file_path, app_name)

