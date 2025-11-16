"""State snapshotter for capturing comprehensive system state."""

import time
from typing import Dict, Any, List, Optional
from ..config import (
    STATE_SNAPSHOT_ENABLED,
    STATE_SNAPSHOT_INTERVAL,
    STATE_SNAPSHOT_INCLUDE_DOCUMENTS,
    STATE_SNAPSHOT_INCLUDE_ALL_TABS
)
from .app_monitor import list_running_apps, get_active_app
from .tab_monitor import list_chrome_tabs, list_chrome_tabs_with_content, get_active_chrome_tab
from .window_monitor import get_all_windows, get_window_bounds
from .system_context import get_system_info


class StateSnapshotter:
    """Captures and maintains comprehensive snapshots of current system state."""
    
    def __init__(self):
        """Initialize the state snapshotter."""
        self._last_snapshot_time = 0
        self._current_snapshot: Optional[Dict[str, Any]] = None
    
    def get_full_snapshot(self) -> Dict[str, Any]:
        """
        Get comprehensive current state snapshot.
        
        Returns:
            Dict with apps, windows, tabs, documents, system context
        """
        # Update snapshot if needed
        current_time = time.time()
        if (current_time - self._last_snapshot_time >= STATE_SNAPSHOT_INTERVAL or
            self._current_snapshot is None):
            self.update_snapshot()
        
        return self._current_snapshot or {}
    
    def update_snapshot(self) -> None:
        """Refresh the current state snapshot."""
        if not STATE_SNAPSHOT_ENABLED:
            self._current_snapshot = {}
            return
        
        try:
            snapshot = {
                "timestamp": time.time(),
                "apps": self.get_apps_snapshot(),
                "windows": self.get_windows_snapshot(),
                "tabs": self.get_tabs_snapshot(),
                "system_context": get_system_info()
            }
            
            if STATE_SNAPSHOT_INCLUDE_DOCUMENTS:
                snapshot["documents"] = self.get_documents_snapshot()
            
            self._current_snapshot = snapshot
            self._last_snapshot_time = time.time()
        except Exception as e:
            print(f"Warning: Failed to update state snapshot: {e}")
            self._current_snapshot = {}
    
    def get_apps_snapshot(self) -> List[Dict[str, Any]]:
        """
        Get snapshot of all running apps with window info.
        
        Returns:
            List of app dicts with name, is_active, windows
        """
        try:
            running_apps = list_running_apps()
            active_app = get_active_app()
            
            apps = []
            for app_name in running_apps:
                windows = get_all_windows(app_name)
                apps.append({
                    "name": app_name,
                    "is_active": app_name == active_app,
                    "windows": windows
                })
            
            return apps
        except Exception:
            return []
    
    def get_windows_snapshot(self) -> List[Dict[str, Any]]:
        """
        Get snapshot of all windows across all apps.
        
        Returns:
            List of window dicts with app_name, window details
        """
        try:
            running_apps = list_running_apps()
            all_windows = []
            
            for app_name in running_apps:
                windows = get_all_windows(app_name)
                for window in windows:
                    window["app_name"] = app_name
                    all_windows.append(window)
            
            return all_windows
        except Exception:
            return []
    
    def get_tabs_snapshot(self) -> List[Dict[str, Any]]:
        """
        Get snapshot of all browser tabs.
        
        Returns:
            List of tab dicts
        """
        try:
            if STATE_SNAPSHOT_INCLUDE_ALL_TABS:
                tabs, _ = list_chrome_tabs()
            else:
                # Only active tab
                active_tab = get_active_chrome_tab()
                tabs = [active_tab] if active_tab else []
            
            return tabs
        except Exception:
            return []
    
    def get_documents_snapshot(self) -> List[Dict[str, Any]]:
        """
        Get snapshot of active documents in editors.
        
        Returns:
            List of document dicts with app_name, file_path, etc.
        """
        # Placeholder for document tracking
        # Could be extended to track open files in editors like Cursor, VS Code, etc.
        # For now, return empty list
        return []
    
    def format_snapshot_for_llm(self) -> str:
        """
        Format state snapshot in human-readable format for LLM context.
        
        Returns:
            Formatted string describing current system state
        """
        snapshot = self.get_full_snapshot()
        if not snapshot:
            return "=== CURRENT SYSTEM STATE ===\nNo state information available.\n"
        
        lines = ["=== CURRENT SYSTEM STATE ==="]
        
        # Active app
        active_app = get_active_app()
        if active_app:
            lines.append(f"Active App: {active_app}")
        else:
            lines.append("Active App: (none)")
        
        # All running apps with windows
        apps = snapshot.get("apps", [])
        if apps:
            lines.append(f"\nAll Running Apps ({len(apps)}):")
            for i, app in enumerate(apps, 1):
                app_name = app.get("name", "Unknown")
                is_active = app.get("is_active", False)
                windows = app.get("windows", [])
                
                status = "(active)" if is_active else ""
                lines.append(f"  {i}. {app_name} {status}")
                
                for window in windows:
                    bounds = window.get("bounds")
                    title = window.get("title", "Untitled")
                    if bounds:
                        lines.append(f"     - Window: {title} [{bounds[0]}, {bounds[1]}, {bounds[2]}, {bounds[3]}]")
                    else:
                        lines.append(f"     - Window: {title}")
        
        # All Chrome tabs
        tabs = snapshot.get("tabs", [])
        if tabs:
            lines.append(f"\nAll Chrome Tabs ({len(tabs)}):")
            for i, tab in enumerate(tabs, 1):
                index = tab.get("index", i)
                title = tab.get("title", "Untitled")
                url = tab.get("url", "")
                domain = tab.get("domain", "")
                is_active = tab.get("is_active", False)
                
                status = "(active)" if is_active else ""
                lines.append(f"  Tab {index} [{domain}] {status}: {title} | {url}")
        
        # Active documents
        if STATE_SNAPSHOT_INCLUDE_DOCUMENTS:
            documents = snapshot.get("documents", [])
            if documents:
                lines.append("\nActive Documents:")
                for doc in documents:
                    app_name = doc.get("app_name", "Unknown")
                    file_path = doc.get("file_path", "")
                    lines.append(f"  - {app_name}: {file_path}")
        
        # System context
        system_context = snapshot.get("system_context", {})
        if system_context:
            active_monitor = system_context.get("active_monitor")
            if active_monitor:
                lines.append(f"\nActive Monitor: {active_monitor}")
        
        return "\n".join(lines) + "\n"

