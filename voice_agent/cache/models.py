"""Data models for cache storage."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class AppData:
    """Data model for application information."""
    name: str
    is_running: bool = False
    windows: List[Dict[str, Any]] = field(default_factory=list)
    last_interaction: Optional[float] = None
    interaction_count: int = 0


@dataclass
class TabData:
    """Data model for tab information."""
    index: int
    title: str
    url: str
    domain: str
    window_index: int
    is_active: bool = False
    last_interaction: Optional[float] = None


@dataclass
class FileData:
    """Data model for file information."""
    path: str
    name: str
    app: str
    file_type: str
    last_opened: float
    open_count: int = 0


@dataclass
class ProjectData:
    """Data model for project information."""
    name: str
    path: str
    project_type: str = "unknown"
    last_accessed: float = 0

