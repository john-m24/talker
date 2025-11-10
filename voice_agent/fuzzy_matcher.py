"""Fuzzy matching utilities for app and preset name matching."""

import difflib
from typing import List, Optional


def match_app_name(text: str, running_apps: List[str], installed_apps: List[str]) -> Optional[str]:
    """
    Match a text input to an app name using fuzzy matching.
    
    Prioritizes running apps over installed apps. Returns the best matching
    app name or None if no good match is found.
    
    Args:
        text: Text to match against app names
        running_apps: List of running app names
        installed_apps: List of installed app names
        
    Returns:
        Best matching app name or None if no good match
    """
    text_lower = text.lower().strip()
    if not text_lower:
        return None
    
    # Combine running and installed apps (prioritize running)
    # Check running apps first
    all_apps = list(set(running_apps + installed_apps))
    
    best_match = None
    best_score = 0.0
    best_is_running = False
    
    for app in all_apps:
        app_lower = app.lower()
        score = 0.0
        is_running = app in running_apps
        
        # Exact match (highest priority)
        if app_lower == text_lower:
            score = 100.0
        # Starts with (high priority)
        elif app_lower.startswith(text_lower):
            score = 80.0 + (len(text_lower) / len(app_lower)) * 10
        # Contains (medium priority)
        elif text_lower in app_lower:
            score = 50.0 + (len(text_lower) / len(app_lower)) * 10
        # Fuzzy match (lower priority)
        else:
            ratio = difflib.SequenceMatcher(None, text_lower, app_lower).ratio()
            if ratio > 0.3:  # Threshold for fuzzy matching
                score = ratio * 40.0
        
        # Boost score if app is running (prioritize running apps)
        if is_running:
            score += 5.0
        
        # Update best match if this is better
        if score > best_score:
            best_score = score
            best_match = app
            best_is_running = is_running
    
    # Return best match if score is above threshold
    if best_score >= 30.0:  # Minimum threshold for fuzzy matching
        return best_match
    
    return None


def match_preset_name(text: str, available_presets: List[str]) -> Optional[str]:
    """
    Match a text input to a preset name using fuzzy matching.
    
    Returns the best matching preset name or None if no good match is found.
    
    Args:
        text: Text to match against preset names
        available_presets: List of available preset names
        
    Returns:
        Best matching preset name or None if no good match
    """
    text_lower = text.lower().strip()
    if not text_lower or not available_presets:
        return None
    
    best_match = None
    best_score = 0.0
    
    for preset in available_presets:
        preset_lower = preset.lower()
        score = 0.0
        
        # Exact match
        if preset_lower == text_lower:
            score = 100.0
        # Starts with
        elif preset_lower.startswith(text_lower):
            score = 80.0 + (len(text_lower) / len(preset_lower)) * 10
        # Contains
        elif text_lower in preset_lower:
            score = 50.0 + (len(text_lower) / len(preset_lower)) * 10
        # Fuzzy match
        else:
            ratio = difflib.SequenceMatcher(None, text_lower, preset_lower).ratio()
            if ratio > 0.3:
                score = ratio * 40.0
        
        # Update best match if this is better
        if score > best_score:
            best_score = score
            best_match = preset
    
    # Return best match if score is above threshold
    if best_score >= 30.0:  # Minimum threshold for fuzzy matching
        return best_match
    
    return None

