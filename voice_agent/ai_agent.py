"""AI agent for parsing voice commands into structured intents."""

import json
import openai
from typing import Dict, List, Optional, Union
from .config import LLM_ENDPOINT, LLM_MODEL


class AIAgent:
    """AI agent that uses OpenAI-compatible API to parse user commands."""
    
    def __init__(self, endpoint: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the AI agent.
        
        Args:
            endpoint: LLM endpoint URL (defaults to config value)
            model: Model name (defaults to config value)
        """
        self.endpoint = endpoint or LLM_ENDPOINT
        self.model = model or LLM_MODEL
        
        # Initialize OpenAI client with custom endpoint
        self.client = openai.OpenAI(
            base_url=self.endpoint,
            api_key="not-needed"  # Local endpoints don't require real API keys
        )
    
    def parse_intent(
        self, 
        text: str, 
        running_apps: List[str], 
        installed_apps: Optional[List[str]] = None,
        chrome_tabs: Optional[List[Dict[str, Union[str, int]]]] = None,
        available_presets: Optional[List[str]] = None
    ) -> Dict[str, Union[List[Dict], bool, Optional[str]]]:
        """
        Parse user command text into structured intents (supports single or multiple commands).
        
        Args:
            text: User's command text
            running_apps: List of currently running applications
            installed_apps: Optional list of installed applications
            chrome_tabs: Optional list of Chrome tabs with 'index' and 'title' keys
            available_presets: Optional list of available preset names
            
        Returns:
            Dictionary with 'commands' array (list of intent dicts), 'needs_clarification', and 'clarification_reason'
            Each intent in 'commands' has 'type' and optionally 'app_name', 'monitor', 'maximize', 'tab_title', 'tab_index', 'preset_name'
            Example (single command): {"commands": [{"type": "focus_app", "app_name": "Docker Desktop"}], "needs_clarification": false, "clarification_reason": null}
            Example (multiple commands): {"commands": [{"type": "place_app", "app_name": "Google Chrome", "monitor": "left"}, {"type": "place_app", "app_name": "Cursor", "monitor": "right"}], "needs_clarification": false, "clarification_reason": null}
            Example (preset): {"commands": [{"type": "activate_preset", "preset_name": "code space"}], "needs_clarification": false, "clarification_reason": null}
        """
        # Build context for the AI
        context_parts = [
            "You are a macOS window control assistant. Parse the user's command and return a JSON response.",
            "",
            "Available commands:",
            "- 'list_apps' or 'list applications' - list running applications",
            "- 'focus_app' - bring an application to the front (will launch the app if it's not running)",
            "- 'place_app' - move an application window to a specific monitor (main, right, or left) (will launch the app if it's not running)",
            "- 'switch_tab' - switch to a specific Chrome tab",
            "- 'list_tabs' - list all open Chrome tabs",
            "- 'close_app' - quit/close an application completely",
            "- 'close_tab' - close a specific Chrome tab",
            "- 'activate_preset' - activate a named preset window layout",
            "",
            f"Currently running applications: {', '.join(running_apps) if running_apps else 'None'}",
        ]
        
        # Add available presets context if presets are configured
        if available_presets:
            context_parts.append(
                f"Available presets: {', '.join(available_presets)}"
            )
        
        # Add Chrome tabs context if available
        if chrome_tabs:
            tabs_info = []
            for tab in chrome_tabs[:20]:  # Limit to 20 tabs to avoid token limits
                tabs_info.append(f"Tab {tab['index']}: {tab['title']}")
            if tabs_info:
                context_parts.append(
                    f"Open Chrome tabs: {'; '.join(tabs_info)}"
                )
        
        if installed_apps:
            # Limit to first 50 apps to avoid token limits
            apps_preview = installed_apps[:50]
            context_parts.append(
                f"Some installed applications (for reference): {', '.join(apps_preview)}"
            )
        
        context_parts.extend([
            "",
            "User command:",
            text,
            "",
            "IMPORTANT: The user may give multiple commands in a single utterance.",
            "Look for conjunctions like 'and', 'then', 'also' that indicate multiple commands.",
            "Examples of multiple commands:",
            "- 'Open google on the left and cursor on the right' -> two place_app commands",
            "- 'Focus chrome and list tabs' -> focus_app and list_tabs commands",
            "- 'Put X on left and Y on right' -> two place_app commands",
            "",
            "Return a JSON object with:",
            "- 'commands': an array of intent objects (even if there's only one command)",
            "- 'needs_clarification': (boolean) true if any command is ambiguous, missing information, or unclear; false otherwise",
            "- 'clarification_reason': (string, optional) brief explanation of why clarification is needed, or null if not needed",
            "",
            "Each intent object in the 'commands' array should have:",
            "- 'type': either 'list_apps', 'focus_app', 'place_app', 'switch_tab', 'list_tabs', 'close_app', 'close_tab', or 'activate_preset'",
            "- 'app_name': (for focus_app, place_app, and close_app) the exact application name - prefer matching from running apps, but if not found, use the closest match from installed apps (focus_app and place_app will launch the app if it's not running)",
            "- 'monitor': (for place_app) one of 'main', 'right', or 'left' - parse from phrases like 'main monitor', 'right monitor', 'left monitor', 'main screen', 'right screen', 'left screen', 'main display', etc.",
            "- 'maximize': (for place_app, optional boolean) true if user wants to maximize the window, false otherwise",
            "- 'tab_title': (for switch_tab and close_tab) match keywords from the user's command to the Chrome tab titles",
            "- 'tab_index': (for switch_tab and close_tab, optional) the tab number if user specifies a number",
            "- 'preset_name': (for activate_preset) the exact preset name from the available presets list (case-insensitive matching is supported)",
            "",
            "Monitor placement patterns to recognize:",
            "- 'put X on [right/left/main] monitor' -> type: 'place_app', monitor: 'right'/'left'/'main'",
            "- 'move X to [main/right/left] screen/display' -> type: 'place_app', monitor: 'main'/'right'/'left'",
            "- 'place X on [monitor] and maximize' -> type: 'place_app', monitor: [monitor], maximize: true",
            "- 'show X on [monitor]' -> type: 'place_app', monitor: [monitor]",
            "- 'open X on [monitor]' -> type: 'place_app', monitor: [monitor]",
            "",
            "If the user wants to focus an app, match their fuzzy input to the exact app name from the running apps list.",
            "If no matching app is found in running apps, use the closest match from installed apps.",
            "IMPORTANT: focus_app and place_app commands can open apps even if they're not currently running - the system will launch them automatically.",
            "When the user says 'open [App]' or 'launch [App]', use type 'focus_app' - it will launch the app if needed.",
            "If the user wants to place an app on a monitor, use type 'place_app' and extract the monitor name.",
            "If the user wants to switch tabs, match keywords from their command to the Chrome tab titles.",
            "For example: 'Gmail' matches 'Gmail - Inbox', 'YouTube' matches 'YouTube - Watch', etc.",
            "If the user asks to list tabs or see what tabs are open, return type 'list_tabs'.",
            "If the user wants to close/quit an app, use type 'close_app' and extract the app name.",
            "Patterns for close_app: 'close [App]', 'quit [App]', 'exit [App]' -> type: 'close_app'.",
            "If the user wants to close a tab, use type 'close_tab' and extract tab_title or tab_index.",
            "Patterns for close_tab: 'close tab [Number]', 'close [Tab Name]' -> type: 'close_tab'.",
            "If the user wants to activate a preset, use type 'activate_preset' and extract the preset name.",
            "Preset activation patterns to recognize:",
            "- 'activate [preset name]' -> type: 'activate_preset', preset_name: '[preset name]'",
            "- '[preset name]' (standalone, if it matches an available preset) -> type: 'activate_preset', preset_name: '[preset name]'",
            "- 'set up [preset name]' -> type: 'activate_preset', preset_name: '[preset name]'",
            "- 'load [preset name]' -> type: 'activate_preset', preset_name: '[preset name]'",
            "- 'switch to [preset name]' -> type: 'activate_preset', preset_name: '[preset name]'",
            "Match the user's input to the available presets list (case-insensitive, partial matching supported).",
            "If multiple presets match or preset name is ambiguous, set needs_clarification to true.",
            "If preset name is not found in available presets, set needs_clarification to true.",
            "If the command is unclear, default to 'list_apps'.",
            "",
            "When parsing multiple commands:",
            "- Split on conjunctions: 'and', 'then', 'also', 'plus'",
            "- Each command should be parsed independently",
            "- Maintain the order of commands as spoken",
            "- If one command is unclear, still parse the others if possible",
            "",
            "Clarification assessment:",
            "Set 'needs_clarification' to true if:",
            "- Any command is ambiguous (multiple possible interpretations)",
            "- Required information is missing for any command (e.g., app name not found in running apps, monitor not specified for place_app)",
            "- Any command doesn't make sense in context",
            "- The intent is unclear or vague for any command",
            "Examples: 'bring it to view' when multiple apps are running, 'focus' without app name, 'do the thing', etc.",
            "If all commands are clear and all required information is present, set 'needs_clarification' to false.",
            "When clarification is needed, still return your best guess for the intents, but flag it for clarification.",
        ])
        
        prompt = "\n".join(context_parts)
        
        # Debug: Print the prompt being sent to the LLM
        print("\n" + "=" * 80)
        print("DEBUG: Prompt sent to LLM:")
        print("=" * 80)
        print(prompt)
        print("=" * 80 + "\n")
        
        try:
            # Try with response_format first (for models that support JSON mode)
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that parses commands into structured JSON. Always return valid JSON only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.1,  # Low temperature for consistent parsing
                    response_format={"type": "json_object"}  # Request JSON response
                )
            except Exception as format_error:
                # Fallback if response_format is not supported
                print(f"Note: JSON mode not supported, using fallback: {format_error}")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that parses commands into structured JSON. Always return valid JSON only, wrapped in a code block or as plain JSON."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.1
                )
            
            # Extract JSON from response
            content = response.choices[0].message.content.strip()
            
            # Debug: Print the raw response from the LLM
            print("DEBUG: Raw LLM response:")
            print(content)
            print()
            
            # Try to extract JSON from code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            try:
                result = json.loads(content)
                
                # Debug: Print the parsed result
                print("DEBUG: Parsed intent:")
                print(json.dumps(result, indent=2))
                print()
                
                # Normalize to new structure with 'commands' array
                # Handle backward compatibility: if old format (has 'type' at top level), convert to new format
                if "commands" in result:
                    # New format with commands array
                    commands = result.get("commands", [])
                    if not isinstance(commands, list):
                        commands = [commands] if commands else []
                elif "type" in result:
                    # Old format - single command, convert to new format
                    commands = [result]
                    result = {"commands": commands}
                else:
                    # Invalid structure, default to list_apps
                    commands = [{"type": "list_apps"}]
                    result = {"commands": commands}
                
                # Ensure needs_clarification and clarification_reason fields exist
                if "needs_clarification" not in result:
                    result["needs_clarification"] = False
                if "clarification_reason" not in result:
                    result["clarification_reason"] = None
                
                # Ensure each command has required fields
                for cmd in commands:
                    if "type" not in cmd:
                        cmd["type"] = "list_apps"
                
                result["commands"] = commands
                
                return result
            except json.JSONDecodeError as e:
                print(f"Error parsing AI response as JSON: {e}")
                print(f"Response was: {content}")
                return {"commands": [{"type": "list_apps"}], "needs_clarification": False, "clarification_reason": None}
                
        except Exception as e:
            print(f"Error calling AI agent: {e}")
            import traceback
            traceback.print_exc()
            return {"commands": [{"type": "list_apps"}], "needs_clarification": False, "clarification_reason": None}

