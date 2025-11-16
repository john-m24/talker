"""System monitoring package for activity tracking and state snapshots."""

from .activity_monitor import ActivityMonitor
from .state_snapshotter import StateSnapshotter
from .app_monitor import list_running_apps, list_installed_apps, get_active_app
from .tab_monitor import list_chrome_tabs, list_chrome_tabs_with_content, get_active_chrome_tab
from .window_monitor import get_window_bounds, get_all_windows
from .system_context import get_system_info

__all__ = [
    'ActivityMonitor',
    'StateSnapshotter',
    'list_running_apps',
    'list_installed_apps',
    'get_active_app',
    'list_chrome_tabs',
    'list_chrome_tabs_with_content',
    'get_active_chrome_tab',
    'get_window_bounds',
    'get_all_windows',
    'get_system_info',
]

