"""Tab control functions for browsers using AppleScript."""

import re
import time
from typing import List, Optional, Dict, Union
from urllib.parse import urlparse
from .utils import AppleScriptExecutor, escape_applescript_string

# Create a module-level executor instance
_executor = AppleScriptExecutor()

# Module-level cache for tab content
# Structure: {url: {"content": str, "title": str, "timestamp": float}}
_tab_content_cache: Dict[str, Dict[str, Union[str, float]]] = {}


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


def list_chrome_tabs() -> tuple[List[Dict[str, Union[str, int, bool]]], Optional[str]]:
    """
    Get a list of all open Chrome tabs with rich metadata.
    
    Returns:
        Tuple of (list of tab dicts, raw AppleScript output)
        Tab dicts have: index, title, url, domain, window_index, 
        local_index, is_active
        Example: ([{"index": 1, "title": "Gmail - Inbox", "url": "https://mail.google.com", 
                  "domain": "mail.google.com", "window_index": 1, "local_index": 1, "is_active": True}], raw_output)
    """
    try:
        script = '''
        tell application "Google Chrome"
            set tabList to {}
            set globalTabIndex to 1
            set windowIndex to 1
            repeat with w in windows
                set activeTabIndex to active tab index of w
                set localTabIndex to 1
                repeat with t in tabs of w
                    set isActive to (localTabIndex = activeTabIndex)
                    set tabTitle to title of t
                    set tabURL to URL of t
                    set end of tabList to {globalTabIndex, tabTitle, tabURL, windowIndex, localTabIndex, isActive}
                    set globalTabIndex to globalTabIndex + 1
                    set localTabIndex to localTabIndex + 1
                end repeat
                set windowIndex to windowIndex + 1
            end repeat
            return tabList
        end tell
        '''
        success, stdout, stderr = _executor.execute(script, check=True)
        
        if not success:
            print(f"Error listing Chrome tabs: {stderr}")
            return [], None
        
        raw_output = stdout if stdout else None
        
        # Parse the result
        # AppleScript returns either:
        # - With braces: {1, "Title", "URL", 1, 1, true}, {2, "Title", "URL", 1, 2, false}
        # - Without braces: 1, "Title", "URL", 1, 1, true, 2, "Title", "URL", 1, 2, false
        tabs = []
        if stdout:
            # Use findall to find ALL tab entries in the string
            # Pattern: number, "quoted string", "quoted string", number, number, true/false
            pattern = r'(\d+),\s*"([^"]*)",\s*"([^"]*)",\s*(\d+),\s*(\d+),\s*(true|false)'
            matches = re.findall(pattern, stdout)
            
            if matches:
                # Found matches using regex - process all of them
                for match in matches:
                    try:
                        global_index = int(match[0])
                        title = match[1]
                        url = match[2]
                        window_index = int(match[3])
                        local_index = int(match[4])
                        is_active = match[5].lower() == "true"
                        
                        # Extract domain from URL
                        domain = _extract_domain(url)
                        
                        tabs.append({
                            "index": global_index,
                            "title": title,
                            "url": url,
                            "domain": domain,
                            "window_index": window_index,
                            "local_index": local_index,
                            "is_active": is_active
                        })
                    except (ValueError, IndexError) as e:
                        print(f"Warning: Failed to parse tab entry: {match}... Error: {e}")
                        continue
            else:
                # Fallback: try splitting by }, { for brace format
                if "}, {" in stdout:
                    tab_entries = stdout.split("}, {")
                else:
                    # Single tab case or no braces
                    tab_entries = [stdout]
                
                for entry in tab_entries:
                    # Clean up the entry
                    entry = entry.strip()
                    # Remove outer braces
                    if entry.startswith("{"):
                        entry = entry[1:]
                    if entry.endswith("}"):
                        entry = entry[:-1]
                    entry = entry.strip()
                    
                    if not entry:
                        continue
                    
                    # Try regex again on individual entry
                    match = re.match(pattern, entry)
                    if match:
                        try:
                            global_index = int(match.group(1))
                            title = match.group(2)
                            url = match.group(3)
                            window_index = int(match.group(4))
                            local_index = int(match.group(5))
                            is_active = match.group(6).lower() == "true"
                            
                            domain = _extract_domain(url)
                            
                            tabs.append({
                                "index": global_index,
                                "title": title,
                                "url": url,
                                "domain": domain,
                                "window_index": window_index,
                                "local_index": local_index,
                                "is_active": is_active
                            })
                        except (ValueError, IndexError) as e:
                            print(f"Warning: Failed to parse tab entry: {entry[:100]}... Error: {e}")
                            continue
                    else:
                        # Last resort: split by comma (may fail if titles/URLs contain commas)
                        parts = [p.strip().strip('"') for p in entry.split(", ")]
                        if len(parts) >= 6:
                            try:
                                global_index = int(parts[0])
                                title = parts[1]
                                url = parts[2]
                                window_index = int(parts[3])
                                local_index = int(parts[4])
                                is_active = parts[5].lower() == "true"
                                
                                domain = _extract_domain(url)
                                
                                tabs.append({
                                    "index": global_index,
                                    "title": title,
                                    "url": url,
                                    "domain": domain,
                                    "window_index": window_index,
                                    "local_index": local_index,
                                    "is_active": is_active
                                })
                            except (ValueError, IndexError) as e:
                                print(f"Warning: Failed to parse tab entry (fallback): {entry[:100]}... Error: {e}")
                                continue
                        else:
                            print(f"Warning: Tab entry has {len(parts)} parts, expected 6: {entry[:100]}...")
        
        return tabs, raw_output
    except Exception as e:
        print(f"Unexpected error listing Chrome tabs: {e}")
        return [], None


