"""Command to close Chrome tabs."""

from typing import Dict, Any
from .base import Command
from ..tab_control import close_chrome_tab


class CloseTabCommand(Command):
    """Command to close Chrome tabs."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "close_tab"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the close tab command."""
        tab_title = intent.get("tab_title")
        tab_index = intent.get("tab_index")
        content_query = intent.get("content_query")
        chrome_tabs = intent.get("chrome_tabs", [])
        
        if tab_index:
            print(f"Closing Chrome tab #{tab_index}...")
            success = close_chrome_tab(tab_index=tab_index)
        elif tab_title or content_query:
            # Enhanced matching: search in titles and content summaries
            matching_tab = None
            
            if chrome_tabs:
                # Search for matching tab
                for tab in chrome_tabs:
                    # Match by title
                    if tab_title and tab_title.lower() in tab.get('title', '').lower():
                        matching_tab = tab
                        break
                    
                    # Match by content summary
                    if content_query:
                        content_summary = tab.get('content_summary', '').lower()
                        if content_query.lower() in content_summary:
                            matching_tab = tab
                            break
                    
                    # Also check if tab_title matches content
                    if tab_title:
                        content_summary = tab.get('content_summary', '').lower()
                        if tab_title.lower() in content_summary:
                            matching_tab = tab
                            break
            
            if matching_tab:
                print(f"Closing Chrome tab #{matching_tab['index']}: {matching_tab.get('title', 'N/A')}...")
                success = close_chrome_tab(tab_index=matching_tab['index'])
            else:
                # Fallback to original behavior
                if tab_title:
                    print(f"Closing Chrome tab matching '{tab_title}'...")
                    success = close_chrome_tab(tab_title=tab_title)
                else:
                    print("Error: No matching tab found")
                    success = False
        else:
            print("Error: No tab specified")
            success = False
        
        if success:
            print(f"✓ Successfully closed tab\n")
        else:
            print(f"✗ Failed to close tab\n")
        
        return success











