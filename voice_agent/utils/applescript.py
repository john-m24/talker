"""AppleScript execution utilities."""

import subprocess
from typing import Optional, Tuple


def escape_applescript_string(text: str) -> str:
    """
    Escape special characters for AppleScript string literals.
    
    Args:
        text: String to escape
        
    Returns:
        Escaped string safe for use in AppleScript
    """
    # Escape backslashes first (must be first)
    text = text.replace("\\", "\\\\")
    # Escape double quotes
    text = text.replace('"', '\\"')
    # Escape newlines
    text = text.replace("\n", "\\n")
    # Escape carriage returns
    text = text.replace("\r", "\\r")
    # Escape tabs
    text = text.replace("\t", "\\t")
    return text


class AppleScriptExecutor:
    """Centralized AppleScript execution with standardized error handling."""
    
    def __init__(self):
        """Initialize the AppleScript executor."""
        pass
    
    def execute(self, script: str, check: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Execute an AppleScript command.
        
        Args:
            script: AppleScript code to execute
            check: If True, raise CalledProcessError on non-zero exit code
            
        Returns:
            Tuple of (success, stdout, stderr)
            - success: True if return code is 0, False otherwise
            - stdout: Standard output (None if empty)
            - stderr: Standard error (None if empty)
        """
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=check
            )
            
            success = result.returncode == 0
            stdout = result.stdout.strip() if result.stdout.strip() else None
            stderr = result.stderr.strip() if result.stderr.strip() else None
            
            return success, stdout, stderr
        except subprocess.CalledProcessError as e:
            return False, e.stdout.strip() if e.stdout else None, e.stderr.strip() if e.stderr else None
        except Exception as e:
            return False, None, str(e)
    
    def execute_safe(self, script: str) -> Tuple[bool, Optional[str]]:
        """
        Execute an AppleScript command safely, returning only success and output.
        
        Args:
            script: AppleScript code to execute
            
        Returns:
            Tuple of (success, output)
            - success: True if execution succeeded
            - output: Standard output or None
        """
        success, stdout, stderr = self.execute(script, check=False)
        return success, stdout

