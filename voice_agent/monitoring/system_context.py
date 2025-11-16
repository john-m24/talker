"""System context monitoring functions using AppleScript."""

from typing import Dict, List, Optional, Tuple, Any
from ..utils import AppleScriptExecutor
from ..config import MONITORS

# Create a module-level executor instance
_executor = AppleScriptExecutor()


def get_active_monitor() -> Optional[str]:
    """
    Get which monitor has the active window.
    
    Returns:
        Monitor name (e.g., "main", "left", "right") or None
    """
    try:
        script = '''
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
            if frontApp is not "" then
                tell process frontApp
                    try
                        set winPos to position of window 1
                        set x to item 1 of winPos
                        set y to item 2 of winPos
                        return {x, y}
                    on error
                        return {0, 0}
                    end try
                end tell
            end if
        end tell
        '''
        success, stdout, _ = _executor.execute(script)
        if not success or not stdout:
            return None
        
        # Parse position
        pos_str = stdout.replace("{", "").replace("}", "")
        pos_parts = [int(p.strip()) for p in pos_str.split(",")]
        if len(pos_parts) >= 2:
            x, y = pos_parts[0], pos_parts[1]
            
            # Find which monitor contains this point
            for monitor_name, monitor_config in MONITORS.items():
                mx = monitor_config.get("x", 0)
                my = monitor_config.get("y", 0)
                mw = monitor_config.get("w", 1920)
                mh = monitor_config.get("h", 1080)
                
                if mx <= x < mx + mw and my <= y < my + mh:
                    return monitor_name
        
        return None
    except Exception:
        return None


def get_all_monitors() -> Dict[str, Dict[str, int]]:
    """
    Get all monitor configurations.
    
    Returns:
        Dict mapping monitor name to monitor config (x, y, w, h)
    """
    return MONITORS.copy()


def get_active_space() -> Optional[int]:
    """
    Get current desktop space number (if possible via AppleScript).
    
    Returns:
        Space number (1-based) or None if not available
    """
    # Note: Getting active space via AppleScript is limited on macOS
    # This is a placeholder for future implementation
    # May require Accessibility API or other methods
    return None


def get_screen_resolution() -> Tuple[int, int]:
    """
    Get primary screen resolution.
    
    Returns:
        Tuple of (width, height)
    """
    try:
        script = '''
        tell application "System Events"
            set screenRes to size of desktop 1
            return screenRes
        end tell
        '''
        success, stdout, _ = _executor.execute(script)
        if success and stdout:
            # Parse: {width, height}
            res_str = stdout.replace("{", "").replace("}", "")
            res_parts = [int(p.strip()) for p in res_str.split(",")]
            if len(res_parts) >= 2:
                return tuple(res_parts[:2])
        
        # Fallback to first monitor if available
        if MONITORS:
            first_monitor = list(MONITORS.values())[0]
            return (first_monitor.get("w", 1920), first_monitor.get("h", 1080))
        
        return (1920, 1080)  # Default fallback
    except Exception:
        return (1920, 1080)  # Default fallback


def get_system_info() -> Dict[str, Any]:
    """
    Get general system information.
    
    Returns:
        Dict with system information
    """
    return {
        "active_monitor": get_active_monitor(),
        "monitors": get_all_monitors(),
        "screen_resolution": get_screen_resolution(),
        "active_space": get_active_space()
    }

