"""Command executor to route intents to appropriate command classes."""

from typing import Any, Dict, List
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
    
    def execute(self, intent: Any, running_apps: list = None, chrome_tabs: list = None) -> bool:
        """
        Execute command(s) based on the parsed intent(s).
        
        Args:
            intent: Can be:
                - A single intent dictionary (backward compatible)
                - A list of intent dictionaries
                - A dictionary with 'commands' array (from AI agent)
            running_apps: List of running applications (for commands that need it)
            chrome_tabs: List of Chrome tabs (for commands that need it)
            
        Returns:
            True if all executions succeeded, False if any failed
        """
        # Normalize input to a list of intents
        commands_list = self._normalize_to_commands_list(intent)
        
        if not commands_list:
            print("Error: No commands to execute\n")
            return False
        
        # Execute each command sequentially
        all_succeeded = True
        for i, cmd_intent in enumerate(commands_list, 1):
            if len(commands_list) > 1:
                print(f"Executing command {i} of {len(commands_list)}...")
            
            intent_type = cmd_intent.get("type", "list_apps")
            
            # Find the command that can handle this intent type
            command_found = False
            for command in self.commands:
                if command.can_handle(intent_type):
                    # Add context data to intent for commands that need it
                    enhanced_intent = cmd_intent.copy()
                    if running_apps is not None:
                        enhanced_intent["running_apps"] = running_apps
                    if chrome_tabs is not None:
                        enhanced_intent["chrome_tabs"] = chrome_tabs
                    
                    success = command.execute(enhanced_intent)
                    if not success:
                        all_succeeded = False
                    command_found = True
                    break
            
            if not command_found:
                print(f"Unknown intent type: {intent_type}\n")
                all_succeeded = False
        
        return all_succeeded
    
    def _normalize_to_commands_list(self, intent: Any) -> List[Dict[str, Any]]:
        """
        Normalize various intent formats to a list of command intents.
        
        Args:
            intent: Can be a dict with 'commands' array, a list of intents, or a single intent dict
            
        Returns:
            List of intent dictionaries
        """
        if isinstance(intent, list):
            # Already a list of intents
            return intent
        elif isinstance(intent, dict):
            if "commands" in intent:
                # New format with commands array
                commands = intent.get("commands", [])
                if isinstance(commands, list):
                    return commands
                else:
                    # Single command in commands field (shouldn't happen, but handle it)
                    return [commands] if commands else []
            elif "type" in intent:
                # Single intent dict (backward compatible)
                return [intent]
            else:
                # Invalid structure
                return []
        else:
            # Invalid type
            return []

