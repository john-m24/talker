"""Cache package for organized data storage."""

from .cache import (
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

# For backward compatibility, import from cache module directly
# This allows existing code to use: from voice_agent.cache import CacheManager

