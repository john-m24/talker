"""Command executor to route intents to appropriate command classes."""

from typing import Any, Dict, List
from .base import Command
from .list_apps import ListAppsCommand
from .list_tabs import ListTabsCommand
from .list_recent_files import ListRecentFilesCommand
from .list_projects import ListProjectsCommand
from .focus_app import FocusAppCommand
from .place_app import PlaceAppCommand
from .switch_tab import SwitchTabCommand
from .open_url import OpenUrlCommand
from .close_app import CloseAppCommand
from .close_tab import CloseTabCommand
from .activate_preset import ActivatePresetCommand
from .query import QueryCommand


class CommandExecutor:
    """Executes commands based on parsed intents."""
    
    def __init__(self):
        """Initialize the command executor with available commands."""
        self.commands: List[Command] = [
            ListAppsCommand(),
            ListTabsCommand(),
            ListRecentFilesCommand(),
            ListProjectsCommand(),
            FocusAppCommand(),
            PlaceAppCommand(),
            SwitchTabCommand(),
            OpenUrlCommand(),
            CloseAppCommand(),
            CloseTabCommand(),
            ActivatePresetCommand(),
            QueryCommand(),
        ]
    
    def execute(self, intent: Any, running_apps: list = None, chrome_tabs: list = None, recent_files: list = None, active_projects: list = None, current_project: dict = None) -> bool:
        """
        Execute command(s) based on the parsed intent(s).
        
        Args:
            intent: Can be:
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
                    if recent_files is not None:
                        enhanced_intent["recent_files"] = recent_files
                    if active_projects is not None:
                        enhanced_intent["active_projects"] = active_projects
                    if current_project is not None:
                        enhanced_intent["current_project"] = current_project
                    
                    success = command.execute(enhanced_intent)
                    if not success:
                        all_succeeded = False
                    
                    # If command doesn't produce results, signal "done" immediately
                    if not command.produces_results():
                        try:
                            from ..api_server import send_results
                            send_results("", [])  # Empty result signals "done, close client"
                        except Exception:
                            pass
                    
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
                # Format with commands array
                commands = intent.get("commands", [])
                if isinstance(commands, list):
                    return commands
                else:
                    # Single command in commands field (shouldn't happen, but handle it)
                    return [commands] if commands else []
            else:
                # Invalid structure - must have commands array
                return []
        else:
            # Invalid type
            return []

