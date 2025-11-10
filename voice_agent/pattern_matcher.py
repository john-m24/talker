"""Pattern matcher for parsing common commands without LLM."""

import re
from typing import Optional, Dict, Any, List
from .fuzzy_matcher import match_app_name, match_preset_name


class PatternMatcher:
    """Pattern matcher for common command patterns."""
    
    def __init__(self):
        """Initialize pattern matcher with regex patterns."""
        # Compile regex patterns for common commands
        self.patterns = {
            # Explicit focus commands
            'focus_app_explicit': re.compile(
                r'^(?:focus|bring|show|open|launch)\s+(.+)$',
                re.IGNORECASE
            ),
            # Place app commands
            'place_app': re.compile(
                r'^(?:place|put|move|show|open)\s+(.+?)\s+on\s+(?:the\s+)?(main|left|right|center)\s+(?:monitor|screen|display)(?:\s+and\s+maximize)?$',
                re.IGNORECASE
            ),
            # Place app with maximize
            'place_app_maximize': re.compile(
                r'^(?:place|put|move|show|open)\s+(.+?)\s+on\s+(?:the\s+)?(main|left|right|center)\s+(?:monitor|screen|display)\s+and\s+maximize$',
                re.IGNORECASE
            ),
            # Close app commands
            'close_app': re.compile(
                r'^(?:close|quit)\s+(.+)$',
                re.IGNORECASE
            ),
            # Switch tab (numeric)
            'switch_tab_numeric': re.compile(
                r'^(?:switch\s+to\s+tab|go\s+to\s+tab|tab)\s+(\d+)$',
                re.IGNORECASE
            ),
            # Close tab (numeric)
            'close_tab_numeric': re.compile(
                r'^close\s+tab(?:s)?\s+(\d+(?:\s*,\s*\d+)*)$',
                re.IGNORECASE
            ),
            # Activate preset
            'activate_preset': re.compile(
                r'^(?:activate|load|set\s+up|switch\s+to)\s+(.+)$',
                re.IGNORECASE
            ),
        }
    
    def match_pattern(
        self,
        text: str,
        running_apps: List[str],
        installed_apps: List[str],
        available_presets: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Match text against command patterns and return parsed intent.
        
        Args:
            text: User command text
            running_apps: List of running app names
            installed_apps: List of installed app names
            available_presets: Optional list of available preset names
            
        Returns:
            Parsed intent dict or None if no pattern matches
        """
        text = text.strip()
        if not text:
            return None
        
        # Try explicit focus commands first
        match = self.patterns['focus_app_explicit'].match(text)
        if match:
            app_text = match.group(1).strip()
            app_name = match_app_name(app_text, running_apps, installed_apps)
            if app_name:
                return {
                    "commands": [{"type": "focus_app", "app_name": app_name}],
                    "needs_clarification": False,
                    "clarification_reason": None
                }
        
        # Try place app with maximize
        match = self.patterns['place_app_maximize'].match(text)
        if match:
            app_text = match.group(1).strip()
            monitor = match.group(2).lower()
            app_name = match_app_name(app_text, running_apps, installed_apps)
            if app_name:
                # Normalize monitor name
                if monitor == "center":
                    monitor = "main"
                return {
                    "commands": [{
                        "type": "place_app",
                        "app_name": app_name,
                        "monitor": monitor,
                        "maximize": True
                    }],
                    "needs_clarification": False,
                    "clarification_reason": None
                }
        
        # Try place app
        match = self.patterns['place_app'].match(text)
        if match:
            app_text = match.group(1).strip()
            monitor = match.group(2).lower()
            app_name = match_app_name(app_text, running_apps, installed_apps)
            if app_name:
                # Normalize monitor name
                if monitor == "center":
                    monitor = "main"
                # Check for maximize keyword
                maximize = "maximize" in text.lower() or "max" in text.lower()
                return {
                    "commands": [{
                        "type": "place_app",
                        "app_name": app_name,
                        "monitor": monitor,
                        "maximize": maximize
                    }],
                    "needs_clarification": False,
                    "clarification_reason": None
                }
        
        # Try close app
        match = self.patterns['close_app'].match(text)
        if match:
            app_text = match.group(1).strip()
            app_name = match_app_name(app_text, running_apps, installed_apps)
            if app_name:
                return {
                    "commands": [{"type": "close_app", "app_name": app_name}],
                    "needs_clarification": False,
                    "clarification_reason": None
                }
        
        # Try switch tab (numeric)
        match = self.patterns['switch_tab_numeric'].match(text)
        if match:
            tab_index = int(match.group(1))
            return {
                "commands": [{"type": "switch_tab", "tab_index": tab_index}],
                "needs_clarification": False,
                "clarification_reason": None
            }
        
        # Try close tab (numeric)
        match = self.patterns['close_tab_numeric'].match(text)
        if match:
            indices_str = match.group(1)
            # Parse comma-separated numbers
            tab_indices = [int(x.strip()) for x in indices_str.split(',')]
            return {
                "commands": [{"type": "close_tab", "tab_indices": tab_indices}],
                "needs_clarification": False,
                "clarification_reason": None
            }
        
        # Try activate preset
        if available_presets:
            match = self.patterns['activate_preset'].match(text)
            if match:
                preset_text = match.group(1).strip()
                preset_name = match_preset_name(preset_text, available_presets)
                if preset_name:
                    return {
                        "commands": [{"type": "activate_preset", "preset_name": preset_name}],
                        "needs_clarification": False,
                        "clarification_reason": None
                    }
            
            # Also try if text is just a preset name (implicit preset activation)
            preset_name = match_preset_name(text, available_presets)
            if preset_name:
                return {
                    "commands": [{"type": "activate_preset", "preset_name": preset_name}],
                    "needs_clarification": False,
                    "clarification_reason": None
                }
        
        # Try implicit focus (just app name)
        # Only if it's a single word or short phrase and matches an app
        words = text.split()
        if len(words) <= 3:  # Allow short phrases like "google chrome"
            app_name = match_app_name(text, running_apps, installed_apps)
            if app_name:
                # Make sure it's not a preset (presets take priority)
                if not available_presets or not match_preset_name(text, available_presets):
                    return {
                        "commands": [{"type": "focus_app", "app_name": app_name}],
                        "needs_clarification": False,
                        "clarification_reason": None
                    }
        
        return None

