"""AI agent for parsing voice commands into structured intents."""

import json
import hashlib
import openai
from typing import Dict, List, Optional, Union
from .config import LLM_ENDPOINT, LLM_MODEL, LLM_CACHE_ENABLED
from .hardcoded_commands import get_hardcoded_command
from .pattern_matcher import PatternMatcher
from .cache import CacheKeys, get_cache_manager


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
        # Fall back to global cache manager if not provided (for testing/mocking support)
        self.cache_manager = cache_manager if cache_manager is not None else get_cache_manager()
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
        available_presets: Optional[List[str]] = None,
        recent_files: Optional[List[Dict]] = None,
        active_projects: Optional[List[Dict]] = None,
        current_project: Optional[Dict] = None
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
        
        # Tier 1: Check hardcoded commands (instant, 0ms)
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
        
        # Simple question detection (handle as 'query' without LLM when clear)
        question_starts = ("what", "which", "when", "where", "why", "who", "how")
        if normalized_text.endswith("?") or normalized_text.startswith(question_starts):
            return {
                "commands": [{"type": "query", "question": text.strip()}],
                "needs_clarification": False,
                "clarification_reason": None,
            }
        
        # Tier 3: Fall back to LLM with text-only cache (slow, ~500-2000ms, only when needed)
        # Generate text-only cache key (normalized text hash)
        cache_key = None
        if LLM_CACHE_ENABLED and self.cache_manager:
            text_hash = hashlib.md5(normalized_text.encode()).hexdigest()
            cache_key = CacheKeys.llm_response(text_hash)
            
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
            "- 'focus_app' - bring an application to the front (will launch the app if it's not running). Can optionally open a file, folder, or project: use 'file_path'/'file_name' (for files) or 'project_name'/'project_path' (for projects/folders).",
            "- 'place_app' - move an application window to a specific monitor or position. Can specify exact bounds [left, top, right, bottom] calculated from monitor dimensions, or use monitor for simple placement. Can optionally open a file, folder, or project: use 'file_path'/'file_name' (for files) or 'project_name'/'project_path' (for projects/folders).",
            "- 'switch_tab' - switch to a specific Chrome tab (for existing tabs)",
            "- 'open_url' - open a URL in Chrome by creating a new tab (for new tabs)",
            "- 'list_tabs' - list all open Chrome tabs",
            "- 'close_app' - quit/close an application completely",
            "- 'close_tab' - close a specific Chrome tab",
            "- 'activate_preset' - activate a named preset window layout",
            "- 'list_recent_files' - list recently opened files",
            "- 'list_projects' - list active projects",
            "- 'query' - answer general questions about tabs, apps, files, projects, and system state",
            "",
            f"Currently running applications: {', '.join(running_apps) if running_apps else 'None'}",
        ]
        
        # Include recent query responses if available (for follow-ups)
        try:
            if self.cache_manager and hasattr(self.cache_manager, "get_recent_queries"):
                recent_q = self.cache_manager.get_recent_queries(max_count=5)  # type: ignore[attr-defined]
                if recent_q:
                    qa_lines = []
                    for qa in recent_q:
                        q = str(qa.get("question", "")).strip()
                        a = str(qa.get("answer", "")).strip()
                        if q and a:
                            qa_lines.append(f"Q: {q}\nA: {a}")
                    if qa_lines:
                        context_parts.append("Recent query responses (for context, most recent first):\n" + "\n\n".join(qa_lines))
        except Exception:
            pass
        
        # Add file context if available
        if recent_files:
            # Prioritize code files in context
            code_files = [f for f in recent_files if f.get('type') == 'code']
            other_files = [f for f in recent_files if f.get('type') != 'code']
            top_files = (code_files[:10] + other_files[:5])[:10]
            
            if top_files:
                file_info = []
                for f in top_files:
                    file_name = f.get('name', '')
                    file_type = f.get('type', 'other')
                    app = f.get('app', '')
                    if app:
                        file_info.append(f"{file_name} ({file_type}, default app: {app})")
                    else:
                        file_info.append(f"{file_name} ({file_type})")
                
                context_parts.append(
                    f"Recently opened files (top 10, prioritizing code files): {', '.join(file_info)}"
                )
        
        if current_project:
            project_name = current_project.get('name', 'Unknown')
            project_path = current_project.get('path', '')
            context_parts.append(
                f"Current project: {project_name} ({project_path})"
            )
        
        if active_projects:
            # Include all active projects, not just top 5
            project_info = []
            for p in active_projects:
                name = p.get('name', '')
                path = p.get('path', '')
                if path:
                    project_info.append(f"{name} ({path})")
                else:
                    project_info.append(name)
            context_parts.append(
                f"All active projects ({len(active_projects)} total): {', '.join(project_info)}"
            )
        
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
            # Include all installed apps - no limit
            context_parts.append(
                f"All installed applications: {', '.join(installed_apps)}"
            )
        
        # Add monitor context for window placement
        from .config import MONITORS
        if MONITORS:
            monitor_info = []
            for monitor_name, monitor_config in MONITORS.items():
                x = monitor_config.get("x", 0)
                y = monitor_config.get("y", 0)
                w = monitor_config.get("w", 1920)
                h = monitor_config.get("h", 1080)
                monitor_info.append(f"{monitor_name}: {{x: {x}, y: {y}, w: {w}, h: {h}}}")
            context_parts.append(
                f"Available monitors: {', '.join(monitor_info)}"
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
            "- 'type': either 'list_apps', 'focus_app', 'place_app', 'switch_tab', 'list_tabs', 'close_app', 'close_tab', 'activate_preset', 'list_recent_files', or 'list_projects'",
            "- 'app_name': (for focus_app, place_app, and close_app, string, required for close_app, optional for focus_app/place_app when file/project is specified) the exact application name - MUST be from the installed apps list. Verify the app exists in installed apps before using it. If the user mentions something that's not an app (like a file name), do NOT use it as app_name. If the user specifies an app, use it. If the user opens a file/project without specifying an app, intelligently infer the best app from ALL installed apps based on file type, file extension, and context. Prefer matching from running apps, but if not found, use the closest match from installed apps (focus_app and place_app will launch the app if it's not running) (non-empty string if provided)",
            "- 'file_path': (for focus_app and place_app, string, optional) exact file path to open in the app",
            "- 'file_name': (for focus_app and place_app, string, optional) file name for fuzzy matching (use this if user says 'open x file in app' or 'open x file in app on monitor')",
            "- 'project_path': (for focus_app and place_app, string, optional) exact project/folder path to open in the app",
            "- 'project_name': (for focus_app and place_app, string, optional) project/folder name - MUST match the EXACT project name from the active projects list. When the user mentions a project name (e.g., 'anythingllm', 'anything llm', 'anything-llm'), find the matching project in the active projects list and use its EXACT name. For example, if the user says 'anythingllm' or 'anything llm', and the active projects list contains 'anything-llm', use 'anything-llm' as the project_name. Match user input to the exact project name from the list, accounting for variations in spacing, hyphens, and case.",
            "- 'monitor': (for place_app, enum, optional) MUST be one of the monitor names from the 'Available monitors' list in context. DO NOT use monitor names that don't exist in the available monitors list. Optional if bounds provided.",
            "- 'bounds': (for place_app, array<integer>, optional) exact window bounds [left, top, right, bottom] in absolute screen coordinates. AI calculates these based on monitor dimensions and user intent. PREFERRED when user requests positioning like 'left half', 'right side', 'maximize', or specific dimensions.",
            "- 'tab_index': (for switch_tab, integer, required) the tab number - YOU MUST analyze all tabs and return the specific tab_index of the best matching tab (positive integer, 1-based)",
            "- 'tab_indices': (for close_tab, array<integer>, required) array of tab indices - for single tab use [3], for multiple tabs use [2, 5, 8] (array of positive integers, non-empty, 1-based)",
            "- 'preset_name': (for activate_preset, string, required) the exact preset name from the available presets list (case-insensitive matching is supported) (non-empty string)",
            "",
            "CRITICAL: Monitor name validation:",
            "You MUST ONLY use monitor names that appear in the 'Available monitors' list provided in the context.",
            "If the user says 'right' or 'left' but those monitors don't exist in the available monitors list, DO NOT use them as monitor names.",
            "Instead, calculate bounds based on the available monitor(s). For example:",
            "- User says 'put X on right' but only 'main' exists -> calculate bounds for right half of main monitor",
            "- User says 'put X on left monitor' but only 'main' exists -> calculate bounds for left half of main monitor",
            "",
            "Monitor placement patterns to recognize:",
            "- 'put X on [monitor] monitor' -> type: 'place_app', monitor: [monitor] (ONLY if monitor exists in available monitors)",
            "- 'move X to [monitor] screen/display' -> type: 'place_app', monitor: [monitor] (ONLY if monitor exists in available monitors)",
            "- 'put X on left half' or 'snap X to left' -> type: 'place_app', app_name: X, bounds: [monitor_x, monitor_y, monitor_x + monitor_w/2, monitor_y + monitor_h] (use available monitor, calculate bounds)",
            "- 'put X on right half' or 'snap X to right' -> type: 'place_app', app_name: X, bounds: [monitor_x + monitor_w/2, monitor_y, monitor_x + monitor_w, monitor_y + monitor_h] (use available monitor, calculate bounds)",
            "- 'resize X to 1200x800' -> type: 'place_app', app_name: X, bounds: [monitor_x + (monitor_w-1200)/2, monitor_y + (monitor_h-800)/2, monitor_x + (monitor_w-1200)/2 + 1200, monitor_y + (monitor_h-800)/2 + 800]",
            "- 'center X on [monitor]' -> type: 'place_app', app_name: X, monitor: [monitor] (if exists), bounds: [calculate centered based on current window size]",
            "- 'maximize X' -> type: 'place_app', app_name: X, bounds: [monitor_x, monitor_y, monitor_x + monitor_w, monitor_y + monitor_h] (use available monitor)",
            "- 'show X on [monitor]' -> type: 'place_app', monitor: [monitor] (ONLY if monitor exists)",
            "- 'open X on [monitor]' -> type: 'place_app', monitor: [monitor] (ONLY if monitor exists)",
            "- 'open X file in Y app on [monitor]' -> type: 'place_app', app_name: Y, file_name: X, monitor: [monitor] (ONLY if monitor exists)",
            "- 'open X in Y on [monitor]' -> type: 'place_app', app_name: Y, file_name: X, monitor: [monitor] (ONLY if monitor exists)",
            "- 'put X file in Y on [monitor]' -> type: 'place_app', app_name: Y, file_name: X, monitor: [monitor] (ONLY if monitor exists)",
            "- 'open X project in Y app on [monitor]' -> type: 'place_app', app_name: Y, project_name: X, monitor: [monitor] (ONLY if monitor exists)",
            "- 'open X folder in Y on [monitor]' -> type: 'place_app', app_name: Y, project_name: X, monitor: [monitor] (ONLY if monitor exists)",
            "",
            "Window bounds calculation guidance:",
            "When user requests positioning (left/right half, maximize, specific dimensions), ALWAYS calculate bounds instead of using monitor names.",
            "You have access to monitor dimensions in the context. Calculate exact bounds [left, top, right, bottom] based on user intent and monitor coordinates.",
            "For 'left half': [monitor_x, monitor_y, monitor_x + monitor_w/2, monitor_y + monitor_h] (use first/only available monitor)",
            "For 'right half': [monitor_x + monitor_w/2, monitor_y, monitor_x + monitor_w, monitor_y + monitor_h] (use first/only available monitor)",
            "For specific dimensions like '1200x800', center on monitor: [monitor_x + (monitor_w-1200)/2, monitor_y + (monitor_h-800)/2, monitor_x + (monitor_w-1200)/2 + 1200, monitor_y + (monitor_h-800)/2 + 800]",
            "For 'maximize', use full monitor: [monitor_x, monitor_y, monitor_x + monitor_w, monitor_y + monitor_h] (use first/only available monitor)",
            "If user mentions a monitor name that doesn't exist, use the available monitor(s) and calculate bounds based on the positioning intent.",
            "",
            "If the user wants to focus an app, match their fuzzy input to the exact app name from the running apps list.",
            "If no matching app is found in running apps, use the closest match from installed apps.",
            "CRITICAL: Before using an app_name, verify it exists in the installed apps list. If the app name is not in the installed apps list, it is likely incorrect.",
            "If the user says 'open [file]' or 'open [file] on [monitor]' without specifying an app, you MUST intelligently infer the best app from ALL installed apps based on:",
            "1. File extension and type (e.g., .mov/.mp4 -> video player, .py/.js -> code editor, .jpg/.png -> image viewer)",
            "2. File's default app (if available in recent_files context)",
            "3. Common apps for that file type from the installed apps list",
            "4. User's likely intent (e.g., code files -> code editor, videos -> video player)",
            "Look through ALL installed apps and pick the most appropriate one. For example:",
            "- Video files (.mov, .mp4, .avi, .mkv) -> find any video player in installed apps (QuickTime Player, VLC, IINA, etc.)",
            "- Image files (.jpg, .png, .gif, .webp) -> find any image viewer in installed apps (Preview, Photos, etc.)",
            "- Code files (.py, .js, .ts, .jsx, .tsx) -> find any code editor in installed apps (Cursor, VS Code, PyCharm, etc.)",
            "- PDF files -> find any PDF viewer in installed apps (Preview, Adobe Acrobat Reader, etc.)",
            "- Text files (.txt, .md) -> find any text editor in installed apps (TextEdit, Cursor, VS Code, etc.)",
            "If you cannot determine the app from the file type and installed apps, set needs_clarification to true and ask which app to use.",
            "IMPORTANT: focus_app and place_app commands can open apps even if they're not currently running - the system will launch them automatically.",
            "When the user says 'open [App]' or 'launch [App]', use type 'focus_app' - it will launch the app if needed.",
            "If the user wants to place an app on a monitor, use type 'place_app' and extract the monitor name.",
            "If the user says 'open X file in Y app on [monitor]', use type 'place_app' with app_name: Y, file_name: X, and monitor: [monitor].",
            "If the user says 'open X project in Y app on [monitor]' or 'open X folder in Y on [monitor]', use type 'place_app' with app_name: Y, project_name: X, and monitor: [monitor].",
            "If the user says 'open [file] on [monitor]' without specifying an app, use type 'place_app' with file_name: [file], app_name: [inferred from file type], and monitor: [monitor].",
            "CRITICAL: When the user mentions a project name, you MUST match it to the EXACT project name from the active projects list. For example:",
            "- User says 'anythingllm' or 'anything llm' -> match to 'anything-llm' from the list",
            "- User says 'talk to computer' -> match to 'talk-to-computer' from the list",
            "- User says 'private gpt' -> match to 'private-gpt' from the list",
            "Look through the active projects list and find the project that matches the user's input, accounting for variations in spacing, hyphens, underscores, and case. Use the EXACT name from the list, not the user's input.",
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
            "- 'go to github' -> Analyze all tabs, find the one with 'github.com' in domain/URL, return tab_index (use switch_tab)",
            "- 'switch to tab about Python' -> Analyze all tabs, find the one with 'Python' in content summary or title, return tab_index",
            "- 'open chatgpt in chrome' -> User wants to open a NEW tab, return type: 'open_url', url: 'https://chatgpt.com'",
            "- 'open github in chrome' -> User wants to open a NEW tab, return type: 'open_url', url: 'https://github.com'",
            "",
            "DECISION: switch_tab vs open_url:",
            "- Use 'switch_tab' when user wants to go to an EXISTING tab (e.g., 'go to github', 'switch to reddit tab', 'show me the youtube tab')",
            "- Use 'open_url' when user explicitly wants to OPEN a NEW tab (e.g., 'open chatgpt in chrome', 'open a new tab for github', 'open youtube in chrome')",
            "- If user says 'open [site]' and a tab already exists, you can still use 'open_url' if the intent is clearly to create a new tab",
            "- When in doubt, analyze existing tabs first: if a matching tab exists and user says 'go to' or 'switch to', use 'switch_tab'; if user says 'open [site] in chrome', use 'open_url'",
            "",
            "QUESTION DETECTION:",
            "- If the input is a question (starts with who/what/when/where/why/how or ends with '?'), return a single 'query' intent:",
            "  {\"type\": \"query\", \"question\": \"[user's original question]\"}",
            "- Do not generate commands when it's clearly a question.",
            "",
            "CRITICAL: You MUST return 'tab_index' (integer) for switch_tab or 'tab_indices' (array<integer>) for close_tab when you find matching tab(s).",
            "For open_url: Return 'url' (string) - the URL to open (e.g., 'https://chatgpt.com', 'https://github.com'). The system will normalize it if needed.",
            "Do NOT return 'tab_title' or 'content_query' - return the specific 'tab_index' or 'tab_indices' of the matching tab(s), or 'url' for open_url.",
            "For close_tab: Always use 'tab_indices' array, even for single tab (e.g., tab_indices: [3] instead of tab_index: 3).",
            "If no matching tab is found for switch_tab and user wants to go to existing tab, set 'needs_clarification' to true.",
            "For open_url, you don't need to check if tab exists - just return the URL to open.",
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

    def answer_query(
        self,
        question: str,
        running_apps: Optional[List[str]] = None,
        installed_apps: Optional[List[str]] = None,
        chrome_tabs: Optional[List[Dict[str, Union[str, int]]]] = None,
        recent_files: Optional[List[Dict]] = None,
        active_projects: Optional[List[Dict]] = None,
        current_project: Optional[Dict] = None,
        available_presets: Optional[List[str]] = None,
        command_history: Optional[List[str]] = None,
        recent_queries: Optional[List[Dict]] = None,
    ) -> str:
        """
        Answer a general question using the LLM with all available context.
        Returns a concise natural-language answer.
        """
        context_parts: List[str] = [
            "You are a helpful macOS assistant with access to system information.",
            "Answer the user's question based on the context provided below.",
            "",
            "=== SYSTEM CONTEXT ===",
        ]
        
        if running_apps:
            context_parts.append(f"Running applications ({len(running_apps)}): {', '.join(running_apps)}")
        else:
            context_parts.append("Running applications: None")
        
        if installed_apps:
            apps_preview = ", ".join(installed_apps[:50])
            more = f"... and {len(installed_apps) - 50} more" if len(installed_apps) > 50 else ""
            context_parts.append(f"Installed applications ({len(installed_apps)} total): {apps_preview}")
            if more:
                context_parts.append(more)
        
        if chrome_tabs:
            context_parts.append(f"\nOpen Chrome tabs ({len(chrome_tabs)} total):")
            for tab in chrome_tabs:
                domain = tab.get('domain', 'N/A')
                title = tab.get('title', 'N/A')
                url = tab.get('url', '')
                index = tab.get('index', '?')
                active = " (ACTIVE)" if tab.get('is_active') else ""
                window = f" [Window {tab.get('window_index', '?')}]" if tab.get('window_index') else ""
                tab_str = f"  Tab {index} [{domain}]{active}{window}: {title}"
                if url:
                    tab_str += f" | {url}"
                content_summary = tab.get('content_summary', '')
                if content_summary:
                    content_preview = content_summary[:200] + "..." if len(content_summary) > 200 else content_summary
                    tab_str += f"\n    Content: {content_preview}"
                context_parts.append(tab_str)
        else:
            context_parts.append("\nOpen Chrome tabs: None")
        
        if recent_files:
            context_parts.append(f"\nRecently opened files ({len(recent_files)} shown):")
            for f in recent_files[:20]:
                file_name = f.get('name', 'Unknown')
                file_type = f.get('type', 'other')
                app = f.get('app', '')
                path = f.get('path', '')
                line = f"  - {file_name} ({file_type}"
                if app:
                    line += f", opened in {app}"
                line += ")"
                context_parts.append(line)
                if path:
                    context_parts.append(f"    Path: {path}")
        
        if active_projects:
            context_parts.append(f"\nActive projects ({len(active_projects)}):")
            for p in active_projects:
                name = p.get('name', 'Unknown')
                path = p.get('path', '')
                if path:
                    context_parts.append(f"  - {name} ({path})")
                else:
                    context_parts.append(f"  - {name}")
        
        if current_project:
            project_name = current_project.get('name', 'Unknown')
            project_path = current_project.get('path', '')
            context_parts.append(f"\nCurrent project: {project_name}")
            if project_path:
                context_parts.append(f"  Path: {project_path}")
        
        if available_presets:
            context_parts.append(f"\nAvailable presets: {', '.join(available_presets)}")
        
        if command_history:
            history_preview = [h for h in command_history[:10] if isinstance(h, str)]
            if history_preview:
                context_parts.append(f"\nRecent commands ({len(history_preview)}):")
                for h in history_preview:
                    context_parts.append(f"  - {h}")
        
        if recent_queries:
            qa_lines = []
            for qa in recent_queries[:5]:
                q = str(qa.get("question", "")).strip()
                a = str(qa.get("answer", "")).strip()
                if q and a:
                    qa_lines.append(f"Q: {q}\nA: {a}")
            if qa_lines:
                context_parts.append("\nRecent query responses (most recent first):\n" + "\n\n".join(qa_lines))
        
        context_parts.extend([
            "",
            "=== USER QUESTION ===",
            question.strip(),
            "",
            "Provide a clear, concise, and accurate answer grounded in the context.",
            "If the answer is not derivable from the context, say so briefly.",
        ])
        
        prompt = "\n".join(context_parts)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that answers questions about the user's system state, applications, tabs, files, and projects. Provide clear, accurate answers based on the context provided."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Sorry, I couldn't answer that due to an error: {e}"

