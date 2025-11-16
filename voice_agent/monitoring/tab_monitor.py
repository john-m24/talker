"""Tab monitoring functions for browsers using AppleScript."""

import time
from typing import List, Optional, Dict, Union, Tuple
from urllib.parse import urlparse
from ..utils import AppleScriptExecutor, escape_applescript_string
from ..config import CACHE_TABS_TTL
from ..cache import get_cache_manager

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
            set tabData to ""
            set globalTabIndex to 1
            set windowIndex to 1
            repeat with w in windows
                set activeTabIndex to active tab index of w
                set localTabIndex to 1
                repeat with t in tabs of w
                    set isActive to (localTabIndex = activeTabIndex)
                    set tabTitle to title of t
                    set tabURL to URL of t
                    -- Use ||| as delimiter to avoid parsing issues with commas in titles/URLs
                    if tabData is not "" then
                        set tabData to tabData & linefeed
                    end if
                    set tabData to tabData & (globalTabIndex as text) & "|||" & tabTitle & "|||" & tabURL & "|||" & (windowIndex as text) & "|||" & (localTabIndex as text) & "|||" & (isActive as text)
                    set globalTabIndex to globalTabIndex + 1
                    set localTabIndex to localTabIndex + 1
                end repeat
                set windowIndex to windowIndex + 1
            end repeat
            return tabData
        end tell
        '''
        success, stdout, stderr = _executor.execute(script, check=True)
        
        if not success:
            print(f"Error listing Chrome tabs: {stderr}")
            return [], None
        
        raw_output = stdout if stdout else None
        
        # Parse the result
        # AppleScript now returns one tab per line with ||| delimiter:
        # Format: globalIndex|||title|||url|||windowIndex|||localIndex|||isActive
        tabs = []
        if stdout:
            lines = stdout.strip().split('\n')
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue
                
                # Split by ||| delimiter
                parts = line.split('|||')
                
                if len(parts) != 6:
                    continue
                
                try:
                    global_index = int(parts[0])
                    title = parts[1]
                    url = parts[2]
                    window_index = int(parts[3])
                    local_index = int(parts[4])
                    is_active = parts[5].lower() == "true"
                    
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
                    print(f"Warning: Failed to parse tab {line_num}: {e}")
                    continue
        
        return tabs, raw_output
    except Exception as e:
        print(f"Unexpected error listing Chrome tabs: {e}")
        return [], None


def get_active_chrome_tab() -> Optional[Dict[str, Union[str, int]]]:
    """
    Get the currently active Chrome tab info (more efficient than listing all tabs).
    
    Returns:
        Dict with index, title, url, domain, or None if Chrome not active or query fails
    """
    try:
        script = '''
        tell application "Google Chrome"
            try
                set activeWindow to front window
                set activeTab to active tab of activeWindow
                set tabIndex to 1
                set globalIndex to 1
                
                -- Count tabs in all windows before this one
                repeat with w in windows
                    if w is not activeWindow then
                        set globalIndex to globalIndex + (count of tabs of w)
                    else
                        -- Find local index in active window
                        repeat with t in tabs of w
                            if t is activeTab then
                                exit repeat
                            end if
                            set tabIndex to tabIndex + 1
                            set globalIndex to globalIndex + 1
                        end repeat
                        exit repeat
                    end if
                end repeat
                
                return {globalIndex, title of activeTab, URL of activeTab}
            on error
                return ""
            end try
        end tell
        '''
        success, stdout, _ = _executor.execute(script)
        if not success or not stdout:
            return None
        
        # Parse: {globalIndex, title, url}
        parts = stdout.replace("{", "").replace("}", "").split(", ")
        if len(parts) >= 3:
            try:
                global_index = int(parts[0].strip())
                title = parts[1].strip('"')
                url = parts[2].strip('"')
                domain = _extract_domain(url)
                
                return {
                    "index": global_index,
                    "title": title,
                    "url": url,
                    "domain": domain
                }
            except (ValueError, IndexError):
                return None
        return None
    except Exception:
        return None


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


def list_chrome_tabs_with_content() -> Tuple[List[Dict[str, Union[str, int, bool]]], Optional[str]]:
    """
    Get a list of all Chrome tabs with content summaries pre-loaded.
    Uses cache if enabled.
    
    Returns:
        Tuple of (list of tab dicts with 'content_summary' field added, raw AppleScript output)
    """
    # Check cache first
    cache_manager = get_cache_manager()
    if cache_manager:
        cached = cache_manager.get_tabs("tabs")
        cached_raw = cache_manager.get_tabs("tabs_raw")
        if cached is not None and cached_raw is not None:
            return cached, cached_raw
    
    # Cache miss - fetch from Chrome
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
    
    # Cache the result
    if cache_manager:
        cache_manager.set_tabs("tabs", tabs, ttl=CACHE_TABS_TTL)
        if raw_output:
            cache_manager.set_tabs("tabs_raw", raw_output, ttl=CACHE_TABS_TTL)
    
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

