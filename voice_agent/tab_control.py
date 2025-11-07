"""Tab control functions for browsers using AppleScript."""

from typing import List, Optional, Dict, Union
from .utils import AppleScriptExecutor

# Create a module-level executor instance
_executor = AppleScriptExecutor()


def list_chrome_tabs() -> List[Dict[str, Union[str, int]]]:
    """
    Get a list of all open Chrome tabs with their titles and indices.
    
    Returns:
        List of dicts with 'index' and 'title' keys
        Example: [{"index": 1, "title": "Gmail - Inbox"}, {"index": 2, "title": "YouTube"}]
    """
    try:
        script = '''
        tell application "Google Chrome"
            set tabList to {}
            set tabIndex to 1
            repeat with w in windows
                repeat with t in tabs of w
                    set end of tabList to {tabIndex, title of t}
                    set tabIndex to tabIndex + 1
                end repeat
            end repeat
            return tabList
        end tell
        '''
        success, stdout, stderr = _executor.execute(script, check=True)
        
        if not success:
            print(f"Error listing Chrome tabs: {stderr}")
            return []
        
        # Parse the result (format: {1, "Title 1"}, {2, "Title 2"}, ...)
        tabs = []
        if stdout:
            # Split by }, { to get individual tab entries
            tab_entries = stdout.split("}, {")
            for entry in tab_entries:
                entry = entry.replace("{", "").replace("}", "").strip()
                parts = entry.split(", ", 1)
                if len(parts) == 2:
                    try:
                        tab_index = int(parts[0])
                        tab_title = parts[1].strip('"')
                        tabs.append({
                            "index": tab_index,
                            "title": tab_title
                        })
                    except (ValueError, IndexError):
                        continue
        
        return tabs
    except Exception as e:
        print(f"Unexpected error listing Chrome tabs: {e}")
        return []


def switch_to_chrome_tab(tab_title: Optional[str] = None, tab_index: Optional[int] = None) -> bool:
    """
    Switch to a specific Chrome tab by title or index.
    
    Args:
        tab_title: Title of the tab to switch to (fuzzy matching via contains)
        tab_index: Index of the tab (1-based)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if tab_index:
            # Switch by index
            script = f'''
            tell application "Google Chrome"
                activate
                set frontWindow to front window
                set active tab index of frontWindow to {tab_index}
            end tell
            '''
        elif tab_title:
            # Switch by title (fuzzy match)
            script = f'''
            tell application "Google Chrome"
                activate
                set frontWindow to front window
                set tabIndex to 1
                repeat with t in tabs of frontWindow
                    if title of t contains "{tab_title}" then
                        set active tab index of frontWindow to tabIndex
                        return true
                    end if
                    set tabIndex to tabIndex + 1
                end repeat
            end tell
            '''
        else:
            return False
            
        success, stdout, stderr = _executor.execute(script)
        
        if success:
            return True
        else:
            print(f"Error switching Chrome tab: {stderr}")
            return False
    except Exception as e:
        print(f"Unexpected error switching Chrome tab: {e}")
        return False


def close_chrome_tab(tab_title: Optional[str] = None, tab_index: Optional[int] = None) -> bool:
    """
    Close a specific Chrome tab by title or index.
    Closes the tab directly without confirmation dialog.
    Supports global tab indices (across all windows) when using tab_index.
    
    Args:
        tab_title: Title of the tab to close (fuzzy matching via contains, searches front window only)
        tab_index: Global index of the tab (1-based, across all windows, matching list_chrome_tabs)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if tab_index:
            # Close by global index (across all windows)
            script = f'''
            tell application "Google Chrome"
                activate
                set globalTabIndex to 1
                repeat with w in windows
                    repeat with t in tabs of w
                        if globalTabIndex = {tab_index} then
                            close t
                            return true
                        end if
                        set globalTabIndex to globalTabIndex + 1
                    end repeat
                end repeat
            end tell
            '''
        elif tab_title:
            # Close by title (fuzzy match, searches front window only for consistency with switch_to_chrome_tab)
            script = f'''
            tell application "Google Chrome"
                activate
                set frontWindow to front window
                repeat with t in tabs of frontWindow
                    if title of t contains "{tab_title}" then
                        close t
                        return true
                    end if
                end repeat
            end tell
            '''
        else:
            return False
            
        success, stdout, stderr = _executor.execute(script)
        
        if success:
            return True
        else:
            print(f"Error closing Chrome tab: {stderr}")
            return False
    except Exception as e:
        print(f"Unexpected error closing Chrome tab: {e}")
        return False

