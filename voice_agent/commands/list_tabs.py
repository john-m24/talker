"""Command to list Chrome tabs."""

from typing import Dict, Any
from .base import Command


class ListTabsCommand(Command):
    """Command to list Chrome tabs."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "list_tabs"
    
    def produces_results(self) -> bool:
        """This command produces results to display."""
        return True
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the list tabs command."""
        # Force fresh data by invalidating cache before getting chrome_tabs
        from ..cache import get_cache_manager
        cache_manager = get_cache_manager()
        if cache_manager:
            cache_manager.invalidate("browsers.chrome", "tabs")
            cache_manager.invalidate("browsers.chrome", "tabs_raw")
        
        # Now get fresh chrome_tabs data
        from ..tab_control import list_chrome_tabs_with_content
        chrome_tabs, _ = list_chrome_tabs_with_content()
        
        # Format tabs for display
        items = []
        if chrome_tabs:
            for tab in chrome_tabs:
                domain = tab.get('domain', 'N/A')
                title = tab.get('title', 'N/A')
                url = tab.get('url', '')
                active = " (active)" if tab.get('is_active') else ""
                window = f" [W{tab.get('window_index', '?')}]" if tab.get('window_index') else ""
                
                # Format: "{index}. [{domain}]{active}{window}: {title}"
                tab_line = f"{tab['index']}. [{domain}]{active}{window}: {title}"
                if url:
                    tab_line += f" | {url}"
                items.append(tab_line)
        else:
            items = ["Chrome is not running or has no tabs"]
        
        # Send results to Electron client via API
        try:
            from ..api_server import send_results
            send_results("Open Chrome Tabs", items)
        except Exception as e:
            # Fall back to console if API fails
            pass
        
        # Also output to console as fallback
        print(f"\nOpen Chrome tabs:")
        if chrome_tabs:
            for tab in chrome_tabs:
                domain = tab.get('domain', 'N/A')
                title = tab.get('title', 'N/A')
                url = tab.get('url', '')
                content_summary = tab.get('content_summary', '')
                active = " (active)" if tab.get('is_active') else ""
                window = f" [W{tab.get('window_index', '?')}]" if tab.get('window_index') else ""
                
                # Format: "  {index}. [{domain}]{active}{window}: {title} | {url}"
                tab_line = f"  {tab['index']}. [{domain}]{active}{window}: {title}"
                if url:
                    tab_line += f" | {url}"
                print(tab_line)
                
                # Show content summary if available
                if content_summary:
                    # Truncate for display
                    content_display = content_summary[:200] + "..." if len(content_summary) > 200 else content_summary
                    print(f"      Content: {content_display}")
        else:
            print("  Chrome is not running or has no tabs")
        print()
        return True

