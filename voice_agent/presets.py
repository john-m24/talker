"""Presets configuration module for window layouts."""

import os
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from .config import CACHE_PRESETS_TTL
from .cache import get_cache_manager


def _get_presets_file_path() -> str:
    """
    Get the path to the presets configuration file.
    
    Priority:
    1. VOICE_AGENT_PRESETS_FILE environment variable
    2. ~/.voice_agent_presets.json (user home directory)
    3. presets.json in project root
    
    Returns:
        Path to the presets file
    """
    # Check environment variable first
    env_path = os.getenv("VOICE_AGENT_PRESETS_FILE")
    if env_path:
        return env_path
    
    # Check user home directory
    home_presets = os.path.expanduser("~/.voice_agent_presets.json")
    if os.path.exists(home_presets):
        return home_presets
    
    # Fallback to project root
    project_root = Path(__file__).parent.parent
    project_presets = project_root / "presets.json"
    return str(project_presets)


def load_presets() -> Dict[str, Any]:
    """
    Load presets from JSON configuration file.
    Uses cache if enabled.
    
    Returns:
        Dictionary mapping preset names to preset configurations.
        Each preset config has an 'apps' list with app placement instructions.
        Returns empty dict if file doesn't exist or is invalid.
    """
    # Check cache first
    cache_manager = get_cache_manager()
    if cache_manager:
        cached = cache_manager.get_system("presets")
        if cached is not None:
            return cached
    
    # Cache miss - load from file
    presets_file = _get_presets_file_path()
    
    if not os.path.exists(presets_file):
        # File doesn't exist - this is OK, return empty dict
        return {}
    
    try:
        with open(presets_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validate and filter presets
        valid_presets = {}
        for preset_name, preset_config in data.items():
            if _validate_preset(preset_name, preset_config):
                valid_presets[preset_name] = preset_config
            else:
                print(f"Warning: Skipping invalid preset '{preset_name}'")
        
        # Cache the result
        if cache_manager:
            cache_manager.set_system("presets", valid_presets, ttl=CACHE_PRESETS_TTL)
        
        return valid_presets
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in presets file '{presets_file}': {e}")
        return {}
    except Exception as e:
        print(f"Error loading presets from '{presets_file}': {e}")
        return {}


def _validate_preset(preset_name: str, preset_config: Any) -> bool:
    """
    Validate a preset configuration structure.
    
    Args:
        preset_name: Name of the preset
        preset_config: Preset configuration dictionary
        
    Returns:
        True if preset is valid, False otherwise
    """
    if not isinstance(preset_config, dict):
        return False
    
    if "apps" not in preset_config:
        return False
    
    apps = preset_config["apps"]
    if not isinstance(apps, list):
        return False
    
    # Validate each app entry
    for app_entry in apps:
        if not isinstance(app_entry, dict):
            return False
        
        # Required fields
        if "app_name" not in app_entry or "monitor" not in app_entry:
            return False
        
        # Validate monitor value
        monitor = app_entry["monitor"]
        if monitor not in ["main", "left", "right"]:
            return False
        
        # Validate maximize if present (should be boolean)
        if "maximize" in app_entry and not isinstance(app_entry["maximize"], bool):
            return False
    
    return True


def get_preset(preset_name: str, presets: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Get a specific preset by name (case-insensitive matching).
    
    Args:
        preset_name: Name of the preset to retrieve
        presets: Optional presets dictionary (if None, loads from file)
        
    Returns:
        Preset configuration dictionary if found, None otherwise
    """
    if presets is None:
        presets = load_presets()
    
    # Case-insensitive exact match first
    for name, config in presets.items():
        if name.lower() == preset_name.lower():
            return config
    
    # Case-insensitive partial match
    matches = []
    preset_name_lower = preset_name.lower()
    for name, config in presets.items():
        if preset_name_lower in name.lower() or name.lower() in preset_name_lower:
            matches.append((name, config))
    
    if len(matches) == 1:
        return matches[0][1]
    elif len(matches) > 1:
        # Multiple matches - return None, caller should handle ambiguity
        return None
    
    return None


def list_presets(presets: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Get a list of available preset names.
    
    Args:
        presets: Optional presets dictionary (if None, loads from file)
        
    Returns:
        List of preset names
    """
    if presets is None:
        presets = load_presets()
    
    return list(presets.keys())


def find_matching_presets(preset_name: str, presets: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Find all presets that match the given name (case-insensitive, partial matching).
    
    Args:
        preset_name: Name or partial name to search for
        presets: Optional presets dictionary (if None, loads from file)
        
    Returns:
        List of matching preset names (empty if none found)
    """
    if presets is None:
        presets = load_presets()
    
    matches = []
    preset_name_lower = preset_name.lower()
    
    for name in presets.keys():
        if preset_name_lower == name.lower():
            # Exact match - return immediately
            return [name]
        elif preset_name_lower in name.lower() or name.lower() in preset_name_lower:
            matches.append(name)
    
    return matches

