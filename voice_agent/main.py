"""Main entry point for the voice window agent."""

import sys
from .stt import transcribe_once
from .ai_agent import AIAgent
from .window_control import list_running_apps, list_installed_apps, activate_app
from .config import LLM_ENDPOINT, STT_ENGINE


def print_help():
    """Print welcome message and help text."""
    print("=" * 60)
    print("macOS Voice Window Agent")
    print("=" * 60)
    print("\n🎤 Voice Commands:")
    print("  - 'Bring [App] to view' / 'Focus [App]' / 'Show [App]'")
    print("  - 'List apps' / 'What's running'")
    print("  - 'quit' or 'exit' to stop")
    print(f"\nUsing LLM endpoint: {LLM_ENDPOINT}")
    print(f"Using STT engine: {STT_ENGINE.upper()}")
    print("=" * 60)
    if STT_ENGINE.lower() in ["whisper", "macos"]:
        print("\nSpeak your command, then press Enter when done.\n")
    else:
        print("\nSpeak your command (will auto-detect start/stop).\n")


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
    
    # Main loop
    while True:
        try:
            # Get user input
            text = transcribe_once()
            
            if not text:
                continue
            
            # Check for quit commands
            if text.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            
            # Get current running apps for context
            running_apps = list_running_apps()
            
            # Parse intent using AI agent
            print(f"\n📝 Processing: '{text}'...")
            intent = agent.parse_intent(text, running_apps, installed_apps)
            
            # Execute command
            intent_type = intent.get("type", "list_apps")
            
            if intent_type == "list_apps":
                print("\nCurrently running applications:")
                if running_apps:
                    for i, app in enumerate(running_apps, 1):
                        print(f"  {i}. {app}")
                else:
                    print("  (No applications running)")
                print()
            
            elif intent_type == "focus_app":
                app_name = intent.get("app_name")
                if app_name:
                    print(f"Bringing '{app_name}' to front...")
                    success = activate_app(app_name)
                    if success:
                        print(f"✓ Successfully activated '{app_name}'\n")
                    else:
                        print(f"✗ Failed to activate '{app_name}'\n")
                else:
                    print("Error: No app name specified in intent\n")
            
            else:
                print(f"Unknown intent type: {intent_type}\n")
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()

