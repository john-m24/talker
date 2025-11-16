"""File control functions for opening files and folders in applications."""

import os
import subprocess
from typing import Optional, List
from .utils import AppleScriptExecutor, escape_applescript_string
from .window_control import list_installed_apps
from .file_context import FileContextTracker
from .cache import get_cache_manager


# Create a module-level executor instance
_executor = AppleScriptExecutor()


def infer_app_for_file(file_path: str) -> Optional[str]:
    """
    Intelligently infer the best app for a file from ALL installed apps.
    
    This function:
    1. First tries the file's default app (from macOS)
    2. Then searches ALL installed apps for apps that match the file type
    3. Returns the best match
    
    Args:
        file_path: Path to the file
        
    Returns:
        App name if found, None otherwise
    """
    # First, try to get the file's default app
    file_tracker = FileContextTracker(cache_manager=get_cache_manager())
    default_app = file_tracker._get_app_for_file(file_path)
    if default_app:
        installed_apps = list_installed_apps()
        if default_app in installed_apps:
            return default_app
    
    # Get file extension
    ext = os.path.splitext(file_path)[1].lower()
    if not ext:
        return None
    
    # Get all installed apps
    installed_apps = list_installed_apps()
    if not installed_apps:
        return None
    
    # Define file type categories and keywords to match
    video_extensions = {'.mov', '.mp4', '.avi', '.mkv', '.m4v', '.wmv', '.flv', '.webm', '.3gp'}
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif', '.heic', '.heif', '.svg'}
    code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.clj', '.sh', '.bash', '.zsh', '.fish'}
    text_extensions = {'.txt', '.md', '.markdown', '.rst', '.org', '.log', '.csv'}
    pdf_extensions = {'.pdf'}
    
    # Keywords to match in app names for each category
    video_keywords = ['video', 'player', 'quicktime', 'vlc', 'iina', 'mpv', 'mplayer', 'ffmpeg', 'media']
    image_keywords = ['preview', 'photos', 'image', 'viewer', 'gimp', 'photoshop', 'pixelmator', 'affinity', 'sketch', 'figma']
    code_keywords = ['cursor', 'code', 'editor', 'xcode', 'pycharm', 'intellij', 'sublime', 'atom', 'vim', 'emacs', 'neovim', 'zed', 'nova']
    text_keywords = ['textedit', 'text', 'editor', 'note', 'notes', 'bear', 'obsidian', 'typora']
    pdf_keywords = ['preview', 'acrobat', 'pdf', 'reader', 'adobe']
    
    # Determine file type category
    if ext in video_extensions:
        keywords = video_keywords
    elif ext in image_extensions:
        keywords = image_keywords
    elif ext in code_extensions:
        keywords = code_keywords
    elif ext in pdf_extensions:
        keywords = pdf_keywords
    elif ext in text_extensions:
        keywords = text_keywords
    else:
        # For unknown extensions, try to match based on common patterns
        keywords = []
    
    # Search through ALL installed apps for matches
    matches = []
    for app in installed_apps:
        app_lower = app.lower()
        # Check if app name contains any keyword
        for keyword in keywords:
            if keyword in app_lower:
                matches.append(app)
                break
    
    # If we found matches, return the first one
    if matches:
        return matches[0]
    
    # If no matches found, return None (let AI handle it or ask for clarification)
    return None


def open_path_in_app(path: str, app_name: str) -> bool:
    """
    Open a file or folder in a specific application.
    
    Args:
        path: Path to the file or folder to open
        app_name: Name of the application to open the path in
        
    Returns:
        True if successful, False otherwise
    """
    # Check if app is installed first
    installed_apps = list_installed_apps()
    if app_name not in installed_apps:
        print(f"Error: Application '{app_name}' is not installed")
        return False
    
    if not os.path.exists(path):
        print(f"Error: Path not found: {path}")
        return False
    
    # Normalize path
    path = os.path.abspath(path)
    
    # Escape special characters for AppleScript
    escaped_path = escape_applescript_string(path)
    escaped_app = escape_applescript_string(app_name)
    
    try:
        # Use macOS 'open' command first (simpler, more reliable, works for both files and folders)
        cmd = ["open", "-a", app_name, path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return True
        
        # Fallback to AppleScript if 'open' command fails
        script = f'''
        tell application "{escaped_app}"
            activate
            open POSIX file "{escaped_path}"
        end tell
        '''
        
        success, stdout, stderr = _executor.execute(script, check=True)
        
        if success:
            return True
        else:
            print(f"Error opening path in {app_name}: {stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"Error: Timeout opening path in {app_name}")
        return False
    except Exception as e:
        print(f"Error opening path in {app_name}: {e}")
        return False



