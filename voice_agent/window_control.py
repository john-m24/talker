"""Window control functions using AppleScript."""

import os
from typing import List, Optional
from .config import MONITORS, CACHE_APPS_TTL
from .utils import AppleScriptExecutor, escape_applescript_string
from .cache import get_cache_manager, CacheKeys


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
        cached = cache_manager.get(CacheKeys.RUNNING_APPS)
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
            cache_manager.set(CacheKeys.RUNNING_APPS, apps, ttl=CACHE_APPS_TTL)
        
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
        cached = cache_manager.get(CacheKeys.INSTALLED_APPS)
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
            cache_manager.set(CacheKeys.INSTALLED_APPS, apps, ttl=CACHE_APPS_TTL * 3)  # 3x TTL for installed apps
        
        return apps
    except Exception as e:
        print(f"Error listing installed apps: {e}")
        return []


# Create a module-level executor instance
_executor = AppleScriptExecutor()


def show_apps_list(apps: List[str]) -> bool:
    """
    Display a list of applications in a macOS dialog pop-up on screen.
    
    Args:
        apps: List of application names to display
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not apps:
            message = "No applications are currently running."
        else:
            # Format apps list with numbers
            apps_text = "\n".join([f"{i}. {app}" for i, app in enumerate(apps, 1)])
            message = f"Currently running applications:\n\n{apps_text}"
        
        # Escape special characters for AppleScript
        escaped_message = escape_applescript_string(message)
        
        # Create AppleScript to show dialog pop-up
        script = f'''
        tell application "System Events"
            activate
        end tell
        
        display dialog "{escaped_message}" buttons {{"OK"}} default button "OK" with title "Running Applications"
        '''
        
        success, stdout, stderr = _executor.execute(script)
        
        if success:
            return True
        else:
            print(f"Error showing apps list dialog: {stderr}")
            return False
    except Exception as e:
        print(f"Error showing apps list dialog: {e}")
        return False


def activate_app(app_name: str) -> bool:
    """
    Activate (bring to front) an application by name.
    If the app is not running, it will be launched automatically.
    
    Args:
        app_name: Name of the application to activate
        
    Returns:
        True if successful, False otherwise
    """
    # Try to activate first - macOS can often find apps even if they're not
    # in the standard directories we scan. Only check installed apps as a
    # fallback if activation fails.
    try:
        # First, try to activate (this will launch the app if it's not running)
        script = f'tell application "{app_name}" to activate'
        success, stdout, stderr = _executor.execute(script)
        
        if success:
            return True
        
        # If activate failed, check if app is installed to provide better error message
        installed_apps = list_installed_apps()
        if app_name not in installed_apps:
            print(f"Error: Application '{app_name}' is not installed")
            return False
        
        # If activate failed, try explicitly launching the app
        # This handles cases where the app name might need to be resolved
        launch_script = f'''
        tell application "System Events"
            try
                set appPath to POSIX path of (path to application "{app_name}")
                do shell script "open " & quoted form of appPath
                return true
            on error
                -- Try direct launch as fallback
                try
                    tell application "{app_name}" to launch
                    delay 0.5
                    tell application "{app_name}" to activate
                    return true
                on error errMsg
                    return false
                end try
            end try
        end tell
        '''
        success, stdout, stderr = _executor.execute(launch_script)
        
        if success:
            return True
        else:
            print(f"Error activating/launching app '{app_name}': {stderr}")
            return False
    except Exception as e:
        print(f"Unexpected error activating app '{app_name}': {e}")
        return False


def close_app(app_name: str) -> bool:
    """
    Quit (close) an application completely by name.
    This terminates the application process, not just closing windows.
    
    Args:
        app_name: Name of the application to quit
        
    Returns:
        True if successful, False otherwise
    """
    try:
        script = f'tell application "{app_name}" to quit'
        success, stdout, stderr = _executor.execute(script)
        
        if success:
            return True
        else:
            print(f"Error closing app '{app_name}': {stderr}")
            return False
    except Exception as e:
        print(f"Unexpected error closing app '{app_name}': {e}")
        return False


def place_app_on_monitor(app_name: str, monitor_name: str, maximize: bool = False) -> bool:
    """
    Place an application's front window on a specific monitor.
    
    Args:
        app_name: Name of the application to move
        monitor_name: Name of the monitor ("main", "right", or "left")
        maximize: If True, maximize the window to fill the entire monitor.
                  If False and app is newly launched, will default to True.
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if app is running before we activate it
        # If not running, default to maximizing when launched
        running_apps = list_running_apps()
        is_running = app_name in running_apps
        
        # If app is not running and maximize wasn't explicitly set to False,
        # default to maximizing newly launched apps
        if not is_running and not maximize:
            maximize = True
        
        # Look up monitor coordinates
        if monitor_name not in MONITORS:
            print(f"Error: Unknown monitor '{monitor_name}'. Available: {', '.join(MONITORS.keys())}")
            return False
        
        monitor = MONITORS[monitor_name]
        x = monitor["x"]
        y = monitor["y"]
        w = monitor["w"]
        h = monitor["h"]
        
        # Debug: Print monitor info
        print(f"DEBUG: Placing '{app_name}' on monitor '{monitor_name}'")
        print(f"DEBUG: Monitor coordinates: x={x}, y={y}, w={w}, h={h}")
        print(f"DEBUG: App was running: {is_running}, Maximize: {maximize}")
        
        # Calculate window bounds: {left, top, right, bottom}
        if maximize:
            # Fill entire monitor
            left = x
            top = y
            right = x + w
            bottom = y + h
        else:
            # Try to preserve current window size, but ensure it fits on the monitor
            # First, get current window size
            get_size_script = f'''
            tell application "{app_name}"
                activate
                try
                    set currentBounds to bounds of front window
                    return currentBounds
                on error
                    -- Fallback: try using System Events
                    try
                        tell application "System Events"
                            tell process "{app_name}"
                                set winPos to position of window 1
                                set winSize to size of window 1
                                set x1 to item 1 of winPos
                                set y1 to item 2 of winPos
                                set w1 to item 1 of winSize
                                set h1 to item 2 of winSize
                                return {{x1, y1, x1 + w1, y1 + h1}}
                            end tell
                        end tell
                    on error
                        return {{0, 0, 800, 600}}
                    end try
                end try
            end tell
            '''
            
            try:
                success, stdout, stderr = _executor.execute(get_size_script, check=True)
                if not success or not stdout:
                    raise Exception(f"Failed to get window size: {stderr}")
                
                # Parse bounds: {left, top, right, bottom}
                bounds_str = stdout.replace("{", "").replace("}", "")
                bounds_parts = [int(p.strip()) for p in bounds_str.split(",")]
                if len(bounds_parts) == 4:
                    current_left, current_top, current_right, current_bottom = bounds_parts
                    current_w = current_right - current_left
                    current_h = current_bottom - current_top
                    
                    # Ensure window fits on monitor
                    window_w = min(current_w, w)
                    window_h = min(current_h, h)
                    
                    left = x
                    top = y
                    right = x + window_w
                    bottom = y + window_h
                else:
                    # Fallback to default size
                    left = x
                    top = y
                    right = x + min(800, w)
                    bottom = y + min(600, h)
            except Exception:
                # Fallback to default size if we can't get current size
                left = x
                top = y
                right = x + min(800, w)
                bottom = y + min(600, h)
        
        # Move and resize the window
        # If app was just launched, add a delay to let the window appear
        delay_line = ""
        if not is_running:
            delay_line = "            delay 0.5\n"
        
        # Use try-catch to handle apps that don't support "count of windows"
        script = f'''
        tell application "{app_name}"
            activate
{delay_line}            try
                set bounds of front window to {{{left}, {top}, {right}, {bottom}}}
                return true
            on error errMsg
                -- Some apps don't support "front window" directly, try using System Events
                try
                    tell application "System Events"
                        tell process "{app_name}"
                            set frontmost to true
{delay_line}                            set position of window 1 to {{{left}, {top}}}
                            set size of window 1 to {{{right - left}, {bottom - top}}}
                        end tell
                    end tell
                    return true
                on error errMsg2
                    return false
                end try
            end try
        end tell
        '''
        
        # Debug: Print the AppleScript being executed
        print(f"DEBUG: AppleScript to execute:")
        print(script)
        print(f"DEBUG: Window bounds: left={left}, top={top}, right={right}, bottom={bottom}")
        
        success, stdout, stderr = _executor.execute(script)
        
        # Debug: Print the result
        print(f"DEBUG: AppleScript success: {success}")
        if stdout:
            print(f"DEBUG: AppleScript stdout: {stdout}")
        if stderr:
            print(f"DEBUG: AppleScript stderr: {stderr}")
        
        if success:
            return True
        else:
            print(f"Error placing '{app_name}' on {monitor_name} monitor: {stderr}")
            return False
            
    except Exception as e:
        print(f"Unexpected error placing '{app_name}' on {monitor_name} monitor: {e}")
        import traceback
        traceback.print_exc()
        return False
