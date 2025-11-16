"""Cache manager for system data and command history with hierarchical namespaces."""

import json
import os
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

# Module-level singleton instance
_instance: Optional['CacheManager'] = None


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
    """Manages caching of system data and command history with hierarchical namespaces."""
    
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
        
        # Set persistent data path
        self.persistent_data_path = os.path.expanduser("~/.voice_agent_data.json")
        
        # Hierarchical namespace-based cache: {namespace_path: {key: {"value": Any, "timestamp": float, "ttl": float}}}
        # Example: {"apps": {"running": {...}}, "browsers.chrome": {"tabs": {...}}}
        self._cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        # Persistent data (saved to disk): command history, recent queries, etc.
        self._persistent_data: Dict[str, Any] = {
            "command_history": [],
            "recent_queries": []
        }
        
        # Load persistent data and migrate old cache/history if needed
        if self.enabled:
            self._load_persistent_data()
            self._migrate_old_history()
            self._migrate_old_cache()
    
    def get(self, namespace_path: str, key: str, default: Any = None) -> Any:
        """
        Get a value from cache using hierarchical namespace path.
        
        Args:
            namespace_path: Hierarchical namespace path (e.g., "apps", "browsers.chrome", "llm.responses")
            key: Key within the namespace
            default: Default value if key not found or expired
            
        Returns:
            Cached value or default
        """
        if not self.enabled:
            return default
        
        if namespace_path not in self._cache:
            return default
        
        namespace_cache = self._cache[namespace_path]
        if key not in namespace_cache:
            return default
        
        entry = namespace_cache[key]
        timestamp = entry.get("timestamp", 0)
        ttl = entry.get("ttl", 0)
        
        # Check if expired
        if ttl > 0 and (time.time() - timestamp) > ttl:
            # Expired, remove from cache
            del namespace_cache[key]
            # Clean up empty namespaces
            if not namespace_cache:
                del self._cache[namespace_path]
            return default
        
        return entry.get("value", default)
    
    def set(self, namespace_path: str, key: str, value: Any, ttl: float = 0) -> None:
        """
        Set a value in cache using hierarchical namespace path.
        
        Args:
            namespace_path: Hierarchical namespace path (e.g., "apps", "browsers.chrome", "llm.responses")
            key: Key within the namespace
            value: Value to cache
            ttl: Time to live in seconds (0 = no expiration)
        """
        if not self.enabled:
            return
        
        if namespace_path not in self._cache:
            self._cache[namespace_path] = {}
        
        self._cache[namespace_path][key] = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl
        }
    
    def invalidate(self, namespace_path: str, key: Optional[str] = None) -> None:
        """
        Invalidate (remove) a cache entry or entire namespace.
        
        Args:
            namespace_path: Hierarchical namespace path
            key: Optional key within the namespace. If None, invalidates entire namespace.
        """
        if not self.enabled:
            return
        
        if namespace_path not in self._cache:
            return
        
        if key is None:
            # Invalidate entire namespace
            del self._cache[namespace_path]
        else:
            # Invalidate specific key
            namespace_cache = self._cache[namespace_path]
            if key in namespace_cache:
                del namespace_cache[key]
            # Clean up empty namespaces
            if not namespace_cache:
                del self._cache[namespace_path]
    
    def invalidate_all(self) -> None:
        """Invalidate all cache entries."""
        self._cache.clear()
    
    # Convenience methods for common namespaces
    def get_apps(self, key: str, default: Any = None) -> Any:
        """Get value from apps namespace."""
        return self.get("apps", key, default)
    
    def set_apps(self, key: str, value: Any, ttl: float = 0) -> None:
        """Set value in apps namespace."""
        self.set("apps", key, value, ttl)
    
    def get_tabs(self, key: str, default: Any = None) -> Any:
        """Get value from browsers.chrome namespace (for tabs)."""
        return self.get("browsers.chrome", key, default)
    
    def set_tabs(self, key: str, value: Any, ttl: float = 0) -> None:
        """Set value in browsers.chrome namespace (for tabs)."""
        self.set("browsers.chrome", key, value, ttl)
    
    def get_files(self, key: str, default: Any = None) -> Any:
        """Get value from files namespace."""
        return self.get("files", key, default)
    
    def set_files(self, key: str, value: Any, ttl: float = 0) -> None:
        """Set value in files namespace."""
        self.set("files", key, value, ttl)
    
    def get_system(self, key: str, default: Any = None) -> Any:
        """Get value from system namespace."""
        return self.get("system", key, default)
    
    def set_system(self, key: str, value: Any, ttl: float = 0) -> None:
        """Set value in system namespace."""
        self.set("system", key, value, ttl)
    
    def get_llm(self, key: str, default: Any = None) -> Any:
        """Get value from llm.responses namespace."""
        return self.get("llm.responses", key, default)
    
    def set_llm(self, key: str, value: Any, ttl: float = 0) -> None:
        """Set value in llm.responses namespace."""
        self.set("llm.responses", key, value, ttl)
    
    # Persistent data methods
    def add_query_response(self, question: str, answer: str) -> None:
        """
        Add a query Q&A pair to persistent recent queries.
        
        Args:
            question: User question text
            answer: Answer text
        """
        if not self.enabled:
            return
        
        try:
            recent = self._persistent_data.get("recent_queries", []) or []
            # Prepend newest
            recent.insert(0, {
                "question": str(question or "").strip(),
                "answer": str(answer or "").strip(),
                "timestamp": time.time(),
            })
            # Keep last 10
            if len(recent) > 10:
                recent = recent[:10]
            self._persistent_data["recent_queries"] = recent
            self._save_persistent_data()
        except Exception:
            # Fail silently; query context is best-effort
            pass
    
    def get_recent_queries(self, max_count: int = 10) -> List[Dict]:
        """
        Get recent query Q&A pairs (most recent first).
        
        Args:
            max_count: Maximum number of entries to return
        
        Returns:
            List of {'question', 'answer', 'timestamp'} dicts
        """
        if not self.enabled:
            return []
        recent = self._persistent_data.get("recent_queries", []) or []
        if not isinstance(recent, list):
            return []
        return recent[:max_count]
    
    def add_to_history(self, command: str) -> None:
        """
        Add a command to history.
        
        Args:
            command: Command text to add
        """
        if not self.enabled:
            return
        
        history = self._persistent_data.get("command_history", []) or []
        if not isinstance(history, list):
            history = []
        
        # Remove if already exists (move to front)
        if command in history:
            history.remove(command)
        
        # Add to front
        history.insert(0, command)
        
        # Trim to history_size
        if len(history) > self.history_size:
            history = history[:self.history_size]
        
        self._persistent_data["command_history"] = history
        self._save_persistent_data()
    
    def get_history(self) -> List[str]:
        """
        Get command history.
        
        Returns:
            List of previous commands (most recent first)
        """
        if not self.enabled:
            return []
        
        history = self._persistent_data.get("command_history", []) or []
        if not isinstance(history, list):
            return []
        return history.copy()
    
    def clear_history(self) -> None:
        """Clear command history."""
        if "command_history" in self._persistent_data:
            self._persistent_data["command_history"] = []
        self._save_persistent_data()
    
    def _load_persistent_data(self) -> None:
        """Load persistent data from disk."""
        if not os.path.exists(self.persistent_data_path):
            return
        
        try:
            with open(self.persistent_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._persistent_data.update(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load persistent data from {self.persistent_data_path}: {e}")
    
    def _save_persistent_data(self) -> None:
        """Save persistent data to disk."""
        try:
            # Ensure directory exists
            data_dir = os.path.dirname(self.persistent_data_path)
            if data_dir and not os.path.exists(data_dir):
                os.makedirs(data_dir, exist_ok=True)
            
            with open(self.persistent_data_path, 'w', encoding='utf-8') as f:
                json.dump(self._persistent_data, f, indent=2)
        except IOError as e:
            print(f"Warning: Failed to save persistent data to {self.persistent_data_path}: {e}")
    
    def _migrate_old_history(self) -> None:
        """
        Migrate old history file format to new persistent data storage.
        This is a one-time migration that runs on first load.
        """
        # Check if migration already happened
        if self._persistent_data.get("_history_migration_complete", False):
            return
        
        # If we already have history in persistent_data, skip
        if self._persistent_data.get("command_history"):
            self._persistent_data["_history_migration_complete"] = True
            self._save_persistent_data()
            return
        
        # Try to load from old history file
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        # Migrate to persistent_data
                        self._persistent_data["command_history"] = data[:self.history_size]
                        self._save_persistent_data()
            except (json.JSONDecodeError, IOError):
                # If migration fails, just mark as complete
                pass
        
        self._persistent_data["_history_migration_complete"] = True
        self._save_persistent_data()
    
    def _migrate_old_cache(self) -> None:
        """
        Migrate old flat cache format to new hierarchical namespace structure.
        This is a one-time migration that runs on first load.
        Note: Old cache was in-memory only, so this mainly marks migration as complete.
        """
        # Check if migration already happened by looking for a marker
        if self._persistent_data.get("_cache_migration_complete", False):
            return
        
        # Mark migration as complete
        # Note: Old cache was in-memory only, so we can't migrate from disk
        # Any existing cache will be rebuilt naturally as the system runs
        self._persistent_data["_cache_migration_complete"] = True
        self._save_persistent_data()


__all__ = [
    'CacheManager',
    'get_cache_manager',
    'initialize_cache_manager',
    'reset_cache_manager',
]