def _get_cached_content(url: str) -> Optional[Dict[str, Union[str, float]]]:
    """
    Get cached content for a URL.
    
    Args:
        url: Tab URL
        
    Returns:
        Cached content dict with 'content', 'title', 'timestamp' or None
    """
    return _tab_content_cache.get(url)


def _cache_content(url: str, content: str, title: str) -> None:
    """
    Cache content for a URL.
    
    Args:
        url: Tab URL
        content: Content summary
        title: Tab title
    """
    _tab_content_cache[url] = {
        "content": content,
        "title": title,
        "timestamp": time.time()
    }


def _is_cache_valid(url: str, current_title: str) -> bool:
    """
    Check if cached content is still valid.
    
    Args:
        url: Tab URL
        current_title: Current tab title
        
    Returns:
        True if cache is valid, False otherwise
    """
    cached = _get_cached_content(url)
    if not cached:
        return False
    
    # Invalidate if title changed (tab navigated)
    if cached.get("title") != current_title:
        return False
    
    return True


def get_tab_content_summary(tab_index: Optional[int] = None, tab_url: Optional[str] = None) -> Optional[str]:
    """
    Get a content summary for a Chrome tab by executing JavaScript.
    
    Args:
        tab_index: Global tab index (1-based)
        tab_url: Tab URL to find (alternative to index)
        
    Returns:
        Content summary string, or None if failed
    """
    # JavaScript to extract summary: title, h1, h2s, first paragraph
    # Use string concatenation to avoid template literal issues
    js_code = """(function() {
        var title = document.title || '';
        var h1El = document.querySelector('h1');
        var h1 = h1El ? h1El.innerText : '';
        var h2s = Array.from(document.querySelectorAll('h2')).slice(0, 3)
            .map(function(h) { return h.innerText; }).join(' | ');
        var pEl = document.querySelector('p');
        var firstP = pEl ? pEl.innerText.substring(0, 200) : '';
        return 'Title: ' + title + '\\nMain: ' + h1 + '\\nSections: ' + h2s + '\\nSummary: ' + firstP;
    })()"""
    
    # Escape JavaScript for AppleScript
    escaped_js = escape_applescript_string(js_code)
    
    try:
        if tab_index:
            # Execute JavaScript in specific tab by index
            script = f'''
            tell application "Google Chrome"
                activate
                set globalTabIndex to 1
                repeat with w in windows
                    repeat with t in tabs of w
                        if globalTabIndex = {tab_index} then
                            try
                                set pageContent to execute javascript "{escaped_js}" in t
                                return pageContent
                            on error
                                return ""
                            end try
                        end if
                        set globalTabIndex to globalTabIndex + 1
                    end repeat
                end repeat
            end tell
            '''
        elif tab_url:
            # Find tab by URL and execute JavaScript
            escaped_url = escape_applescript_string(tab_url)
            script = f'''
            tell application "Google Chrome"
                activate
                repeat with w in windows
                    repeat with t in tabs of w
                        if URL of t contains "{escaped_url}" then
                            try
                                set pageContent to execute javascript "{escaped_js}" in t
                                return pageContent
                            on error
                                return ""
                            end try
                        end if
                    end repeat
                end repeat
            end tell
            '''
        else:
            # Execute in active tab
            script = f'''
            tell application "Google Chrome"
                activate
                set frontWindow to front window
                set activeTab to active tab of frontWindow
                try
                    set pageContent to execute javascript "{escaped_js}" in activeTab
                    return pageContent
                on error
                    return ""
                end try
            end tell
            '''
        
        success, stdout, stderr = _executor.execute(script)
        
        if success and stdout:
            # Limit to ~500 chars to balance detail vs token usage
            content = stdout.strip()
            if len(content) > 500:
                content = content[:500] + "..."
            return content
        else:
            return None
            
    except Exception as e:
        # Silently fail - some pages may block JavaScript execution
        return None


