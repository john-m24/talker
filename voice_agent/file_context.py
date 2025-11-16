"""File system and project context tracking."""

import os
import time
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from .cache import get_cache_manager
from .config import CACHE_FILES_TTL
from .fuzzy_matcher import match_app_name


class FileContextTracker:
    """Tracks recently opened files and active projects."""
    
    def __init__(self, cache_manager=None):
        """
        Initialize file context tracker.
        
        Args:
            cache_manager: CacheManager instance (optional)
        """
        self.cache_manager = cache_manager or get_cache_manager()
    
    def get_recent_files(self, max_files: int = 20, max_age_hours: int = 24) -> List[Dict]:
        """
        Get recently opened files from macOS Recent Items.
        
        Args:
            max_files: Maximum number of files to return
            max_age_hours: Maximum age of files in hours
            
        Returns:
            List of dicts with 'path', 'name', 'app', 'timestamp', 'type' keys
        """
        # Check cache first
        if self.cache_manager:
            cached = self.cache_manager.get_files("recent")
            if cached is not None:
                # Filter by age
                cutoff = time.time() - (max_age_hours * 3600)
                recent = [f for f in cached if f.get('timestamp', 0) > cutoff]
                return recent[:max_files]
        
        # Fetch from macOS using mdfind (Spotlight)
        files = self._get_recent_files_mdfind(max_files, max_age_hours)
        
        # Cache results
        if self.cache_manager:
            self.cache_manager.set_files(
                "recent",
                files,
                ttl=CACHE_FILES_TTL
            )
        
        return files
    
    def _get_recent_files_mdfind(self, max_files: int, max_age_hours: int) -> List[Dict]:
        """Get recent files using mdfind (Spotlight)."""
        try:
            # Find files modified in last N hours
            cutoff_timestamp = time.time() - (max_age_hours * 3600)
            
            # Use mdfind to find recently modified files
            # Search in common user directories
            search_paths = [
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Downloads"),
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Projects"),
                os.path.expanduser("~/Code"),
                os.path.expanduser("~/workspace"),
            ]
            
            files = []
            seen_paths = set()
            
            for search_path in search_paths:
                if not os.path.exists(search_path):
                    continue
                
                try:
                    # Use mdfind to find recently modified files
                    # Note: mdfind date queries are complex, so we'll use a simpler approach
                    # Find all files and filter by modification time
                    cmd = [
                        "mdfind",
                        "-onlyin", search_path,
                        "kMDItemContentTypeTree == 'public.data' || kMDItemContentTypeTree == 'public.text' || kMDItemContentTypeTree == 'public.source-code'"
                    ]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        paths = result.stdout.strip().split('\n')
                        for path in paths:
                            if not path or path in seen_paths:
                                continue
                            
                            if os.path.exists(path) and os.path.isfile(path):
                                try:
                                    stat = os.stat(path)
                                    if stat.st_mtime >= cutoff_timestamp:
                                        file_info = {
                                            'path': path,
                                            'name': os.path.basename(path),
                                            'app': self._get_app_for_file(path),
                                            'timestamp': stat.st_mtime,
                                            'type': self._get_file_type(path)
                                        }
                                        files.append(file_info)
                                        seen_paths.add(path)
                                        
                                        if len(files) >= max_files * 2:  # Get more than needed for filtering
                                            break
                                except (OSError, PermissionError):
                                    continue
                except subprocess.TimeoutExpired:
                    continue
                except Exception:
                    continue
                
                if len(files) >= max_files * 2:
                    break
            
            # Sort by timestamp (most recent first)
            files.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Limit to max_files
            return files[:max_files]
            
        except Exception as e:
            print(f"Error getting recent files: {e}")
            return []
    
    def _get_file_type(self, file_path: str) -> str:
        """Get file type from extension."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.go', '.rs', '.rb', '.php', '.swift', '.kt']:
            return 'code'
        elif ext in ['.md', '.txt', '.rtf']:
            return 'text'
        elif ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']:
            return 'document'
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']:
            return 'image'
        elif ext in ['.mp4', '.mov', '.avi', '.mkv']:
            return 'video'
        else:
            return 'other'
    
    def _get_app_for_file(self, file_path: str) -> Optional[str]:
        """Get the default app for a file type."""
        try:
            # Use macOS 'mdls' to get default app
            cmd = ["mdls", "-name", "kMDItemContentType", file_path]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                # Get UTI from output
                uti = result.stdout.strip().split('=')[-1].strip()
                if uti:
                    # Use 'duti' or AppleScript to get default app
                    script = f'''
                    tell application "System Events"
                        set fileType to "{uti}"
                        try
                            set defaultApp to default application of fileType
                            return name of defaultApp
                        on error
                            return ""
                        end try
                    end tell
                    '''
                    result = subprocess.run(
                        ["osascript", "-e", script],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        app_name = result.stdout.strip()
                        if app_name:
                            return app_name
        except Exception:
            pass
        
        # Fallback: try to infer from file extension
        ext = os.path.splitext(file_path)[1].lower()
        ext_to_app = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.md': 'Markdown',
            '.txt': 'TextEdit',
            '.pdf': 'Preview',
        }
        return ext_to_app.get(ext)
    
    def get_active_projects(self) -> List[Dict]:
        """
        Detect active projects (git repos, IDE projects, etc.).
        
        Returns:
            List of dicts with 'path', 'name', 'type', 'last_accessed' keys
        """
        # Check cache first
        if self.cache_manager:
            cached = self.cache_manager.get_files("projects")
            if cached is not None:
                return cached
        
        projects = []
        
        # Find git repositories in common locations
        common_paths = [
            os.path.expanduser("~/Documents"),
            os.path.expanduser("~/Projects"),
            os.path.expanduser("~/Code"),
            os.path.expanduser("~/workspace"),
        ]
        
        for base_path in common_paths:
            if os.path.exists(base_path):
                projects.extend(self._find_projects(base_path, max_depth=3))
        
        # Also check recently opened files for project hints
        recent_files = self.get_recent_files(max_files=50, max_age_hours=24)
        for file_info in recent_files:
            project = self._extract_project_from_file(file_info['path'])
            if project and project not in projects:
                projects.append(project)
        
        # Sort by last accessed
        projects.sort(key=lambda x: x.get('last_accessed', 0), reverse=True)
        
        # Limit to top 20
        projects = projects[:20]
        
        # Cache results
        if self.cache_manager:
            self.cache_manager.set_files(
                "projects",
                projects,
                ttl=CACHE_FILES_TTL
            )
        
        return projects
    
    def _find_projects(self, base_path: str, max_depth: int = 3) -> List[Dict]:
        """Find projects recursively."""
        projects = []
        
        def search(path: Path, depth: int):
            if depth > max_depth:
                return
            
            # Check if this is a project
            project = self._detect_project(path)
            if project:
                projects.append(project)
                return  # Don't search inside projects
            
            # Search subdirectories
            try:
                for item in path.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        search(item, depth + 1)
            except (PermissionError, OSError):
                pass
        
        search(Path(base_path), 0)
        return projects
    
    def _detect_project(self, path: Path) -> Optional[Dict]:
        """Detect if a directory is a project."""
        project_indicators = [
            ('.git', 'git'),
            ('package.json', 'node'),
            ('Cargo.toml', 'rust'),
            ('pyproject.toml', 'python'),
            ('Pipfile', 'python'),
            ('requirements.txt', 'python'),
            ('go.mod', 'go'),
            ('pom.xml', 'java'),
            ('build.gradle', 'java'),
            ('CMakeLists.txt', 'cmake'),
            ('Makefile', 'c'),
        ]
        
        for indicator, project_type in project_indicators:
            indicator_path = path / indicator
            if indicator_path.exists():
                try:
                    stat = os.stat(path)
                    return {
                        'path': str(path),
                        'name': path.name,
                        'type': project_type,
                        'last_accessed': stat.st_mtime
                    }
                except (OSError, PermissionError):
                    pass
        
        return None
    
    def _extract_project_from_file(self, file_path: str) -> Optional[Dict]:
        """Extract project info from a file path."""
        path = Path(file_path)
        
        # Walk up to find project indicators
        for parent in path.parents:
            project = self._detect_project(parent)
            if project:
                return project
        
        return None
    
    def get_current_project(self) -> Optional[Dict]:
        """
        Get the currently active project (based on recent files and open windows).
        
        Returns:
            Dict with 'path', 'name', 'type', 'last_accessed' keys or None
        """
        # Check cache first
        if self.cache_manager:
            cached = self.cache_manager.get_files("current_project")
            if cached is not None:
                return cached
        
        # Get most recent file
        recent_files = self.get_recent_files(max_files=10, max_age_hours=1)
        if recent_files:
            # Extract project from most recent file
            project = self._extract_project_from_file(recent_files[0]['path'])
            if project:
                # Cache result
                if self.cache_manager:
                    self.cache_manager.set_files(
                        "current_project",
                        project,
                        ttl=CACHE_FILES_TTL
                    )
                return project
        
        # Fallback: get most recently accessed project
        active_projects = self.get_active_projects()
        if active_projects:
            current = active_projects[0]
            # Cache result
            if self.cache_manager:
                self.cache_manager.set_files(
                    "current_project",
                    current,
                    ttl=CACHE_FILES_TTL
                )
            return current
        
        return None
    
    def find_file(self, file_name: str, current_project: Optional[Dict] = None) -> Optional[str]:
        """
        Find a file with fuzzy matching, prioritizing current project.
        
        Args:
            file_name: File name to search for (can be partial)
            current_project: Current project dict (optional)
            
        Returns:
            Full file path if found, None otherwise
        """
        file_name_lower = file_name.lower().strip()
        if not file_name_lower:
            return None
        
        # Priority 1: Current project
        if current_project:
            project_path = Path(current_project['path'])
            matches = self._search_in_directory(project_path, file_name_lower)
            if matches:
                # Return most recently accessed match
                matches.sort(key=lambda x: os.stat(x).st_mtime, reverse=True)
                return matches[0]
        
        # Priority 2: Recent files
        recent_files = self.get_recent_files(max_files=50, max_age_hours=24)
        matches = []
        for file_info in recent_files:
            if file_name_lower in file_info['name'].lower():
                matches.append((file_info['path'], file_info['timestamp']))
        
        if matches:
            # Sort by timestamp (most recent first)
            matches.sort(key=lambda x: x[1], reverse=True)
            return matches[0][0]
        
        # Priority 3: Search in common directories
        common_paths = [
            os.path.expanduser("~/Documents"),
            os.path.expanduser("~/Projects"),
            os.path.expanduser("~/Code"),
            os.path.expanduser("~/workspace"),
        ]
        
        for base_path in common_paths:
            if os.path.exists(base_path):
                matches = self._search_in_directory(Path(base_path), file_name_lower, max_depth=3)
                if matches:
                    # Return most recently accessed match
                    matches.sort(key=lambda x: os.stat(x).st_mtime, reverse=True)
                    return matches[0]
        
        return None
    
    def find_project(self, project_name: str) -> Optional[str]:
        """
        Find a project by name using fuzzy matching.
        
        Args:
            project_name: Project name to search for (can be partial)
            
        Returns:
            Full project path if found, None otherwise
        """
        project_name_lower = project_name.lower().strip()
        if not project_name_lower:
            return None
        
        # Get active projects
        projects = self.get_active_projects()
        
        if not projects:
            return None
        
        # Try exact match first
        for project in projects:
            name = project.get('name', '').lower()
            if name == project_name_lower:
                return project.get('path')
        
        # Try fuzzy matching (contains match)
        for project in projects:
            name = project.get('name', '').lower()
            if project_name_lower in name or name in project_name_lower:
                return project.get('path')
        
        # Try partial matching (word boundaries)
        for project in projects:
            name = project.get('name', '').lower()
            # Check if project name starts with the search term
            if name.startswith(project_name_lower):
                return project.get('path')
            # Check if search term is a word in the project name
            words = name.split()
            search_words = project_name_lower.split()
            # Check if all search words are in project name
            if all(any(word.startswith(sw) or sw in word for word in words) for sw in search_words):
                return project.get('path')
        
        return None
    
    def _search_in_directory(self, directory: Path, file_name: str, max_depth: int = 3) -> List[str]:
        """Search for files in a directory recursively."""
        matches = []
        
        def search(path: Path, depth: int):
            if depth > max_depth:
                return
            
            try:
                for item in path.iterdir():
                    if item.is_file():
                        if file_name in item.name.lower():
                            matches.append(str(item))
                    elif item.is_dir() and not item.name.startswith('.'):
                        search(item, depth + 1)
            except (PermissionError, OSError):
                pass
        
        search(directory, 0)
        return matches

