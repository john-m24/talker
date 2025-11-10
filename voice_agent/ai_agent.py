"""AI agent for parsing voice commands into structured intents."""

import json
import hashlib
import openai
from typing import Dict, List, Optional, Union
from .config import LLM_ENDPOINT, LLM_MODEL, LLM_CACHE_ENABLED
from .hardcoded_commands import get_hardcoded_command
from .pattern_matcher import PatternMatcher


class AIAgent:
    """AI agent that uses OpenAI-compatible API to parse user commands."""
    
    def __init__(self, endpoint: Optional[str] = None, model: Optional[str] = None, cache_manager=None):
        """
        Initialize the AI agent.
        
        Args:
            endpoint: LLM endpoint URL (defaults to config value)
            model: Model name (defaults to config value)
            cache_manager: CacheManager instance for LLM response caching (optional)
        """
        self.endpoint = endpoint or LLM_ENDPOINT
        self.model = model or LLM_MODEL
        self.cache_manager = cache_manager
        self.pattern_matcher = PatternMatcher()
        
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
        chrome_tabs_raw: Optional[str] = None,
        available_presets: Optional[List[str]] = None
    ) -> Dict[str, Union[List[Dict], bool, Optional[str]]]:
        """
        Parse user command text into structured intents (supports single or multiple commands).
        
        Args:
            text: User's command text
            running_apps: List of currently running applications
            installed_apps: Optional list of installed applications
            chrome_tabs: Optional list of Chrome tabs with 'index', 'title', 'url', 'domain', 'content_summary' keys
            available_presets: Optional list of available preset names
            
        Returns:
            Dictionary with 'commands' array (list of intent dicts), 'needs_clarification', and 'clarification_reason'
            Each intent in 'commands' has 'type' and optionally 'app_name', 'monitor', 'maximize', 'tab_index', 'tab_indices', 'preset_name'
            Example (single command): {"commands": [{"type": "focus_app", "app_name": "Docker Desktop"}], "needs_clarification": false, "clarification_reason": null}
            Example (multiple commands): {"commands": [{"type": "place_app", "app_name": "Google Chrome", "monitor": "left"}, {"type": "place_app", "app_name": "Cursor", "monitor": "right"}], "needs_clarification": false, "clarification_reason": null}
            Example (preset): {"commands": [{"type": "activate_preset", "preset_name": "code space"}], "needs_clarification": false, "clarification_reason": null}
        """
        # Normalize input text
        normalized_text = text.lower().strip()
        
        # Tier 1: Check hardcoded commands first (instant, 0ms)
        hardcoded_result = get_hardcoded_command(normalized_text)
        if hardcoded_result is not None:
            return hardcoded_result
        
        # Tier 2: Try pattern matching (fast, ~10-50ms, no LLM)
        pattern_result = self.pattern_matcher.match_pattern(
            normalized_text,
            running_apps,
            installed_apps or [],
            available_presets
        )
        if pattern_result is not None:
            return pattern_result
        
        # Tier 3: Fall back to LLM with text-only cache (slow, ~500-2000ms, only when needed)
        # Generate text-only cache key (normalized text hash)
        cache_key = None
        if LLM_CACHE_ENABLED and self.cache_manager:
            cache_key = f"llm_response:{hashlib.md5(normalized_text.encode()).hexdigest()}"
            
            # Check text-only cache first
            cached_result = self.cache_manager.get(cache_key)
            if cached_result is not None:
                # Validate context after cache hit
                validated_result = self._validate_context(
                    cached_result,
                    running_apps,
                    installed_apps or [],
                    available_presets
                )
                return validated_result
        
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
        # First, include raw AppleScript output for AI to parse
        if chrome_tabs_raw:
            context_parts.append(
                f"Raw Chrome tabs data from AppleScript (parse this to find ALL tabs):\n{chrome_tabs_raw}"
            )
            context_parts.append(
                "IMPORTANT: Parse the raw data above to find ALL tabs. The format is: "
                "globalIndex, \"title\", \"url\", windowIndex, localIndex, isActive, "
                "nextGlobalIndex, \"nextTitle\", \"nextUrl\", windowIndex, localIndex, isActive, ..."
            )
            context_parts.append(
                "Each tab entry consists of 6 values: globalIndex (1-based across all windows), "
                "title (quoted string), url (quoted string), windowIndex (1-based), "
                "localIndex (1-based within window), isActive (true/false)."
            )
        
        # Also include parsed tabs for reference (may be incomplete due to parsing issues)
        if chrome_tabs:
            tabs_info = []
            for tab in chrome_tabs:  # Include all tabs since we're using summaries
                domain = tab.get('domain', 'N/A')
                title = tab.get('title', 'N/A')
                url = tab.get('url', '')
                content_summary = tab.get('content_summary', '')
                active = " (ACTIVE)" if tab.get('is_active') else ""
                window = f" [Window {tab.get('window_index', '?')}]" if tab.get('window_index') else ""
                
                # Format for AI analysis: clear structure with all information
                tab_str = f"Tab {tab['index']} [{domain}]{active}{window}"
                tab_str += f"\n  Title: {title}"
                if url:
                    tab_str += f"\n  URL: {url}"
                if content_summary:
                    # Include full content summary for AI analysis
                    content_display = content_summary[:500] + "..." if len(content_summary) > 500 else content_summary
                    tab_str += f"\n  Content: {content_display}"
                tabs_info.append(tab_str)
            
            if tabs_info:
                context_parts.append(
                    f"Parsed Chrome tabs ({len(chrome_tabs)} found - may be incomplete, use raw data above for complete list):\n" + "\n\n".join(tabs_info)
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
            normalized_text,
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
            "- 'app_name': (for focus_app, place_app, and close_app, string, required) the exact application name - prefer matching from running apps, but if not found, use the closest match from installed apps (focus_app and place_app will launch the app if it's not running) (non-empty string)",
            "- 'monitor': (for place_app, enum, required) one of 'main', 'right', or 'left' - parse from phrases like 'main monitor', 'right monitor', 'left monitor', 'main screen', 'right screen', 'left screen', 'main display', etc.",
            "- 'maximize': (for place_app, boolean, optional) true if user wants to maximize the window, false otherwise (default: false)",
            "- 'tab_index': (for switch_tab, integer, required) the tab number - YOU MUST analyze all tabs and return the specific tab_index of the best matching tab (positive integer, 1-based)",
            "- 'tab_indices': (for close_tab, array<integer>, required) array of tab indices - for single tab use [3], for multiple tabs use [2, 5, 8] (array of positive integers, non-empty, 1-based)",
            "- 'preset_name': (for activate_preset, string, required) the exact preset name from the available presets list (case-insensitive matching is supported) (non-empty string)",
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
            "If the user wants to switch tabs, you MUST analyze ALL open tabs and select the best match.",
            "CRITICAL: You have access to RAW Chrome tabs data from AppleScript. Parse this raw data to find ALL tabs.",
            "The raw data format is: globalIndex, \"title\", \"url\", windowIndex, localIndex, isActive, nextGlobalIndex, \"nextTitle\", ...",
            "Each tab entry has 6 values separated by commas. Parse ALL entries in the raw data.",
            "",
            "You also have parsed tab information (may be incomplete), but ALWAYS use the raw data as the source of truth.",
            "IMPORTANT: Tab information includes:",
            "- Tab index (globalIndex - use this in 'tab_index' field)",
            "- Domain (extracted from URL, e.g., 'reddit.com', 'github.com')",
            "- URL (full URL of the tab)",
            "- Title (tab title)",
            "- Content summary (page content summary - may be available for parsed tabs)",
            "- Active status (which tab is currently active)",
            "",
            "Analyze the user's request and match it against ALL available tab information from the raw data:",
            "- If user mentions a website name (e.g., 'reddit', 'github', 'youtube'), match against domains and URLs",
            "- If user mentions content topics (e.g., 'tab with reddit and local AI', 'tab about Python'), match against content summaries",
            "- If user mentions a tab title, match against titles",
            "- Consider ALL fields (domain, URL, title, content) when making your decision",
            "",
            "Examples:",
            "- 'switch to reddit' -> Analyze all tabs, find the one with 'reddit.com' in domain/URL, return tab_index",
            "- 'go to the tab with reddit and local AI' -> Analyze all tabs, find the one with 'reddit' and 'local AI' in content summary, return tab_index",
            "- 'open github' -> Analyze all tabs, find the one with 'github.com' in domain/URL, return tab_index",
            "- 'switch to tab about Python' -> Analyze all tabs, find the one with 'Python' in content summary or title, return tab_index",
            "",
            "CRITICAL: You MUST return 'tab_index' (integer) for switch_tab or 'tab_indices' (array<integer>) for close_tab when you find matching tab(s).",
            "Do NOT return 'tab_title' or 'content_query' - return the specific 'tab_index' or 'tab_indices' of the matching tab(s).",
            "For close_tab: Always use 'tab_indices' array, even for single tab (e.g., tab_indices: [3] instead of tab_index: 3).",
            "If no matching tab is found, set 'needs_clarification' to true.",
            "If the user asks to list tabs or see what tabs are open, return type 'list_tabs'.",
            "If the user wants to close/quit an app, use type 'close_app' and extract the app name.",
            "Patterns for close_app: 'close [App]', 'quit [App]', 'exit [App]' -> type: 'close_app'.",
            "If the user wants to close a tab, use type 'close_tab' and extract tab_indices array.",
            "For single tab: 'close tab 3' -> type: 'close_tab', tab_indices: [3]",
            "For multiple tabs: 'close tabs 1, 3, and 5' -> type: 'close_tab', tab_indices: [1, 3, 5]",
            "For bulk operations: 'close all reddit tabs' -> analyze all tabs, find all matching tabs, return tab_indices: [2, 5, 8]",
            "Patterns for close_tab: 'close tab [Number]', 'close tabs [Numbers]', 'close all [domain] tabs' -> type: 'close_tab', tab_indices: [array]",
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
            
            # Try to extract JSON from code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            try:
                result = json.loads(content)
                
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
                
                # Cache the result with text-only key (if caching is enabled)
                if cache_key and self.cache_manager:
                    # Cache with no TTL (text-only key means context changes don't invalidate)
                    self.cache_manager.set(cache_key, result, ttl=0)
                
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
    
    def _validate_context(
        self,
        cached_result: Dict[str, Union[List[Dict], bool, Optional[str]]],
        running_apps: List[str],
        installed_apps: List[str],
        available_presets: Optional[List[str]] = None
    ) -> Dict[str, Union[List[Dict], bool, Optional[str]]]:
        """
        Validate and update app names from current context after cache hit.
        
        Args:
            cached_result: Cached intent result
            running_apps: List of currently running apps
            installed_apps: List of installed apps
            available_presets: Optional list of available presets
            
        Returns:
            Validated intent result with updated app names if needed
        """
        from .fuzzy_matcher import match_app_name, match_preset_name
        
        # Make a copy to avoid modifying the cached result
        result = json.loads(json.dumps(cached_result))
        commands = result.get("commands", [])
        
        # Validate each command
        for cmd in commands:
            cmd_type = cmd.get("type")
            
            # Validate app_name for app commands
            if cmd_type in ["focus_app", "place_app", "close_app"]:
                app_name = cmd.get("app_name")
                if app_name:
                    # Check if app name exists in current context
                    if app_name not in running_apps and app_name not in installed_apps:
                        # Try fuzzy matching to find current app name
                        matched_app = match_app_name(app_name, running_apps, installed_apps)
                        if matched_app:
                            cmd["app_name"] = matched_app
                        else:
                            # App not found, but keep original (might be valid)
                            pass
            
            # Validate preset_name for preset commands
            if cmd_type == "activate_preset" and available_presets:
                preset_name = cmd.get("preset_name")
                if preset_name:
                    # Check if preset name exists in current context
                    if preset_name not in available_presets:
                        # Try fuzzy matching to find current preset name
                        matched_preset = match_preset_name(preset_name, available_presets)
                        if matched_preset:
                            cmd["preset_name"] = matched_preset
                        else:
                            # Preset not found, mark as needing clarification
                            result["needs_clarification"] = True
                            result["clarification_reason"] = f"Preset '{preset_name}' not found in available presets"
        
        return result

