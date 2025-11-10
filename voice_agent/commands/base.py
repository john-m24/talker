"""Base command class for voice agent commands."""

from abc import ABC, abstractmethod
from typing import Dict, Any


class Command(ABC):
    """Abstract base class for voice agent commands."""
    
    @abstractmethod
    def execute(self, intent: Dict[str, Any]) -> bool:
        """
        Execute the command based on the parsed intent.
        
        Args:
            intent: Parsed intent dictionary with command-specific fields
            
        Returns:
            True if execution succeeded, False otherwise
        """
        pass
    
    @abstractmethod
    def can_handle(self, intent_type: str) -> bool:
        """
        Check if this command can handle the given intent type.
        
        Args:
            intent_type: The intent type string
            
        Returns:
            True if this command can handle the intent type
        """
        pass
    
    def produces_results(self) -> bool:
        """
        Return True if this command produces displayable results.
        
        Query commands (list_*) return True.
        Action commands (focus, place, close, etc.) return False (default).
        
        Returns:
            True if this command produces results to display, False otherwise
        """
        return False  # Default: action commands don't produce results

