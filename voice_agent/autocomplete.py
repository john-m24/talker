"""Auto-complete engine for text input suggestions."""

import difflib
from typing import Dict, List, Optional, Any


class Suggestion:
    """Represents a single suggestion."""
    
    def __init__(self, text: str, display: str, score: float, source: str):
        """
        Initialize a suggestion.
        
        Args:
            text: The actual text to insert
            display: Display text to show in UI
            score: Relevance score (higher is better)
            source: Source of suggestion (e.g., "app", "tab", "preset", "history")
        """
        self.text = text
        self.display = display
        self.score = score
        self.source = source
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for UI consumption."""
        return {
            "text": self.text,
            "display": self.display,
            "score": self.score,
            "source": self.source
        }


class AutocompleteEngine:
    """Engine for generating auto-complete suggestions."""
    
    def __init__(self, max_suggestions: int = 5):
        """
        Initialize the auto-complete engine.
        
        Args:
            max_suggestions: Maximum number of suggestions to return
        """
        self.max_suggestions = max_suggestions
    
    def suggest_apps(self, text: str, running_apps: List[str], installed_apps: List[str]) -> List[Suggestion]:
        """
        Suggest app names based on input text.
        
        Args:
            text: User input text
            running_apps: List of running app names
            installed_apps: List of installed app names
            
        Returns:
            List of suggestions sorted by relevance
        """
        suggestions = []
        text_lower = text.lower()
        
        # Combine running and installed apps (prioritize running)
        all_apps = list(set(running_apps + installed_apps))
        
        for app in all_apps:
            app_lower = app.lower()
            
            # Exact match (highest priority)
            if app_lower == text_lower:
                suggestions.append(Suggestion(app, app, 100.0, "app"))
            # Starts with (high priority)
            elif app_lower.startswith(text_lower):
                score = 80.0 + (len(text_lower) / len(app_lower)) * 10
                suggestions.append(Suggestion(app, app, score, "app"))
            # Contains (medium priority)
            elif text_lower in app_lower:
                score = 50.0 + (len(text_lower) / len(app_lower)) * 10
                suggestions.append(Suggestion(app, app, score, "app"))
            # Fuzzy match (lower priority)
            else:
                ratio = difflib.SequenceMatcher(None, text_lower, app_lower).ratio()
                if ratio > 0.3:  # Threshold for fuzzy matching
                    score = ratio * 40.0
                    suggestions.append(Suggestion(app, app, score, "app"))
        
        # Sort by score (descending) and return top suggestions
        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions[:self.max_suggestions]
    
    def suggest_tabs(self, text: str, chrome_tabs: List[Dict[str, Any]]) -> List[Suggestion]:
        """
        Suggest tab names/domains based on input text.
        
        Args:
            text: User input text
            chrome_tabs: List of Chrome tab dicts with 'title', 'url', 'domain' keys
            
        Returns:
            List of suggestions sorted by relevance
        """
        suggestions = []
        text_lower = text.lower()
        
        for tab in chrome_tabs:
            title = tab.get("title", "")
            domain = tab.get("domain", "")
            url = tab.get("url", "")
            index = tab.get("index", 0)
            
            # Check title
            title_lower = title.lower()
            if text_lower in title_lower:
                if title_lower.startswith(text_lower):
                    score = 70.0
                else:
                    score = 50.0
                display = f"Tab: {title[:50]}" if len(title) > 50 else f"Tab: {title}"
                suggestions.append(Suggestion(f"switch to tab {index}", display, score, "tab"))
            
            # Check domain
            domain_lower = domain.lower()
            if text_lower in domain_lower:
                if domain_lower.startswith(text_lower):
                    score = 75.0
                else:
                    score = 55.0
                display = f"Tab: {domain}"
                suggestions.append(Suggestion(f"switch to tab {index}", display, score, "tab"))
            
            # Check URL
            url_lower = url.lower()
            if text_lower in url_lower:
                score = 45.0
                display = f"Tab: {domain or url[:30]}"
                suggestions.append(Suggestion(f"switch to tab {index}", display, score, "tab"))
        
        # Remove duplicates (same tab_index) and keep highest score
        seen = {}
        for suggestion in suggestions:
            key = suggestion.text
            if key not in seen or seen[key].score < suggestion.score:
                seen[key] = suggestion
        
        suggestions = list(seen.values())
        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions[:self.max_suggestions]
    
    def suggest_presets(self, text: str, presets: List[str]) -> List[Suggestion]:
        """
        Suggest preset names based on input text.
        
        Args:
            text: User input text
            presets: List of preset names
            
        Returns:
            List of suggestions sorted by relevance
        """
        suggestions = []
        text_lower = text.lower()
        
        for preset in presets:
            preset_lower = preset.lower()
            
            # Exact match
            if preset_lower == text_lower:
                suggestions.append(Suggestion(preset, f"Preset: {preset}", 100.0, "preset"))
            # Starts with
            elif preset_lower.startswith(text_lower):
                score = 80.0 + (len(text_lower) / len(preset_lower)) * 10
                suggestions.append(Suggestion(preset, f"Preset: {preset}", score, "preset"))
            # Contains
            elif text_lower in preset_lower:
                score = 50.0 + (len(text_lower) / len(preset_lower)) * 10
                suggestions.append(Suggestion(preset, f"Preset: {preset}", score, "preset"))
            # Fuzzy match
            else:
                ratio = difflib.SequenceMatcher(None, text_lower, preset_lower).ratio()
                if ratio > 0.3:
                    score = ratio * 40.0
                    suggestions.append(Suggestion(preset, f"Preset: {preset}", score, "preset"))
        
        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions[:self.max_suggestions]
    
    def suggest_commands(self, text: str, command_history: List[str]) -> List[Suggestion]:
        """
        Suggest previous commands from history.
        
        Args:
            text: User input text
            command_history: List of previous commands
            
        Returns:
            List of suggestions sorted by relevance
        """
        suggestions = []
        text_lower = text.lower()
        
        for cmd in command_history:
            cmd_lower = cmd.lower()
            
            # Starts with
            if cmd_lower.startswith(text_lower):
                score = 60.0 + (len(text_lower) / len(cmd_lower)) * 10
                display = f"Previous: {cmd[:50]}" if len(cmd) > 50 else f"Previous: {cmd}"
                suggestions.append(Suggestion(cmd, display, score, "history"))
            # Contains
            elif text_lower in cmd_lower:
                score = 40.0 + (len(text_lower) / len(cmd_lower)) * 10
                display = f"Previous: {cmd[:50]}" if len(cmd) > 50 else f"Previous: {cmd}"
                suggestions.append(Suggestion(cmd, display, score, "history"))
        
        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions[:self.max_suggestions]
    
    def suggest_all(self, text: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate all suggestions based on input text and context.
        
        Args:
            text: User input text
            context: Context dict with keys:
                - running_apps: List of running app names
                - chrome_tabs: List of Chrome tab dicts
                - presets: List of preset names
                - command_history: List of previous commands
        
        Returns:
            List of suggestion dicts sorted by relevance
        """
        all_suggestions = []
        
        # Extract context
        running_apps = context.get("running_apps", [])
        installed_apps = context.get("installed_apps", [])
        chrome_tabs = context.get("chrome_tabs", [])
        presets = context.get("presets", [])
        command_history = context.get("command_history", [])
        
        # Context-aware suggestions
        text_lower = text.lower()
        
        # If text starts with command keywords, suggest relevant items
        if text_lower.startswith("focus ") or text_lower.startswith("open ") or text_lower.startswith("show "):
            # Suggest apps
            query = text_lower.split(" ", 1)[1] if " " in text_lower else ""
            if query:
                all_suggestions.extend(self.suggest_apps(query, running_apps, installed_apps))
        elif text_lower.startswith("switch ") or text_lower.startswith("go to "):
            # Suggest tabs
            query = text_lower.split(" ", 1)[1] if " " in text_lower else ""
            if query:
                all_suggestions.extend(self.suggest_tabs(query, chrome_tabs))
        elif text_lower.startswith("activate ") or text_lower.startswith("load "):
            # Suggest presets
            query = text_lower.split(" ", 1)[1] if " " in text_lower else ""
            if query:
                all_suggestions.extend(self.suggest_presets(query, presets))
        else:
            # General suggestions - try all sources
            all_suggestions.extend(self.suggest_apps(text, running_apps, installed_apps))
            all_suggestions.extend(self.suggest_tabs(text, chrome_tabs))
            all_suggestions.extend(self.suggest_presets(text, presets))
            all_suggestions.extend(self.suggest_commands(text, command_history))
        
        # Sort all suggestions by score and return top N
        all_suggestions.sort(key=lambda s: s.score, reverse=True)
        
        # Convert to dicts
        return [s.to_dict() for s in all_suggestions[:self.max_suggestions]]

