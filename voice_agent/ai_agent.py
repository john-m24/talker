"""AI agent for parsing voice commands into structured intents."""

import json
import hashlib
import openai
from typing import Dict, List, Optional, Union, Any
from .config import LLM_ENDPOINT, LLM_MODEL, LLM_CACHE_ENABLED
from .hardcoded_commands import get_hardcoded_command
from .pattern_matcher import PatternMatcher
from .cache import get_cache_manager


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
        current_project: Optional[Dict] = None,
        state_snapshotter: Optional[Any] = None
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
        text_hash = None
        if LLM_CACHE_ENABLED and self.cache_manager:
            text_hash = hashlib.md5(normalized_text.encode()).hexdigest()
            
            # Check text-only cache first using llm.responses namespace
            cached_result = self.cache_manager.get_llm(text_hash)
            if cached_result is not None:
                # Validate context after cache hit
                validated_result = self._validate_context(
                    cached_result,
                    running_apps,
                    installed_apps or [],
                    available_presets
                )
                return validated_result
        
        # Build optimized prompt for the AI
        prompt = self._build_optimized_prompt(
            normalized_text,
            running_apps,
            installed_apps,
            chrome_tabs,
            chrome_tabs_raw,
            available_presets,
            recent_files,
            active_projects,
            current_project,
            state_snapshotter
        )
        
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
                
                # Normalize to structure with 'commands' array
                if "commands" in result:
                    commands = result.get("commands", [])
                    if not isinstance(commands, list):
                        commands = [commands] if commands else []
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
                if text_hash and self.cache_manager:
                    # Cache with no TTL (text-only key means context changes don't invalidate)
                    self.cache_manager.set_llm(text_hash, result, ttl=0)
                
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
    
    def _build_optimized_prompt(
        self,
        normalized_text: str,
        running_apps: List[str],
        installed_apps: Optional[List[str]],
        chrome_tabs: Optional[List[Dict[str, Union[str, int]]]],
        chrome_tabs_raw: Optional[str],
        available_presets: Optional[List[str]],
        recent_files: Optional[List[Dict]],
        active_projects: Optional[List[Dict]],
        current_project: Optional[Dict],
        state_snapshotter: Optional[Any]
    ) -> str:
        """
        Build optimized prompt for LLM with condensed structure and rich context.
        
        Returns:
            Complete prompt string
        """
        context_parts = []
        
        # 1. System role + user command (immediate context)
        context_parts.extend([
            "You are a macOS window control assistant. Parse the user's command and return a JSON response.",
            "",
            "User command:",
            normalized_text,
            "",
        ])
        
        # 2. Available commands (compact list)
        context_parts.extend([
            "Available commands:",
            "- list_apps: list running applications",
            "- focus_app: bring app to front (launches if needed), can open file/project",
            "- place_app: move app window to monitor/position, can open file/project",
            "- switch_tab: switch to existing Chrome tab",
            "- open_url: open URL in new Chrome tab",
            "- list_tabs: list all open Chrome tabs",
            "- close_app: quit/close application",
            "- close_tab: close Chrome tab(s)",
            "- activate_preset: activate preset window layout",
            "- list_recent_files: list recently opened files",
            "- list_projects: list active projects",
            "- query: answer questions about system state",
            "",
        ])
        
        # 3. Context data (rich, well-formatted)
        if running_apps:
            context_parts.append(f"Running applications: {', '.join(running_apps)}")
        else:
            context_parts.append("Running applications: None")
        
        if installed_apps:
            context_parts.append(f"Installed applications ({len(installed_apps)} total): {', '.join(installed_apps)}")
        
        # Recent queries (keep at 5)
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
                        context_parts.append("\nRecent query responses (most recent first):\n" + "\n\n".join(qa_lines))
        except Exception:
            pass
        
        # Activity history (reduced from 20 to 15)
        try:
            if self.cache_manager and hasattr(self.cache_manager, "get_activity_history"):
                activity_history = self.cache_manager.get_activity_history(max_count=15)  # type: ignore[attr-defined]
                if activity_history:
                    import time
                    from .monitoring import get_active_app, get_active_chrome_tab
                    
                    current_app = None
                    current_tab_index = None
                    try:
                        current_app = get_active_app()
                        current_tab = get_active_chrome_tab()
                        if current_tab:
                            current_tab_index = current_tab.get("index")
                    except Exception:
                        pass
                    
                    activity_lines = []
                    for activity in activity_history:
                        action = activity.get("action", "")
                        details = activity.get("details", {})
                        timestamp = activity.get("timestamp", 0)
                        age_seconds = int(time.time() - timestamp) if timestamp else 0
                        age_str = f"{age_seconds}s ago" if age_seconds < 60 else f"{age_seconds // 60}m ago"
                        
                        if action == "switch_tab":
                            from_tab = details.get("from_tab")
                            to_tab = details.get("to_tab")
                            if to_tab == current_tab_index:
                                continue
                            tab_info = details.get("tab_info", {})
                            title = tab_info.get("title", "")
                            activity_lines.append(f"  {age_str}: Switched from tab {from_tab} to tab {to_tab} ({title})")
                        elif action == "activate_app":
                            app_name = details.get("app_name", "")
                            if app_name == current_app:
                                continue
                            previous_app = details.get("previous_app")
                            if previous_app:
                                activity_lines.append(f"  {age_str}: Activated {app_name} (was {previous_app})")
                            else:
                                activity_lines.append(f"  {age_str}: Activated {app_name}")
                        elif action == "place_app":
                            app_name = details.get("app_name", "")
                            if app_name == current_app:
                                continue
                            activity_lines.append(f"  {age_str}: Moved {app_name} window")
                        elif action == "close_tab":
                            closed_tabs = details.get("closed_tabs", [])
                            activity_lines.append(f"  {age_str}: Closed tab(s) {closed_tabs}")
                        elif action == "open_url":
                            url = details.get("url", "")
                            activity_lines.append(f"  {age_str}: Opened URL {url}")
                    
                    if activity_lines:
                        context_parts.append("\nRecent activity history (most recent first):\n" + "\n".join(activity_lines))
        except Exception:
            pass
        
        # State snapshot
        try:
            from .config import STATE_SNAPSHOT_ENABLED
            if STATE_SNAPSHOT_ENABLED:
                snapshotter = state_snapshotter
                if snapshotter is None:
                    from .monitoring import StateSnapshotter
                    snapshotter = StateSnapshotter()
                state_snapshot = snapshotter.format_snapshot_for_llm()
                if state_snapshot:
                    context_parts.append("\n" + state_snapshot)
        except Exception:
            pass
        
        # Recent files (reduced from 10 to 7 code files)
        if recent_files:
            code_files = [f for f in recent_files if f.get('type') == 'code']
            other_files = [f for f in recent_files if f.get('type') != 'code']
            top_files = (code_files[:7] + other_files[:3])[:7]
            
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
                
                context_parts.append(f"Recently opened files: {', '.join(file_info)}")
        
        if current_project:
            project_name = current_project.get('name', 'Unknown')
            project_path = current_project.get('path', '')
            context_parts.append(f"Current project: {project_name} ({project_path})")
        
        if active_projects:
            project_info = []
            for p in active_projects:
                name = p.get('name', '')
                path = p.get('path', '')
                if path:
                    project_info.append(f"{name} ({path})")
                else:
                    project_info.append(name)
            context_parts.append(f"Active projects ({len(active_projects)}): {', '.join(project_info)}")
        
        if available_presets:
            context_parts.append(f"Available presets: {', '.join(available_presets)}")
        
        # Chrome tabs (limit content_summary to 200 chars)
        if chrome_tabs_raw:
            context_parts.append(f"Raw Chrome tabs data (parse to find ALL tabs):\n{chrome_tabs_raw}")
            context_parts.append("Format: globalIndex, \"title\", \"url\", windowIndex, localIndex, isActive, ... (6 values per tab)")
        
        if chrome_tabs:
            tabs_info = []
            for tab in chrome_tabs:
                domain = tab.get('domain', 'N/A')
                title = tab.get('title', 'N/A')
                url = tab.get('url', '')
                content_summary = tab.get('content_summary', '')
                active = " (ACTIVE)" if tab.get('is_active') else ""
                window = f" [Window {tab.get('window_index', '?')}]" if tab.get('window_index') else ""
                
                tab_str = f"Tab {tab['index']} [{domain}]{active}{window}\n  Title: {title}"
                if url:
                    tab_str += f"\n  URL: {url}"
                if content_summary:
                    content_display = content_summary[:200] + "..." if len(content_summary) > 200 else content_summary
                    tab_str += f"\n  Content: {content_display}"
                tabs_info.append(tab_str)
            
            if tabs_info:
                context_parts.append(f"Parsed Chrome tabs ({len(chrome_tabs)}):\n" + "\n\n".join(tabs_info))
        
        # Monitors
        from .config import MONITORS
        if MONITORS:
            monitor_info = []
            for monitor_name, monitor_config in MONITORS.items():
                x = monitor_config.get("x", 0)
                y = monitor_config.get("y", 0)
                w = monitor_config.get("w", 1920)
                h = monitor_config.get("h", 1080)
                monitor_info.append(f"{monitor_name}: {{x: {x}, y: {y}, w: {w}, h: {h}}}")
            context_parts.append(f"Available monitors: {', '.join(monitor_info)}")
        
        # 4. Field definitions (structured, compact)
        context_parts.extend([
            "",
            "Fields:",
            "type (enum: list_apps|focus_app|place_app|switch_tab|open_url|close_app|close_tab|activate_preset|list_tabs|list_recent_files|list_projects|query)",
            "app_name (str, must exist in installed_apps)",
            "file_path/name (str, opt)",
            "project_path/name (str, opt, exact match from active_projects)",
            "monitor (str, must exist in available_monitors)",
            "bounds ([left,top,right,bottom], opt)",
            "tab_index (int, 1-based, from raw Chrome tabs data)",
            "tab_indices ([int], 1-based)",
            "preset_name (str, from available_presets)",
            "url (str, for open_url)",
            "",
        ])
        
        # 5. Validation rules (consolidated, essential only)
        context_parts.extend([
            "Validation:",
            "(1) Monitor names must exist in available_monitors list",
            "(2) app_name must be in installed_apps",
            "(3) project_name must match exact from active_projects",
            "(4) Use raw Chrome tabs data as source of truth for tab_index",
            "(5) For file/project opening without app specified, infer best app from file type and installed_apps",
            "",
        ])
        
        # 6. Few-shot examples (2-3 examples showing inference)
        context_parts.extend([
            "Examples:",
            "Input: 'focus chrome' | Context: running_apps=['Google Chrome', 'Cursor']",
            "Output: {\"commands\": [{\"type\": \"focus_app\", \"app_name\": \"Google Chrome\"}], \"needs_clarification\": false, \"clarification_reason\": null}",
            "",
            "Input: 'put cursor on left and chrome on right' | Context: monitors={'left': {...}, 'right': {...}}",
            "Output: {\"commands\": [{\"type\": \"place_app\", \"app_name\": \"Cursor\", \"monitor\": \"left\"}, {\"type\": \"place_app\", \"app_name\": \"Google Chrome\", \"monitor\": \"right\"}], \"needs_clarification\": false, \"clarification_reason\": null}",
            "",
            "Input: 'switch to reddit' | Context: chrome_tabs with domain='reddit.com' at tab_index=3",
            "Output: {\"commands\": [{\"type\": \"switch_tab\", \"tab_index\": 3}], \"needs_clarification\": false, \"clarification_reason\": null}",
            "",
        ])
        
        # 7. Output format (brief JSON structure reminder)
        context_parts.extend([
            "Return JSON:",
            "{\"commands\": [{\"type\": \"...\", ...}], \"needs_clarification\": bool, \"clarification_reason\": str|null}",
            "",
            "Multiple commands: Split on 'and', 'then', 'also', 'plus'. Each command parsed independently.",
            "Clarification: Set needs_clarification=true if ambiguous, missing info, or unclear intent.",
            "Use switch_tab for existing tabs, open_url for new tabs.",
            "For questions (who/what/when/where/why/how or '?'), return type: 'query'.",
        ])
        
        return "\n".join(context_parts)
    
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
        
        # Include activity history if available (for temporal queries)
        try:
            cache_manager = get_cache_manager()
            if cache_manager and hasattr(cache_manager, "get_activity_history"):
                activity_history = cache_manager.get_activity_history(max_count=20)  # type: ignore[attr-defined]
                if activity_history:
                    import time
                    from .monitoring import get_active_app, get_active_chrome_tab
                    
                    # Get current state to filter out command-initiated activities
                    current_app = None
                    current_tab_index = None
                    try:
                        current_app = get_active_app()
                        current_tab = get_active_chrome_tab()
                        if current_tab:
                            current_tab_index = current_tab.get("index")
                    except Exception:
                        # If state retrieval fails, fall back to showing all activities
                        pass
                    
                    activity_lines = []
                    for activity in activity_history:
                        action = activity.get("action", "")
                        details = activity.get("details", {})
                        timestamp = activity.get("timestamp", 0)
                        age_seconds = int(time.time() - timestamp) if timestamp else 0
                        age_str = f"{age_seconds}s ago" if age_seconds < 60 else f"{age_seconds // 60}m ago"
                        
                        if action == "switch_tab":
                            from_tab = details.get("from_tab")
                            to_tab = details.get("to_tab")
                            # Skip if this activity switched TO the current tab (command-initiated)
                            if to_tab == current_tab_index:
                                continue
                            tab_info = details.get("tab_info", {})
                            title = tab_info.get("title", "")
                            activity_lines.append(f"  {age_str}: Switched from tab {from_tab} to tab {to_tab} ({title})")
                        elif action == "activate_app":
                            app_name = details.get("app_name", "")
                            # Skip if this activity activated the current app (command-initiated)
                            if app_name == current_app:
                                continue
                            previous_app = details.get("previous_app")
                            if previous_app:
                                activity_lines.append(f"  {age_str}: Activated {app_name} (was {previous_app})")
                            else:
                                activity_lines.append(f"  {age_str}: Activated {app_name}")
                        elif action == "place_app":
                            app_name = details.get("app_name", "")
                            # Skip if this activity moved the current app (command-initiated)
                            if app_name == current_app:
                                continue
                            activity_lines.append(f"  {age_str}: Moved {app_name} window")
                        elif action == "close_tab":
                            closed_tabs = details.get("closed_tabs", [])
                            activity_lines.append(f"  {age_str}: Closed tab(s) {closed_tabs}")
                        elif action == "open_url":
                            url = details.get("url", "")
                            activity_lines.append(f"  {age_str}: Opened URL {url}")
                    
                    if activity_lines:
                        context_parts.append("\nRecent activity history (most recent first, excluding command-initiated actions):\n" + "\n".join(activity_lines))
        except Exception:
            pass
        
        # Include current state snapshot if available
        try:
            from .monitoring import StateSnapshotter
            from .config import STATE_SNAPSHOT_ENABLED
            if STATE_SNAPSHOT_ENABLED:
                # answer_query doesn't receive state_snapshotter parameter, create new instance
                snapshotter = StateSnapshotter()
                state_snapshot = snapshotter.format_snapshot_for_llm()
                if state_snapshot:
                    context_parts.append("\n" + state_snapshot)
        except Exception:
            pass
        
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
