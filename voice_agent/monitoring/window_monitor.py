"""Window monitoring functions using AppleScript."""

from typing import List, Optional, Tuple, Dict, Any
from ..utils import AppleScriptExecutor

# Create a module-level executor instance
_executor = AppleScriptExecutor()


def get_window_bounds(app_name: str) -> Optional[tuple[int, int, int, int]]:
    """
    Get the current bounds of an application's front window.
    Does NOT activate the app (non-intrusive monitoring).
    
    Args:
        app_name: Name of the application
        
    Returns:
        Tuple of (left, top, right, bottom) or None on failure
    """
    try:
        # Use System Events only - doesn't activate the app
        get_size_script = f'''
        tell application "System Events"
            tell process "{app_name}"
                try
                    set winPos to position of window 1
                    set winSize to size of window 1
                    set x1 to item 1 of winPos
                    set y1 to item 2 of winPos
                    set w1 to item 1 of winSize
                    set h1 to item 2 of winSize
                    return {{x1, y1, x1 + w1, y1 + h1}}
                on error
                    return {{0, 0, 800, 600}}
                end try
            end tell
        end tell
        '''
        
        success, stdout, stderr = _executor.execute(get_size_script, check=True)
        if not success or not stdout:
            return None
        
        # Parse bounds: {left, top, right, bottom}
        bounds_str = stdout.replace("{", "").replace("}", "")
        bounds_parts = [int(p.strip()) for p in bounds_str.split(",")]
        if len(bounds_parts) == 4:
            return tuple(bounds_parts)
        return None
    except Exception:
        return None


def get_all_windows(app_name: str) -> List[Dict[str, Any]]:
    """
    Get all windows for an application with their details.
    
    Args:
        app_name: Name of the application
        
    Returns:
        List of window dicts with 'index', 'title', 'bounds', 'is_minimized', 'is_fullscreen'
    """
    windows = []
    try:
        script = f'''
        tell application "System Events"
            tell process "{app_name}"
                set winList to ""
                set winIndex to 1
                repeat with w in windows
                    try
                        set winTitle to title of w
                        set winPos to position of w
                        set winSize to size of w
                        set isMin to minimized of w
                        try
                            set isFull to fullscreen of w
                        on error
                            set isFull to false
                        end try
                        
                        set x1 to item 1 of winPos
                        set y1 to item 2 of winPos
                        set w1 to item 1 of winSize
                        set h1 to item 2 of winSize
                        
                        if winList is not "" then
                            set winList to winList & linefeed
                        end if
                        set winList to winList & (winIndex as text) & "|||" & winTitle & "|||" & (x1 as text) & "," & (y1 as text) & "," & ((x1 + w1) as text) & "," & ((y1 + h1) as text) & "|||" & (isMin as text) & "|||" & (isFull as text)
                        set winIndex to winIndex + 1
                    on error
                        -- Skip windows we can't access
                    end try
                end repeat
                return winList
            end tell
        end tell
        '''
        
        success, stdout, _ = _executor.execute(script)
        if not success or not stdout:
            return windows
        
        # Parse window data
        lines = stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split('|||')
            if len(parts) >= 5:
                try:
                    index = int(parts[0])
                    title = parts[1]
                    bounds_str = parts[2]
                    is_minimized = parts[3].lower() == "true"
                    is_fullscreen = parts[4].lower() == "true"
                    
                    # Parse bounds
                    bounds_parts = [int(p.strip()) for p in bounds_str.split(",")]
                    if len(bounds_parts) == 4:
                        bounds = tuple(bounds_parts)
                    else:
                        bounds = None
                    
                    windows.append({
                        "index": index,
                        "title": title,
                        "bounds": bounds,
                        "is_minimized": is_minimized,
                        "is_fullscreen": is_fullscreen
                    })
                except (ValueError, IndexError):
                    continue
        
        return windows
    except Exception:
        return []

