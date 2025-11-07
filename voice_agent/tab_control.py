"""Tab control functions for browsers using AppleScript."""

import subprocess
from typing import List, Optional, Dict, Union


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
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse the result (format: {1, "Title 1"}, {2, "Title 2"}, ...)
        tabs = []
        if result.stdout.strip():
            # Split by }, { to get individual tab entries
            tab_entries = result.stdout.strip().split("}, {")
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
    except subprocess.CalledProcessError as e:
        print(f"Error listing Chrome tabs: {e.stderr}")
        return []
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
            
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            return True
        else:
            print(f"Error switching Chrome tab: {result.stderr}")
            return False
    except Exception as e:
        print(f"Unexpected error switching Chrome tab: {e}")
        return False

