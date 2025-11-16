"""Tab control functions for browsers using AppleScript."""

import time
from typing import List, Optional
from .utils import AppleScriptExecutor, escape_applescript_string
from .monitoring.tab_monitor import list_chrome_tabs, list_chrome_tabs_with_content
from .cache import get_cache_manager
from .config import CACHE_ACTIVITY_HISTORY_SIZE

# Re-export monitoring functions for backward compatibility
__all__ = ['list_chrome_tabs', 'list_chrome_tabs_with_content', 'switch_to_chrome_tab', 'close_chrome_tab', 'close_chrome_tabs_by_indices', 'open_url_in_chrome']

# Create a module-level executor instance
_executor = AppleScriptExecutor()


def _extract_domain(url: str) -> str:
    """
    Extract domain from URL.
    
    Args:
        url: Full URL
        
    Returns:
        Domain name (e.g., "github.com")
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        return domain
    except Exception:
        return ''


# list_chrome_tabs and list_chrome_tabs_with_content are now imported from monitoring.tab_monitor


def switch_to_chrome_tab(tab_index: int) -> bool:
    """
    Switch to a specific Chrome tab by index.
    
    Args:
        tab_index: Global index of the tab (integer, 1-based, across all windows, matching list_chrome_tabs)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not tab_index or tab_index <= 0:
            print(f"Error: Invalid tab_index: {tab_index} (must be positive integer)")
            return False
        
        # Switch by global index (across all windows)
        script = f'''
        tell application "Google Chrome"
            activate
            set globalTabIndex to 1
            repeat with w in windows
                set localTabIndex to 1
                repeat with t in tabs of w
                    if globalTabIndex = {tab_index} then
                        set active tab index of w to localTabIndex
                        return true
                    end if
                    set globalTabIndex to globalTabIndex + 1
                    set localTabIndex to localTabIndex + 1
                end repeat
            end repeat
        end tell
        '''
            
        success, stdout, stderr = _executor.execute(script)
        
        if success:
            return True
        else:
            print(f"Error switching Chrome tab: {stderr}")
            return False
    except Exception as e:
        print(f"Unexpected error switching Chrome tab: {e}")
        return False


def close_chrome_tab(tab_index: int) -> bool:
    """
    Close a specific Chrome tab by index.
    Closes the tab directly without confirmation dialog.
    Supports global tab indices (across all windows).
    
    Args:
        tab_index: Global index of the tab (integer, 1-based, across all windows, matching list_chrome_tabs)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not tab_index or tab_index <= 0:
            print(f"Error: Invalid tab_index: {tab_index} (must be positive integer)")
            return False
        
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
            
        success, stdout, stderr = _executor.execute(script)
        
        if success:
            return True
        else:
            print(f"Error closing Chrome tab: {stderr}")
            return False
    except Exception as e:
        print(f"Unexpected error closing Chrome tab: {e}")
        return False


def close_chrome_tabs_by_indices(tab_indices: List[int]) -> int:
    """
    Close multiple Chrome tabs by their global indices.
    Closes tabs from highest to lowest index to avoid index shifting.
    Fails immediately if any tab index is invalid (doesn't close any tabs).
    
    Args:
        tab_indices: List of global tab indices (array<integer>, 1-based, across all windows)
        
    Returns:
        Number of successfully closed tabs (should match input length if successful)
    """
    try:
        if not tab_indices or len(tab_indices) == 0:
            print("Error: tab_indices array is empty")
            return 0
        
        # Validate all indices are positive integers
        for idx in tab_indices:
            if not isinstance(idx, int) or idx <= 0:
                print(f"Error: Invalid tab index: {idx} (must be positive integer)")
                return 0
        
        # Sort indices in descending order to avoid index shifting
        sorted_indices = sorted(tab_indices, reverse=True)
        
        # First, validate all indices exist by checking against current tabs
        tabs, _ = list_chrome_tabs()
        existing_indices = {tab['index'] for tab in tabs}
        
        for idx in sorted_indices:
            if idx not in existing_indices:
                print(f"Error: Tab index {idx} does not exist")
                return 0
        
        # Close tabs from highest to lowest index
        closed_count = 0
        for idx in sorted_indices:
            if close_chrome_tab(tab_index=idx):
                closed_count += 1
                # Small delay to avoid overwhelming Chrome
                time.sleep(0.1)
            else:
                # If any tab fails to close, stop and return count so far
                print(f"Error: Failed to close tab {idx}")
                return closed_count
        
        return closed_count
    except Exception as e:
        print(f"Unexpected error closing Chrome tabs: {e}")
        return 0


def _normalize_url(url: str) -> str:
    """
    Normalize a URL by adding protocol if missing and handling common site names.
    
    Args:
        url: URL string (may be just a domain name or site name)
        
    Returns:
        Normalized URL with protocol
    """
    url = url.strip()
    if not url:
        return url
    
    # If it already has a protocol, return as-is
    if url.startswith(('http://', 'https://')):
        return url
    
    # If it looks like a domain (contains dots), add https://
    if '.' in url:
        return f"https://{url}"
    
    # Otherwise, treat as a site name and add .com
    # Common site names like "chatgpt" -> "chatgpt.com"
    return f"https://{url}.com"


def open_url_in_chrome(url: str) -> bool:
    """
    Open a URL in Chrome by creating a new tab.
    Always creates a new tab - does not check for existing tabs.
    The AI should decide whether to use switch_tab or open_url.
    
    Args:
        url: URL to open (will be normalized if needed)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not url:
            print("Error: No URL specified")
            return False
        
        # Normalize the URL
        normalized_url = _normalize_url(url)
        
        # Escape the URL for AppleScript
        escaped_url = escape_applescript_string(normalized_url)
        
        # Open URL in new tab
        script = f'''
        tell application "Google Chrome"
            activate
            open location "{escaped_url}"
        end tell
        '''
        
        success, stdout, stderr = _executor.execute(script)
        
        if success:
            return True
        else:
            print(f"Error opening URL in Chrome: {stderr}")
            return False
    except Exception as e:
        print(f"Unexpected error opening URL in Chrome: {e}")
        return False