def list_chrome_tabs_with_content() -> tuple[List[Dict[str, Union[str, int, bool]]], Optional[str]]:
    """
    Get a list of all Chrome tabs with content summaries pre-loaded.
    
    Returns:
        Tuple of (list of tab dicts with 'content_summary' field added, raw AppleScript output)
    """
    # Get basic tab metadata and raw output
    tabs, raw_output = list_chrome_tabs()
    
    # Read content for each tab (with caching)
    for tab in tabs:
        url = tab.get("url", "")
        title = tab.get("title", "")
        
        # Don't skip tabs without URLs - they might be special pages
        # Just skip content reading for them
        if not url:
            tab["content_summary"] = ""
            continue
        
        # Check cache first
        if _is_cache_valid(url, title):
            cached = _get_cached_content(url)
            if cached:
                tab["content_summary"] = cached["content"]
                continue
        
        # Read content if not cached or invalid
        content = get_tab_content_summary(tab_index=tab["index"])
        if content:
            tab["content_summary"] = content
            # Cache it
            _cache_content(url, content, title)
        else:
            # Store empty string if content read failed
            tab["content_summary"] = ""
            # Still cache empty to avoid repeated failures
            _cache_content(url, "", title)
        
        # Small delay to avoid overwhelming Chrome
        time.sleep(0.1)
    
    return tabs, raw_output


def clear_tab_cache() -> None:
    """Clear the tab content cache."""
    global _tab_content_cache
    _tab_content_cache.clear()


def get_cache_stats() -> Dict[str, int]:
    """
    Get cache statistics.
    
    Returns:
        Dict with 'size' (number of cached entries) and 'hits' (not implemented yet)
    """
    return {
        "size": len(_tab_content_cache),
        "hits": 0  # Could implement hit tracking if needed
    }


def switch_to_chrome_tab(tab_title: Optional[str] = None, tab_index: Optional[int] = None) -> bool:
    """
    Switch to a specific Chrome tab by title or index.
    
    Args:
        tab_title: Title of the tab to switch to (fuzzy matching via contains)
        tab_index: Global index of the tab (1-based, across all windows, matching list_chrome_tabs)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if tab_index:
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
        elif tab_title:
            # Switch by title (fuzzy match, searches front window only for consistency)
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

