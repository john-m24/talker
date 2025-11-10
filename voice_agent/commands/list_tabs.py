"""Command to list Chrome tabs."""

from typing import Dict, Any
from .base import Command


class ListTabsCommand(Command):
    """Command to list Chrome tabs."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "list_tabs"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the list tabs command."""
        chrome_tabs = intent.get("chrome_tabs")
        
        # Always use web dialog - create one if it doesn't exist
        try:
            from ..web.dialog import get_active_dialog, WebTextInputDialog
            from ..cache import get_cache_manager
            from ..autocomplete import AutocompleteEngine
            from ..config import AUTOCOMPLETE_MAX_SUGGESTIONS
            
            active_dialog = get_active_dialog()
            if not active_dialog:
                # Create a new dialog if none exists
                cache_manager = get_cache_manager()
                autocomplete_engine = AutocompleteEngine(max_suggestions=AUTOCOMPLETE_MAX_SUGGESTIONS)
                active_dialog = WebTextInputDialog(autocomplete_engine, cache_manager)
                # Open the dialog
                active_dialog.show()
            
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
                        url_display = url[:60] + "..." if len(url) > 60 else url
                        tab_line += f" | {url_display}"
                    items.append(tab_line)
            else:
                items = ["Chrome is not running or has no tabs"]
            
            # Send results to dialog
            active_dialog.send_results("Open Chrome Tabs", items)
            return True
        except Exception as e:
            # If web dialog fails, fall back to console (shouldn't happen)
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
                        url_display = url[:60] + "..." if len(url) > 60 else url
                        tab_line += f" | {url_display}"
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

