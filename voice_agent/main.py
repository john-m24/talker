"""Main entry point for the voice window agent."""

import sys
import time
from .stt import transcribe_once
from .ai_agent import AIAgent
from .window_control import list_running_apps, list_installed_apps, activate_app, place_app_on_monitor
from .tab_control import list_chrome_tabs, switch_to_chrome_tab
from .clarification import show_clarification_dialog
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
            start_stt = time.time()
            text = transcribe_once()
            stt_time = time.time() - start_stt
            print(f"⏱️  STT (Speech Recognition) took: {stt_time:.2f}s")
            
            if not text:
                continue
            
            # Check for quit commands
            if text.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            
            # Get current running apps for context
            start_apps = time.time()
            running_apps = list_running_apps()
            apps_time = time.time() - start_apps
            print(f"⏱️  List apps took: {apps_time:.2f}s")
            
            # Get Chrome tabs if Chrome is running (for tab switching context)
            chrome_tabs = None
            if "Google Chrome" in running_apps:
                chrome_tabs = list_chrome_tabs()
            
            # Parse intent using AI agent
            print(f"\n📝 Processing: '{text}'...")
            start_llm = time.time()
            intent = agent.parse_intent(text, running_apps, installed_apps, chrome_tabs=chrome_tabs)
            llm_time = time.time() - start_llm
            print(f"⏱️  LLM (Intent Parsing) took: {llm_time:.2f}s")
            print(f"⏱️  Total processing time: {stt_time + apps_time + llm_time:.2f}s\n")
            
            # Check if clarification is needed
            needs_clarification = intent.get("needs_clarification", False)
            if needs_clarification:
                clarification_reason = intent.get("clarification_reason")
                print("⚠️  Command needs clarification...")
                if clarification_reason:
                    print(f"   Reason: {clarification_reason}")
                
                # Show clarification dialog
                confirmed_text = show_clarification_dialog(text, reason=clarification_reason)
                
                if confirmed_text is None:
                    # User cancelled
                    print("   Clarification cancelled, skipping command.\n")
                    continue
                
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
            
            elif intent_type == "list_tabs":
                print("\nOpen Chrome tabs:")
                if chrome_tabs:
                    for tab in chrome_tabs:
                        print(f"  {tab['index']}. {tab['title']}")
                else:
                    print("  Chrome is not running or has no tabs")
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
            
            elif intent_type == "place_app":
                app_name = intent.get("app_name")
                monitor = intent.get("monitor")
                maximize = intent.get("maximize", False)
                
                if app_name and monitor:
                    monitor_display = monitor.replace("_", " ").title()
                    maximize_text = " and maximizing" if maximize else ""
                    print(f"Placing '{app_name}' on {monitor_display} monitor{maximize_text}...")
                    success = place_app_on_monitor(app_name, monitor, maximize=maximize)
                    if success:
                        print(f"✓ Successfully placed '{app_name}' on {monitor_display} monitor\n")
                    else:
                        print(f"✗ Failed to place '{app_name}' on {monitor_display} monitor\n")
                else:
                    missing = []
                    if not app_name:
                        missing.append("app name")
                    if not monitor:
                        missing.append("monitor")
                    print(f"Error: Missing {', '.join(missing)} in intent\n")
            
            elif intent_type == "switch_tab":
                tab_title = intent.get("tab_title")
                tab_index = intent.get("tab_index")
                
                if tab_index:
                    print(f"Switching to Chrome tab #{tab_index}...")
                    success = switch_to_chrome_tab(tab_index=tab_index)
                elif tab_title:
                    print(f"Switching to Chrome tab matching '{tab_title}'...")
                    success = switch_to_chrome_tab(tab_title=tab_title)
                else:
                    print("Error: No tab specified")
                    success = False
                
                if success:
                    print(f"✓ Successfully switched tab\n")
                else:
                    print(f"✗ Failed to switch tab\n")
            
            else:
                print(f"Unknown intent type: {intent_type}\n")
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()

