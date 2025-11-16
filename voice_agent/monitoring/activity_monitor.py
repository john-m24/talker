"""Activity monitor for tracking system-level changes using polling."""

import threading
import time
from typing import Optional, Dict, Any
from ..config import (
    SYSTEM_MONITOR_ENABLED,
    SYSTEM_MONITOR_APP_INTERVAL,
    SYSTEM_MONITOR_TAB_INTERVAL,
    SYSTEM_MONITOR_WINDOW_INTERVAL,
    SYSTEM_MONITOR_WINDOW_THRESHOLD,
    CACHE_ACTIVITY_HISTORY_SIZE
)
from ..cache import get_cache_manager
from .app_monitor import get_active_app
from .tab_monitor import get_active_chrome_tab
from .window_monitor import get_window_bounds


class ActivityMonitor:
    """Monitors system activity and logs changes to activity history."""
    
    def __init__(self):
        """Initialize the activity monitor."""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cache_manager = get_cache_manager()
        
        # Track previous state for change detection
        self._previous_app: Optional[str] = None
        self._previous_tab: Optional[Dict[str, Any]] = None
        self._previous_bounds: Optional[Dict[str, tuple[int, int, int, int]]] = {}  # app_name -> bounds
        
        # Track last activity timestamp per action type to avoid duplicate logging
        self._last_activity_timestamps: Dict[str, float] = {}
        self._cooldown_period = 0.5  # 0.5 seconds cooldown between same action type
    
    def start(self) -> None:
        """Start monitoring in a background thread."""
        if not SYSTEM_MONITOR_ENABLED:
            return
        
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Stop monitoring gracefully."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
    
    def _monitor_loop(self) -> None:
        """Main polling loop with conditional checks."""
        last_app_check = 0
        last_tab_check = 0
        last_window_check = 0
        
        while self._running:
            try:
                current_time = time.time()
                
                # Poll active app (every app_interval seconds)
                if current_time - last_app_check >= SYSTEM_MONITOR_APP_INTERVAL:
                    self._check_app_change()
                    last_app_check = current_time
                
                # Poll Chrome tabs (every tab_interval seconds, only if Chrome is active)
                if current_time - last_tab_check >= SYSTEM_MONITOR_TAB_INTERVAL:
                    active_app = get_active_app()
                    if active_app == "Google Chrome":
                        self._check_tab_change()
                    last_tab_check = current_time
                
                # Poll window bounds (every window_interval seconds, only for active app)
                if current_time - last_window_check >= SYSTEM_MONITOR_WINDOW_INTERVAL:
                    active_app = get_active_app()
                    if active_app:
                        self._check_window_change(active_app)
                    last_window_check = current_time
                
                # Sleep for a short interval to avoid busy-waiting
                time.sleep(0.1)
                
            except Exception as e:
                # Continue monitoring even if one check fails
                print(f"Warning: Activity monitor error: {e}")
                time.sleep(1.0)
    
    def _check_app_change(self) -> None:
        """Check if active app has changed and log if so."""
        try:
            current_app = get_active_app()
            if current_app and current_app != self._previous_app:
                # Check cooldown
                if not self._should_log_activity("activate_app", current_app):
                    return
                
                # Log app activation
                if self._cache_manager:
                    self._cache_manager.add_activity(
                        "activate_app",
                        {
                            "app_name": current_app,
                            "previous_app": self._previous_app
                        },
                        activity_history_size=CACHE_ACTIVITY_HISTORY_SIZE
                    )
                
                self._previous_app = current_app
                # Reset window bounds tracking for new app
                if current_app not in self._previous_bounds:
                    self._previous_bounds[current_app] = None
        except Exception:
            pass  # Fail silently
    
    def _check_tab_change(self) -> None:
        """Check if active Chrome tab has changed and log if so."""
        try:
            current_tab = get_active_chrome_tab()
            if not current_tab:
                return
            
            # Compare with previous tab
            if self._previous_tab is None or current_tab.get("index") != self._previous_tab.get("index"):
                # Check cooldown
                if not self._should_log_activity("switch_tab", current_tab.get("index")):
                    return
                
                # Log tab switch
                if self._cache_manager:
                    from_tab = self._previous_tab.get("index") if self._previous_tab else None
                    self._cache_manager.add_activity(
                        "switch_tab",
                        {
                            "from_tab": from_tab,
                            "to_tab": current_tab.get("index"),
                            "tab_info": {
                                "title": current_tab.get("title"),
                                "url": current_tab.get("url"),
                                "domain": current_tab.get("domain")
                            }
                        },
                        activity_history_size=CACHE_ACTIVITY_HISTORY_SIZE
                    )
                
                self._previous_tab = current_tab
        except Exception:
            pass  # Fail silently
    
    def _check_window_change(self, app_name: str) -> None:
        """Check if window bounds have changed significantly and log if so."""
        try:
            current_bounds = get_window_bounds(app_name)
            if not current_bounds:
                return
            
            previous_bounds = self._previous_bounds.get(app_name)
            
            # Check if bounds changed significantly
            if previous_bounds is None:
                # First time seeing this app's window, just store bounds
                self._previous_bounds[app_name] = current_bounds
                return
            
            # Calculate change distance
            left_diff = abs(current_bounds[0] - previous_bounds[0])
            top_diff = abs(current_bounds[1] - previous_bounds[1])
            right_diff = abs(current_bounds[2] - previous_bounds[2])
            bottom_diff = abs(current_bounds[3] - previous_bounds[3])
            
            max_diff = max(left_diff, top_diff, right_diff, bottom_diff)
            
            if max_diff >= SYSTEM_MONITOR_WINDOW_THRESHOLD:
                # Check cooldown
                if not self._should_log_activity("place_app", app_name):
                    return
                
                # Log window movement
                if self._cache_manager:
                    self._cache_manager.add_activity(
                        "place_app",
                        {
                            "app_name": app_name,
                            "bounds": list(current_bounds),
                            "previous_bounds": list(previous_bounds)
                        },
                        activity_history_size=CACHE_ACTIVITY_HISTORY_SIZE
                    )
                
                self._previous_bounds[app_name] = current_bounds
        except Exception:
            pass  # Fail silently
    
    def _should_log_activity(self, action_type: str, identifier: Any) -> bool:
        """
        Check if activity should be logged (cooldown check).
        
        Args:
            action_type: Type of action
            identifier: Unique identifier for the action (app name, tab index, etc.)
            
        Returns:
            True if should log, False if in cooldown
        """
        key = f"{action_type}:{identifier}"
        current_time = time.time()
        last_time = self._last_activity_timestamps.get(key, 0)
        
        if current_time - last_time < self._cooldown_period:
            return False
        
        self._last_activity_timestamps[key] = current_time
        return True

