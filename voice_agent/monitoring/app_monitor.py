"""Application monitoring functions using AppleScript."""

import os
from typing import List, Optional
from ..utils import AppleScriptExecutor
from ..config import CACHE_APPS_TTL
from ..cache import get_cache_manager

# Create a module-level executor instance
_executor = AppleScriptExecutor()


def get_active_app() -> Optional[str]:
    """
    Get current frontmost application via AppleScript.
    
    Returns:
        Name of the frontmost app, or None if query fails
    """
    try:
        script = '''
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
            return frontApp
        end tell
        '''
        success, stdout, _ = _executor.execute(script)
        if success and stdout:
            return stdout.strip()
        return None
    except Exception:
        return None


def list_running_apps() -> List[str]:
    """
    Get a list of currently running, non-background applications.
    Uses cache if enabled.
    
    Returns:
        List of application names (strings)
    """
    # Check cache first
    cache_manager = get_cache_manager()
    if cache_manager:
        cached = cache_manager.get_apps("running")
        if cached is not None:
            return cached
    
    # Cache miss - fetch from system
    try:
        # Use linefeed delimiter to avoid issues with commas in app names
        script = '''
        tell application "System Events"
            set appList to ""
            set processList to every process whose background only is false
            repeat with proc in processList
                if appList is not "" then
                    set appList to appList & linefeed
                end if
                set appList to appList & name of proc
            end repeat
            return appList
        end tell
        '''
        success, stdout, stderr = _executor.execute(script, check=True)
        
        if not success:
            print(f"Error listing running apps: {stderr}")
            return []
        
        # Parse the newline-separated list
        apps = [app.strip() for app in stdout.strip().split('\n') if app.strip()] if stdout else []
        
        # Cache the result
        if cache_manager:
            cache_manager.set_apps("running", apps, ttl=CACHE_APPS_TTL)
        
        return apps
    except Exception as e:
        print(f"Unexpected error listing apps: {e}")
        return []


def list_installed_apps() -> List[str]:
    """
    Get a list of installed applications from common macOS locations.
    Uses cache if enabled.
    
    Returns:
        List of application names (without .app extension)
    """
    # Check cache first
    cache_manager = get_cache_manager()
    if cache_manager:
        cached = cache_manager.get_apps("installed")
        if cached is not None:
            return cached
    
    # Cache miss - fetch from filesystem across multiple locations
    apps_set = set()
    candidate_dirs = [
        "/Applications",
        "/Applications/Utilities",
        "/System/Applications",
        "/System/Applications/Utilities",
        "/System/Library/CoreServices",  # Finder.app and other system apps
        os.path.expanduser("~/Applications"),
    ]
    
    try:
        for base in candidate_dirs:
            if not os.path.exists(base):
                continue
            for item in os.listdir(base):
                if item.endswith(".app"):
                    # Remove .app extension
                    app_name = item[:-4]
                    apps_set.add(app_name)
        
        apps = sorted(apps_set)
        
        # Cache the result (longer TTL for installed apps)
        if cache_manager:
            cache_manager.set_apps("installed", apps, ttl=CACHE_APPS_TTL * 3)  # 3x TTL for installed apps
        
        return apps
    except Exception as e:
        print(f"Error listing installed apps: {e}")
        return []

