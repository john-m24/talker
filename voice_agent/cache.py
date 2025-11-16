"""Cache manager for system data and command history.

This module provides backward compatibility by importing from the new cache package.
The new implementation uses hierarchical namespaces for better organization.
"""

# Import from the new cache package
from .cache.cache import (
    CacheManager,
    get_cache_manager,
    initialize_cache_manager,
    reset_cache_manager,
)

__all__ = [
    'CacheManager',
    'get_cache_manager',
    'initialize_cache_manager',
    'reset_cache_manager',
]
