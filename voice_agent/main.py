"""Main entry point for the voice window agent."""

import sys
import time
from typing import Optional, Tuple
from .stt import transcribe_once
from .ai_agent import AIAgent
from .window_control import list_running_apps, list_installed_apps
from .tab_control import list_chrome_tabs
from .clarification import show_clarification_dialog
from .commands import CommandExecutor
from .config import LLM_ENDPOINT, STT_ENGINE


def print_help():
    """Print welcome message and help text."""
    print("=" * 60)
    print("macOS Voice Window Agent")
    print("=" * 60)
    print("\n🎤 Voice Commands:")
    print("  - 'Bring [App] to view' / 'Focus [App]' / 'Show [App]'")
    print("  - 'Put [App] on [main/right/left] monitor' / 'Move [App] to [main/right/left] screen'")
    print("  - 'Place [App] on [monitor] and maximize'")
    print("  - 'List apps' / 'What's running'")
    print("  - 'Switch to [Tab]' / 'Go to tab [Number]' / 'List tabs'")
    print("  - 'quit' or 'exit' to stop")
    print(f"\nUsing LLM endpoint: {LLM_ENDPOINT}")
    print(f"Using STT engine: {STT_ENGINE.upper()}")
    print("=" * 60)
    print("\nSpeak your command (will auto-detect when you start and stop speaking).\n")


def time_operation(operation_name: str, func, *args, **kwargs):
    """
    Time an operation and print the duration.
    
    Args:
        operation_name: Name of the operation for display
        func: Function to call
        *args, **kwargs: Arguments to pass to the function
        
    Returns:
        Result of the function call
    """
    start_time = time.time()
    result = func(*args, **kwargs)
    elapsed = time.time() - start_time
    print(f"⏱️  {operation_name} took: {elapsed:.2f}s")
    return result


def handle_clarification(
    text: str,
    intent: dict,
    agent: AIAgent,
    running_apps: list,
    installed_apps: list,
    chrome_tabs: Optional[list]
) -> Tuple[str, dict]:
    """
    Handle clarification dialog if needed.
    
    Args:
        text: Original transcribed text
        intent: Parsed intent dictionary
        agent: AI agent instance
        running_apps: List of running apps
        installed_apps: List of installed apps
        chrome_tabs: List of Chrome tabs
        
    Returns:
        Tuple of (final_text, final_intent)
    """
    needs_clarification = intent.get("needs_clarification", False)
    if not needs_clarification:
        return text, intent
    
    clarification_reason = intent.get("clarification_reason")
    print("⚠️  Command needs clarification...")
    if clarification_reason:
        print(f"   Reason: {clarification_reason}")
    
    # Show clarification dialog
    confirmed_text = show_clarification_dialog(text, reason=clarification_reason)
    
    if confirmed_text is None:
        # User cancelled
        print("   Clarification cancelled, skipping command.\n")
        return None, None
    
    if confirmed_text != text:
        # User corrected the text, re-parse intent
        print(f"   Corrected text: '{confirmed_text}'")
        text = confirmed_text
        
        # Re-parse intent with corrected text
        start_llm = time.time()
        intent = agent.parse_intent(text, running_apps, installed_apps, chrome_tabs=chrome_tabs)
        llm_time = time.time() - start_llm
        print(f"⏱️  LLM (Re-parsing) took: {llm_time:.2f}s\n")
    else:
        # User confirmed, proceed with original intent
        print("   Text confirmed, proceeding with command.\n")
    
    return text, intent


def main():
    """Main loop for the voice agent."""
    print_help()
    
    # Initialize AI agent
    try:
        agent = AIAgent()
        print("AI agent initialized successfully.\n")
    except Exception as e:
        print(f"Error initializing AI agent: {e}")
        print("Please check your LLM endpoint configuration.")
        sys.exit(1)
    
    # Get installed apps once (for context)
    installed_apps = list_installed_apps()
    
    # Initialize command executor
    command_executor = CommandExecutor()
    
    # Main loop
    while True:
        try:
            # Get user input
            text = time_operation("STT (Speech Recognition)", transcribe_once)
            
            if not text:
                continue
            
            # Check for quit commands
            if text.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            
            # Get current running apps for context
            running_apps = time_operation("List apps", list_running_apps)
            
            # Get Chrome tabs if Chrome is running (for tab switching context)
            chrome_tabs = None
            if "Google Chrome" in running_apps:
                chrome_tabs = list_chrome_tabs()
            
            # Parse intent using AI agent
            print(f"\n📝 Processing: '{text}'...")
            intent = time_operation(
                "LLM (Intent Parsing)",
                agent.parse_intent,
                text, running_apps, installed_apps, chrome_tabs=chrome_tabs
            )
            
            # Handle clarification if needed
            text, intent = handle_clarification(
                text, intent, agent, running_apps, installed_apps, chrome_tabs
            )
            
            if text is None or intent is None:
                # User cancelled clarification
                continue
            
            # Execute command using command executor
            command_executor.execute(intent, running_apps=running_apps, chrome_tabs=chrome_tabs)
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()

