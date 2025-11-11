"""Command to open URLs in Chrome."""

from typing import Dict, Any
from .base import Command
from ..tab_control import open_url_in_chrome


class OpenUrlCommand(Command):
    """Command to open URLs in Chrome by creating new tabs."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "open_url"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the open URL command - creates a new tab."""
        url = intent.get("url")
        
        # Validate url is provided
        if not url:
            print("Error: No URL specified")
            return False
        
        if not isinstance(url, str) or not url.strip():
            print(f"Error: Invalid URL: {url}")
            return False
        
        # Open URL in new tab
        print(f"Opening '{url}' in Chrome...")
        success = open_url_in_chrome(url=url)
        
        if success:
            print(f"✓ Successfully opened URL\n")
        else:
            print(f"✗ Failed to open URL\n")
        
        return success

