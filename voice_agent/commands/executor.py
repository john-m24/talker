"""Command executor to route intents to appropriate command classes."""

from typing import Dict, Any, List
from .base import Command
from .list_apps import ListAppsCommand
from .list_tabs import ListTabsCommand
from .focus_app import FocusAppCommand
from .place_app import PlaceAppCommand
from .switch_tab import SwitchTabCommand


class CommandExecutor:
    """Executes commands based on parsed intents."""
    
    def __init__(self):
        """Initialize the command executor with available commands."""
        self.commands: List[Command] = [
            ListAppsCommand(),
            ListTabsCommand(),
            FocusAppCommand(),
            PlaceAppCommand(),
            SwitchTabCommand(),
        ]
    
    def execute(self, intent: Dict[str, Any], running_apps: list = None, chrome_tabs: list = None) -> bool:
        """
        Execute a command based on the parsed intent.
        
        Args:
            intent: Parsed intent dictionary
            running_apps: List of running applications (for commands that need it)
            chrome_tabs: List of Chrome tabs (for commands that need it)
            
        Returns:
            True if execution succeeded, False otherwise
        """
        intent_type = intent.get("type", "list_apps")
        
        # Find the command that can handle this intent type
        for command in self.commands:
            if command.can_handle(intent_type):
                # Add context data to intent for commands that need it
                enhanced_intent = intent.copy()
                if running_apps is not None:
                    enhanced_intent["running_apps"] = running_apps
                if chrome_tabs is not None:
                    enhanced_intent["chrome_tabs"] = chrome_tabs
                
                return command.execute(enhanced_intent)
        
        # No command found for this intent type
        print(f"Unknown intent type: {intent_type}\n")
        return False

