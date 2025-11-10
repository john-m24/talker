"""Cache manager for system data and command history."""

import json
import os
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

# Module-level singleton instance
_instance: Optional['CacheManager'] = None


class CacheKeys:
    """Constants for cache keys to avoid typos and ensure consistency."""
    RUNNING_APPS = "running_apps"
    INSTALLED_APPS = "installed_apps"
    CHROME_TABS = "chrome_tabs"
    CHROME_TABS_RAW = "chrome_tabs_raw"
    PRESETS = "presets"
    LLM_RESPONSE = "llm_response:"
    COMMAND_PATTERNS = "command_patterns"
    COMMAND_FREQUENCY = "command_frequency"
    COMMAND_SEQUENCES = "command_sequences"
    RECENT_FILES = "recent_files"
    ACTIVE_PROJECTS = "active_projects"
    CURRENT_PROJECT = "current_project"
    
    @staticmethod
    def llm_response(text_hash: str) -> str:
        """Generate LLM response cache key from text hash."""
        return f"{CacheKeys.LLM_RESPONSE}{text_hash}"


def get_cache_manager() -> Optional['CacheManager']:
    """
    Get the global cache manager instance.
    
    Returns:
        CacheManager instance if initialized, None otherwise
    """
    return _instance


def initialize_cache_manager(
    enabled: bool = True,
    history_size: int = 100,
    history_path: Optional[str] = None
) -> Optional['CacheManager']:
    """
    Initialize the global cache manager instance.
    
    This function is idempotent - if called multiple times, it returns
    the existing instance without re-initializing.
    
    Args:
        enabled: Whether caching is enabled
        history_size: Maximum number of commands to store in history
        history_path: Path to history JSON file (defaults to ~/.voice_agent_history.json)
        
    Returns:
        CacheManager instance if enabled, None otherwise
    """
    global _instance
    
    # Idempotent: return existing instance if already initialized
    if _instance is not None:
        return _instance
    
    # Create new instance if enabled
    if enabled:
        _instance = CacheManager(
            enabled=enabled,
            history_size=history_size,
            history_path=history_path
        )
    
    return _instance


def reset_cache_manager() -> None:
    """
    Reset the global cache manager instance (for testing).
    
    This sets the global instance to None, allowing a fresh instance
    to be created on the next call to initialize_cache_manager().
    """
    global _instance
    _instance = None


class CacheManager:
    """Manages caching of system data and command history."""
    
    def __init__(self, enabled: bool = True, history_size: int = 100, history_path: Optional[str] = None):
        """
        Initialize the cache manager.
        
        Args:
            enabled: Whether caching is enabled
            history_size: Maximum number of commands to store in history
            history_path: Path to history JSON file (defaults to ~/.voice_agent_history.json)
        """
        self.enabled = enabled
        self.history_size = history_size
        
        # Set history path
        if history_path is None:
            history_path = os.path.expanduser("~/.voice_agent_history.json")
        self.history_path = history_path
        
        # In-memory cache: {key: {"value": Any, "timestamp": float, "ttl": float}}
        self._cache: Dict[str, Dict[str, Any]] = {}
        
        # Command history
        self._history: List[str] = []
        
        # Load history from disk if it exists
        if self.enabled:
            self._load_history()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from cache if it exists and hasn't expired.
        
        Args:
            key: Cache key
            default: Default value if key not found or expired
            
        Returns:
            Cached value or default
        """
        if not self.enabled:
            return default
        
        if key not in self._cache:
            return default
        
        entry = self._cache[key]
        timestamp = entry.get("timestamp", 0)
        ttl = entry.get("ttl", 0)
        
        # Check if expired
        if ttl > 0 and (time.time() - timestamp) > ttl:
            # Expired, remove from cache
            del self._cache[key]
            return default
        
        return entry.get("value", default)
    
    def set(self, key: str, value: Any, ttl: float = 0) -> None:
        """
        Set a value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (0 = no expiration)
        """
        if not self.enabled:
            return
        
        self._cache[key] = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl
        }
    
    def invalidate(self, key: str) -> None:
        """
        Invalidate (remove) a cache entry.
        
        Args:
            key: Cache key to invalidate
        """
        if key in self._cache:
            del self._cache[key]
    
    def invalidate_all(self) -> None:
        """Invalidate all cache entries."""
        self._cache.clear()
    
    def add_to_history(self, command: str) -> None:
        """
        Add a command to history.
        
        Args:
            command: Command text to add
        """
        if not self.enabled:
            return
        
        # Remove if already exists (move to front)
        if command in self._history:
            self._history.remove(command)
        
        # Add to front
        self._history.insert(0, command)
        
        # Trim to history_size
        if len(self._history) > self.history_size:
            self._history = self._history[:self.history_size]
        
        # Persist to disk
        self._save_history()
    
    def get_history(self) -> List[str]:
        """
        Get command history.
        
        Returns:
            List of previous commands (most recent first)
        """
        if not self.enabled:
            return []
        
        return self._history.copy()
    
    def clear_history(self) -> None:
        """Clear command history."""
        self._history.clear()
        self._save_history()
    
    def _load_history(self) -> None:
        """Load command history from disk."""
        if not os.path.exists(self.history_path):
            return
        
        try:
            with open(self.history_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    self._history = data[:self.history_size]  # Trim to size
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load command history from {self.history_path}: {e}")
            self._history = []
    
    def _save_history(self) -> None:
        """Save command history to disk."""
        try:
            # Ensure directory exists
            history_dir = os.path.dirname(self.history_path)
            if history_dir and not os.path.exists(history_dir):
                os.makedirs(history_dir, exist_ok=True)
            
            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(self._history, f, indent=2)
        except IOError as e:
            print(f"Warning: Failed to save command history to {self.history_path}: {e}")


__all__ = [
    'CacheManager',
    'CacheKeys',
    'get_cache_manager',
    'initialize_cache_manager',
    'reset_cache_manager',
]

