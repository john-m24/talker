"""Window control functions using AppleScript."""

from typing import List, Optional
from .config import MONITORS
from .utils import AppleScriptExecutor, escape_applescript_string
from .monitoring.app_monitor import list_running_apps, list_installed_apps
from .monitoring.window_monitor import get_window_bounds

# Re-export monitoring functions for backward compatibility
__all__ = ['list_running_apps', 'list_installed_apps', 'get_window_bounds', 'activate_app', 'close_app', 'set_window_bounds', 'place_app_on_monitor', 'show_apps_list']


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


# get_window_bounds is now imported from monitoring.window_monitor


def set_window_bounds(app_name: str, left: int, top: int, right: int, bottom: int) -> bool:
    """
    Set the bounds of an application's front window.
    
    Args:
        app_name: Name of the application
        left: Left edge coordinate
        top: Top edge coordinate
        right: Right edge coordinate
        bottom: Bottom edge coordinate
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if app is running to determine if we need a delay
        running_apps = list_running_apps()
        is_running = app_name in running_apps
        
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
        
        success, stdout, stderr = _executor.execute(script)
        
        if success:
            return True
        else:
            print(f"Error setting window bounds for '{app_name}': {stderr}")
            return False
    except Exception as e:
        print(f"Unexpected error setting window bounds for '{app_name}': {e}")
        return False


def place_app_on_monitor(app_name: str, monitor_name: Optional[str] = None, maximize: bool = False, bounds: Optional[List[int]] = None) -> bool:
    """
    Place an application's front window on a specific monitor or at specific bounds.
    
    Args:
        app_name: Name of the application to move
        monitor_name: Name of the monitor ("main", "right", or "left"). Optional if bounds provided.
        maximize: If True, maximize the window to fill the entire monitor.
                  If False and app is newly launched, will default to True.
                  Ignored if bounds provided.
        bounds: Optional list of [left, top, right, bottom] in screen coordinates.
                If provided, these bounds are used directly.
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # If bounds provided, use them directly
        if bounds is not None:
            if len(bounds) != 4:
                print(f"Error: bounds must be a list of 4 integers [left, top, right, bottom]")
                return False
            left, top, right, bottom = bounds
            return set_window_bounds(app_name, left, top, right, bottom)
        
        # Otherwise, use monitor-based placement (existing behavior)
        if monitor_name is None:
            print(f"Error: Either monitor_name or bounds must be provided")
            return False
        
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
            current_bounds = get_window_bounds(app_name)
            if current_bounds:
                current_left, current_top, current_right, current_bottom = current_bounds
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
        
        return set_window_bounds(app_name, left, top, right, bottom)
            
    except Exception as e:
        print(f"Unexpected error placing '{app_name}': {e}")
        import traceback
        traceback.print_exc()
        return False
